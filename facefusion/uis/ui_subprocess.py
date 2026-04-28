import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from facefusion import logger, state_manager


def _project_dir() -> Path:
	return Path(__file__).resolve().parent.parent.parent


def _build_command(job_id : str, project_dir : Path) -> List[str]:
	config_path = state_manager.get_item('config_path') or str(project_dir / 'facefusion.ini')
	jobs_path = state_manager.get_item('jobs_path') or str(project_dir / '.jobs')

	command : List[str] = []
	caffeinate = shutil.which('caffeinate')
	if caffeinate:
		command += [ caffeinate, '-dimsu' ]
	command += [
		sys.executable, '-u',
		str(project_dir / 'facefusion.py'), 'job-run',
		job_id,
		'--config-path', config_path,
		'--jobs-path', jobs_path,
	]
	return command


def spawn_job_worker(job_id : str) -> Optional[int]:
	project_dir = _project_dir()
	log_dir = project_dir / 'logs'
	log_dir.mkdir(exist_ok = True)
	timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
	log_path = log_dir / ('job-' + timestamp + '-' + job_id + '.log')

	command = _build_command(job_id, project_dir)
	worker_env = { **os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONFAULTHANDLER': '1' }

	try:
		log_file = open(log_path, 'wb')
		process = subprocess.Popen(
			command,
			cwd = str(project_dir),
			stdout = log_file,
			stderr = subprocess.STDOUT,
			start_new_session = True,
			env = worker_env,
		)
	except OSError as exception:
		logger.error('worker_spawn_failed: ' + str(exception), __name__)
		return None

	logger.info('worker_spawned pid=' + str(process.pid) + ' job_id=' + job_id + ' log=' + str(log_path), __name__)
	threading.Thread(
		target = _tail_log_to_stdout,
		args = (log_path, process.pid, job_id),
		daemon = True,
	).start()
	return process.pid


def _tail_log_to_stdout(log_path : Path, worker_pid : int, job_id : str) -> None:
	for _ in range(50):
		if log_path.exists():
			break
		time.sleep(0.1)
	if not log_path.exists():
		return
	prefix = ('[' + job_id + '] ').encode('utf-8')
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
					if not is_worker_alive(worker_pid):
						if line_buffer:
							sys.stdout.buffer.write(prefix + line_buffer)
							sys.stdout.buffer.flush()
						return
					time.sleep(0.2)
	except Exception as exception:
		logger.error('log_tail_failed job_id=' + job_id + ': ' + str(exception), __name__)


def signal_worker(pid : int, sig : int = signal.SIGTERM) -> bool:
	try:
		os.kill(pid, sig)
		return True
	except ProcessLookupError:
		return False
	except PermissionError as exception:
		logger.error('worker_signal_failed pid=' + str(pid) + ': ' + str(exception), __name__)
		return False


def is_worker_alive(pid : int) -> bool:
	try:
		os.kill(pid, 0)
		return True
	except (ProcessLookupError, PermissionError):
		return False
