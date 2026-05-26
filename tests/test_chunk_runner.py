import subprocess
import threading
from pathlib import Path
from typing import List, Tuple

import pytest

from facefusion import state_manager
from facefusion.workflows import chunk_runner


@pytest.fixture(scope = 'function', autouse = True)
def before_each() -> None:
	state_manager.STATE_SET['cli'].clear()
	state_manager.STATE_SET['ui'].clear()


class DummyProcess:
	def wait(self) -> int:
		return 0


def test_build_chunk_command_includes_step_index() -> None:
	state_manager.init_item('config_path', 'custom.ini')
	state_manager.init_item('jobs_path', 'custom-jobs')

	command = chunk_runner._build_chunk_command('job-test', 2)
	chunk_run_index = command.index('chunk-run')

	assert command[chunk_run_index + 1:chunk_run_index + 3] == [ 'job-test', '2' ]
	assert command[chunk_run_index + 3:] == [ '--config-path', 'custom.ini', '--jobs-path', 'custom-jobs' ]


def test_run_chunked_passes_step_index_to_each_chunk(monkeypatch : pytest.MonkeyPatch, tmp_path : Path) -> None:
	spawn_calls : List[Tuple[str, int, int, int, int]] = []

	def fake_spawn_chunk(job_id : str, step_index : int, chunk_index : int, start_index : int, end_index : int) -> Tuple[subprocess.Popen, Path]:
		spawn_calls.append((job_id, step_index, chunk_index, start_index, end_index))
		log_path = tmp_path / f'chunk-{chunk_index}.log'
		log_path.write_text('done\n')
		return DummyProcess(), log_path #type:ignore[return-value]

	def fake_tail_log_to_stdout(log_path : Path, prefix_label : str, stop_event : threading.Event) -> None:
		return None

	monkeypatch.setattr(chunk_runner, '_spawn_chunk', fake_spawn_chunk)
	monkeypatch.setattr(chunk_runner, '_tail_log_to_stdout', fake_tail_log_to_stdout)

	error_code = chunk_runner.run_chunked([ '0.jpg', '1.jpg', '2.jpg', '3.jpg', '4.jpg' ], 2, 'job-test', 3)

	assert error_code == 0
	assert spawn_calls ==\
	[
		('job-test', 3, 0, 0, 2),
		('job-test', 3, 1, 2, 4),
		('job-test', 3, 2, 4, 5)
	]
