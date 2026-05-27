# Run 04 Handoff

Created: 2026-05-26 21:45 AST

## Goal

Resume Run 04 at chunk 15 without losing the existing temp-frame state, complete remaining chunks, then merge frames, restore audio, and finalize:

```text
output/My-Movie-1-faceswap-shan-run-04.mov
```

## Current State

- Project: `/Users/jordanjones/Documents/facefusion`
- Job id: `headless-2026-05-26-18-59-40`
- Source: `faces/shan_1.jpeg`
- Target: `videos/My Movie 1.mov`
- Output: `output/My-Movie-1-faceswap-shan-run-04.mov`
- Config intent: Fix E, `inswapper_128_fp16`, CPU execution provider, `face_swapper` only, chunk size `250`
- Total frames from Run 04 startup log: `14557`
- Expected chunks: `59`, zero-indexed `000` through `058`
- Parent PID `74022` no longer exists. Do not use `kill -CONT 74022`; there is nothing to resume by signal.

Run 04 did not reach chunk 20. It stopped after chunk 14 completed. No FaceFusion process was running at handoff verification.

## Completed Chunk Logs

These logs exist and are the current proof that chunks `000` through `014` completed:

```text
logs/job-20260526-190205-headless-2026-05-26-18-59-40-chunk-000-00000000-00000250.log
logs/job-20260526-191331-headless-2026-05-26-18-59-40-chunk-001-00000250-00000500.log
logs/job-20260526-192338-headless-2026-05-26-18-59-40-chunk-002-00000500-00000750.log
logs/job-20260526-193615-headless-2026-05-26-18-59-40-chunk-003-00000750-00001000.log
logs/job-20260526-194156-headless-2026-05-26-18-59-40-chunk-004-00001000-00001250.log
logs/job-20260526-195047-headless-2026-05-26-18-59-40-chunk-005-00001250-00001500.log
logs/job-20260526-195140-headless-2026-05-26-18-59-40-chunk-006-00001500-00001750.log
logs/job-20260526-200358-headless-2026-05-26-18-59-40-chunk-007-00001750-00002000.log
logs/job-20260526-201802-headless-2026-05-26-18-59-40-chunk-008-00002000-00002250.log
logs/job-20260526-202629-headless-2026-05-26-18-59-40-chunk-009-00002250-00002500.log
logs/job-20260526-204049-headless-2026-05-26-18-59-40-chunk-010-00002500-00002750.log
logs/job-20260526-204254-headless-2026-05-26-18-59-40-chunk-011-00002750-00003000.log
logs/job-20260526-205428-headless-2026-05-26-18-59-40-chunk-012-00003000-00003250.log
logs/job-20260526-211002-headless-2026-05-26-18-59-40-chunk-013-00003250-00003500.log
logs/job-20260526-212354-headless-2026-05-26-18-59-40-chunk-014-00003500-00003750.log
```

No `chunk-015` log exists. No `chunk-020-00005000-00005250.log` exists.

## Temp Files To Preserve

Preserve this directory exactly as-is:

```text
/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1/
```

Read-only checks during resume on 2026-05-27 corrected the handoff path. The project-local `.temp/facefusion/My Movie 1/` frame set is stale from Apr 28 and must not be used for Run 04 continuation.

Read-only checks of the actual Run 04 temp directory:

```text
PNG count: 14557
All temp files newer than Run 04 start time: 2026-05-26 18:59:40
Present checked files: 00000001.png, 00003750.png, 00003751.png, 00014557.png
```

Important nuance: chunk ranges in logs and code are offsets into `resolve_temp_frame_paths()`, not guaranteed filename numbers. Keep the sorted temp-frame list stable.

Do not delete `/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1/`. Do not run a fresh `headless-run` or `job-run` against this target before the recovery decision, because `image_to_video.setup()` clears and recreates the target temp directory.

## Resume Target

Start at zero-indexed chunk `15`.

```text
chunk 15: code-offset range [3750,4000)
chunk 16: code-offset range [4000,4250)
...
chunk 58: code-offset range [14500,14557)
```

The internal chunk command uses environment variables for the code-offset slice. A single-chunk manual command for chunk 15 is:

```sh
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate facefusion

log="logs/job-$(date +%Y%m%d-%H%M%S)-headless-2026-05-26-18-59-40-chunk-015-00003750-00004000.log"
FACEFUSION_CHUNK_START=3750 \
FACEFUSION_CHUNK_END=4000 \
PYTHONUNBUFFERED=1 \
PYTHONFAULTHANDLER=1 \
caffeinate -dimsu python -u facefusion.py chunk-run headless-2026-05-26-18-59-40 0 \
  --config-path facefusion.ini \
  --temp-path /var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T \
  --jobs-path .jobs \
  --execution-providers cpu \
  --execution-thread-count 12 \
  --log-level info > "$log" 2>&1
```

Repeat for chunks `16` through `58`, updating the chunk number and `[start,end)` range. After all remaining chunks complete, the future session must still merge frames, restore audio, and finalize the MOV. There is currently no committed resume-from-chunk CLI; either add a focused recovery helper or run a carefully reviewed one-off script that:

1. Uses the existing job args from `.jobs/queued/headless-2026-05-26-18-59-40.json`.
2. Processes chunk ranges `15..58` against the existing temp directory.
3. Calls the same merge/audio/finalize path that the parent would have called.
4. Leaves `/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1/` untouched until the final output is verified.

## Verification Commands For Next Session

Run these before touching recovery:

```sh
pgrep -fl 'facefusion.py|headless-2026-05-26-18-59-40|chunk-run' || true
ls -lh logs/*headless-2026-05-26-18-59-40*chunk-014-00003500-00003750.log
ls -lh logs/*headless-2026-05-26-18-59-40*chunk-015* 2>/dev/null || true
find "/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1" -maxdepth 1 -type f -name "*.png" | wc -l
ls -lh "/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1/00000001.png" "/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1/00003750.png" "/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1/00014557.png"
```

Expected before recovery:

- No FaceFusion PIDs.
- Chunk 14 log exists.
- Chunk 15 log absent.
- Temp PNG count remains `14557` in `/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1/`.

## Final Output Validation

After finalizing `output/My-Movie-1-faceswap-shan-run-04.mov`, run the evaluator against the same scoreboard window used for Fix E:

```sh
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate facefusion
python tools/evaluate_swap.py \
  --source faces/shan_1.jpeg \
  --target output/My-Movie-1-faceswap-shan-run-04.mov \
  --start-frame 1800 \
  --end-frame 2700 \
  --stride 1 \
  --ref-match \
  --csv output/eval-run-04-window-1800-2700.csv \
  --summary output/eval-run-04-window-1800-2700.txt
```
