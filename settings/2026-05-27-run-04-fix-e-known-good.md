# Run 04 - Fix E Known-Good Settings

Status: `known-good`
Recorded: 2026-05-31
Run dates: 2026-05-27 to 2026-05-28
Job id: `headless-2026-05-27-18-33-04`

This is the first production output observed as an improvement over Run 03.
Keep it as the baseline before changing swapper model, execution provider, or
enhancement settings again.

## Artifacts

| Artifact | Path |
|---|---|
| Settings snapshot | `settings/2026-05-27-run-04-fix-e.ini` |
| Final output | `output/My-Movie-1-faceswap-shan-run-04.mov` |
| Completed job record | `.jobs/completed/headless-2026-05-27-18-33-04.json` |
| Full rerun log | `logs/run04-full-rerun-20260527-183249.log` |
| Handoff/provenance | `docs/run-04-handoff.md` |
| Baseline eval CSV | `output/eval-run-03-window-1800-2700.csv` |
| Fix E smoke CSV | `output/eval-fixE-smoke.csv` |
| Input ceiling CSV | `output/eval-input-window-1800-2700.csv` |

## Inputs

| Item | Value |
|---|---|
| Source | `faces/shan_1.jpeg` |
| Target | `videos/My Movie 1.mov` |
| Output | `output/My-Movie-1-faceswap-shan-run-04.mov` |
| Frame count | `14557` |
| Output duration | `485.256553` seconds |

## Key Settings

| Setting | Value | Reason |
|---|---|---|
| `processors` | `face_swapper` | Keeps enhancer off; Fix E smoke reduced identity flicker versus Run 03. |
| `face_swapper_model` | `inswapper_128_fp16` | Replaced `hyperswap_1c_256`, which was the unstable Run 03 baseline. |
| `execution_providers` | `cpu` | Avoids the Apple Silicon/CoreML nondeterminism suspected in flicker. |
| `execution_thread_count` | `12` | Throughput setting used for the completed production render. |
| `chunk_size_frames` | `250` | Keeps the crash-resistant chunked render path enabled. |
| `face_swapper_pixel_boost` | `512x512` | Preserves detail on close-ups. |
| `face_selector_mode` | `many` | Avoids reference-threshold dropouts during this baseline. |
| `face_detector_angles` | `0 90 180 270` | Retains robust face detection across rotated/head-tilted frames. |
| `face_mask_types` | `box occlusion region` | Best current blend/masking baseline. |
| `output_video_preset` | `slow` | Production-quality x264 preset used by Run 04. |
| `keep_temp` | `true` in job record | Preserved temp frames during the production run. |

Configured but inactive: `face_enhancer_model = gfpgan_1.4` and
`face_enhancer_blend = 80`. These do not affect this baseline unless
`face_enhancer` is added back to `processors`.

## Scoreboard

30-second smoke window, frames 1800-2700, ref-matched eval.

| Metric | Run 03 baseline | Target | Fix E smoke |
|---|---:|---:|---:|
| State transitions (`shan`/`other`/`no-face`) | 72 | <30 | 25 |
| Shan share of detected frames | 64.7% | >90% | 92.3% |
| Mean shan-run length | 0.43 s | >2 s | 2.14 s |
| Max `other`-run length | 1.33 s | <0.5 s | 0.33 s |
| Median cosine distance to source | 0.291 | <0.20 | 0.175 |

Final-output bounded evaluator smoke on Run 04 sampled frames 1800-2700 at
stride 2 with `--ref-match`: 451 sampled frames, 308 detected frames, median
cosine distance `0.1706`, and 92.2% of detected frames below 0.4.

## Validation

Run 04 completion proof:

- `logs/run04-full-rerun-20260527-183249.log` shows all 59 chunks completed.
- The same log shows `processing to video succeeded` and `hard_exit(0)`.
- `.jobs/completed/headless-2026-05-27-18-33-04.json` marks the step completed.
- `ffprobe` reports valid H.264 video at 1280x720, 30 fps, 14,557 frames, plus AAC audio.
- No active `facefusion.py`, `ffmpeg`, `evaluate_swap.py`, `recover_run04.py`, or Run 04 worker process was present at resume verification on 2026-05-31.

## Reuse Notes

Use this entry as the baseline for future full renders. If rerunning, change the
output name first so the Run 04 artifact is preserved.

```sh
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate facefusion
python facefusion.py headless-run \
  --config-path settings/2026-05-27-run-04-fix-e.ini \
  --source-paths faces/shan_1.jpeg \
  --target-path "videos/My Movie 1.mov" \
  --output-path output/My-Movie-1-faceswap-shan-run-04-next.mov \
  --processors face_swapper \
  --execution-providers cpu \
  --execution-thread-count 12
```

If changing any major lever, rerun a scoreboard-compatible eval before a full
production render:

```sh
PYTHONPATH=. python tools/evaluate_swap.py \
  --source faces/shan_1.jpeg \
  --target output/My-Movie-1-faceswap-shan-run-04-next.mov \
  --start-frame 1800 \
  --end-frame 2700 \
  --stride 2 \
  --ref-match \
  --csv output/eval-next-window-1800-2700.csv
```

Avoid treating these as equivalent to Fix E without a new A/B:

- `hyperswap_1c_256`
- `coreml` execution provider for the quality baseline
- adding `face_enhancer` back to `processors`
- reducing or disabling chunking for long production renders
