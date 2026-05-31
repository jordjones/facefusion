# Run 04 Quality Review

Status: `reviewed`
Recorded: 2026-05-31
Baseline: `settings/2026-05-27-run-04-fix-e.ini`
Output reviewed: `output/My-Movie-1-faceswap-shan-run-04.mov`

This review analyzes the completed Run 04 output before changing settings for
the next render. No config change has been applied yet.

## Artifacts

| Artifact | Path |
|---|---|
| Scoreboard-window CSV | `output/eval-run-04-window-1800-2700.csv` |
| Scoreboard-window summary | `output/eval-run-04-window-1800-2700.txt` |
| Full-video sample CSV | `output/eval-run-04-full-sample-500.csv` |
| Full-video sample summary | `output/eval-run-04-full-sample-500.txt` |
| Temporary visual review frames | `.temp/run04-quality-review-20260531/` |

The temporary visual review directory is intentionally not part of the durable
registry because it contains extracted video frames. Regenerate it from the CSV
frame numbers if needed.

## Quantitative Findings

### Scoreboard window

Frames `1800-2700`, stride `1`, source-match selector:

| Metric | Value |
|---|---:|
| Sampled frames | 901 |
| Detected frames | 621 / 901 (68.9%) |
| Median cosine distance | 0.1718 |
| Mean cosine distance | 0.2301 |
| P95 cosine distance | 0.5630 |
| Source-identity frames under 0.4 | 566 / 621 (91.1%) |
| State transitions (`shan` / `other` / `no-face`) | 37 |
| Mean source-identity run length | 1.72 s |
| Max other-identity run length | 0.50 s |
| Max no-face run length | 3.83 s |

The median identity score remains strong and close to the Fix E smoke. The
strict stride-1 pass is weaker on transition/run-length metrics than the
earlier stride-2 smoke, so treat Run 04 as improved but not fully closed.

### Full-video sample

500 evenly spaced frames across the full output:

| Metric | Value |
|---|---:|
| Sampled frames | 500 |
| Detected frames | 330 / 500 (66.0%) |
| Median cosine distance | 0.2070 |
| Mean cosine distance | 0.2744 |
| P95 cosine distance | 0.8276 |
| Source-identity frames under 0.4 | 280 / 330 (84.8%) |
| Multi-face detected frames | 16 / 330 |

The full-video sample is harder than the scoreboard window. The weakest frames
are concentrated around partial profiles, heavy occlusion, faces near the frame
edge, and frames where the detector is effectively operating on too little
usable face information.

## Visual Findings

Targeted frame review covered the worst-score clusters from both the scoreboard
window and the full-video sample.

Observed pattern:

- Good frontal or three-quarter frames usually keep the improved Run 04 identity
  lock.
- Most bad-score frames are hard-source frames: profile, steep downward angle,
  hair/hand occlusion, partial face crop, or no usable face.
- Several high-distance frames are better understood as false-positive or
  low-quality detections than as ordinary swapper instability.
- There is no evidence from the sampled frames that compression settings are the
  main quality limiter.
- Some close or edge-cropped frames show a soft blended face region; this is a
  mask/landmark confidence problem more than an encoder problem.

## Next Settings Candidates

Keep the Run 04 baseline as the production starting point:

- `face_swapper_model = inswapper_128_fp16`
- `execution_providers = cpu`
- `processors = face_swapper`
- `face_swapper_pixel_boost = 512x512`
- `chunk_size_frames = 250`

Recommended next smoke tests, in order:

1. Landmark-refinement threshold:

   ```ini
   [face_landmarker]
   face_landmarker_score = 0.60
   ```

   Rationale: in the full-video sample, `other` frames had much lower
   landmarker scores than source-identity frames. This setting does not skip or
   gate faces; it decides when FaceFusion trusts the 68-point landmarker instead
   of falling back to detector-derived landmarks. At 0.60, 25 / 50 sampled
   `other` frames and 5 / 280 sampled source-identity frames would use the
   fallback path. Validate visually because this is a geometry-stability lever,
   not a no-swap/dropout lever.

2. Multi-source identity set:

   Use several same-person source images that cover frontal, three-quarter,
   profile, and downward-looking poses. The swapper averages source faces, so
   this may improve side/profile identity stability more directly than changing
   the model.

   ```sh
   --source-paths faces/shan_1.jpeg faces/shan_profile.jpeg faces/shan_downward.jpeg
   ```

   Only use high-quality source images of the same intended identity.

3. Mask-edge smoke:

   ```ini
   [face_masker]
   face_mask_blur = 0.35
   face_mask_padding = 4 4 8 4
   ```

   Rationale: sampled edge/cropped frames show soft blend artifacts. This should
   be tested visually, not judged only by cosine distance.

Do not use these as the first next step:

- `hyperswap_1c_256`
- `coreml` for the quality baseline
- re-enabling `face_enhancer` globally
- changing encoder settings as the primary fix

## Suggested Smoke Command

Run a bounded smoke before any new full render:

```sh
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate facefusion
python facefusion.py headless-run \
  --config-path settings/2026-05-27-run-04-fix-e.ini \
  --source-paths faces/shan_1.jpeg \
  --target-path "videos/My Movie 1.mov" \
  --output-path output/My-Movie-1-faceswap-shan-run-05-f1-landmark-refine-threshold.mov \
  --processors face_swapper \
  --execution-providers cpu \
  --execution-thread-count 12 \
  --trim-frame-start 1800 \
  --trim-frame-end 2701 \
  --face-landmarker-score 0.60
```

Then evaluate the trimmed output using local frame numbers. Frame `1` in this
smoke output maps to approximately original frame `1800`.

```sh
PYTHONPATH=. python tools/evaluate_swap.py \
  --source faces/shan_1.jpeg \
  --target output/My-Movie-1-faceswap-shan-run-05-f1-landmark-refine-threshold.mov \
  --start-frame 1 \
  --end-frame 901 \
  --stride 1 \
  --ref-match \
  --csv output/eval-run-05-f1-window-1800-2700.csv
```

Compare both metrics and visual contact sheets before promoting the setting.
