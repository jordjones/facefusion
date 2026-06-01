# Settings Registry

This folder records FaceFusion settings that have actually been tried, along
with their observed outcome. Use it as the durable run/config registry. Keep
the top-level `settings.md` as the narrative explanation of the current config.

## Entry Convention

Use dated names:

```text
YYYY-MM-DD-run-XX-short-name.md
YYYY-MM-DD-run-XX-short-name.ini
```

Each run entry should include:

- status: `known-good`, `experimental`, `rejected`, `historical`, or `reviewed`
- source, target, output, and job id when available
- the meaningful config levers and what changed from the prior baseline
- evidence: output path, logs, evaluator CSVs, visual notes, or ffprobe checks
- follow-up: what to preserve, what to test next, and what not to reuse

Do not copy videos, temp frames, model files, raw private dumps, or credentials
into this folder. Link to existing project artifacts instead.

## Entries

| Entry | Status | Summary |
|---|---|---|
| `2026-05-27-run-04-fix-e-known-good.md` | known-good | Improved Run 04 baseline: `inswapper_128_fp16`, CPU-only, `face_swapper` only, chunked render. |
| `2026-05-31-run-04-quality-review.md` | reviewed | Run 04 metrics and visual diagnosis; recommends landmark-refinement, multi-source, and mask-edge smoke tests before the next full render. |
| `2026-06-01-intensity-kail-smoke.md` | experimental | Intensity/Kail smoke runs; completed 60-second Kail two-source test with box mask and `face_swapper_pixel_boost=256x256`. |
