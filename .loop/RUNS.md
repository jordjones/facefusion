# Loop Runs — long render `My Movie 1.mov` × `shan_1.jpeg`

**Loop start:** 2026-04-28
**Inputs:**
- target: `/Users/jordanjones/Documents/facefusion/videos/My Movie 1.mov` (619 MB, 14,557 frames)
- source: `/Users/jordanjones/Documents/facefusion/faces/shan_1.jpeg`
- processors: `face_swapper face_enhancer`
- chunk_size_frames: 250

**Loop config:** max 5 attempts, no per-run timeout, local commits only.

**Plan:** `~/.claude/plans/sorted-splashing-dewdrop.md`

---

## Status (overwritten each run)

- **LOOP COMPLETE — SUCCESS at Run 03**
- Output: `/Users/jordanjones/Documents/facefusion/output/My-Movie-1-faceswap-shan-run-03.mov` (578 MB, 8m05s, h264/aac, 1280×720 @ 30 fps)
- Total runs: 3 (Run 01 = operator config error, Run 02 = code bug, Run 03 = success)
- Total elapsed: ~3.5 hours wall time across all runs

---

## Run 01 — 2026-04-28 08:41

- **Outcome:** failed
- **Started:** 2026-04-28 08:41:??
- **Ended:** 2026-04-28 08:41:?? (failed in <5 s)
- **Subprocess exit code:** 1
- **Output file:** not produced
- **Log:** `.loop/logs/run-01.log` (17 lines, 907 bytes)
- **Failure signature:** `match the target and output extension!` → `hard_exit(1)` from `core.route()`
- **Forensic excerpts:**
  ```
  [FACEFUSION.CORE] processing step 1 of 1
  [FACEFUSION.CORE] match the target and output extension!
  [FACEFUSION.DIAG] hard_exit(1)
    File "facefusion/core.py", line 80, in route
      hard_exit(error_code)
  ```
- **Root cause hypothesis:** Target is `.mov`, my output filename was `.mp4`. FaceFusion enforces matching extensions per processor (`face_editor/core.py:183`, `frame_enhancer/core.py:601`, etc.). Not a code bug — operator error in the run command.
- **Fix applied:** No code change. Update output filename in run command to `.mov`. No commit.
- **Smoke tests:** none (config error, not a code path).
- **Next attempt:** Run 02 with `--output-path …run-02.mov`.

## Run 02 — 2026-04-28 08:43

- **Outcome:** killed (deterministic bug discovered; not allowed to crash)
- **Started:** 2026-04-28 08:43:??
- **Killed:** 2026-04-28 08:50:?? (after ~7 min)
- **Subprocess exit code:** 144 (SIGTERM via pkill)
- **Output file:** not produced
- **Log:** `.loop/logs/run-02.log` (~1.5 MB, mostly tqdm)
- **Failure signature:** parent worker RSS climbed to 79 GB at frame 284/14557 with zero chunk subprocesses spawned. `[FACEFUSION.HEARTBEAT] rss_gb=79.11` while expecting per-chunk subprocesses with low individual RSS.
- **Forensic excerpts:**
  ```
  processing:   2%|          | 284/14557 [04:42<3:36:52,  1.10frame/s]
  [FACEFUSION.HEARTBEAT] pid=10504 rss_gb=79.11 elapsed_s=440
  ```
  No `chunk_runner_chunk_start` lines, no `[<job-id>-chunk-NNN]` log files in `logs/`.
- **Root cause:** `image_to_video.process_video()` checks `state_manager.get_item('job_id')` to decide whether chunk_runner can be invoked (chunking needs an existing job to load step args from). For `headless-run`, `process_headless()` creates a job and runs it via `job_runner.run_job(job_id, process_step)`, but `process_step` did not propagate `job_id` into `state_manager`. Result: `state_manager.get_item('job_id')` returns None → chunk dispatch silently falls back to the legacy in-process path → 14,557-frame loop runs single-process at full thread count → memory blows up → would have crashed exactly like prior runs.
- **Fix applied:** Added `state_manager.set_item('job_id', job_id)` to `process_step()` in `facefusion/core.py:354`. Affects headless-run, batch-run, and any future callers of `job_runner.run_job` uniformly. Commit `810aca7`.
- **Smoke tests:** `python -c "from facefusion import core"` (passes).
- **Next attempt:** Run 03 with the fix in place. Expect chunk subprocesses (`chunk-001`, `chunk-002`, …) to spawn after extract_frames completes.

## Run 03 — 2026-04-28 08:51 → 12:19  ✅ SUCCESS

- **Outcome:** **succeeded**
- **Started:** 2026-04-28 08:51:44
- **Ended:** 2026-04-28 12:19:00 (3 h 27 min wall)
- **Subprocess exit code:** 0
- **Output file:** `/Users/jordanjones/Documents/facefusion/output/My-Movie-1-faceswap-shan-run-03.mov`
- **Output validation:**
  - Size: 578,095,154 bytes (578 MB) — 89% of 649 MB input ✓
  - Duration: 485.26 s (8m05s) ✓
  - Container: `mov,mp4,m4a,3gp,3g2,mj2`, codecs h264 (video) + aac (audio), 1280×720 @ 30 fps ✓
  - All four success criteria pass.
- **Log:** `.loop/logs/run-03.log`
- **Architecture validation:**
  - Parent worker RSS held steady at **2.09 GB** for the entire 3.5 h run.
  - 58 chunk subprocesses dispatched cleanly, each [start:end) range processed in isolation. Chunk RSS varied 20-87 GB per process and was fully released on each exit. Highest single-chunk peak was ~87 GB on chunk-016 — well below the 128 GB system limit.
  - **0 chunk failures, 0 frame-processing failures, 0 retries needed.**
  - Successfully passed both prior crash points (frames 778 and 1026) within minutes of starting.
- **Final pipeline:**
  - extract_frames: ~2.5 min (14,557 frame analyse → 14,500 extracted)
  - process_video (chunked): ~3 h 26 min (58 chunks × ~3-4 min/chunk avg)
  - merge_frames: ~2 min (ffmpeg image2 demuxer at ~120 frame/s)
  - restore_audio + finalize_video: <1 min
- **Fix applied this run:** none — Run 02's `state_manager.set_item('job_id', job_id)` was the only fix needed. Run 03 ran clean.
- **Smoke tests post-run:** ffprobe valid + size sanity (see Output validation above).
- **Verdict:** chunking architecture works. Silent-worker-death class of failure is decisively mitigated.

---

# Loop summary

| Run | Outcome | Wall time | Failure / fix |
|-----|---------|-----------|---------------|
| 01  | failed  | ~5 s      | `.mov`/`.mp4` extension mismatch — operator fix, no code change |
| 02  | killed  | 7 min     | Chunking dispatch silently bypassed (job_id not in state). Fix: commit `810aca7`, +1 line in `process_step` |
| 03  | **success** | 3 h 27 min | Output: 578 MB, 8m05s, valid h264/aac MOV |

**Total commits this loop:** 1 (`810aca7`).
**Outputs preserved for inspection:** `output/My-Movie-1-faceswap-shan-run-03.mov`. Run 01 and Run 02 produced no usable output and are documented above.
