import atexit
import os
import resource
import signal
import sys
import threading
import traceback
from time import sleep, time
from types import FrameType

from facefusion import process_manager, state_manager
from facefusion.temp_helper import clear_temp_directory
from facefusion.types import ErrorCode


def _diag_log(message : str) -> None:
	sys.stderr.write('[FACEFUSION.DIAG] ' + message + '\n')
	sys.stderr.write(''.join(traceback.format_stack()))
	sys.stderr.flush()


_PROBE_SIGNALS = [
	signal.SIGTERM,
	signal.SIGHUP,
	signal.SIGABRT,
	signal.SIGPIPE,
	signal.SIGUSR1,
	signal.SIGUSR2,
]


def _signal_probe(signum : int, frame : FrameType) -> None:
	sys.stderr.write(f'[FACEFUSION.SIGNAL] signum={signum} name={signal.Signals(signum).name} pid={os.getpid()}\n')
	sys.stderr.write(''.join(traceback.format_stack(frame)))
	sys.stderr.flush()
	signal.signal(signum, signal.SIG_DFL)
	os.kill(os.getpid(), signum)


def _atexit_probe() -> None:
	sys.stderr.write(f'[FACEFUSION.ATEXIT] pid={os.getpid()}\n')
	sys.stderr.flush()


def _heartbeat_loop(interval_seconds : float) -> None:
	page_size = resource.getpagesize() if hasattr(resource, 'getpagesize') else 4096
	start = time()
	while True:
		try:
			usage = resource.getrusage(resource.RUSAGE_SELF)
			rss_bytes = usage.ru_maxrss if sys.platform == 'darwin' else usage.ru_maxrss * 1024
			rss_gb = rss_bytes / (1024 ** 3)
			elapsed = time() - start
			sys.stderr.write(f'[FACEFUSION.HEARTBEAT] pid={os.getpid()} rss_gb={rss_gb:.2f} elapsed_s={elapsed:.0f}\n')
			sys.stderr.flush()
		except Exception:
			pass
		sleep(interval_seconds)


def install_diagnostics(heartbeat_interval_seconds : float = 10.0) -> None:
	for signum in _PROBE_SIGNALS:
		try:
			signal.signal(signum, _signal_probe)
		except (OSError, ValueError):
			pass
	atexit.register(_atexit_probe)
	thread = threading.Thread(target = _heartbeat_loop, args = (heartbeat_interval_seconds,), daemon = True, name = 'facefusion-heartbeat')
	thread.start()
	sys.stderr.write(f'[FACEFUSION.DIAG_INSTALLED] pid={os.getpid()} heartbeat_interval_s={heartbeat_interval_seconds}\n')
	sys.stderr.flush()


def fatal_exit(error_code : ErrorCode) -> None:
	_diag_log('fatal_exit(' + str(error_code) + ')')
	os._exit(error_code)


def hard_exit(error_code : ErrorCode) -> None:
	_diag_log('hard_exit(' + str(error_code) + ')')
	sys.exit(error_code)


def signal_exit(signum : int, frame : FrameType) -> None:
	_diag_log('signal_exit(signum=' + str(signum) + ')')
	graceful_exit(0)


def graceful_exit(error_code : ErrorCode) -> None:
	_diag_log('graceful_exit(' + str(error_code) + ')')
	signal.signal(signal.SIGINT, signal.SIG_IGN)
	process_manager.stop()

	while process_manager.is_processing():
		sleep(0.5)

	if state_manager.get_item('target_path'):
		clear_temp_directory(state_manager.get_item('target_path'))

	hard_exit(error_code)
