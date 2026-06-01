# FaceFusion Worklog

Last updated: 2026-05-31 (Run 04 quality review)

## Ongoing Workstreams

### Face-swap output quality
- **Goal:** Every face-swap render meets the per-frame identity-stability bar — the swapped identity stays locked across frames, sub-second flicker minimized, source-identity tightness maintained.
- **Status:** `ongoing`
- **Scoreboard** (frames 1800-2700, ref-matched eval; Fix E smoke was stride 2, Run 04 review is stride 1):

| Metric | Baseline (run-03) | Target | Fix E smoke | Run 04 strict review |
|---|---:|---:|---:|---:|
| State transitions (shan/other/no-face) | 72 | <30 | 25 | 37 |
| Shan share of detected frames | 64.7% | >90% | 92.3% | 91.1% |
| Mean shan-run length | 0.43 s | >2 s | 2.14 s | 1.72 s |
| Max "other"-run length | 1.33 s | <0.5 s | 0.33 s | 0.50 s |
| Median cosine distance to source | 0.291 | <0.20 | 0.175 | 0.1718 |

- **Context:** Diagnosed run-03's flicker as a combination of `hyperswap_1c_256` (community-reported instability), CoreML FP16 non-determinism on Apple Silicon, and GFPGAN's lack of temporal smoothing. Fix E (`inswapper_128_fp16` + CPU-only + no enhancer) cleared all four targets in a 30-s smoke. Run 04 was ultimately completed by full rerun job `headless-2026-05-27-18-33-04`; a separate agent session then kept printing PreToolUse hook messages after FaceFusion had already exited.
- **Run 04 final state:** Final output exists at `output/My-Movie-1-faceswap-shan-run-04.mov` (536 MB, mtime 2026-05-28 03:42). The render log `logs/run04-full-rerun-20260527-183249.log` shows 59/59 chunks completed, one all-chunks summary, `processing to video succeeded`, `hard_exit(0)`, and zero failure markers. `.jobs/completed/headless-2026-05-27-18-33-04.json` has its single step marked `completed`.
- **Loop diagnosis:** The perpetual terminal activity was stale Codex/Claude tool-hook output after completion, not active video processing. Current verification found no `facefusion.py`, `ffmpeg`, `evaluate_swap.py`, or Run 04 worker process. A stale Codex process in the FaceFusion cwd was observed but not killed.
- **Temp-frame note:** The old chunk-41 recovery instructions are obsolete for Run 04 because the final MOV has been finalized. Preserve logs/output for provenance; no current resume signal or recovery command is needed.
- **Eval tool:** `tools/evaluate_swap.py` — per-frame ArcFace cosine-distance evaluator with `--ref-match`, `--start-frame`/`--end-frame`/`--stride` flags. Reusable against any future render to score against the scoreboard.
- **Settings registry:** `settings/2026-05-27-run-04-fix-e-known-good.md` and `settings/2026-05-27-run-04-fix-e.ini` preserve the improved Run 04/Fix E baseline. `settings/2026-05-31-run-04-quality-review.md` records the latest review and next smoke-test candidates.
- **Files:** `tools/evaluate_swap.py`, `tools/recover_run04.py`, `facefusion.ini` (Fix E values), `settings/README.md`, `settings/2026-05-27-run-04-fix-e-known-good.md`, `settings/2026-05-27-run-04-fix-e.ini`, `settings/2026-05-31-run-04-quality-review.md`, `docs/run-04-handoff.md`, `.jobs/completed/headless-2026-05-27-18-33-04.json`, `logs/run04-full-rerun-20260527-183249.log`, `logs/job-20260527-184155-headless-2026-05-27-18-33-04-chunk-000-00000000-00000250.log` through `logs/job-20260528-033749-headless-2026-05-27-18-33-04-chunk-058-00014500-00014557.log`, `output/My-Movie-1-faceswap-shan-run-04.mov`, `output/eval-run-03-window-1800-2700.csv` (baseline), `output/eval-fixE-smoke.csv` (target met), `output/eval-input-window-1800-2700.csv` (input ceiling reference), `output/eval-run-04-window-1800-2700.csv`, `output/eval-run-04-full-sample-500.csv`, `videos/My-Movie-1-input-window-1800-2700.mov` (input clip for visual reference)
- **Validation:** `ffprobe` reports a valid MOV with H.264 video (1280x720, 30 fps, 14,557 frames, 485.233s) and AAC audio (485.257s). `ffmpeg -v error` decode smoke passed for the first video frame and first second of audio. Bounded evaluator smoke on frames 1800-2700, stride 2, source-match selector sampled 451 frames, detected 308, and reported median cosine distance `0.1706` with 92.2% of detected frames below 0.4. Full stride-1 review on frames 1800-2700 sampled 901 frames, detected 621, median cosine distance `0.1718`, 91.1% under 0.4, 37 state transitions, and mean source-identity run length `1.72 s`. Full-video 500-frame sample detected 330 frames, median cosine distance `0.2070`, and 84.8% under 0.4. Targeted visual review found the weakest frames cluster around profile/downward poses, occlusion, frame-edge partial faces, and false-positive low-quality detections. Git status was clean before quality-review artifacts.
- **Plan:** `~/.claude/plans/sunny-foraging-bengio.md`
- **Last session:** 2026-05-31
- **Next:** Run a bounded smoke from the Run 04 baseline with `face_landmarker_score = 0.60` as a landmark-refinement threshold, not a no-swap gate; compare metrics and visual contact sheets before promoting it to the next full render. If source photos are available, also test a multi-source identity set covering frontal, three-quarter, profile, and downward-looking poses.

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

### 2026-05-31
- Added `settings/` as the durable settings registry for configs that have actually been tried.
- Recorded Run 04/Fix E as the current known-good improved baseline, with a human-readable run record plus a reusable `.ini` snapshot.
- Linked the registry from `settings.md` and this workstream so future config iterations start from the preserved Run 04 baseline.
- Reviewed the completed Run 04 MOV with a stride-1 scoreboard pass and a 500-frame full-video sample; saved evaluator outputs under `output/eval-run-04-*`.
- Added `settings/2026-05-31-run-04-quality-review.md` with next smoke candidates. Run 04 is improved but not closed under the stricter pass; next bounded test is `face_landmarker_score = 0.60` as a landmark-refinement threshold.
- Committed `fc8b79a` for the quality review and tried to push `master` to `origin/master`; GitHub returned 403 because `origin` points at `facefusion/facefusion.git` and the current authenticated user does not have push permission.
- Handoff complete locally; remote publish still needs either a writable fork or upstream access.

### 2026-05-30
- Handoff for the completed Run 04 production render and the prior terminal session that entered a PreToolUse hook loop after completion.
- Verified the final MOV at `output/My-Movie-1-faceswap-shan-run-04.mov`: file exists, job record is completed, 59/59 chunks completed, no failure markers, `processing to video succeeded`, valid video/audio streams, decode smoke passed, and no active FaceFusion/ffmpeg/evaluator PIDs remained.
- Confirmed the terminal loop was stale agent/tool-hook activity rather than video processing. A stale Codex process in `/Users/jordanjones/Documents/facefusion` was observed but not killed.
- Bounded quality smoke on frames 1800-2700, stride 2, ref-match selector produced median cosine distance `0.1706`; this does not update the scoreboard transition/run-length metrics.
- Next: visually inspect the MOV; if accepted, close or park Run 04, otherwise run a full scoreboard-compatible evaluator pass before another render.

### 2026-05-27
- Corrected the Run 04 handoff path to the actual macOS temp root `/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T`, added `tools/recover_run04.py`, and committed the recovery helper (`42cc430`, `57ba9a9`).
- Resumed Run 04 from chunk `015`, then executed bounded recovery runs through chunk `040` at the user's updated stop boundary. Chunk `026` had one interrupted partial log from a terminated open-ended wrapper; the complete proof log is `logs/job-20260527-062922-headless-2026-05-26-18-59-40-chunk-026-00006500-00006750.log`.
- Verified chunks `000` through `040` have successful completion logs with `hard_exit(0)` and `ATEXIT`, verified the actual temp directory still contains exactly 14,557 PNG frames, verified no FaceFusion/recovery PIDs remain, and verified the next dry-run target is chunk `041` (`[10250,10500)`).
- Handoff target is now chunk `041`. Run `source /opt/anaconda3/etc/profile.d/conda.sh && conda activate facefusion && python tools/recover_run04.py --start-chunk 41` to process chunks `041` through `058` and finalize the Run 04 MOV.

### 2026-05-26
- Took over the Claude-era FaceFusion state, committed evaluator/docs/chunk-run fixes, and launched Run 04 with Fix E (`inswapper_128_fp16`, CPU provider, face swapper only) against `videos/My Movie 1.mov`.
- Run 04 job id: `headless-2026-05-26-18-59-40`; output target: `output/My-Movie-1-faceswap-shan-run-04.mov`; chunk size: `250`; total frames logged by the run: `14557`; total chunks expected: `59`.
- User intentionally requested a future-session pause after chunk 20 started. Monitoring instead found that parent PID `74022` disappeared before chunk 20 and after chunk 14 completed; no FaceFusion or chunk subprocess remained by verification time.
- Confirmed chunk logs `000` through `014` exist and end with normal `hard_exit(0)`/`ATEXIT` diagnostics. Confirmed no chunk `015` or chunk `020` log exists.
- Handoff target is now chunk `15`, code-offset range `[3750,4000)`. Preserve `/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1/` and avoid any fresh run path that clears target temp frames before the recovery path is chosen.

### 2026-04-28
- Shipped resilience layer: skip-on-error + serial retry in video, graceful processor failure in image, diagnostic probes (signal/atexit/heartbeat) in exit_helper wired through core.cli.
- Two repros (frames 1026 then 778) confirmed silent worker death bypasses every Python-level instrumentation (no diag, no signal log, no atexit, no traceback). 76 GB free RAM ruled out Jetsam. Most likely SIGKILL or a native abort/_exit in the CoreML provider.
- Built subprocess chunking end to end: new `chunk-run` CLI subcommand, new `chunk_runner.py` workflow, env-var-gated slice path in `image_to_video.process()`, `chunk_size_frames = 250` default. Rollback knob = 0.
- Drove the autonomous fix-and-retry loop (Run 01-03) to first success. Run 01: extension mismatch. Run 02: chunking dispatch silently bypassed because `state_manager.get_item('job_id')` was None for headless-run — fixed via 1-line edit in `process_step` (commit `810aca7`). Run 03: 3 h 27 min, zero failures, valid 578 MB output video.
- Shipped documentation suite: `settings.md`, `.loop/README.md` (autonomous loop pattern), `docs/MODELS_AND_SETTINGS.md` (176 models, 186 UI controls catalog), then via `/doc-project` added `docs/architecture.md` (system pipeline + directory map + maintenance notes, 18.9 KB) and `docs/file_tree.md` (247 source files).
- Total commits this session: 14 on master, none pushed.
- **Later session — flicker diagnosis (Ongoing: Face-swap output quality):** Built `tools/evaluate_swap.py` (per-frame ArcFace cosine-distance evaluator, ref-match + windowed-stride flags). Quantified user-reported flicker on run-03 — 30-s window showed 72 state transitions, 35% of detected frames as non-shan identity, mean shan-run only 0.43 s.
- Tested four configs: Fix A+B (reference-mode selector + lower detector floor) → no improvement, attribution proved selector wasn't the lever. Fix D (drop GFPGAN) → marginal median tightening only, GFPGAN was sweetening but not the dominant cause. **Fix E (inswapper_128_fp16 + CPU-only + no enhancer)** → 65% reduction in transitions, 92.3% shan share, mean shan-run 2.14 s. All four scoreboard targets met on the smoke.
- Three parallel investigations (codebase trace of `balance_source_embedding`, ini settings audit, web research) converged on the same picture: hyperswap_1c is documented unstable for video, CoreML FP16 fallback is non-deterministic on Apple Silicon, GFPGAN has no temporal smoothing.
- Re-baselined the input video itself — 30.8% of frames have no face in the original (cuts, b-roll, hands), so the "33% no-face" figure I'd been treating as a flaw was actually the natural ceiling. Detection was never the problem.
- Full Run 04 rerender deferred per user (compute reserved). Repo HEAD on Fix E config (commit `ced0e3b`). Plan at `~/.claude/plans/sunny-foraging-bengio.md` covers Step 6 A/B isolation if desired before production.

### 2026-04-27
- Investigated silent worker death at 7%. Added `[FACEFUSION.DIAG]` stack-trace logging to all four exit paths in `exit_helper.py` and wrapped `future.result()` in `image_to_video.py` (note: the wrap was later replaced with skip-on-error logic — the abandon behavior it added is what motivated the new workstream).
- Earlier in session: subprocess-decoupled UI worker, caffeinate wrapper, real-time tail-thread for worker logs into server stdout.
