import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from facefusion import logger, state_manager
from facefusion.types import ErrorCode

CHUNK_RETRY_LIMIT = 1
CHUNK_FAILURE_RATE_ABORT_THRESHOLD = 0.50


def _project_dir() -> Path:
	return Path(__file__).resolve().parent.parent.parent


def _build_chunk_command(job_id : str) -> List[str]:
	project_dir = _project_dir()
	config_path = state_manager.get_item('config_path') or str(project_dir / 'facefusion.ini')
	jobs_path = state_manager.get_item('jobs_path') or str(project_dir / '.jobs')

	command : List[str] = []
	caffeinate = shutil.which('caffeinate')
	if caffeinate:
		command += [ caffeinate, '-dimsu' ]
	command += [
		sys.executable, '-u',
		str(project_dir / 'facefusion.py'), 'chunk-run',
		job_id,
		'--config-path', config_path,
		'--jobs-path', jobs_path,
	]
	return command


def _spawn_chunk(job_id : str, chunk_index : int, start_index : int, end_index : int) -> Tuple[subprocess.Popen, Path]:
	project_dir = _project_dir()
	log_dir = project_dir / 'logs'
	log_dir.mkdir(exist_ok = True)
	timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
	chunk_label = f'chunk-{chunk_index:03d}-{start_index:08d}-{end_index:08d}'
	log_path = log_dir / f'job-{timestamp}-{job_id}-{chunk_label}.log'

	env = {
		**os.environ,
		'PYTHONUNBUFFERED': '1',
		'PYTHONFAULTHANDLER': '1',
		'FACEFUSION_CHUNK_START': str(start_index),
		'FACEFUSION_CHUNK_END': str(end_index),
	}

	log_file = open(log_path, 'wb')
	process = subprocess.Popen(
		_build_chunk_command(job_id),
		cwd = str(project_dir),
		stdout = log_file,
		stderr = subprocess.STDOUT,
		start_new_session = True,
		env = env,
	)
	return process, log_path


def _tail_log_to_stdout(log_path : Path, prefix_label : str, stop_event : threading.Event) -> None:
	for _ in range(50):
		if log_path.exists():
			break
		stop_event.wait(0.1)
	if not log_path.exists():
		return
	prefix = f'[{prefix_label}] '.encode('utf-8')
	try:
		with open(log_path, 'rb') as handle:
			line_buffer = b''
			while True:
				chunk = handle.read(8192)
				if chunk:
					line_buffer += chunk
					while True:
						newline_index = -1
						for index, byte in enumerate(line_buffer):
							if byte == 0x0a or byte == 0x0d:
								newline_index = index
								break
						if newline_index == -1:
							break
						line = line_buffer[: newline_index + 1]
						line_buffer = line_buffer[newline_index + 1 :]
						sys.stdout.buffer.write(prefix + line)
					sys.stdout.buffer.flush()
				else:
					if stop_event.is_set():
						if line_buffer:
							sys.stdout.buffer.write(prefix + line_buffer)
							sys.stdout.buffer.flush()
						return
					stop_event.wait(0.2)
	except Exception as exception:
		logger.error(f'chunk_log_tail_failed prefix={prefix_label}: {exception}', __name__)


def run_chunked(temp_frame_paths : List[str], chunk_size : int, job_id : str) -> ErrorCode:
	chunks : List[Tuple[int, int, int]] = []
	for chunk_index, start_index in enumerate(range(0, len(temp_frame_paths), chunk_size)):
		end_index = min(start_index + chunk_size, len(temp_frame_paths))
		chunks.append((chunk_index, start_index, end_index))

	logger.info(f'chunk_runner_start: total_chunks={len(chunks)} chunk_size={chunk_size} total_frames={len(temp_frame_paths)} job_id={job_id}', __name__)

	failed_chunks : List[Tuple[int, int, int]] = []

	for chunk_index, start_index, end_index in chunks:
		success = False
		for attempt in range(CHUNK_RETRY_LIMIT + 1):
			attempt_label = '' if attempt == 0 else f' retry={attempt}'
			logger.info(f'chunk_runner_chunk_start: chunk={chunk_index} range=[{start_index},{end_index}){attempt_label}', __name__)

			process, log_path = _spawn_chunk(job_id, chunk_index, start_index, end_index)
			prefix_label = f'{job_id}-chunk-{chunk_index:03d}'
			stop_event = threading.Event()
			tail_thread = threading.Thread(
				target = _tail_log_to_stdout,
				args = (log_path, prefix_label, stop_event),
				daemon = True,
			)
			tail_thread.start()

			return_code = process.wait()
			stop_event.set()
			tail_thread.join(timeout = 5.0)

			if return_code == 0:
				success = True
				logger.info(f'chunk_runner_chunk_completed: chunk={chunk_index} range=[{start_index},{end_index}){attempt_label}', __name__)
				break
			logger.warn(f'chunk_runner_chunk_failed: chunk={chunk_index} range=[{start_index},{end_index}) exit_code={return_code}{attempt_label}', __name__)

		if not success:
			failed_chunks.append((chunk_index, start_index, end_index))
			logger.error(f'chunk_runner_chunk_skipped: chunk={chunk_index} range=[{start_index},{end_index}) (frames remain as originals)', __name__)

	if failed_chunks:
		failed_frame_count = sum(end - start for _, start, end in failed_chunks)
		failure_rate = failed_frame_count / len(temp_frame_paths)
		logger.warn(f'chunk_runner_summary: {len(failed_chunks)}/{len(chunks)} chunks failed; {failed_frame_count}/{len(temp_frame_paths)} frames will use originals ({failure_rate:.1%})', __name__)
		if failure_rate > CHUNK_FAILURE_RATE_ABORT_THRESHOLD:
			logger.error(f'chunk_runner_aborted: failure rate {failure_rate:.1%} exceeds {CHUNK_FAILURE_RATE_ABORT_THRESHOLD:.0%} threshold', __name__)
			return 1
	else:
		logger.info(f'chunk_runner_summary: all {len(chunks)} chunks completed', __name__)

	return 0
