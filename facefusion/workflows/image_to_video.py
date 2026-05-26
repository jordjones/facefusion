import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from typing import Optional, Tuple

import numpy
from tqdm import tqdm

from facefusion import ffmpeg
from facefusion import logger, process_manager, state_manager, translator, video_manager
from facefusion.audio import create_empty_audio_frame, get_audio_frame, get_voice_frame
from facefusion.common_helper import get_first
from facefusion.content_analyser import analyse_video
from facefusion.filesystem import filter_audio_paths, is_video
from facefusion.processors.core import get_processors_modules
from facefusion.temp_helper import clear_temp_directory, create_temp_directory, move_temp_file, resolve_temp_frame_paths
from facefusion.time_helper import calculate_end_time
from facefusion.types import ErrorCode
from facefusion.vision import conditional_merge_vision_mask, detect_video_resolution, extract_vision_mask, pack_resolution, read_static_image, read_static_images, read_static_video_frame, restrict_trim_frame, restrict_video_fps, restrict_video_resolution, scale_resolution, write_image
from facefusion.workflows.core import is_process_stopping

FRAME_FAILURE_ABORT_THRESHOLD = 0.50


def _chunk_range_from_env() -> Tuple[Optional[int], Optional[int]]:
	start = os.environ.get('FACEFUSION_CHUNK_START')
	end = os.environ.get('FACEFUSION_CHUNK_END')
	if start is not None and end is not None:
		try:
			return int(start), int(end)
		except ValueError:
			return None, None
	return None, None


def process(start_time : float) -> ErrorCode:
	chunk_start, chunk_end = _chunk_range_from_env()

	if chunk_start is not None and chunk_end is not None:
		logger.info(f'chunk_subprocess_start: range=[{chunk_start},{chunk_end})', __name__)
		process_manager.start()
		error_code = process_video()
		process_manager.end()
		return error_code

	tasks =\
	[
		setup,
		extract_frames,
		process_video,
		merge_frames,
		restore_audio,
		partial(finalize_video, start_time)
	]
	process_manager.start()

	for task in tasks:
		error_code = task() #type:ignore[operator]

		if error_code > 0:
			process_manager.end()
			return error_code

	process_manager.end()
	return 0


def setup() -> ErrorCode:
	trim_frame_start, trim_frame_end = restrict_trim_frame(state_manager.get_item('target_path'), state_manager.get_item('trim_frame_start'), state_manager.get_item('trim_frame_end'))

	if analyse_video(state_manager.get_item('target_path'), trim_frame_start, trim_frame_end):
		return 3

	logger.debug(translator.get('clearing_temp'), __name__)
	clear_temp_directory(state_manager.get_item('target_path'))
	logger.debug(translator.get('creating_temp'), __name__)
	create_temp_directory(state_manager.get_item('target_path'))
	return 0


def extract_frames() -> ErrorCode:
	trim_frame_start, trim_frame_end = restrict_trim_frame(state_manager.get_item('target_path'), state_manager.get_item('trim_frame_start'), state_manager.get_item('trim_frame_end'))
	output_video_resolution = scale_resolution(detect_video_resolution(state_manager.get_item('target_path')), state_manager.get_item('output_video_scale'))
	temp_video_resolution = restrict_video_resolution(state_manager.get_item('target_path'), output_video_resolution)
	temp_video_fps = restrict_video_fps(state_manager.get_item('target_path'), state_manager.get_item('output_video_fps'))
	logger.info(translator.get('extracting_frames').format(resolution=pack_resolution(temp_video_resolution), fps=temp_video_fps), __name__)

	if ffmpeg.extract_frames(state_manager.get_item('target_path'), temp_video_resolution, temp_video_fps, trim_frame_start, trim_frame_end):
		logger.debug(translator.get('extracting_frames_succeeded'), __name__)
	else:
		if is_process_stopping():
			return 4
		logger.error(translator.get('extracting_frames_failed'), __name__)
		return 1
	return 0


def process_video() -> ErrorCode:
	temp_frame_paths = resolve_temp_frame_paths(state_manager.get_item('target_path'))

	if not temp_frame_paths:
		logger.error(translator.get('temp_frames_not_found'), __name__)
		return 1

	chunk_start, chunk_end = _chunk_range_from_env()

	if chunk_start is not None and chunk_end is not None:
		return _process_video_slice(temp_frame_paths, chunk_start, chunk_end)

	chunk_size = state_manager.get_item('chunk_size_frames') or 0
	if chunk_size > 0 and len(temp_frame_paths) > chunk_size:
		from facefusion.workflows import chunk_runner
		job_id = state_manager.get_item('job_id')
		if job_id:
			step_index = state_manager.get_item('step_index') or 0
			return chunk_runner.run_chunked(temp_frame_paths, chunk_size, job_id, step_index)
		logger.warn('chunk_runner_skipped: no job_id in state, falling back to in-process', __name__)

	return _process_video_slice(temp_frame_paths, 0, len(temp_frame_paths))


def _process_video_slice(temp_frame_paths : list, start_index : int, end_index : int) -> ErrorCode:
	slice_paths = temp_frame_paths[start_index:end_index]
	if not slice_paths:
		return 0

	desc = f'processing[{start_index}:{end_index}]' if (start_index, end_index) != (0, len(temp_frame_paths)) else translator.get('processing')

	with tqdm(total = len(slice_paths), desc = desc, unit = 'frame', ascii = ' =', disable = state_manager.get_item('log_level') in [ 'warn', 'error' ]) as progress:
		progress.set_postfix(execution_providers = state_manager.get_item('execution_providers'))

		failed_frames : list[tuple[int, str]] = []

		with ThreadPoolExecutor(max_workers = state_manager.get_item('execution_thread_count')) as executor:
			futures = []
			future_to_frame : dict = {}

			for offset, temp_frame_path in enumerate(slice_paths):
				frame_number = start_index + offset
				future = executor.submit(process_temp_frame, temp_frame_path, frame_number)
				futures.append(future)
				future_to_frame[future] = frame_number

			for future in as_completed(futures):
				if is_process_stopping():
					for __future__ in futures:
						__future__.cancel()

				if not future.cancelled():
					try:
						future.result()
					except Exception as exception:
						frame_number = future_to_frame[future]
						failed_frames.append((frame_number, str(exception)))
						logger.warn(f'frame_processing_failed (skipping): frame={frame_number}: {exception}\n{traceback.format_exc()}', __name__)
					progress.update()

	if failed_frames and not is_process_stopping():
		retry_frame_numbers = [frame_number for frame_number, _ in failed_frames]
		logger.info(f'frame_processing_retry: attempting serial retry of {len(retry_frame_numbers)} failed frame(s)', __name__)
		recovered : set = set()
		for frame_number in retry_frame_numbers:
			try:
				process_temp_frame(temp_frame_paths[frame_number], frame_number)
				recovered.add(frame_number)
			except Exception as exception:
				logger.warn(f'frame_processing_retry_failed: frame={frame_number}: {exception}', __name__)
		if recovered:
			logger.info(f'frame_processing_retry_recovered: {len(recovered)}/{len(retry_frame_numbers)} previously-failed frames recovered on retry', __name__)
			failed_frames = [entry for entry in failed_frames if entry[0] not in recovered]

	if failed_frames:
		failure_rate = len(failed_frames) / len(slice_paths)
		logger.warn(f'frame_processing_summary: {len(failed_frames)}/{len(slice_paths)} frames failed ({failure_rate:.1%}); using original frames for those positions', __name__)
		if failure_rate > FRAME_FAILURE_ABORT_THRESHOLD:
			logger.error(f'frame_processing_aborted: failure rate {failure_rate:.1%} exceeds {FRAME_FAILURE_ABORT_THRESHOLD:.0%} threshold', __name__)
			return 1

	for processor_module in get_processors_modules(state_manager.get_item('processors')):
		processor_module.post_process()

	if is_process_stopping():
		return 4
	return 0


def merge_frames() -> ErrorCode:
	trim_frame_start, trim_frame_end = restrict_trim_frame(state_manager.get_item('target_path'), state_manager.get_item('trim_frame_start'), state_manager.get_item('trim_frame_end'))
	output_video_resolution = scale_resolution(detect_video_resolution(state_manager.get_item('target_path')), state_manager.get_item('output_video_scale'))
	temp_video_fps = restrict_video_fps(state_manager.get_item('target_path'), state_manager.get_item('output_video_fps'))

	logger.info(translator.get('merging_video').format(resolution = pack_resolution(output_video_resolution), fps = state_manager.get_item('output_video_fps')), __name__)
	if ffmpeg.merge_video(state_manager.get_item('target_path'), temp_video_fps, output_video_resolution, state_manager.get_item('output_video_fps'), trim_frame_start, trim_frame_end):
		logger.debug(translator.get('merging_video_succeeded'), __name__)
	else:
		if is_process_stopping():
			return 4
		logger.error(translator.get('merging_video_failed'), __name__)
		return 1
	return 0


def restore_audio() -> ErrorCode:
	trim_frame_start, trim_frame_end = restrict_trim_frame(state_manager.get_item('target_path'), state_manager.get_item('trim_frame_start'), state_manager.get_item('trim_frame_end'))

	if state_manager.get_item('output_audio_volume') == 0:
		logger.info(translator.get('skipping_audio'), __name__)
		move_temp_file(state_manager.get_item('target_path'), state_manager.get_item('output_path'))
	else:
		source_audio_path = get_first(filter_audio_paths(state_manager.get_item('source_paths')))
		if source_audio_path:
			if ffmpeg.replace_audio(state_manager.get_item('target_path'), source_audio_path, state_manager.get_item('output_path')):
				video_manager.clear_video_pool()
				logger.debug(translator.get('replacing_audio_succeeded'), __name__)
			else:
				video_manager.clear_video_pool()
				if is_process_stopping():
					return 4
				logger.warn(translator.get('replacing_audio_skipped'), __name__)
				move_temp_file(state_manager.get_item('target_path'), state_manager.get_item('output_path'))
		else:
			if ffmpeg.restore_audio(state_manager.get_item('target_path'), state_manager.get_item('output_path'), trim_frame_start, trim_frame_end):
				video_manager.clear_video_pool()
				logger.debug(translator.get('restoring_audio_succeeded'), __name__)
			else:
				video_manager.clear_video_pool()
				if is_process_stopping():
					return 4
				logger.warn(translator.get('restoring_audio_skipped'), __name__)
				move_temp_file(state_manager.get_item('target_path'), state_manager.get_item('output_path'))
	return 0


def process_temp_frame(temp_frame_path : str, frame_number : int) -> bool:
	reference_vision_frame = read_static_video_frame(state_manager.get_item('target_path'), state_manager.get_item('reference_frame_number'))
	source_vision_frames = read_static_images(state_manager.get_item('source_paths'))
	source_audio_path = get_first(filter_audio_paths(state_manager.get_item('source_paths')))
	temp_video_fps = restrict_video_fps(state_manager.get_item('target_path'), state_manager.get_item('output_video_fps'))
	target_vision_frame = read_static_image(temp_frame_path, 'rgba')
	temp_vision_frame = target_vision_frame.copy()
	temp_vision_mask = extract_vision_mask(temp_vision_frame)

	source_audio_frame = get_audio_frame(source_audio_path, temp_video_fps, frame_number)
	source_voice_frame = get_voice_frame(source_audio_path, temp_video_fps, frame_number)

	if not numpy.any(source_audio_frame):
		source_audio_frame = create_empty_audio_frame()
	if not numpy.any(source_voice_frame):
		source_voice_frame = create_empty_audio_frame()

	for processor_module in get_processors_modules(state_manager.get_item('processors')):
		temp_vision_frame, temp_vision_mask = processor_module.process_frame(
		{
			'reference_vision_frame': reference_vision_frame,
			'source_vision_frames': source_vision_frames,
			'source_audio_frame': source_audio_frame,
			'source_voice_frame': source_voice_frame,
			'target_vision_frame': target_vision_frame[:, :, :3],
			'temp_vision_frame': temp_vision_frame[:, :, :3],
			'temp_vision_mask': temp_vision_mask
		})

	temp_vision_frame = conditional_merge_vision_mask(temp_vision_frame, temp_vision_mask)
	return write_image(temp_frame_path, temp_vision_frame)


def finalize_video(start_time : float) -> ErrorCode:
	logger.debug(translator.get('clearing_temp'), __name__)
	clear_temp_directory(state_manager.get_item('target_path'))

	if is_video(state_manager.get_item('output_path')):
		logger.info(translator.get('processing_video_succeeded').format(seconds = calculate_end_time(start_time)), __name__)
	else:
		logger.error(translator.get('processing_video_failed'), __name__)
		return 1
	return 0
