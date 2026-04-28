# Architecture: facefusion (personal fork)

## Overview

FaceFusion is a face-manipulation pipeline (face swap, enhancement, upscaling, expression and age editing, lip sync, background removal, frame colorization) operating on images and videos via a Gradio dashboard or a headless CLI. This fork (v3.6.0) is a personal-use derivative running locally on Apple Silicon (M4 Max, 128 GB RAM) via the CoreML execution provider, modified for resilience under long-render workloads — silent worker deaths around 5-7% of long renders motivated subprocess chunking, frame-tolerant skip-and-retry, decoupled UI workers, and a battery of diagnostic probes. Companion docs: [`MODELS_AND_SETTINGS.md`](MODELS_AND_SETTINGS.md) catalogs every model and UI setting; [`../settings.md`](../settings.md) narrates the config-of-record; [`../.loop/README.md`](../.loop/README.md) preserves the autonomous fix-and-retry loop pattern; [`../WORKLOG.md`](../WORKLOG.md) tracks active workstreams.

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ (conda env `facefusion`) |
| ML runtime | ONNX Runtime with CoreML + CPU execution providers |
| UI | Gradio (HTTP server, served at `localhost:7860`) |
| Media I/O | ffmpeg (frame extract, merge, audio restore) |
| Concurrency | `concurrent.futures.ThreadPoolExecutor` per chunk; subprocess chunks via fork+exec |
| Process supervision | `caffeinate` wrapper, decoupled UI worker subprocess, log-tail thread |
| Audio | numpy/scipy via FaceFusion's `audio.py`; voice extraction via UVR-MDX-Net family |
| Models | 176 ONNX models across 17 modules (see `MODELS_AND_SETTINGS.md`) |
| Storage | local filesystem; ONNX weights in `.assets/models/`, temp frames in `.temp/`, jobs in `.jobs/` |
| Config | `facefusion.ini` (config sections), CLI argparse (`facefusion/program.py`), env vars (`FACEFUSION_CHUNK_START/END`, `PYTHONFAULTHANDLER`) |

## System Architecture

```
                     ┌────────────────────────────┐
                     │  launch.command  /          │
                     │  Launch FaceFusion.app      │
                     └─────────────┬───────────────┘
                                   ▼
                     ┌────────────────────────────┐
                     │  Gradio UI server           │
                     │  facefusion.py run          │
                     │  (instant_runner panel)     │
                     └─────────────┬───────────────┘
                              "Start" click
                                   ▼
                  ui_subprocess.spawn_job_worker(job_id)
                                   ▼
        ┌─────────────────────────────────────────────────┐
        │     PARENT WORKER  (caffeinate + python)         │
        │     facefusion.py job-run <job_id>               │
        │  ┌─────────────────────────────────────────┐    │
        │  │  setup → extract_frames → process_video │    │
        │  │       → merge_frames → restore_audio    │    │
        │  │       → finalize_video                  │    │
        │  └────────┬────────────────────────────────┘    │
        │           │ chunk_size_frames > 0               │
        │           ▼                                     │
        │  chunk_runner.run_chunked(...)                  │
        └───────────┬─────────────────────────────────────┘
                    │ for each 250-frame chunk:
                    ▼
        ┌─────────────────────────────────────────────────┐
        │  CHUNK SUBPROCESS  (fresh process tree)          │
        │  facefusion.py chunk-run <job_id>                │
        │  FACEFUSION_CHUNK_START=N FACEFUSION_CHUNK_END=M │
        │                                                  │
        │  conditional_process → image_to_video.process    │
        │      (env vars detected: skip setup/extract/     │
        │       merge/audio/finalize; run process_video    │
        │       on temp_frame_paths[N:M] only)             │
        │                                                  │
        │  ThreadPoolExecutor(execution_thread_count)      │
        │      ↓                                           │
        │  process_temp_frame() per frame:                 │
        │      face_detector → face_landmarker             │
        │      → face_recognizer → face_masker             │
        │      → processors[face_swapper, face_enhancer]   │
        │      → write_image (in place if successful)      │
        └─────────────────────────────────────────────────┘
                    │ subprocess exits
                    ▼
              parent observes return code:
              0 → next chunk;  ≠0 → retry once,
              then skip (originals stay on disk)
                    │
                    ▼ all chunks done
        ┌─────────────────────────────────────────────────┐
        │  parent: ffmpeg.merge_video (image2 demuxer)     │
        │       → ffmpeg.restore_audio                     │
        │       → finalize_video                           │
        └─────────────────────────────────────────────────┘
```

## Data Flow

1. **Launch** — operator runs `bash launch.command` (or double-clicks the .app bundle), which activates the conda env and starts `python facefusion.py run`.
2. **UI configuration** — operator selects target video, source face, processors, models in the Gradio dashboard. State writes into `state_manager` (per-app-context dict) and persists into a job file under `.jobs/`.
3. **Worker spawn** — operator clicks Start. `instant_runner.start()` calls `ui_subprocess.spawn_job_worker(job_id)`, which forks a `caffeinate -dimsu python facefusion.py job-run <id>` subprocess with `PYTHONUNBUFFERED=1` and `PYTHONFAULTHANDLER=1`. A daemon tail thread reads the worker's logfile and prefixes each line into the UI server's stdout.
4. **Parent worker pipeline** — `core.cli` → `route_job_runner` → `job_runner.run_job` → `process_step` (which sets `job_id` in state, then calls `conditional_process`) → `image_to_video.process` (for video targets). The parent runs `setup` (NSFW gate, temp dir prep) and `extract_frames` (ffmpeg dumps `%08d.jpg` frames into `.temp/`).
5. **Chunked frame processing** — `process_video` checks `chunk_size_frames`. If > 0 and the frame total exceeds it, dispatches to `chunk_runner.run_chunked` instead of running in-process. The chunk runner partitions frames into 250-frame ranges and spawns one subprocess per chunk via `chunk-run` CLI subcommand.
6. **Per-chunk inference** — chunk subprocess loads job state from `.jobs/`, applies the step args, applies `FACEFUSION_CHUNK_START/END` to gate `image_to_video.process` to slice-only mode, runs the per-frame ThreadPoolExecutor over its slice, exits cleanly. `process_temp_frame` reads each frame, runs the active processors (each with its own ONNX session), writes the result back in place. Failures are logged + skipped + retried once serially after the parallel pass; the original extracted frame remains on disk for permanently-failed frames.
7. **Merge** — once all chunks complete, the parent runs `ffmpeg.merge_video` (image2 demuxer, `%08d` pattern; indifferent to which frames were processed vs. left as originals) and `ffmpeg.restore_audio` (replaces or restores audio track).
8. **Finalize** — `finalize_video` clears temp frames and verifies the output file is a playable video.

## Directory Map

| Directory / file | Purpose |
|---|---|
| `facefusion.py` | CLI entry point; calls `conda.setup()` then `core.cli()`. |
| `facefusion/core.py` | argparse routing, `route_job_runner`, `process_chunk` (this fork's `chunk-run` handler), `process_step` (sets `job_id` into state, then `conditional_process`), `conditional_process` (dispatches image vs video pipeline). |
| `facefusion/program.py` | Full argparse surface; every config key is registered here as a CLI flag. |
| `facefusion/state_manager.py` | Per-app-context state dict (`cli`, `ui` contexts). All `state_manager.get_item('foo')` reads come from here. |
| `facefusion/exit_helper.py` | Four exit functions (`fatal_exit`, `hard_exit`, `signal_exit`, `graceful_exit`) instrumented with `[FACEFUSION.DIAG]` stack traces. `install_diagnostics()` registers signal probes (SIGTERM/HUP/ABRT/PIPE/USR1/USR2), atexit hook, and 10-s RSS heartbeat thread. Wired in from `core.cli`. |
| `facefusion/workflows/image_to_video.py` | Video pipeline: setup, extract_frames, process_video (with chunk dispatch + skip+retry), merge_frames, restore_audio, finalize_video. Reads `FACEFUSION_CHUNK_START/END` env vars to enter slice-only mode. |
| `facefusion/workflows/image_to_image.py` | Single-image pipeline. Per-processor try/except returns error code 1 on failure rather than crashing. |
| `facefusion/workflows/chunk_runner.py` *(new)* | Subprocess-chunking dispatcher. `_build_chunk_command`, `_spawn_chunk`, `_tail_log_to_stdout`, `run_chunked`. Caffeinate wrapping; per-chunk retry; failure-rate threshold. |
| `facefusion/processors/modules/*/core.py` | One directory per processor (10): `age_modifier`, `background_remover`, `deep_swapper`, `expression_restorer`, `face_debugger`, `face_editor`, `face_enhancer`, `face_swapper`, `frame_colorizer`, `frame_enhancer`, `lip_syncer`. Each exposes `create_static_model_set` (model catalog), `process_frame` (per-frame inference), `pre_process` / `post_process`, and `apply_args`. |
| `facefusion/{content_analyser,face_classifier,face_detector,face_landmarker,face_masker,face_recognizer,voice_extractor}.py` | Common modules shared by every workflow. Each has its own model catalog. |
| `facefusion/inference_manager.py` | ONNX Runtime session caching keyed by (model, providers). |
| `facefusion/uis/components/` (44 files) | Gradio UI controls. One file per logical control group; each binds a Gradio control to a `state_manager` key. `instant_runner.py`, `job_runner.py`, `job_manager.py` are the three operator workflows. |
| `facefusion/uis/ui_subprocess.py` *(new)* | Decoupled-UI worker spawner. Forks the worker with caffeinate + faulthandler env, tails its log into the server's stdout. |
| `facefusion/uis/core.py` / `facefusion/uis/layouts/` | Gradio app composition. |
| `facefusion/jobs/` | Job lifecycle (`job_manager.py`, `job_runner.py`, `job_helper.py`, `job_list.py`). Jobs are JSON files under `.jobs/<status>/<id>.json`. |
| `facefusion/ffmpeg.py` | ffmpeg subprocess invocation: extract_frames, merge_video, restore_audio. `log_failure()` surfaces ffmpeg stderr on non-zero exits. |
| `facefusion/audio.py` | Audio frame loading, voice frame extraction (called per-frame for lip_syncer). |
| `facefusion/face_analyser.py` | Combines detector + landmarker + recognizer + classifier into a `Face` record. |
| `facefusion/face_helper.py` | Geometric helpers: warp_face, paste_back, alignment templates. |
| `facefusion/temp_helper.py` | Temp-directory lifecycle and frame-path resolution (`%08d.jpg` pattern). |
| `facefusion/choices.py` | Enumerated UI choice lists and numeric ranges. |
| `facefusion/locales.py` | i18n strings; FaceFusion maintains an English `LOCALES` dict. |
| `facefusion/types.py` | TypedDicts and Literal types for state, jobs, args, etc. |
| `facefusion.ini` | Default config of record. Section per concern (paths, face_detector, face_selector, face_masker, frame_extraction, output_creation, processors, execution, memory, misc). |
| `tests/` | pytest suite (42 files) covering jobs, ffmpeg, vision, downloads, sanitization, state, etc. |
| `docs/` | This documentation directory. `MODELS_AND_SETTINGS.md` (catalog), `architecture.md` (this file), `file_tree.md` (sorted file list). |
| `.loop/` | Autonomous fix-and-retry loop pattern. `README.md` (template), `RUNS.md` (worked example). |
| `settings.md` | Narrative companion to `MODELS_AND_SETTINGS.md` — the why behind the why-not-defaults. |
| `WORKLOG.md` | Active workstreams + completed workstreams + session log. |
| `launch.command` / `Launch FaceFusion.app/` / `diagnose.command` | Operator scripts to start the UI server / open the .app bundle / diagnose state without remembering conda activation. |

## Key Abstractions

- **`state_manager`** — global per-app-context settings dict. `cli` and `ui` contexts; the UI mirrors writes to both. Every UI control writes here; every processor reads here. Single source of truth at runtime.
- **`processors`** (the master list) — an ordered list of processor module names. Each module exposes a uniform interface (`pre_process('output')`, `process_frame(payload)`, `post_process()`, `apply_args(args, set_item)`, `create_static_model_set('full')`). Adding a new processor is a matter of dropping a module in `facefusion/processors/modules/<name>/`.
- **Job** — a JSON file under `.jobs/<status>/<id>.json` with versioned schema, an array of steps, status (`drafted | queued | started | completed | failed`), and now a `worker_pid`. Jobs are the unit of work for `job-run` and the chunk subprocesses load step args from them via `job_manager.get_steps`.
- **Step args vs job args** — step args carry per-step parameters (target_path, source_paths, processors, model selections); job args carry execution-level parameters (execution_providers, execution_thread_count, video_memory_strategy, log_level). `process_step` merges them via `step_args.update(collect_job_args())`.
- **Chunk subprocess (this fork)** — a worker forked by `chunk_runner.run_chunked` to process a frame slice in isolation. Sees `FACEFUSION_CHUNK_START`/`END` env vars; loads the parent's job state; runs only `process_video()` on the slice; exits. Each chunk's death is independent — the parent advances to the next chunk regardless.
- **Diagnostic probes (this fork)** — `[FACEFUSION.DIAG]` (exit-path traces), `[FACEFUSION.SIGNAL]` (signal handler logs), `[FACEFUSION.ATEXIT]` (atexit hook), `[FACEFUSION.HEARTBEAT]` (10-s RSS pulse). Together they triangulate the kill mode of any worker that dies; absence of all four indicates SIGKILL or native `os._exit/abort`.

## External Interfaces

| Interface | Type | Purpose |
|---|---|---|
| `localhost:7860` | HTTP (Gradio) | Operator UI dashboard. Binds to localhost only. |
| `python facefusion.py run` | CLI subcommand | Launch the Gradio dashboard. |
| `python facefusion.py headless-run …` | CLI subcommand | Headless render with all step args on the command line. |
| `python facefusion.py batch-run …` | CLI subcommand | Render the cartesian product of source/target patterns. |
| `python facefusion.py job-run <id>` | CLI subcommand | Run a queued job (UI workers shell out to this). |
| `python facefusion.py chunk-run <id>` *(this fork)* | CLI subcommand | Run a single frame-range chunk for an in-progress job. Internal — used only by `chunk_runner`. |
| `python facefusion.py force-download` | CLI subcommand | Pre-fetch model weights for offline operation. |
| `python facefusion.py benchmark` | CLI subcommand | Run timed renders at fixed resolutions. |
| GitHub / Hugging Face | HTTPS | Model weight downloads (configurable via `download_providers`). |
| ffmpeg subprocess | local exec | Frame extract, merge, audio restore. Required dependency on `PATH`. |
| `caffeinate -dimsu` (macOS) | local exec | Wraps the worker to prevent system sleep mid-render. |

## Configuration

| File | Role |
|---|---|
| `facefusion.ini` | Default config of record. `chunk_size_frames = 250` is this fork's most important addition. |
| `~/.claude/plans/sorted-splashing-dewdrop.md` | The current/most-recent plan file (contents change per active task). |
| `~/.claude/skills/build-prompt/library/2026-04-28-facefusion-models-settings-reference.md` | The saved prompt that produced `MODELS_AND_SETTINGS.md`. |
| `.gitignore` | Excludes `.assets/`, `.temp/`, `.caches/`, `.jobs/`, `.omc/`, `.playwright-mcp/`, `.loop/logs/`, `output/*.mov`, `output/*.mp4`, `faces/`, `videos/`, `logs/`, `.DS_Store`, `__pycache__/`. |
| Env vars on worker | `PYTHONUNBUFFERED=1`, `PYTHONFAULTHANDLER=1`, `FACEFUSION_CHUNK_START`, `FACEFUSION_CHUNK_END`. |

## Maintenance Notes

- **NSFW analyser disabled.** `facefusion/content_analyser.py:analyse_frame` was patched to always return `False`. Acceptable for this personal-use fork; document in `settings.md`.
- **Subprocess chunking is the load-bearing change.** Without it, long renders die silently around 5-7%. The fork's resilience layer (skip + retry + diagnostic probes) catches Python-level failures but cannot catch native crashes; chunking makes those crashes survivable. Rollback: set `chunk_size_frames = 0`.
- **CoreML fp16→fp32 silent swaps.** `inswapper_128_fp16` and `real_esrgan_*_fp16` are auto-substituted to their fp32 siblings on macOS/CoreML inside `face_swapper/core.py:508-510` and `frame_enhancer/core.py:563-569`. Don't rely on the fp16 variant being used on this hardware.
- **Memory peak per chunk on M4 Max:** observed 87 GB on chunk-016 of the 14,500-frame render with `face_swapper + face_enhancer` and `execution_thread_count = 12`. Safe with 128 GB system RAM; tight if a third processor is added or thread count is bumped.
- **`.temp/` accumulates fast.** A 14,500-frame render produces 14,500 jpeg files (~5 GB). `.temp/` is gitignored; clear it manually (`rm -rf .temp/*`) when not actively rendering.
- **The autonomous loop pattern in `.loop/`** is task-agnostic. Reuse for any long-running CLI that may fail in unknown ways and require code edits between attempts.
- **Currently 11 unpushed commits** on master from the 2026-04-28 session: skip-on-error, retry, image graceful failure, diagnostic probes, WORKLOG, NSFW disable, UI subprocess decoupling, settings & loop docs, MODELS_AND_SETTINGS catalog. Push when reviewed.
