import os
from functools import partial
from typing import Optional, Tuple

from facefusion import logger, process_manager, state_manager
from facefusion.types import ErrorCode
from facefusion.workflows.core import clear, setup
from facefusion.workflows.to_video import analyse_video, extract_frames, finalize_video, merge_frames, process_disk_frames, process_memory_frames, restore_audio


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
		error_code = process_disk_frames()
		process_manager.end()
		return error_code

	tasks =\
	[
		analyse_video,
		clear,
		setup
	]

	if state_manager.get_item('workflow_strategy') == 'disk':
		tasks.extend(
		[
			extract_frames,
			process_disk_frames,
			merge_frames
		])

	if state_manager.get_item('workflow_strategy') == 'memory':
		tasks.append(process_memory_frames)

	tasks.extend(
	[
		restore_audio,
		partial(finalize_video, start_time),
		clear
	])
	process_manager.start()

	for task in tasks:
		error_code = task() #type:ignore[operator]

		if error_code > 0:
			process_manager.end()
			return error_code

	process_manager.end()
	return 0
