# Intensity/Kail Smoke Runs

Status: `experimental`
Recorded: 2026-06-01
Baseline: `settings/2026-05-27-run-04-fix-e.ini`

This entry records the first smoke tests against the `intensity.mp4` target and
the Kail source set. These runs are for visual review only; no ArcFace
scoreboard evaluation was run for this identity.

## Prepared Targets

| Artifact | Path | Notes |
|---|---|---|
| Last 120 seconds | `videos/intensity_120.mp4` | 120.000s, 3600 frames, 1024x576, 30 fps |
| Last 60 seconds | `videos/intensity_60.mp4` | 60.000s, 1800 frames, 1024x576, 30 fps |

The source `videos/intensity.mp4` audio ends before the video stream, so the
trimmed clips have shorter audio than video. The video stream itself is the
expected length and frame count.

## Source Set

Final completed smoke used:

```text
faces/kail/kail_1.jpg
faces/kail/kail_3.jpeg
```

The earlier all-source Kail attempt used `kail_1` through `kail_4` and was
stopped after visual review flagged eye misalignment and odd facial texture.

## Attempt Summary

| Attempt | Target | Status | Notes |
|---|---|---|---|
| `headless-2026-06-01-03-13-06` | `videos/intensity_120.mp4` | stopped | Used all four Kail sources, `face_landmarker_score=0.60`, mask blur `0.35`; user stopped during chunk 001 after reviewing frames 333-336. Job snapshot showed `face_mask_padding` stayed `0 0 0 0`, so do not treat the requested padding test as actually validated. |
| `headless-2026-06-01-03-52-39` | `videos/intensity_60.mp4` | stopped | Used `kail_1` + `kail_3`, box mask, blur `0.30`, padding `0 0 0 0`, inherited `face_swapper_pixel_boost=512x512`; stopped early to reduce texture amplification. |
| `headless-2026-06-01-03-58-32` | `videos/intensity_60.mp4` | complete | Same cautious settings as run 02, plus `face_swapper_pixel_boost=256x256`. |

## Completed Smoke Settings

```sh
/opt/anaconda3/envs/facefusion/bin/python -u facefusion.py headless-run \
  --config-path settings/2026-05-27-run-04-fix-e.ini \
  --source-paths faces/kail/kail_1.jpg faces/kail/kail_3.jpeg \
  --target-path videos/intensity_60.mp4 \
  --output-path output/intensity-60-kail-run-03-kail1-kail3-boxmask-pb256.mp4 \
  --processors face_swapper \
  --execution-providers cpu \
  --execution-thread-count 12 \
  --face-landmarker-score 0.50 \
  --face-mask-types box \
  --face-mask-blur 0.30 \
  --face-mask-padding 0 0 0 0 \
  --face-swapper-pixel-boost 256x256
```

The realized job snapshot confirmed:

- `face_landmarker_score = 0.50`
- `face_mask_types = box`
- `face_mask_blur = 0.30`
- `face_mask_padding = 0 0 0 0`
- `face_swapper_pixel_boost = 256x256`

## Evidence

| Artifact | Path |
|---|---|
| Completed output | `output/intensity-60-kail-run-03-kail1-kail3-boxmask-pb256.mp4` |
| Run log | `logs/intensity-60-kail-run-03-20260601-035831.log` |
| Job record | `.jobs/completed/headless-2026-06-01-03-58-32.json` |

Validation:

- `ffprobe` reported 1024x576 video, 30 fps, 60.000s duration, and 1800 frames.
- Log scan found no `[ERROR]`, traceback, exception, or failure marker.
- Final process check found no active FaceFusion, chunk-run, caffeinate, or tmux process for this run.

## Follow-Up

1. Visually review `output/intensity-60-kail-run-03-kail1-kail3-boxmask-pb256.mp4`, especially eyes and skin texture.
2. If the 60-second smoke is acceptable, promote the same settings to the 120-second target.
3. If eyes or texture are still off, test source selection next before changing multiple mask settings again: compare `kail_1` only, `kail_3` only, and the current two-source blend on the same short target.
4. Do not update the workstream Scoreboard until a scoreboard-compatible evaluator pass is run for the target identity.
