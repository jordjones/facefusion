# FaceFusion Worklog

Last updated: 2026-04-28

## Active Projects

### Frame-tolerant video processing
- **Goal:** A single bad frame produces one unmodified frame in the output video, not an aborted render. Transient failures get one serial retry.
- **Status:** Implemented (skip-on-error + serial retry). Awaiting verification with synthetic failure injection.
- **Files:** `facefusion/workflows/image_to_video.py`
- **Plans:** `~/.claude/plans/sorted-splashing-dewdrop.md`, `~/.claude/plans/frame-resilience-followups.md`
- **Last session:** 2026-04-28
- **Next:** Run synthetic-failure repro (see plan §Verification), then real long render.

### Image-to-image graceful failure
- **Goal:** A processor exception during single-image swap returns a clean error code instead of crashing the worker.
- **Status:** Implemented.
- **Files:** `facefusion/workflows/image_to_image.py`
- **Plan:** `~/.claude/plans/frame-resilience-followups.md` §C
- **Last session:** 2026-04-28
- **Next:** Verify by triggering a deliberate processor failure on an image swap.

#### Findings
- Per-frame skip is safe: `process_temp_frame` only writes the temp frame on success (`image_to_video.py:193`), so a raised exception leaves the original extracted frame on disk. ffmpeg's `image2` demuxer (`ffmpeg.py:243`) merges whatever sequential frames exist — skipped frames appear unmodified in the output.
- Failure-rate guard: aborts the run with error code 1 if more than 50% of frames fail (constant `FRAME_FAILURE_ABORT_THRESHOLD` in `image_to_video.py`), so a fundamentally broken config doesn't silently produce a useless video.

### Silent worker death (paused)
- **Goal:** Identify and survive the native-level termination that kills the worker around frame 1026/14557.
- **Status:** Diagnostics installed; awaiting reproduction with new logging.
- **Files:** `facefusion/exit_helper.py`, `facefusion/workflows/image_to_video.py`
- **Last session:** 2026-04-27
- **Next:** Reproduce the long render with diagnostics live. If `[FACEFUSION.DIAG]` appears in the terminal at termination, the call stack identifies the exit path. If no `[FACEFUSION.DIAG]` line appears, that confirms native-level termination (segfault/OOM/GPU driver) and we plan subprocess-chunk isolation.

#### Findings
- Symptom: `resource_tracker` semaphore-leak warning at frame 1026, then worker dies. Exit code is 0 from FaceFusion's exit paths (signal-based exits all return 0), which explains the absence of error logs.
- Three exit functions exist in `exit_helper.py`: `fatal_exit` (os._exit), `hard_exit` (sys.exit), `graceful_exit` (stops processes, waits, cleans temp, hard_exit). All four (incl. `signal_exit`) now log `[FACEFUSION.DIAG] <fn>(<args>)` + full stack via `traceback.format_stack()` to stderr.
- Skip-on-error from the other workstream protects against Python exceptions but cannot catch a native crash. The two workstreams are independent.

## Completed Workstreams

(none yet)

## Parked

(none)

## Session Log

### 2026-04-28
- Implemented frame-tolerant video processing. Replaced the abandon-on-error block in `process_video()` with skip-and-continue + failure-rate guard. Created this WORKLOG.md.

### 2026-04-27
- Investigated silent worker death at 7%. Added `[FACEFUSION.DIAG]` stack-trace logging to all four exit paths in `exit_helper.py` and wrapped `future.result()` in `image_to_video.py` (note: the wrap was later replaced with skip-on-error logic — the abandon behavior it added is what motivated the new workstream).
- Earlier in session: subprocess-decoupled UI worker, caffeinate wrapper, real-time tail-thread for worker logs into server stdout.
