# FaceFusion Worklog

Last updated: 2026-04-28 (post-loop, post-docs)

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

## Completed Workstreams

### Silent worker death — subprocess chunking
- **Goal:** Survive whatever is killing the worker mid-render (variable frame, ~5-7%) by isolating frame processing into bounded-lifetime subprocesses.
- **Status:** `complete` — validated end-to-end on the 14,500-frame render that previously failed.
- **Outcome:** 3 h 27 min wall time, 0 chunk failures, 0 frame failures, 0 retries triggered. Output: `output/My-Movie-1-faceswap-shan-run-03.mov` (578 MB, 8m05s, valid h264/aac MOV at 89% of input size). Cleanly passed both prior crash points (frames 778 and 1026) within minutes of starting.
- **Files:** `facefusion/workflows/chunk_runner.py` (new), `facefusion/workflows/image_to_video.py`, `facefusion/core.py`, `facefusion/program.py`, `facefusion/args.py`, `facefusion/types.py`, `facefusion.ini`, `facefusion/exit_helper.py`
- **Plan:** `~/.claude/plans/sorted-splashing-dewdrop.md`
- **Run log:** `.loop/RUNS.md` (3 attempts: extension-mismatch fix → job_id propagation fix → success).
- **Rollback:** `chunk_size_frames = 0` in `facefusion.ini` reverts to single-process behavior.

#### Findings
- Two reproductions (frames 1026 and 778) confirmed worker dies via path that bypasses every Python-level instrumentation (no `[FACEFUSION.DIAG]`, no signal log, no atexit, no traceback). Only artifact is `multiprocessing.resource_tracker` warning from the orphaned daemon child — consistent with SIGKILL or native `os._exit()`/`abort()` in a C extension (CoreML provider in onnxruntime suspected). 76 GB free of 128 GB RAM and empty `log show` for jetsam/memorystatus ruled out macOS Jetsam OOM.
- Chunking made root cause irrelevant. Parent worker held 2.09 GB RSS steady for the entire 3.5 h run; chunk subprocesses swung 20-87 GB each and were fully released on exit. Peak 87 GB on chunk-016 — well below 128 GB ceiling.
- Architecture: parent owns setup/extract/merge/audio/finalize. Frame processing delegates to 250-frame subprocess chunks via the new `chunk-run` CLI subcommand. Each chunk subprocess sets `FACEFUSION_CHUNK_START`/`FACEFUSION_CHUNK_END` env vars that gate `image_to_video.process()` to run only `process_video()` on the slice. Failed chunks leave original extracted frames on disk; ffmpeg's `image2` demuxer merges whatever sequential frames exist.
- Diagnostic probes propagate into each chunk subprocess via `core.cli()` — invaluable if a chunk also dies, since the kill mode is visible per chunk.

### Personal-fork documentation suite
- **Goal:** Capture this fork's settings, the autonomous fix-and-retry loop pattern, a comprehensive models-and-settings reference catalog, and a system-level architecture overview so a returning operator can quickly orient and prioritize.
- **Status:** `complete` — five deliverables shipped.
- **Outcome:**
  - `settings.md` — narrative explanation of every non-default key in `facefusion.ini` plus the code-level modifications (NSFW disable, UI subprocess decoupling, diagnostic probes, frame-level resilience, subprocess chunking) not surfaced as config.
  - `.loop/README.md` + `.loop/RUNS.md` + `.loop/forensics/` — task-agnostic autonomous loop pattern preserved as a reusable template, with the FaceFusion render serving as the worked example.
  - `docs/MODELS_AND_SETTINGS.md` — 7,564-word reference catalog covering 176 model entries across 17 modules and 186 UI controls across 44 component files. Includes a quick-reference matrix, master/dependent dependency map, and three prioritization tables.
  - `docs/architecture.md` — 18.9 KB system-level overview: ASCII pipeline diagram (operator-click → Gradio UI → ui_subprocess → parent worker → chunk_runner → per-chunk subprocess → ffmpeg merge), eight-step data flow, full directory map, key abstractions, external interfaces, configuration sources, maintenance notes.
  - `docs/file_tree.md` — sorted listing of 247 source files with project-specific exclusions (cache dirs, render outputs, model assets, personal data dirs).
- **Files:** `settings.md`, `.loop/README.md`, `.loop/RUNS.md`, `.loop/forensics/run-01/run.log`, `docs/MODELS_AND_SETTINGS.md`, `docs/architecture.md`, `docs/file_tree.md`, `.gitignore` (output and tooling-state exclusions)
- **Plans:** `~/.claude/plans/sorted-splashing-dewdrop.md` (chunking + prompt-built catalog)
- **Last session:** 2026-04-28

## Parked

(none)

## Session Log

### 2026-04-28
- Shipped resilience layer: skip-on-error + serial retry in video, graceful processor failure in image, diagnostic probes (signal/atexit/heartbeat) in exit_helper wired through core.cli.
- Two repros (frames 1026 then 778) confirmed silent worker death bypasses every Python-level instrumentation (no diag, no signal log, no atexit, no traceback). 76 GB free RAM ruled out Jetsam. Most likely SIGKILL or a native abort/_exit in the CoreML provider.
- Built subprocess chunking end to end: new `chunk-run` CLI subcommand, new `chunk_runner.py` workflow, env-var-gated slice path in `image_to_video.process()`, `chunk_size_frames = 250` default. Rollback knob = 0.
- Drove the autonomous fix-and-retry loop (Run 01-03) to first success. Run 01: extension mismatch. Run 02: chunking dispatch silently bypassed because `state_manager.get_item('job_id')` was None for headless-run — fixed via 1-line edit in `process_step` (commit `810aca7`). Run 03: 3 h 27 min, zero failures, valid 578 MB output video.
- Shipped documentation suite: `settings.md`, `.loop/README.md` (autonomous loop pattern), `docs/MODELS_AND_SETTINGS.md` (176 models, 186 UI controls catalog), then via `/doc-project` added `docs/architecture.md` (system pipeline + directory map + maintenance notes, 18.9 KB) and `docs/file_tree.md` (247 source files).
- Total commits this session: 14 on master, none pushed.

### 2026-04-27
- Investigated silent worker death at 7%. Added `[FACEFUSION.DIAG]` stack-trace logging to all four exit paths in `exit_helper.py` and wrapped `future.result()` in `image_to_video.py` (note: the wrap was later replaced with skip-on-error logic — the abandon behavior it added is what motivated the new workstream).
- Earlier in session: subprocess-decoupled UI worker, caffeinate wrapper, real-time tail-thread for worker logs into server stdout.
