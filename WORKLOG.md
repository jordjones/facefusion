# FaceFusion Worklog

Last updated: 2026-04-28

## Active Projects

### Frame-tolerant video processing
- **Goal:** A single bad frame produces one unmodified frame in the output video, not an aborted render. Transient failures get one serial retry.
- **Status:** `testing` — skip-on-error + serial retry shipped; same loop now also runs inside each chunk subprocess slice.
- **Context:** Implementation closed today. Awaiting end-to-end verification (synthetic failure injection + real long render).
- **Files:** `facefusion/workflows/image_to_video.py`
- **Plans:** `~/.claude/plans/frame-resilience-followups.md`
- **Last session:** 2026-04-28
- **Next:** Run synthetic-failure repro, then real long render.

### Image-to-image graceful failure
- **Goal:** A processor exception during single-image swap returns a clean error code instead of crashing the worker.
- **Status:** `testing` — try/except wrapping the per-processor loop is shipped.
- **Context:** Implementation closed today. Verification deferred — needs a deliberate processor failure to confirm the worker exits cleanly with code 1 instead of an unhandled traceback.
- **Files:** `facefusion/workflows/image_to_image.py`
- **Plan:** `~/.claude/plans/frame-resilience-followups.md` §C
- **Last session:** 2026-04-28
- **Next:** Inject a synthetic raise in one processor and run a single-image swap from the UI.

#### Findings
- Per-frame skip is safe: `process_temp_frame` only writes the temp frame on success (`image_to_video.py:193`), so a raised exception leaves the original extracted frame on disk. ffmpeg's `image2` demuxer (`ffmpeg.py:243`) merges whatever sequential frames exist — skipped frames appear unmodified in the output.
- Failure-rate guard: aborts the run with error code 1 if more than 50% of frames fail (constant `FRAME_FAILURE_ABORT_THRESHOLD` in `image_to_video.py`), so a fundamentally broken config doesn't silently produce a useless video.

### Silent worker death — subprocess chunking
- **Goal:** Survive whatever is killing the worker mid-render (variable frame, ~5-7%) by isolating frame processing into bounded-lifetime subprocesses. Each chunk gets a fresh process tree; any single death loses ~250 frames, not the whole render.
- **Status:** `testing` — full subprocess-chunking architecture implemented and committed end-to-end. Smoke tests pass (imports, CLI registration, env-var parsing, subprocess command shape).
- **Context:** Built autonomously this session: new `chunk-run` subcommand, new `chunk_runner.py` module, env-var-gated slice processing in `image_to_video.process()`, `chunk_size_frames = 250` default in `facefusion.ini`. Five smoke tests pass. Real long-render verification not yet done.
- **Files:** `facefusion/workflows/chunk_runner.py` (new), `facefusion/workflows/image_to_video.py`, `facefusion/core.py`, `facefusion/program.py`, `facefusion/args.py`, `facefusion/types.py`, `facefusion.ini`, `facefusion/exit_helper.py`
- **Plan:** `~/.claude/plans/sorted-splashing-dewdrop.md`
- **Last session:** 2026-04-28
- **Next:** Relaunch UI server in a fresh terminal. Run the 14,557-frame render. Confirm chunks complete sequentially (`chunk_runner_chunk_completed: chunk=N range=[..,..)` lines). On any chunk death, parent retries once and skips on second failure. Final video should play end to end with at most a handful of unmodified-frame regions.
- **Rollback:** `chunk_size_frames = 0` in `facefusion.ini` reverts to single-process behavior.

#### Findings
- Two reproductions (frames 1026 and 778) confirmed worker dies via path that bypasses our four `exit_helper` paths, the skip+retry layer, faulthandler, and Python tracebacks. Only artifact is `multiprocessing.resource_tracker` warning emitted by the orphaned daemon child after the parent dies — consistent with SIGKILL or native `os._exit()`/`abort()` in a C extension (CoreML provider in onnxruntime suspected).
- 76 GB free of 128 GB RAM and empty `log show` for jetsam/memorystatus rules out macOS Jetsam OOM.
- Architecture: parent worker still owns setup/extract/merge/audio/finalize. Frame processing delegates to 250-frame subprocess chunks via new `chunk-run` CLI command. Each chunk subprocess sets `FACEFUSION_CHUNK_START`/`FACEFUSION_CHUNK_END` env vars that gate `image_to_video.process()` to run only `process_video()` on the slice. `process_temp_frame()` writes in place only on success, so failed chunks leave original extracted frames on disk — ffmpeg's `image2` demuxer merges whatever sequential frames exist.
- Diagnostic probes (`[FACEFUSION.HEARTBEAT]`, `[FACEFUSION.SIGNAL]`, `[FACEFUSION.ATEXIT]`, `[FACEFUSION.DIAG]`) propagate into each chunk subprocess via `core.cli()` — invaluable if a chunk also dies, since the kill mode will be visible per chunk.

## Completed Workstreams

(none yet)

## Parked

(none)

## Session Log

### 2026-04-28
- Shipped resilience layer: skip-on-error + serial retry in video, graceful processor failure in image, diagnostic probes (signal/atexit/heartbeat) in exit_helper wired through core.cli.
- Two repros (frames 1026 then 778) confirmed silent worker death bypasses every Python-level instrumentation (no diag, no signal log, no atexit, no traceback). 76 GB free RAM ruled out Jetsam. Most likely SIGKILL or a native abort/_exit in the CoreML provider.
- Built subprocess chunking end to end: new `chunk-run` CLI subcommand, new `chunk_runner.py` workflow, env-var-gated slice path in `image_to_video.process()`, `chunk_size_frames = 250` default. Rollback knob = 0. Six commits on master, not pushed.

### 2026-04-27
- Investigated silent worker death at 7%. Added `[FACEFUSION.DIAG]` stack-trace logging to all four exit paths in `exit_helper.py` and wrapped `future.result()` in `image_to_video.py` (note: the wrap was later replaced with skip-on-error logic — the abandon behavior it added is what motivated the new workstream).
- Earlier in session: subprocess-decoupled UI worker, caffeinate wrapper, real-time tail-thread for worker logs into server stdout.
