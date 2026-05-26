# FaceFusion settings — current configuration & rationale

This document captures the **non-default** settings on this fork plus the reasoning behind each choice. Read alongside `facefusion.ini`, which is the source of truth.

Also tracks code-level modifications that affect runtime behavior but aren't surfaced as config keys.

Last updated: **2026-05-26** after Codex takeover sync. Current config is Fix E from the flicker diagnosis: `inswapper_128_fp16` + CPU-only + no enhancer.

## CLI invocation pattern

```bash
python facefusion.py headless-run \
  --config-path facefusion.ini \
  --target-path "/path/to/video.mov" \
  --source-paths /path/to/face.jpeg \
  --output-path "/path/to/output.mov" \
  --processors face_swapper
```

Critical: **target and output extensions must match.** `.mov` → `.mov`, `.mp4` → `.mp4`. The processor `pre_process()` enforces this and exits with code 1 if violated.

## `[paths]`

| Key | Value | Why |
|-----|-------|-----|
| `output_path` | `/Users/jordanjones/Documents/facefusion/output` | Personal-machine path. Override per-run via `--output-path`. |

## `[face_detector]`

| Key | Value | Why |
|-----|-------|-----|
| `face_detector_angles` | `0 90 180 270` | Detect faces at all four cardinal rotations. Necessary for any video that includes head tilts, sideways/upside-down moments, or rotated cameras. Faster scan with just `0` but at the cost of missing detections. |

## `[face_selector]`

| Key | Value | Why |
|-----|-------|-----|
| `face_selector_mode` | `many` | Swap every detected face per frame, not just one tracked reference. Avoids the "no swap when reference embedding distance is too large" failure mode that broke the preview during reference-mode tuning. |
| `reference_face_distance` | `1.0` | Loosest threshold. With `many` mode this is largely a no-op, but it's the safe default if mode is later switched to `reference`. |

## `[face_masker]`

| Key | Value | Why |
|-----|-------|-----|
| `face_mask_types` | `box occlusion region` | Combine all three masks. Box gives a baseline rectangle, occlusion handles hands/glasses/mics in front of the face, region drops hairline/jaw to keep blends natural. Default is single-type and produces visible seams. |

## `[output_creation]`

| Key | Value | Why |
|-----|-------|-----|
| `output_video_preset` | `slow` | x264 `-preset slow`. ~2× the merge time but materially better quality for the same bitrate on multi-minute clips. The merge pass is fast (~2 min for 14.5k frames at ~120 frame/s) so the trade-off is favorable. |

## `[processors]`

| Key | Value | Why |
|-----|-------|-----|
| `processors` | `face_swapper` | Fix E keeps the enhancer off. The 30-s smoke showed this materially reduced identity flicker versus the run-03 `face_swapper face_enhancer` path. |
| `face_enhancer_model` | `gfpgan_1.4` | Configured but inactive unless `face_enhancer` is added back to `processors`. Retained for the planned E3 A/B smoke, not part of the current production default. |
| `face_enhancer_blend` | `80` | Configured but inactive for the current Fix E path. If E3 re-enables GFPGAN, this is the blend value to test first. |
| `face_swapper_model` | `inswapper_128_fp16` | Fix E stable-video baseline. In the 30-s smoke, it cut identity transitions from 72 to 25 and improved median cosine distance from 0.291 to 0.175. |
| `face_swapper_pixel_boost` | `512x512` | Process the swap at 512×512 even when the source face is smaller. Recovers detail that would otherwise be lost on close-ups. |

## `[execution]`

| Key | Value | Why |
|-----|-------|-----|
| `execution_providers` | `cpu` | Fix E disables CoreML to avoid the Apple Silicon/CoreML nondeterminism suspected in the flicker diagnosis. CoreML remains available for speed experiments but is not the current quality default. |
| `execution_thread_count` | `12` | High concurrency within a chunk. With chunking on, the failure blast radius is bounded to one chunk, so high thread count is safe and accelerates throughput. |
| `chunk_size_frames` | `250` | **Critical.** Frames are processed in 250-frame subprocess chunks (see `facefusion/workflows/chunk_runner.py`). Each chunk is a fresh process tree — model state, ONNX runtime, leaked semaphores all die with it. Set to `0` to disable chunking and revert to single-process. |

## `[memory]`

| Key | Value | Why |
|-----|-------|-----|
| `video_memory_strategy` | `tolerant` | Loosest memory budgeting. Chunking caps cumulative drift via the subprocess boundary, so within-chunk memory usage doesn't matter. With chunking off, drop to `moderate` or `strict`. |
| `system_memory_limit` | (unset) | No `RLIMIT_DATA` cap. The 128 GB physical RAM is plenty even for the 87 GB peak chunk RSS observed. |

## Code-level modifications (not in `facefusion.ini`)

These are persistent edits to the source tree that change runtime behavior. Reverting requires `git revert`.

### NSFW content_analyser disabled

`facefusion/content_analyser.py` modified so that `analyse_frame` always returns `False`. Done because the original analyser was overzealously flagging benign footage and aborting renders with error code 3.

Trade-off: no content gating. Acceptable for personal use where source material is hand-picked.

### Subprocess-decoupled UI worker

`facefusion/uis/ui_subprocess.py` (new, since 2026-04-27): the UI's "Start" button now spawns the actual render as a separate subprocess wrapped in `caffeinate -dimsu`, with `PYTHONUNBUFFERED=1` and `PYTHONFAULTHANDLER=1` in the environment. Worker stdout streams into the server terminal via a tail thread.

Why: the in-process worker shared its lifecycle with Gradio's HTTP server, and a worker death took the UI down with it.

### Diagnostic probes

`facefusion/exit_helper.py` registers signal handlers for SIGTERM/SIGHUP/SIGABRT/SIGPIPE/SIGUSR1/SIGUSR2 (logging then default action), an `atexit` hook, and a 10-s RSS heartbeat thread. All four exit functions log a stack trace as `[FACEFUSION.DIAG]`.

Why: silent worker deaths are now diagnosable. If a worker dies, exactly one of these prefixes will appear in stderr identifying the kill mode.

### Frame-level resilience

`facefusion/workflows/image_to_video.py`:
- Per-frame failures are logged + skipped (the original frame remains on disk).
- After the parallel pass, failed frames get one serial retry.
- If failure rate exceeds 50%, the run aborts with error code 1 (constant: `FRAME_FAILURE_ABORT_THRESHOLD`).

`facefusion/workflows/image_to_image.py`: per-processor try/except returns error code 1 on a processor failure instead of letting the unhandled exception crash the worker.

### Subprocess chunking

New CLI subcommand `chunk-run` (in `facefusion/program.py` + `facefusion/core.py`). Invoked by `facefusion/workflows/chunk_runner.py` as `chunk-run <job_id> <step_index>` to dispatch the parallel frame-processing pass into 250-frame subprocess chunks. Each chunk subprocess receives `FACEFUSION_CHUNK_START` and `FACEFUSION_CHUNK_END` env vars that gate `image_to_video.process()` to run only the slice and skip setup/extract/merge/audio/finalize (those stay in the parent).

Why: see the `RUNS.md` writeup of the silent worker death, frames 778 and 1026, and the chunked-architecture rationale in `~/.claude/plans/sorted-splashing-dewdrop.md` (one-shot subprocess chunking plan).

## What to change for different scenarios

| Scenario | Adjust |
|----------|--------|
| Short clips (< 250 frames) | `chunk_size_frames = 0` to skip subprocess overhead |
| Different camera orientation | `face_detector_angles` — drop unused rotations to speed up |
| Quality over speed | keep Fix E first; then optionally A/B `face_enhancer` back on and bump `output_video_preset` to `slower` |
| Speed over quality | re-enable `coreml cpu` only after accepting the higher flicker risk; reduce `pixel_boost` to `256x256` |
| Model RAM blowing up | reduce `execution_thread_count` to 4-6, set `video_memory_strategy = moderate` |
| Different face per scene | switch `face_selector_mode` to `reference` and tighten `reference_face_distance` |

## Verifying current settings load correctly

```bash
source /opt/anaconda3/etc/profile.d/conda.sh && conda activate facefusion
python facefusion.py headless-run --help | grep -E "chunk-size|execution-thread|face-swapper-model"
```

Should show all three flags with their `facefusion.ini` defaults.
