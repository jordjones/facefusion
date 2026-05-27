# Run 04 Handoff

Created: 2026-05-26 21:45 AST
Updated: 2026-05-27 08:08 AST

## Goal

Resume Run 04 at chunk 41 without losing the existing temp-frame state, complete remaining chunks, then merge frames, restore audio, and finalize:

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

Run 04 originally stopped after chunk 14 completed. Recovery resumed on 2026-05-27 and intentionally paused after chunk 40 completed. No FaceFusion process was running at handoff verification after the chunk-40 pause. The final MOV has not been created/finalized yet.

## Completed Chunk Logs

These logs exist and are the current proof that chunks `000` through `040` completed. Each verified proof log contains both `[FACEFUSION.DIAG] hard_exit(0)` and `[FACEFUSION.ATEXIT]`.

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
logs/job-20260527-041042-headless-2026-05-26-18-59-40-chunk-015-00003750-00004000.log
logs/job-20260527-042413-headless-2026-05-26-18-59-40-chunk-016-00004000-00004250.log
logs/job-20260527-043708-headless-2026-05-26-18-59-40-chunk-017-00004250-00004500.log
logs/job-20260527-044838-headless-2026-05-26-18-59-40-chunk-018-00004500-00004750.log
logs/job-20260527-050318-headless-2026-05-26-18-59-40-chunk-019-00004750-00005000.log
logs/job-20260527-051947-headless-2026-05-26-18-59-40-chunk-020-00005000-00005250.log
logs/job-20260527-053206-headless-2026-05-26-18-59-40-chunk-021-00005250-00005500.log
logs/job-20260527-054149-headless-2026-05-26-18-59-40-chunk-022-00005500-00005750.log
logs/job-20260527-055446-headless-2026-05-26-18-59-40-chunk-023-00005750-00006000.log
logs/job-20260527-061438-headless-2026-05-26-18-59-40-chunk-024-00006000-00006250.log
logs/job-20260527-062240-headless-2026-05-26-18-59-40-chunk-025-00006250-00006500.log
logs/job-20260527-062922-headless-2026-05-26-18-59-40-chunk-026-00006500-00006750.log
logs/job-20260527-063531-headless-2026-05-26-18-59-40-chunk-027-00006750-00007000.log
logs/job-20260527-064336-headless-2026-05-26-18-59-40-chunk-028-00007000-00007250.log
logs/job-20260527-070530-headless-2026-05-26-18-59-40-chunk-029-00007250-00007500.log
logs/job-20260527-071850-headless-2026-05-26-18-59-40-chunk-030-00007500-00007750.log
logs/job-20260527-072328-headless-2026-05-26-18-59-40-chunk-031-00007750-00008000.log
logs/job-20260527-073447-headless-2026-05-26-18-59-40-chunk-032-00008000-00008250.log
logs/job-20260527-073715-headless-2026-05-26-18-59-40-chunk-033-00008250-00008500.log
logs/job-20260527-074124-headless-2026-05-26-18-59-40-chunk-034-00008500-00008750.log
logs/job-20260527-074204-headless-2026-05-26-18-59-40-chunk-035-00008750-00009000.log
logs/job-20260527-074239-headless-2026-05-26-18-59-40-chunk-036-00009000-00009250.log
logs/job-20260527-074304-headless-2026-05-26-18-59-40-chunk-037-00009250-00009500.log
logs/job-20260527-074331-headless-2026-05-26-18-59-40-chunk-038-00009500-00009750.log
logs/job-20260527-074357-headless-2026-05-26-18-59-40-chunk-039-00009750-00010000.log
logs/job-20260527-075441-headless-2026-05-26-18-59-40-chunk-040-00010000-00010250.log
```

Important: ignore the interrupted partial chunk-026 log at `logs/job-20260527-062828-headless-2026-05-26-18-59-40-chunk-026-00006500-00006750.log`. The complete chunk-026 proof log is `logs/job-20260527-062922-headless-2026-05-26-18-59-40-chunk-026-00006500-00006750.log`.

## Temp Files To Preserve

Preserve this directory exactly as-is:

```text
/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1/
```

Read-only checks during resume on 2026-05-27 corrected the handoff path. The project-local `.temp/facefusion/My Movie 1/` frame set is stale from Apr 28 and must not be used for Run 04 continuation.

Read-only checks of the actual Run 04 temp directory after chunk 040:

```text
PNG count: 14557
All temp files newer than Run 04 start time: 2026-05-26 18:59:40
Present checked files: 00000001.png, 00010250.png, 00010251.png, 00014557.png
```

Important nuance: chunk ranges in logs and code are offsets into `resolve_temp_frame_paths()`, not guaranteed filename numbers. Keep the sorted temp-frame list stable.

Do not delete `/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1/`. Do not run a fresh `headless-run` or `job-run` against this target before the recovery decision, because `image_to_video.setup()` clears and recreates the target temp directory.

## Resume Target

Start at zero-indexed chunk `41`.

```text
chunk 41: code-offset range [10250,10500)
chunk 42: code-offset range [10500,10750)
...
chunk 58: code-offset range [14500,14557)
```

Use the committed recovery helper. It validates the exact temp path, expected frame count, frame sequence, successful prior chunk logs, and skips any already-successful chunk logs.

```sh
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate facefusion
python tools/recover_run04.py --start-chunk 41
```

That command processes chunks `041` through `058` and finalizes automatically after the last chunk. For another controlled pause, add an end boundary:

```sh
python tools/recover_run04.py --start-chunk 41 --end-chunk 45
```

A dry-run of the immediate next chunk should print chunk `041` with range `[10250,10500)` and skip finalization:

```sh
python tools/recover_run04.py --dry-run --start-chunk 41 --end-chunk 41
```

## Verification Commands For Next Session

Run these before touching recovery:

```sh
pgrep -fl 'facefusion.py|headless-2026-05-26-18-59-40|chunk-run' || true
ls -lh logs/*headless-2026-05-26-18-59-40*chunk-040-00010000-00010250.log
ls -lh logs/*headless-2026-05-26-18-59-40*chunk-041* 2>/dev/null || true
find "/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1" -maxdepth 1 -type f -name "*.png" | wc -l
ls -lh "/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1/00000001.png" "/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1/00010250.png" "/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1/00014557.png"
source /opt/anaconda3/etc/profile.d/conda.sh && conda activate facefusion && python tools/recover_run04.py --dry-run --start-chunk 41 --end-chunk 41
```

Expected before recovery:

- No FaceFusion PIDs.
- Chunk 40 log exists and is successful.
- Chunk 41 log absent unless a later session already resumed.
- Temp PNG count remains `14557` in `/var/folders/ps/3p6bv7g917xc_mlskxs4sn7c0000gn/T/facefusion/My Movie 1/`.
- Dry-run reports chunk `041` range `[10250,10500)` and `finalize skipped`.

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
