# Find Better — Models / Speed / Settings Research

**Date:** 2026-07-23 · **Workstream:** Find better (Active Project) · **Fork:** FaceFusion **3.6.0** (upstream `facefusion/facefusion`)
**Hardware:** Apple **M4 Max** — 40-core GPU, 16-core Neural Engine, 128 GB unified, Metal 3 / MPS, **no CUDA**.
**Scope decision (2026-07-23):** stay within FaceFusion (version upgrades in-scope; other tools out).
**Method:** four parallel web-research threads (execution/speed, latest version, best swapper model, stability settings), synthesized. All non-obvious claims cited; caveats preserved.

---

## TL;DR

The two worst problems — **frame-to-frame identity flicker** and **3h27m renders** — share **one root cause**, and it is fixable without leaving 3.6.0:

> The CoreML execution provider is configured with **no `ModelFormat`**, so it defaults to `NeuralNetwork` — an untyped graph that silently runs **FP16 on the GPU/ANE**. That dynamic FP16 dispatch is the flicker. To kill it, we forced **CPU-only**, which is why renders are slow (the 40-core GPU sits idle). Forcing **`ModelFormat=MLProgram`** runs the graph in typed **FP32** → deterministic (no flicker) → we can run on the GPU again → speed. FaceFusion's maintainers shipped exactly this fix in v3.7.0 ("Boost CoreML performance for fp16 models").

Second finding: the earlier hyperswap failure was **variant choice**, not hyperswap. `hyperswap_1c_256` (what we tested) is the *worst* variant for video ("misses frames"); `hyperswap_1a_256` (FF's default since 3.3.2) is the *best-detecting* = fewest dropouts.

Third finding: nothing past 3.6.0 adds new swap/enhancer **models** — so all model/settings wins are available today. The only unique payload of upgrading is 3.7.0's **face tracker** (dropout refill) + processor speed refactor, at the cost of a fork rebase.

---

## Unified diagnosis (why flicker == slowness)

- **Root cause (execution thread, confirmed in FaceFusion source):** 3.6.0's CoreML block is `{'SpecializationStrategy':'FastPrediction', 'ModelCacheDirectory': cache}` — no `ModelFormat` ⇒ default `NeuralNetwork` ⇒ untyped DAG ⇒ CoreML free to run layers in FP16 on GPU, and the ANE is FP16-only. `MLComputeUnits=ALL` lets the same subgraph land on ANE vs GPU depending on thermal/load ⇒ FP16 rounding varies per frame ⇒ identity shimmer.
  - Reproduced independently: ORT+CoreML `NeuralNetwork` output matched CoreML FP16 and diverged ~3.7e-4 from FP32/CPU; `MLProgram` matched FP32/CPU. (https://ym2132.github.io/ONNX_MLProgram_NN_exploration ; HN: https://news.ycombinator.com/item?id=46350075)
- **The fix:** `ModelFormat=MLProgram` ⇒ typed **FP32** ⇒ error floor ~1e-7 (far below visible). FaceFusion 3.7.0 added `resolve_inference_providers()` doing exactly this for macOS CoreML fp16 models. (https://docs.facefusion.io/introduction/changelog)
- **Speed:** on Apple Silicon, ORT+CoreML **FP32 ≈ FP16 speed** (ResNet-50: 10.1 ms vs 10.3 ms) — so MLProgram buys determinism at ~0 speed cost. (https://medium.com/@msridharansundaram/i-optimized-ml-inference-on-apple-silicon-for-weeks-the-bottleneck-was-never-the-model-8ac7049a0aa2)
- **Honest caveat:** ORT/CoreML does not guarantee *bit-identical* GPU output (same class as cuDNN non-determinism), but FP32 magnitude is visually imperceptible. For extra safety, `MLComputeUnits=CPUAndGPU` hard-excludes the FP16-only ANE. **Never** set `AllowLowPrecisionAccumulationOnGPU=1`. Determinism must be **verified empirically** on a smoke (the evaluator scoreboard measures exactly this), not assumed.
- **Speed expectation:** swap stage should drop hard off CPU-only (~1.16 fps), but decode/detect/ffmpeg-encode stay CPU-bound ⇒ *overall* speedup is sub-linear. Rough estimate ~35–90 min vs 3h27m for the 14.5k-frame clip — **benchmark, don't assume**.

---

## Findings by area

### 1. Execution / speed / determinism (M4 Max)
- CoreML EP options (ORT 1.20+): `ModelFormat` (NeuralNetwork|MLProgram, **the determinism lever**), `MLComputeUnits` (ALL|CPUAndGPU|CPUAndNeuralEngine|CPUOnly), `RequireStaticInputShapes`, `AllowLowPrecisionAccumulationOnGPU` (keep 0), `SpecializationStrategy`, `ProfileComputePlan`, `ModelCacheDirectory`. (https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html)
- Our ORT is **1.24.4** — MLProgram fully supported; no ORT upgrade needed.
- Use the official `onnxruntime` wheel (arm64 macOS + CoreML built in); `onnxruntime-silicon` is deprecated. (https://github.com/cansik/onnxruntime-silicon)
- 3.6.0 quirk: on macOS+CoreML it silently swaps `inswapper_128_fp16`→`inswapper_128` and force-routes ghost/uniface to CPU. (source: 3.6.0 execution.py / face_swapper core)

### 2. Best swapper model for video
- Temporal stability is **not** a model feature in 3.6.0 — every swapper is per-frame. "Least flicker" = "detects + swaps the same face on every frame."
- FF default swapper is **`hyperswap_1a_256`** since v3.3.2. Variant behavior:
  - **1A** = best detection, fewest dropped frames; likeness ~6/10. **Best for video.**
  - **1B** = side-view; known native "silent fail-swap" bug → unreliable for long unattended renders.
  - **1C** = best still resemblance (~8/10) but "misses frames, weak on angles" → **worst for video** (what we tested).
- Ranked for video stability: **inswapper_128_fp16** (battle-tested workhorse, soft native 128 → needs pixel-boost) ≈ **hyperswap_1a_256** (sharper native 256, best detection) > 1c > 1b > ghost (has landmark smoothing but thin FF validation) > simswap_512 (softer than inswapper) > simswap_256/uniface/blendswap/hififace (legacy/niche; uniface had a flicker bug). 
- Pixel-boost pairing: inswapper (128 native) benefits most; hyperswap_256 → pair with 512. Keep pixel-boost constant across the clip.
- Sources: FF changelog & docs (https://docs.facefusion.io/usage/cli-arguments/processors/face-swapper), r/FaceFusion hyperswap variant threads, ReActor issue #143, ai-forever/ghost. (Reddit was block-limited to snippets this session.)

### 3. Latest FaceFusion version
- **Latest = 3.7.1 (2026-07-05).** Only 3.6.1, 3.7.0, 3.7.1 exist past 3.6.0. Dev branches `patch/3.7.2` and `v4` in progress, unreleased. (https://github.com/facefusion/facefusion/releases)
- **No new swap/enhancer models** in any post-3.6.0 release.
- 3.7.0 substantive items: **face tracker** to refill faces the detector misses (temporal stability, provider-agnostic — helps even on CPU); **CoreML fp16 boost** (the MLProgram fix, CoreML-only); **multi-frame-aware processors** + **processor-driven model loading** (throughput on any provider); face selector `auto` mode; **QuickTime macOS output fix**. Breaking: installer positional arg; `--system-memory-limit` removed.
- 3.7.1 stabilizes a 3.7.0 perf regression + fixes image-to-image with 2 processors.
- **INI schema delta 3.6.0→3.7.1 is tiny:** `+face_tracker_score`, `+target_frame_amount`, `−system_memory_limit`. But 3.7.0 **rewrote the processor layer** — exactly where this fork's custom chunking/resilience patches live → the real upgrade cost is a **processor-path rebase**, not config. Maturity risk: multi-frame arch is fresh (3.7.2 still tuning); consider waiting for 3.7.2 before a full bump. (https://docs.facefusion.io/introduction/changelog)

### 4. Stability / quality settings
- **Enhancer OFF is correct** — GFPGAN/CodeFormer/RestoreFormer++ are image restorers with no temporal model; run per-frame they provably jitter around eyes/wrinkles (peer-reviewed: arXiv 2410.11828; ECCV 2024 KEEP; ICCV 2025). Get quality from **pixel-boost** (deterministic) instead. If a soft close-up genuinely needs it: `codeformer @ blend 40–50`.
- **Identity lock:** `face_selector_mode = reference` + a loose `reference_face_distance` (~0.6–1.0) so the lock survives off-angle/motion-blur frames (strict 0.3 default drops the swap → flicker). Set `reference_frame_number` to a clean frontal frame.
- **Masks:** stack `box occlusion region` (already set here). Blur ~0.3–0.35. Padding 0 unless a seam shows.
- **Detector:** prefer `retinaface` for continuous video (most accurate landmarks). **Do not raise** detector/landmarker scores to fight flicker — higher scores *drop* hard frames = more dropouts. Keep ~0.5 (lower toward 0.4 if dropouts persist).
- **Output:** `keep_fps = on`; libx264 high quality. Use the Face Debugger processor to sanity-check detection/mask on hard frames before a full render.
- Sources: docs.facefusion.io CLI args (authoritative); LooPIN & magichour guides; flicker literature above.

---

## Ranked shortlist (impact × effort × risk)

| # | Change | Fixes | Effort | Risk | Needs upgrade? |
|---|---|---|---|---|---|
| **1** | CoreML `ModelFormat=MLProgram` + switch `execution_providers` cpu→coreml | **Flicker + speed** | Low (1-line patch + 1 ini line) | Low | No |
| **2** | Swapper A/B: `inswapper_128_fp16` vs `hyperswap_1a_256` @ pixel-boost 512 | Quality/dropouts | Low (config) | Low | No |
| **3** | `face_selector_mode` many→reference (distance ~0.6–1.0, clean ref frame) | Identity dropouts | Low (config) | Low | No |
| **4** | Detector default(yoloface)→`retinaface`, keep scores ~0.5 | Detection stability | Low (config) | Low | No |
| 5 | Enhancer stays OFF (pixel-boost for quality) | Confirms current | — | — | No |
| 6 | Full upgrade to 3.7.1 (face tracker + processor speed refactor) | Dropouts + throughput | **High** (processor-path rebase) | Med | — |

Already in place in `facefusion.ini`: `face_mask_types = box occlusion region`, `face_swapper_pixel_boost = 512x512`, `processors = face_swapper` (no enhancer).

---

## Sequenced test plan (controlled — one variable at a time, scored on the existing scoreboard)

**Baseline for comparison:** Run 04 CPU-only known-good (median cosine 0.172, shan share 91.1%, 37 transitions, mean run 1.72 s).

1. **Smoke 1 — keystone in isolation.** Change ONLY execution: `execution_providers = coreml` + the MLProgram patch. Keep model/masks/pixel-boost identical to known-good. Run 30–60 s, score with `tools/evaluate_swap.py --ref-match`. **Pass = flicker metrics match/beat CPU baseline AND wall-time is materially lower.** This isolates "did we get GPU speed without reintroducing flicker."
2. **Smoke 2 — swapper quality.** On the winning execution config, A/B `hyperswap_1a_256` vs `inswapper_128_fp16` on the same 30–60 s target. Pick per identity (likeness "varies enormously between faces").
3. **Smoke 3 — identity lock.** Add `face_selector_mode = reference` + `retinaface`; confirm dropout metrics improve.
4. **Then:** promote the winning profile to a full render + a new `settings/` known-good snapshot; evaluate the 3.7.1 upgrade as a separate project (its unique win is the face tracker; blocker is the processor-layer rebase — possibly wait for 3.7.2).

---

## Staged patch (NOT yet applied — awaiting approval)

**`facefusion/execution.py`**, CoreML block (add one line):
```python
        if execution_provider == 'coreml':
            inference_option_set =\
            {
                'ModelFormat': 'MLProgram',          # <-- add: typed FP32, deterministic on GPU
                'SpecializationStrategy': 'FastPrediction'
            }
```
**`facefusion.ini`** (line 123): `execution_providers = cpu` → `execution_providers = coreml`
**Rollback:** revert the ini line to `cpu` (and/or remove the one code line). `chunk_size_frames` chunking layer is untouched.
**Cache note:** `.caches/1.24.4` does not exist yet → first CoreML run compiles fresh with MLProgram. If ModelFormat is ever toggled again *after* a CoreML run, `mv .caches/1.24.4 .caches/1.24.4.bak` first (ORT won't invalidate a stale compiled graph).

---

## Smoke 1 experiment results (2026-07-23) — CoreML EP config is NOT a speed win on this stack

Tested on the 10s slice (frames 1800–2100, 300 frames, source `faces/shan_1.jpeg`), scored with `tools/evaluate_swap.py --ref-match --stride 1`. Runtime is ORT **1.24.3** in the `facefusion` conda env (not 1.24.4).

| Config | Quality: frames <0.4 cosine (median) | Speed: chunk-0 250 frames incl. compile | Compile |
|---|---|---|---|
| CPU-only (baseline) | ~91% (0.172) | ~1.16 fps | n/a |
| CoreML `ModelFormat=MLProgram` + `RequireStaticInputShapes=1` (FP32 GPU) | **100%** (0.143), max 0.331 | ~1.06 fps (warm chunk ~0.77 fps) | clean |
| CoreML default `NeuralNetwork` + `MLComputeUnits=CPUAndGPU` (FP16 GPU) | **62.5%** (0.167) — **p95 1.02, max 1.08** | ~1.90 fps | clean |

**Conclusions (hard, evidence-backed):**
1. **Global `ModelFormat=MLProgram` fails to compile** — several models (face detector, dynamic input) produce "unbounded dimension" MLProgram errors on Apple MPS → 100% frame-fallback → abort. This is why upstream's 3.7.0 applies MLProgram *selectively per-model*, not globally.
2. Adding **`RequireStaticInputShapes=1`** fixes the compile (dynamic models fall back to CPU) and gives **deterministic FP32, excellent quality (100% <0.4)** — but it is **not faster** than CPU (the CPU fallback + per-frame GPU round-trip for the 128px swapper erase the gain).
3. **`NeuralNetwork`/FP16 GPU is faster (~1.9 fps) but flickers** — 37.5% of frames have wrong identity (cosine up to 1.08). Excluding the ANE (`CPUAndGPU`) is **not** enough; the GPU FP16 path itself corrupts frames.
4. **Net:** on ORT 1.24.3 / macOS-MPS / M4 Max, CoreML EP config alone **cannot deliver both flicker-free and faster-than-CPU.** The FP32 quality path isn't faster; the fast FP16 path flickers. Real speed must come from the 3.7.x processor/model-loading refactor or non-EP changes (chunk-size/model-reload overhead, lighter detector), not an EP one-liner.
5. **Incidental speed lead:** each chunk subprocess pays ~30–40 s fixed model-load overhead; at 59 chunks for the full render that's ~30–40 min of pure reload cost — a CPU-side tuning target (larger chunks vs the silent-death crash risk that motivated 250-frame chunks).

**Action taken:** reverted `facefusion/execution.py` and `facefusion.ini` to the CPU known-good (git diff clean). The working MLProgram-static cache is preserved at `.caches/1.24.3.mlprogram-static.working.bak` if the deterministic (quality-neutral, not-faster) GPU path is ever wanted.

## Open items / uncertainty
- CoreML determinism for *our* model must be verified on Smoke 1 (evaluator measures it directly). If any residual shimmer, add `MLComputeUnits=CPUAndGPU`.
- Speed numbers are estimates; pipeline has CPU-bound stages. Benchmark before/after.
- Reddit was block-limited this session (snippets only); community model-likeness scores are single-tester/anecdotal. Docs.facefusion.io and source-verified claims are authoritative.
- 3.7.x processor rewrite conflicts with the fork's chunking patches — full-upgrade effort lives there, not in the INI.

## Sources (primary)
- ORT CoreML EP: https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html
- MLProgram vs NeuralNetwork determinism teardown: https://ym2132.github.io/ONNX_MLProgram_NN_exploration
- FaceFusion changelog: https://docs.facefusion.io/introduction/changelog
- FaceFusion releases: https://github.com/facefusion/facefusion/releases
- Face-swapper docs: https://docs.facefusion.io/usage/cli-arguments/processors/face-swapper
- Face-masker / selector / detector docs: https://docs.facefusion.io/usage/cli-arguments/
- Enhancer flicker (peer-reviewed): https://arxiv.org/html/2410.11828v1 · https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/03752.pdf
- Apple Silicon FP32≈FP16 CoreML: https://medium.com/@msridharansundaram/i-optimized-ml-inference-on-apple-silicon-for-weeks-the-bottleneck-was-never-the-model-8ac7049a0aa2
