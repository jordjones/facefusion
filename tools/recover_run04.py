"""Recover Run 04 from an interrupted chunked render.

This is intentionally focused on the 2026-05-26 Run 04 handoff. It resumes
chunk processing from the known job/temp state, then merges frames and restores
audio through FaceFusion's existing workflow functions.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

DEFAULT_JOB_ID = 'headless-2026-05-26-18-59-40'
DEFAULT_TEMP_PATH = '/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T'
DEFAULT_STEP_INDEX = 0
DEFAULT_CHUNK_SIZE = 250
DEFAULT_START_CHUNK = 15
DEFAULT_EXPECTED_FRAME_COUNT = 14557


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Recover FaceFusion Run 04 from a specific chunk.')
    parser.add_argument('--job-id', default=DEFAULT_JOB_ID)
    parser.add_argument('--step-index', type=int, default=DEFAULT_STEP_INDEX)
    parser.add_argument('--config-path', default='facefusion.ini')
    parser.add_argument('--jobs-path', default='.jobs')
    parser.add_argument('--temp-path', default=DEFAULT_TEMP_PATH)
    parser.add_argument('--chunk-size', type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument('--start-chunk', type=int, default=DEFAULT_START_CHUNK)
    parser.add_argument('--end-chunk', type=int)
    parser.add_argument('--expected-frame-count', type=int, default=DEFAULT_EXPECTED_FRAME_COUNT)
    parser.add_argument('--execution-providers', nargs='+', default=['cpu'])
    parser.add_argument('--execution-thread-count', type=int, default=12)
    parser.add_argument('--log-level', default='info')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--no-caffeinate', action='store_true')
    parser.add_argument('--no-finalize', action='store_true')
    parser.add_argument('--rerun-completed', action='store_true')
    return parser.parse_args()


def read_step_args(job_id: str, jobs_path: str, step_index: int) -> dict[str, Any]:
    job_path = PROJECT_DIR / jobs_path / 'queued' / f'{job_id}.json'
    if not job_path.exists():
        raise FileNotFoundError(f'queued job not found: {job_path}')
    with job_path.open() as handle:
        job = json.load(handle)
    steps = job.get('steps') or []
    if step_index not in range(len(steps)):
        raise IndexError(f'step {step_index} not found in {job_path}')
    return steps[step_index].get('args') or {}


def resolve_temp_frames(temp_path: str, target_path: str, temp_frame_format: str) -> list[str]:
    target_name = Path(target_path).stem
    frame_pattern = Path(temp_path) / 'facefusion' / target_name / f'*.{temp_frame_format}'
    return sorted(glob.glob(str(frame_pattern)))


def verify_run04_temp_inventory(args: argparse.Namespace, temp_frames: list[str], temp_frame_format: str) -> None:
    temp_path = Path(args.temp_path).resolve()
    expected_temp_path = Path(DEFAULT_TEMP_PATH).resolve()
    if temp_path != expected_temp_path:
        raise RuntimeError(f'unexpected Run 04 temp path: {temp_path}; expected {expected_temp_path}')

    if len(temp_frames) != args.expected_frame_count:
        raise RuntimeError(f'unexpected Run 04 frame count: {len(temp_frames)}; expected {args.expected_frame_count}')

    for index, temp_frame in enumerate(temp_frames, start=1):
        expected_name = f'{index:08d}.{temp_frame_format}'
        frame_name = Path(temp_frame).name
        if frame_name != expected_name:
            raise RuntimeError(f'unexpected Run 04 frame sequence at offset {index}: {frame_name}; expected {expected_name}')


def completed_log_path(job_id: str, chunk_index: int, start_index: int, end_index: int) -> Path | None:
    log_pattern = PROJECT_DIR / 'logs' / f'*{job_id}*chunk-{chunk_index:03d}-{start_index:08d}-{end_index:08d}.log'
    for log_path in sorted(log_pattern.parent.glob(log_pattern.name)):
        try:
            tail = log_path.read_bytes()[-8192:].decode('utf-8', errors='replace')
        except OSError:
            continue
        if 'hard_exit(0)' in tail and '[FACEFUSION.ATEXIT]' in tail:
            return log_path
    return None


def chunk_bounds(chunk_index: int, chunk_size: int, frame_total: int) -> tuple[int, int]:
    start_index = chunk_index * chunk_size
    end_index = min(start_index + chunk_size, frame_total)
    return start_index, end_index


def verify_completed_prefix(args: argparse.Namespace, frame_total: int) -> None:
    missing_chunks: list[str] = []

    for chunk_index in range(args.start_chunk):
        start_index, end_index = chunk_bounds(chunk_index, args.chunk_size, frame_total)
        if not completed_log_path(args.job_id, chunk_index, start_index, end_index):
            missing_chunks.append(f'{chunk_index:03d} [{start_index},{end_index})')

    if missing_chunks:
        missing = ', '.join(missing_chunks)
        raise RuntimeError(f'cannot finalize: missing completed logs for skipped chunk(s): {missing}')
    if args.start_chunk > 0:
        print(f'verified completed logs for skipped chunks 000..{args.start_chunk - 1:03d}', flush=True)


def build_chunk_command(args: argparse.Namespace) -> list[str]:
    command: list[str] = []
    caffeinate = shutil.which('caffeinate')
    if caffeinate and not args.no_caffeinate:
        command.extend([caffeinate, '-dimsu'])
    command.extend([
        sys.executable,
        '-u',
        str(PROJECT_DIR / 'facefusion.py'),
        'chunk-run',
        args.job_id,
        str(args.step_index),
        '--config-path',
        args.config_path,
        '--temp-path',
        args.temp_path,
        '--jobs-path',
        args.jobs_path,
        '--execution-providers',
        *args.execution_providers,
        '--execution-thread-count',
        str(args.execution_thread_count),
        '--log-level',
        args.log_level,
    ])
    return command


def run_chunk(args: argparse.Namespace, chunk_index: int, start_index: int, end_index: int) -> Path:
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    log_path = PROJECT_DIR / 'logs' / f'job-{timestamp}-{args.job_id}-chunk-{chunk_index:03d}-{start_index:08d}-{end_index:08d}.log'
    env = {
        **os.environ,
        'FACEFUSION_CHUNK_START': str(start_index),
        'FACEFUSION_CHUNK_END': str(end_index),
        'PYTHONUNBUFFERED': '1',
        'PYTHONFAULTHANDLER': '1',
    }
    command = build_chunk_command(args)
    print(f'chunk {chunk_index:03d} start [{start_index},{end_index}) log={log_path.relative_to(PROJECT_DIR)}', flush=True)
    if args.dry_run:
        env_prefix = [
            f'FACEFUSION_CHUNK_START={start_index}',
            f'FACEFUSION_CHUNK_END={end_index}',
            'PYTHONUNBUFFERED=1',
            'PYTHONFAULTHANDLER=1',
        ]
        command_text = ' '.join([ *env_prefix, *(shlex.quote(part) for part in command) ])
        print('  ' + command_text, flush=True)
        return log_path
    with log_path.open('wb') as log_handle:
        process = subprocess.Popen(command, cwd=PROJECT_DIR, stdout=log_handle, stderr=subprocess.STDOUT, env=env)
        return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f'chunk {chunk_index:03d} failed with exit code {return_code}; see {log_path}')
    print(f'chunk {chunk_index:03d} complete', flush=True)
    return log_path


def apply_facefusion_state(args: argparse.Namespace, step_args: dict[str, Any]) -> None:
    from facefusion import logger, state_manager
    from facefusion.args import apply_args, collect_job_args
    from facefusion.jobs import job_manager
    from facefusion.program import create_program

    program = create_program()
    parsed_args = vars(program.parse_args([
        'chunk-run',
        args.job_id,
        str(args.step_index),
        '--config-path',
        args.config_path,
        '--temp-path',
        args.temp_path,
        '--jobs-path',
        args.jobs_path,
        '--execution-providers',
        *args.execution_providers,
        '--execution-thread-count',
        str(args.execution_thread_count),
        '--log-level',
        args.log_level,
    ]))
    apply_args(parsed_args, state_manager.init_item)
    if not job_manager.init_jobs(state_manager.get_item('jobs_path')):
        raise RuntimeError(f'could not initialize jobs path: {state_manager.get_item("jobs_path")}')

    resolved_args = dict(step_args)
    resolved_args.update(collect_job_args())
    apply_args(resolved_args, state_manager.set_item)
    state_manager.set_item('job_id', args.job_id)
    state_manager.set_item('step_index', args.step_index)
    state_manager.set_item('keep_temp', True)
    logger.init(state_manager.get_item('log_level'))


def finalize_output(args: argparse.Namespace, step_args: dict[str, Any]) -> None:
    if args.dry_run or args.no_finalize:
        print('finalize skipped', flush=True)
        return

    from facefusion import process_manager
    from facefusion.workflows import image_to_video

    os.chdir(PROJECT_DIR)
    apply_facefusion_state(args, step_args)
    start_time = time.time()
    print('merge_frames start', flush=True)
    process_manager.start()
    try:
        for task_name, task in [
            ('merge_frames', image_to_video.merge_frames),
            ('restore_audio', image_to_video.restore_audio),
        ]:
            error_code = task()
            if error_code > 0:
                raise RuntimeError(f'{task_name} failed with error code {error_code}')
            print(f'{task_name} complete', flush=True)
        error_code = image_to_video.finalize_video(start_time)
        if error_code > 0:
            raise RuntimeError(f'finalize_video failed with error code {error_code}')
    finally:
        process_manager.end()
    print('finalize complete; temp frames preserved because keep_temp=True', flush=True)


def mark_job_completed(args: argparse.Namespace) -> None:
    from facefusion.jobs import job_manager

    if not job_manager.set_step_status(args.job_id, args.step_index, 'completed'):
        raise RuntimeError(f'could not mark step {args.step_index} completed for job {args.job_id}')
    if not job_manager.move_job_file(args.job_id, 'completed'):
        raise RuntimeError(f'could not move job {args.job_id} to completed')
    print(f'job {args.job_id} moved to completed', flush=True)


def main() -> None:
    os.chdir(PROJECT_DIR)
    args = parse_args()
    step_args = read_step_args(args.job_id, args.jobs_path, args.step_index)
    target_path = step_args.get('target_path')
    temp_frame_format = step_args.get('temp_frame_format') or 'png'
    if not target_path:
        raise RuntimeError('job step has no target_path')

    temp_frames = resolve_temp_frames(args.temp_path, target_path, temp_frame_format)
    if not temp_frames:
        raise RuntimeError(f'no temp frames found under {args.temp_path}')
    verify_run04_temp_inventory(args, temp_frames, temp_frame_format)
    total_chunks = math.ceil(len(temp_frames) / args.chunk_size)
    end_chunk = args.end_chunk if args.end_chunk is not None else total_chunks - 1
    if args.start_chunk < 0 or end_chunk >= total_chunks or args.start_chunk > end_chunk:
        raise RuntimeError(f'invalid chunk range {args.start_chunk}..{end_chunk}; total chunks={total_chunks}')

    print(f'temp_frames={len(temp_frames)} total_chunks={total_chunks} range={args.start_chunk}..{end_chunk}', flush=True)
    print(f'temp_path={args.temp_path}', flush=True)

    if end_chunk == total_chunks - 1 and not args.no_finalize:
        verify_completed_prefix(args, len(temp_frames))

    for chunk_index in range(args.start_chunk, end_chunk + 1):
        start_index, end_index = chunk_bounds(chunk_index, args.chunk_size, len(temp_frames))
        existing_log = completed_log_path(args.job_id, chunk_index, start_index, end_index)
        if existing_log and not args.rerun_completed:
            print(f'chunk {chunk_index:03d} skip existing complete log={existing_log.relative_to(PROJECT_DIR)}', flush=True)
            continue
        run_chunk(args, chunk_index, start_index, end_index)

    if end_chunk < total_chunks - 1 and not args.no_finalize:
        print(f'finalize skipped; processed through chunk {end_chunk:03d}, last chunk is {total_chunks - 1:03d}', flush=True)
        return

    finalize_output(args, step_args)
    if not args.dry_run and not args.no_finalize:
        mark_job_completed(args)


if __name__ == '__main__':
    main()
