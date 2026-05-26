# FaceFusion 3.6.0 — Models & Settings Reference

**Generated:** 2026-04-28
**Last updated:** 2026-05-26
**Version:** FaceFusion 3.6.0 (`facefusion/metadata.py:7`)
**Hardware target:** Apple M4 Max, 128 GB RAM. Current quality baseline is CPU-only (`execution_providers = cpu`); CoreML remains available for speed experiments.
**Scope:** Every UI control reachable from the localhost dashboard (`python facefusion.py run`) and every model selectable from any UI dropdown.

## How to read this doc

- **Master settings** at the top gate everything below them. Tweak these first; their effects cascade.
- **Per-processor sections** group each processor's models and the settings tied specifically to that processor.
- **Cross-cutting settings** apply across processors (face detection, masking, frame extraction, output creation).
- **Dependency map** shows which settings activate which other settings — useful for planning A/B experiments.
- **Prioritization appendix** picks out the lowest-cost-highest-leverage tweaks.

### Tier scales (consistent across the doc)

- **Speed** — relative *within each processor*: `fast` | `medium` | `slow` | `very slow`. A "fast" face_enhancer is much slower than a "fast" face_detector — speed tiers are intra-processor only.
- **Quality** — relative *within each processor*: `baseline` | `good` | `best`. Anchored against contemporaneous siblings; older models tend to baseline, newer models to best.
- **Memory** — absolute, model + working set: `low` <2 GB | `medium` 2-8 GB | `high` 8-30 GB | `very high` 30+ GB. Empirical observation from the 14,500-frame chunked render: face_swapper + face_enhancer chunks peaked at 87 GB on M4 Max.
- `[needs verification]` flags claims I could not confidently ground in code or in upstream sources. The catalog flagged 13 such models (FaceFusion-native hyperswap variants, several community upscalers, a few community deep_swapper celebrity models).

### Sources of truth

- FaceFusion source tree at `/Users/jordanjones/Documents/facefusion/`. Every processor directory has a `core.py` with `create_static_model_set` defining its models. Every UI control lives under `facefusion/uis/components/`. The argparse surface is `facefusion/program.py`.
- Upstream `facefusion/facefusion` GitHub repo for capability claims.
- Authoritative external sources for underlying model architectures (cited inline where used).

When sources disagree, the FaceFusion source code wins.

---

## Table of contents

1. [Quick reference matrix](#quick-reference-matrix)
2. [Master settings](#master-settings)
3. Per-processor sections
   - [face_swapper](#face_swapper)
   - [face_enhancer](#face_enhancer)
   - [frame_enhancer](#frame_enhancer)
   - [expression_restorer](#expression_restorer)
   - [age_modifier](#age_modifier)
   - [background_remover](#background_remover)
   - [deep_swapper](#deep_swapper)
   - [face_editor](#face_editor)
   - [frame_colorizer](#frame_colorizer)
   - [lip_syncer](#lip_syncer)
   - [face_debugger](#face_debugger)
4. Common-module sections
   - [face_detector](#face_detector)
   - [face_landmarker](#face_landmarker)
   - [face_recognizer](#face_recognizer)
   - [face_classifier](#face_classifier)
   - [face_masker](#face_masker)
   - [voice_extractor](#voice_extractor)
   - [content_analyser](#content_analyser)
5. [Cross-cutting settings](#cross-cutting-settings)
6. [Dependency map](#dependency-map)
7. [Experimentation prioritization](#experimentation-prioritization)
8. [Open questions](#open-questions)

---

## Quick reference matrix

Per-processor headline view. Default model is the value in `facefusion.ini` or the in-code fallback. Speed/quality tiers are *within the processor*.

| Processor | Default model | Speed tier | Quality tier | Memory tier | Verdict |
|---|---|---|---|---|---|
| face_swapper | `inswapper_128_fp16` | fast | good | low | Current Fix E baseline; reduced identity flicker in 30-s smoke versus run-03 |
| face_enhancer | `gfpgan_1.4` (inactive) | medium | best (in 512px tier) | medium | Configured but off in Fix E; re-enable only for A/B smokes |
| frame_enhancer | (off) | — | — | — | Adds 2× to per-frame time; only enable for archive-quality output |
| expression_restorer | `live_portrait` | slow | good | high | Single model option; only enable when needed |
| age_modifier | `styleganex_age` | slow | good | medium | `fran` for 1024px detail at higher cost |
| background_remover | `birefnet_general` | medium | good | medium | `rmbg_2.0` likely best quality (license non-commercial) |
| deep_swapper | (none default) | varies | varies | high | Specialized to specific celebrity identities; not for arbitrary swaps |
| face_editor | `live_portrait` | slow | best | high | Six-model pipeline; expensive but only model option |
| frame_colorizer | `ddcolor` | medium | good | medium | `deoldify_stable` for video temporal consistency |
| lip_syncer | `wav2lip_gan_96` | fast | baseline (96px) | low | Try `edtalk_256` for higher resolution |
| face_debugger | n/a | — | — | low | Visualization only; no models |
| face_detector | `yolo_face` | fast | good | low | `retinaface` if recall matters more than speed |
| face_landmarker | `2dfan4` | medium | best | low | Stable choice; `peppa_wutz` newer alternative |
| face_recognizer | `arcface` | fast | (only option) | low | Single model |
| face_classifier | `fairface` | fast | (only option) | low | Single model |
| face_masker (occluder) | `xseg_1` | fast | good | low | xseg_2/3 negligible quality difference |
| face_masker (parser) | `bisenet_resnet_18` | fast | good | low | resnet_34 marginally better quality |
| voice_extractor | `kim_vocal_2` | medium | good | medium | Used only when lip_syncer is enabled |
| content_analyser | (always all 3) | medium | n/a | low | Currently disabled in this fork (returns False unconditionally — see `settings.md`) |

---

## Master settings

These gate everything below. Tweaking any of these has the broadest impact.

### `processors`

UI: `processors.py:16` (CheckboxGroup). CLI: `--processors`. `facefusion.ini` `[processors]`.

The pipeline is the ordered subset of processors chosen here. Each enabled processor adds a per-frame inference pass. Order matters: face_swapper before face_enhancer makes the enhancer clean up the swap; reversed, the enhancer would be discarded.

- **Type:** list of strings.
- **Choices:** `age_modifier`, `background_remover`, `deep_swapper`, `expression_restorer`, `face_debugger`, `face_editor`, `face_enhancer`, `face_swapper`, `frame_colorizer`, `frame_enhancer`, `lip_syncer`.
- **Current default:** `face_swapper`.
- **Speed impact:** linear in the number of enabled processors. Each adds 30-100% per-frame time on M4 Max.
- **M4 Max note:** memory grows proportionally with active processors. The 87 GB chunk peak observed on the 14,500-frame run-03 render was with `face_swapper + face_enhancer`; current Fix E is lighter because the enhancer is disabled. Adding another processor (e.g., `frame_enhancer`) still needs chunked validation.

### `execution_providers`

UI: `execution.py:17` (CheckboxGroup). `facefusion.ini` `[execution]`.

Ordered list of inference backends. ONNX Runtime tries them in order per session; fallback to CPU if a model isn't supported on the chosen accelerator.

- **Type:** ordered list.
- **Choices:** `cuda`, `tensorrt`, `rocm`, `migraphx`, `coreml`, `openvino`, `qnn`, `directml`, `cpu`. M4 Max only `coreml` and `cpu` are useful.
- **Current default:** `cpu`.
- **Speed impact:** very high. CoreML on Apple Silicon can deliver large speedups over CPU for many face models, but it is no longer the quality default for this fork.
- **Quality impact:** none in principle. In practice, the run-03 flicker diagnosis implicated CoreML FP16 nondeterminism alongside `hyperswap_1c_256` and GFPGAN. Some fp16 variants (notably `inswapper_128_fp16`, `real_esrgan_*_fp16`) are also silently swapped to fp32 on macOS/CoreML in code (`face_swapper/core.py:508-510`, `frame_enhancer/core.py:563-569`).
- **M4 Max note:** the silent worker death class of failure traced back to CoreML provider instability under sustained 12-thread concurrency. Subprocess chunking (see `chunk_size_frames`) bounds that blast radius, but current Fix E avoids CoreML for output quality.

### `execution_thread_count`

UI: `execution_thread_count.py:15` (Slider). `facefusion.ini` `[execution]`.

Number of parallel ThreadPoolExecutor workers in `process_video()`. Each worker holds an active inference session and per-frame buffers.

- **Type:** int.
- **Range:** 1-32, step 1 (`choices.py:155`).
- **Current default:** 12.
- **Speed impact:** diminishing returns above the number of physical cores. M4 Max has 16 cores; 12-16 saturates throughput.
- **Memory impact:** linear with thread count. Per-thread RAM = 5-10 GB on face_swapper+enhancer at 1280×720 input.
- **M4 Max note:** with chunking on, 12 is fine because the chunk subprocess boundary recycles state every 250 frames. With chunking off, drop to 4-6 to bound memory drift across the full render.

### `chunk_size_frames` *(local fork addition)*

CLI: `--chunk-size-frames`. `facefusion.ini` `[execution]`. *Not in upstream.*

Process video in subprocess chunks of N frames. 0 disables chunking and runs in-process. Each chunk subprocess gets a fresh ONNX runtime state and dies cleanly on exit — bounding memory drift and isolating the silent-death failure mode that plagued long renders on this fork. If CoreML is re-enabled for speed experiments, every chunk also gets fresh CoreML provider state.

- **Type:** int.
- **Range:** 0 = disabled; otherwise positive int. Tested at 250.
- **Current default:** 250.
- **Speed impact:** model-load latency once per chunk (~10-20 s on M4 Max). For a 14,500-frame render at 250-frame chunks → 58 chunks × ~15 s = ~15 min total chunking overhead.
- **Quality impact:** none.
- **M4 Max note:** validated end-to-end on this fork's 3.5 h render. Without chunking, the worker died silently around 5-7% with no recoverable diagnostic. With chunking, the same render completed first-try.

### `video_memory_strategy`

UI: `memory.py:18` (Dropdown). `facefusion.ini` `[memory]`.

ONNX Runtime memory arena strategy. Affects how aggressively cached buffers are reused vs. released.

- **Type:** string.
- **Choices:** `strict` (release after each inference) | `moderate` | `tolerant` (keep arenas alive).
- **Current default:** `tolerant`.
- **Speed impact:** `tolerant` is faster (no realloc); `strict` slowest.
- **Memory impact:** `tolerant` highest peak; `strict` lowest.
- **M4 Max note:** with chunking on, `tolerant` is safe because per-chunk drift dies with the subprocess. With chunking off and a long render, `moderate` is safer.

### `system_memory_limit`

UI: `memory.py:23` (Slider). `facefusion.ini` `[memory]`.

Caps the process's `RLIMIT_DATA` (POSIX) or working set (Windows). 0 = no cap.

- **Type:** int (GB).
- **Range:** 0-128, step 4 (`choices.py:156`).
- **Current default:** 0 (unset).
- **Memory impact:** if set, the worker dies on `MemoryError` rather than swapping. Useful as a guardrail; not necessary on a 128 GB machine.

### `output_video_preset`

UI: `output_options.py:84` (Dropdown). `facefusion.ini` `[output_creation]`.

x264/x265/x266 encoder preset. Direct trade-off between encode speed and output size at fixed quality.

- **Type:** string.
- **Choices:** `ultrafast | superfast | veryfast | faster | fast | medium | slow | slower | veryslow`.
- **Current default:** `slow`.
- **Speed impact:** merge phase only (~2 min on the 14,500-frame render at `slow`).
- **Quality impact:** at fixed CRF, `slow` produces ~10-15% smaller files than `medium`. Diminishing returns past `slow`; `veryslow` is rarely worth 2× the merge time.

---

## face_swapper

Source: [`facefusion/processors/modules/face_swapper/core.py`](../facefusion/processors/modules/face_swapper/core.py)

Replaces target faces with a source identity, frame by frame. The pipeline: face detect → align (using a `template`) → embedding (ArcFace family) → swap network → blend.

### Models

| Key | Year | License | Input | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|---|
| `inswapper_128` | 2023 | Non-Commercial (InsightFace) | 128² | fast | good | low | Industry default; widely used baseline. ArcFace-128 embedding. |
| `inswapper_128_fp16` | 2023 | Non-Commercial | 128² | fast | good | low | **Current Fix E default in `facefusion.ini:96`.** Half-precision variant; auto-swapped to `inswapper_128` only if CoreML/macOS is re-enabled (`core.py:508-510`). |
| `blendswap_256` | 2023 | Non-Commercial (mapooon) | 256² | fast | good | low | Blending-based swap with StyleGAN-like generator. Lightweight. |
| `simswap_256` | 2020 | Non-Commercial (neuralchen) | 256² | medium | baseline | medium | Older but proven; ArcFace-112 embedding. |
| `simswap_unofficial_512` | 2020 | Non-Commercial | 512² | slow | good | medium | Higher-detail SimSwap; unofficial 512px training. |
| `ghost_1_256` | 2022 | Apache-2.0 (ai-forever) | 256² | medium | good | medium | One-shot swap pipeline; permissive license. |
| `ghost_2_256` | 2022 | Apache-2.0 | 256² | medium | good | medium | Sibling variant; minor architectural tweaks vs ghost_1. |
| `ghost_3_256` | 2022 | Apache-2.0 | 256² | medium | best (in Ghost family) | medium | Latest of three ai-forever variants. |
| `hififace_unofficial_256` | 2021 | Unknown | 256² | medium | good | medium | High-fidelity preserving fine detail; unofficial implementation. |
| `uniface_256` | 2022 | Unknown | 256² | medium | good | medium | Pose-tolerant unified swap; FFHQ template. |
| `hyperswap_1a_256` | 2025 | ResearchRAIL (FaceFusion) | 256² | medium | best | medium | FF-native; speed-leaning of three variants. `[needs verification]` against open benchmarks. |
| `hyperswap_1b_256` | 2025 | ResearchRAIL | 256² | medium | best | medium | Middle of the FF-native trio. |
| `hyperswap_1c_256` | 2025 | ResearchRAIL | 256² | medium | best | medium | Quality-leaning of the trio. Former run-03 default; removed from current baseline after flicker diagnosis. |

**Architecture lineage citations**: GHOST family from [ai-forever/ghost](https://github.com/ai-forever/ghost) (IEEE Access 2022). Hyperswap is FaceFusion-native (no public paper as of 2026-04). InsightFace family at [insightface](https://github.com/deepinsight/insightface). SimSwap from [neuralchen/SimSwap](https://github.com/neuralchen/SimSwap).

### Settings

- **`face_swapper_model`** — Dropdown (`face_swapper_options.py:23`). Picks the model from the table above. **Activates only when `face_swapper` is in `processors`**.
- **`face_swapper_pixel_boost`** — Dropdown (`face_swapper_options.py:29`). Choices: `128x128 | 256x256 | 384x384 | 512x512 | 768x768 | 1024x1024`. The detected face is upsampled to this resolution before being fed to the swap model — recovers detail when the source face crop would otherwise be smaller than the model's native input. Currently `512x512` in the ini. Going higher (768 or 1024) recovers more detail at ~1.5-2× per-frame cost.
- **`face_swapper_weight`** — Slider, float (`face_swapper_options.py:35`). Range `face_swapper_weight_range`. Visibility conditional on the selected model exposing `has_weight_input()`. Blends the swap output with the original face; 0 = original, 1 = full swap. Use 0.7-0.85 to soften over-aggressive swaps.

---

## face_enhancer

Source: [`facefusion/processors/modules/face_enhancer/core.py`](../facefusion/processors/modules/face_enhancer/core.py)

Restores and sharpens swapped or otherwise degraded faces. Blind face restoration: the model takes a face crop and outputs a cleaner version. Critical for hiding seams left by face_swapper.

### Models

| Key | Year | License | Input | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|---|
| `codeformer` | 2022 | S-Lab-1.0 (sczhou) | 512² | medium | good | medium | Transformer + codebook. Robust to unaligned input, good for whole-image restoration. |
| `gfpgan_1.2` | 2022 | Apache-2.0 (TencentARC) | 512² | medium | good | medium | Sharper than 1.3 but slightly less natural skin tone. |
| `gfpgan_1.3` | 2022 | Apache-2.0 | 512² | medium | good | medium | More natural skin, slight softness. |
| `gfpgan_1.4` | 2022 | Apache-2.0 | 512² | medium | best (in GFPGAN) | medium | Configured in `facefusion.ini:93` but inactive unless `face_enhancer` is added to `processors`. Best of the three GFPGAN variants. |
| `gpen_bfr_256` | 2021 | Non-Commercial (yangxy) | 256² | fast | baseline | low | Lowest cost. Beautification-leaning. |
| `gpen_bfr_512` | 2021 | Non-Commercial | 512² | medium | good | medium | Mid-tier GPEN. |
| `gpen_bfr_1024` | 2021 | Non-Commercial | 1024² | slow | best (high-res) | high | Doubled detail vs 512. ~2× per-frame cost. |
| `gpen_bfr_2048` | 2021 | Non-Commercial | 2048² | very slow | best (extreme) | high | 4 megapixel output. Mostly impractical for video. |
| `restoreformer_plus_plus` | 2022 | Apache-2.0 (wzhouxiff) | 512² | medium | good | medium | Transformer-based; Apache alternative to GFPGAN. `[needs verification]` for relative quality. |

**Architecture lineage**: GFPGAN from [TencentARC/GFPGAN](https://github.com/TencentARC/GFPGAN) (37k+ stars). CodeFormer from [sczhou/CodeFormer](https://github.com/sczhou/CodeFormer) (NeurIPS 2022). GPEN from [yangxy/GPEN](https://github.com/yangxy/GPEN). RestoreFormer++ from [wzhouxiff/RestoreFormerPlusPlus](https://github.com/wzhouxiff/RestoreFormerPlusPlus).

### Settings

- **`face_enhancer_model`** — Dropdown (`face_enhancer_options.py:23`). Picks model from the table.
- **`face_enhancer_blend`** — Slider, int 0-100 (`face_enhancer_options.py:29`). Blend percentage of enhanced output over original. Configured at 80 but inactive in Fix E because `face_enhancer` is off. If re-enabled, 60-85 is the likely tuning range to avoid the over-restored "porcelain" look that 100 produces.
- **`face_enhancer_weight`** — Slider, float (`face_enhancer_options.py:37`). Visibility conditional on `module.has_weight_input()`. Some models (e.g., `codeformer`) accept a fidelity-vs-quality weight; this slider is hidden when the chosen model doesn't.

---

## frame_enhancer

Source: [`facefusion/processors/modules/frame_enhancer/core.py`](../facefusion/processors/modules/frame_enhancer/core.py)

Whole-frame super-resolution. Upscales the merged frame, not the face crop. Adds 2× or more to per-frame time and is the most common cause of memory blowups. Off by default — only enable for archive-quality output.

### Models

| Key | Year | License | Scale | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|---|
| `real_esrgan_x2` | 2021 | BSD-3-Clause (xinntao) | 2× | medium | good | medium | Industry-standard 2× upscaler. |
| `real_esrgan_x2_fp16` | 2021 | BSD-3-Clause | 2× | medium | good | low | Half-precision. **Auto-swapped to fp32 on CoreML/macOS** (`core.py:563-569`). |
| `real_esrgan_x4` | 2021 | BSD-3-Clause | 4× | slow | good | high | Standard 4× upscaler. |
| `real_esrgan_x4_fp16` | 2021 | BSD-3-Clause | 4× | slow | good | medium | fp16 fallback to fp32 on CoreML. |
| `real_esrgan_x8` | 2021 | BSD-3-Clause | 8× | very slow | good | very high | 64× area increase. Rarely used at video scale. |
| `real_esrgan_x8_fp16` | 2021 | BSD-3-Clause | 8× | very slow | good | high | fp16 fallback on CoreML. |
| `real_hatgan_x4` | 2023 | Apache-2.0 (XPixelGroup) | 4× | slow | best | high | Hybrid Attention Transformer. Newer; permissive license. |
| `clear_reality_x4` | 2023 | Non-Commercial (Kim2091) | 4× | slow | good | medium | Community-tuned for general-purpose clarity. |
| `face_dat_x4` | 2023 | CC-BY-4.0 (Helaman) | 4× | slow | best (face-tuned) | medium | DAT (Dual Aggregation Transformer); face-specialized. |
| `nomos8k_sc_x4` | 2023 | CC-BY-4.0 (Phhofm) | 4× | slow | good | medium | Community-trained; CC-BY permissive. |
| `real_web_photo_x4` | 2024 | CC-BY-4.0 (Helaman) | 4× | slow | good | medium | Tuned for web/social-grade source imagery. |
| `realistic_rescaler_x4` | 2023 | WTFPL (Mutin Choler) | 4× | slow | good | medium | Realism-leaning community model. |
| `remacri_x4` | 2021 | Non-Commercial (FoolhardyVEVO) | 4× | slow | good | medium | Long-popular community upscaler. |
| `siax_x4` | 2021 | WTFPL (NMKD) | 4× | slow | good | medium | NMKD's classic upscaler. |
| `span_kendata_x4` | 2024 | Non-Commercial (terrainer) | 4× | slow | good | medium | SPAN architecture; 2024 community variant. |
| `swin2_sr_x4` | 2022 | Apache-2.0 (mv-lab) | 4× | slow | good | medium | Swin Transformer V2 SR. |
| `tghq_face_x8` | 2019 | GPL-3.0 (TorrentGuy) | 8× | very slow | baseline | high | Older 8× face-specific upscaler. |
| `ultra_sharp_x4` | 2021 | Non-Commercial (Kim2091) | 4× | slow | good | medium | Sharpness-leaning. |
| `ultra_sharp_2_x4` | 2025 | Non-Commercial (Kim2091) | 4× | slow | best | high | 2025 successor. Larger receptive field. |

**Architecture lineage**: Real-ESRGAN from [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN). HAT from [XPixelGroup/HAT](https://github.com/XPixelGroup/HAT). SwinIR/Swin2SR from [mv-lab/swin2sr](https://github.com/mv-lab/swin2sr). The community upscalers (Kim2091, Phhofm, Helaman, NMKD) are documented at [openmodeldb.info](https://openmodeldb.info).

### Settings

- **`frame_enhancer_model`** — Dropdown (`frame_enhancer_options.py:21`).
- **`frame_enhancer_blend`** — Slider, int 0-100 (`frame_enhancer_options.py:27`). Blend the upscaled frame with the original at the original frame's resolution. 80-100 is typical.

---

## expression_restorer

Source: [`facefusion/processors/modules/expression_restorer/core.py`](../facefusion/processors/modules/expression_restorer/core.py)

Restores or transfers facial expression after face_swapper. Commonly used to keep mouth/eye motion consistent when the swap network has flattened the expression.

### Models

| Key | Year | License | Architecture | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|---|
| `live_portrait` | 2024 | MIT (KwaiVGI) | Multi-module pipeline (feature, motion, generator) | slow | good | high | Sole option. Three sub-models loaded per inference; memory-hungry. |

**Architecture lineage**: Live Portrait from [KwaiVGI/LivePortrait](https://github.com/KwaiVGI/LivePortrait) (2024).

### Settings

- **`expression_restorer_model`** — Dropdown (`expression_restorer_options.py:23`). Single option.
- **`expression_restorer_factor`** — Slider, float (`expression_restorer_options.py:29`). Range from `expression_restorer_factor_range`. How strongly to apply restored expression. 0 = unchanged, 1 = full restoration.
- **`expression_restorer_areas`** — CheckboxGroup (`expression_restorer_options.py:37`). Choices typically include eye and mouth regions. Tuning which areas the restoration touches.

---

## age_modifier

Source: [`facefusion/processors/modules/age_modifier/core.py`](../facefusion/processors/modules/age_modifier/core.py)

Shifts perceived age of the face. Requires both swap and identity preservation; slow.

### Models

| Key | Year | License | Input | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|---|
| `fran` | 2024 | MIT (ry-lu) | 1024² | very slow | best | high | High-resolution age modifier. Newer (2024). MIT permissive. |
| `styleganex_age` | 2023 | S-Lab-1.0 (williamyang1991) | 256² or 384² | slow | good | medium | StyleGAN-extended age modifier; ICCV 2023. Handles unaligned faces. |

**Architecture lineage**: StyleGANEX from [williamyang1991/StyleGANEX](https://github.com/williamyang1991/StyleGANEX) (ICCV 2023). FRAN is newer and less documented externally; `[needs verification]` for benchmark positioning.

### Settings

- **`age_modifier_model`** — Dropdown (`age_modifier_options.py:21`).
- **`age_modifier_direction`** — Slider, float (`age_modifier_options.py:29`). Range `age_modifier_direction_range`. Negative = younger, positive = older. Magnitude controls how dramatic the shift is.

---

## background_remover

Source: [`facefusion/processors/modules/background_remover/core.py`](../facefusion/processors/modules/background_remover/core.py)

Segments the foreground subject and replaces the background with a configurable color (with optional despill correction). Useful for green-screen workflows; not face-specific.

### Models (15)

| Key | Year | License | Input | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|---|
| `ben_2` | 2025 | MIT (PramaLLC) | 1024² | medium | best | medium | Latest general-purpose; permissive MIT. |
| `birefnet_general` | 2024 | MIT (ZhengPeng7) | 1024² | medium | best | medium | Bilateral Reference; high-quality general matting. |
| `birefnet_portrait` | 2024 | MIT | 1024² | medium | best | medium | BiRefNet trained for portraits specifically. |
| `corridor_key_1024` | 2025 | Non-Commercial (nikopueringer) | 1024² | medium | best | medium | High-resolution keying; non-commercial. |
| `corridor_key_2048` | 2025 | Non-Commercial | 2048² | slow | best | high | Doubled resolution; doubled cost. |
| `isnet_general` | 2022 | Apache-2.0 (xuebinqin) | 1024² | medium | good | medium | U-2-Net family salient object detection. |
| `modnet` | 2020 | Apache-2.0 (ZHKKKe) | 512² | fast | good | low | Mobile-optimized; lowest cost. |
| `ormbg` | 2024 | Apache-2.0 (schirrmacher) | 1024² | medium | good | medium | Open-replacement for non-commercial BG removers. |
| `rmbg_1.4` | 2023 | Non-Commercial (Bria) | 1024² | medium | good | medium | Bria's first popular open release. |
| `rmbg_2.0` | 2024 | Non-Commercial | 1024² | medium | best | medium | Bria's 2024 update; widely cited as SOTA among open BG removers. |
| `silueta` | 2022 | Apache-2.0 (Kikedao) | 320² | fast | good | low | Lower cost; compact U-Net. |
| `u2net_cloth` | 2021 | MIT (levindabhi) | 768² | medium | good | medium | Specialized for clothing edges. |
| `u2net_general` | 2020 | Apache-2.0 (xuebinqin) | 320² | fast | good | low | Original U-2-Net (Pattern Recognition 2020 best paper). |
| `u2net_human` | 2021 | Apache-2.0 | 320² | fast | good | low | U-2-Net trained on human portraits. |
| `u2netp` | 2021 | Apache-2.0 | 320² | fast | baseline | low | "Pico" U-2-Net; smallest variant. |

**Architecture lineage**: U-2-Net from [xuebinqin/U-2-Net](https://github.com/xuebinqin/U-2-Net) (Pattern Recognition 2020 best paper). BiRefNet from [ZhengPeng7/BiRefNet](https://github.com/ZhengPeng7/BiRefNet). RMBG from Bria's [HF model card](https://huggingface.co/briaai/RMBG-2.0). MODNet from [ZHKKKe/MODNet](https://github.com/ZHKKKe/MODNet).

### Settings

- **`background_remover_model`** — Dropdown (`background_remover_options.py:42`).
- **`background_remover_fill_color`** — 4× Number widgets, RGBA each 0-255 (`background_remover_options.py:50-77`). The color the background is replaced with. Use `(0, 255, 0, 255)` for chroma-key green.
- **`background_remover_despill_color`** — 4× Number widgets, RGBA each 0-255 (`background_remover_options.py:81-108`). Color subtracted to fix spill (foreground edges contaminated by background light). Set to the same as fill_color for basic despill.

---

## deep_swapper

Source: [`facefusion/processors/modules/deep_swapper/core.py`](../facefusion/processors/modules/deep_swapper/core.py)

DeepFaceLab-format `.dfm` swappers. Each model is trained on a *specific identity* — not a generic face swapper. Currently 86 models across 5 community providers, plus user-supplied custom models from `.assets/models/custom/`.

Use this only when you specifically want one of the trained celebrity identities. For arbitrary swaps, use `face_swapper` instead.

### Provider summary

| Provider | Model count | Download scope | Notes |
|---|---|---|---|
| `druuzil` | 76 | full | Largest catalog. Sizes 224-448 px. |
| `iperov` | 24 | lite + full | Default lite-scope provider. Includes `keanu_reeves_320`. |
| `jen` | 8 | full | Smaller curated set. |
| `mats` | 16 | full | Mid-size set. |
| `rumateus` | 38 | full | Largest after druuzil. Sizes 224 px. |
| `custom/` | n | any | User-trained `.dfm` files dropped into `.assets/models/custom/`. |

A representative sample of the 86 models (full list in `core.py:29-246`): `druuzil/elon_musk_320`, `druuzil/scarlett_johansson_320`, `iperov/keanu_reeves_320`, `iperov/bruce_willis_224`, `rumateus/emma_stone_224`, `mats/jim_carrey_320`. **`[needs verification]`** for relative quality across providers — community evaluation is sparse.

### Settings

- **`deep_swapper_model`** — Dropdown (`deep_swapper_options.py:21`). Lists every available model in the form `provider/identity_size`.
- **`deep_swapper_morph`** — Slider, int (`deep_swapper_options.py:27`). Range `deep_swapper_morph_range`. Visibility conditional on `module.has_morph_input()` — only certain DFM models support morph blending. Controls how much of the source identity blends with the target's underlying features.

---

## face_editor

Source: [`facefusion/processors/modules/face_editor/core.py`](../facefusion/processors/modules/face_editor/core.py)

Direct manipulation of facial features (eye gaze, mouth shape, head pose, etc.) without swapping identity. Built on Live Portrait's six-module pipeline. Heavyweight — six model loads per frame.

### Models

| Key | Year | License | Architecture | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|---|
| `live_portrait` | 2024 | MIT (KwaiVGI) | Six-module: feature extractor, motion extractor, eye retargeter, lip retargeter, stitcher, generator | slow | best | high | Sole option. Real-time on small frames; multi-second per frame at 1080p. |

### Settings (15)

All sliders, all gated by `'face_editor' in processors`. Source: `face_editor_options.py:53-157`. Each takes a float in a model-specific range from `face_editor_choices`.

| Setting | Effect |
|---|---|
| `face_editor_eyebrow_direction` | Eyebrow lift (positive = up) |
| `face_editor_eye_gaze_horizontal` | Gaze left/right |
| `face_editor_eye_gaze_vertical` | Gaze up/down |
| `face_editor_eye_open_ratio` | Squint vs wide-eyed |
| `face_editor_lip_open_ratio` | Mouth open/closed |
| `face_editor_mouth_grim` | Grimace amount |
| `face_editor_mouth_pout` | Pout/puff |
| `face_editor_mouth_purse` | Pursed lips |
| `face_editor_mouth_smile` | Smile intensity |
| `face_editor_mouth_position_horizontal` | Mouth shifted left/right |
| `face_editor_mouth_position_vertical` | Mouth shifted up/down |
| `face_editor_head_pitch` | Head nod |
| `face_editor_head_yaw` | Head turn left/right |
| `face_editor_head_roll` | Head tilt |

All 15 settings are independent dials; combinations stack.

---

## frame_colorizer

Source: [`facefusion/processors/modules/frame_colorizer/core.py`](../facefusion/processors/modules/frame_colorizer/core.py)

Adds color to grayscale frames. Five models from two architectural families.

### Models

| Key | Year | License | Family | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|---|
| `ddcolor` | 2023 | Apache-2.0 (piddnad) | Diffusion-based DDColor | medium | good | medium | Modern; permissive license. |
| `ddcolor_artistic` | 2023 | Apache-2.0 | DDColor variant | medium | good | medium | More saturated/vivid. |
| `deoldify` | 2022 | MIT (jantic) | NoGAN | medium | good | medium | Original DeOldify. |
| `deoldify_artistic` | 2022 | MIT | NoGAN, artistic-tuned | medium | good | medium | Stylized output. |
| `deoldify_stable` | 2022 | MIT | NoGAN, stability-tuned | medium | good | medium | Tuned for video temporal consistency — fewest flicker artifacts. |

**Architecture lineage**: DeOldify from [jantic/DeOldify](https://github.com/jantic/DeOldify) (archived Oct 2024 after MIT release). DDColor from [piddnad/DDColor](https://github.com/piddnad/DDColor).

### Settings

- **`frame_colorizer_model`** — Dropdown (`frame_colorizer_options.py:23`).
- **`frame_colorizer_size`** — Dropdown (`frame_colorizer_options.py:29`). Choices from `frame_colorizer_choices.frame_colorizer_sizes`. Internal processing resolution.
- **`frame_colorizer_blend`** — Slider, int 0-100 (`frame_colorizer_options.py:35`). Blend percentage of colorized over original.

---

## lip_syncer

Source: [`facefusion/processors/modules/lip_syncer/core.py`](../facefusion/processors/modules/lip_syncer/core.py)

Drives lip motion from an audio track. Requires `voice_extractor` to clean the audio source first. Three models.

### Models

| Key | Year | License | Input | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|---|
| `wav2lip_96` | 2020 | Non-Commercial (Rudrabha) | 96² | fast | baseline | low | Original Wav2Lip; ACM Multimedia 2020. Soft mouth output. |
| `wav2lip_gan_96` | 2020 | Non-Commercial | 96² | fast | good | low | GAN-discriminator variant; sharper teeth/lips. |
| `edtalk_256` | 2024 | Apache-2.0 (tanshuai0219) | 256² | medium | best | medium | Newer; 256² resolution; permissive license. |

**Architecture lineage**: Wav2Lip from [Rudrabha/Wav2Lip](https://github.com/Rudrabha/Wav2Lip) (ACM MM 2020). EDTalk from [tanshuai0219/EDTalk](https://github.com/tanshuai0219/EDTalk).

### Settings

- **`lip_syncer_model`** — Dropdown (`lip_syncer_options.py:21`).
- **`lip_syncer_weight`** — Slider, float (`lip_syncer_options.py:27`). Range from `lip_syncer_weight_range`. Blends synced lips with original.

---

## face_debugger

Source: `facefusion/processors/modules/face_debugger/`

Visualization-only processor. Draws bounding boxes, landmarks, mask overlays, and similarity metrics directly onto frames. No models. Use to diagnose detection or alignment issues.

### Settings

- **`face_debugger_items`** — CheckboxGroup (`face_debugger_options.py:17`). Choices from `face_debugger_choices.face_debugger_items` — typically `bounding-box`, `face-landmark-5`, `face-landmark-68`, `face-mask`, `face-detector-score`, `face-landmarker-score`, `face-distance`, `age`, `gender`, `race`. Toggle which overlays are drawn.

---

## face_detector

Source: [`facefusion/face_detector.py`](../facefusion/face_detector.py)

Common module (not a processor). Used by every workflow that needs faces. Detects faces and 5-point facial landmarks.

### Models

| Key | Year | License | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|
| `retinaface` | 2020 | Non-Commercial (InsightFace) | medium | best (recall) | low | Two-stage with FPN. Best recall on small faces. |
| `scrfd` | 2021 | Non-Commercial | fast | good | low | Single-stage efficient; designed for production. |
| `yolo_face` | 2022 | GPL-3.0 (derronqi) | fast | good | low | YOLO-architecture; permissive enough for non-commercial. |
| `yunet` | 2023 | MIT (OpenCV) | fast | good | low | Smallest model; OpenCV native. MIT permissive. |
| `many` | n/a | n/a | slow | best | low | Special: runs `retinaface + scrfd + yolo_face + yunet` and unions detections. Slowest, highest recall. |

**Architecture lineage**: RetinaFace and SCRFD from [InsightFace](https://github.com/deepinsight/insightface). YOLOFace from [derronqi/yolov8-face](https://github.com/derronqi/yolov8-face). YuNet from [opencv/opencv_zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet).

### Settings

- **`face_detector_model`** — Dropdown (`face_detector.py:35`). Picks model.
- **`face_detector_size`** — Dropdown (`face_detector.py:40`). Per-model choices from `choices.py:7-14`. Inference resolution: `160x160 | 320x320 | 480x480 | 512x512 | 640x640` (retinaface/scrfd) or fixed `640x640` (yolo_face/yunet/many). Lower = faster, fewer detections.
- **`face_detector_margin`** — Slider, int 0-100 (`face_detector.py:41`). Pixels of margin around the detected box. Higher value catches more peripheral context for downstream alignment but slows the swap if it makes the face crop bigger.
- **`face_detector_angles`** — CheckboxGroup, choices `0 90 180 270` (`face_detector.py:48`). Rotations to scan. Currently `0 90 180 270` in the ini — catches sideways/upside-down faces. Drop to `0` only if every face is upright; saves ~30% detector time.
- **`face_detector_score`** — Slider, float 0-1 step 0.05 (`face_detector.py:53`). Confidence threshold. Lower = more detections (and more false positives). 0.5 is the standard.

---

## face_landmarker

Source: [`facefusion/face_landmarker.py`](../facefusion/face_landmarker.py)

Common module. 68-point facial landmarks for alignment.

### Models

| Key | Year | License | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|
| `2dfan4` | 2018 | MIT (breadbread1984) | medium | best | low | VGG-based 68-point. Mature and stable. |
| `peppa_wutz` | 2023 | Apache-2.0 (unknown vendor) | medium | good | low | Newer 68-point detector. |
| `fan_68_5` | 2024 | OpenRAIL-M (FaceFusion) | fast | n/a | low | Utility model: converts 68-point to 5-point fallback. Not selectable as primary. |

### Settings

- **`face_landmarker_model`** — Dropdown (`face_landmarker.py:19`).
- **`face_landmarker_score`** — Slider, float 0-1 step 0.05 (`face_landmarker.py:24`). Confidence threshold for accepting a landmark prediction.

---

## face_recognizer

Source: [`facefusion/face_recognizer.py`](../facefusion/face_recognizer.py)

Common module. Generates 512-dim face embeddings for identity matching (used by `face_selector_mode = reference`).

### Models

| Key | Year | License | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|
| `arcface` | 2018 | Non-Commercial (InsightFace) | fast | n/a | low | Sole option. ArcFace `w600k_r50` (ResNet50, 600k IDs). Industry-standard embedding space. |

### Settings

None directly. The output drives `face_selector_mode = reference` and `reference_face_distance`.

---

## face_classifier

Source: [`facefusion/face_classifier.py`](../facefusion/face_classifier.py)

Common module. Classifies gender, age range (9 buckets), and race/ethnicity (7 categories). Used by `face_selector` filter modes.

### Models

| Key | Year | License | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|
| `fairface` | 2021 | CC-BY-4.0 (dchen236) | fast | n/a | low | Sole option. Fairness-aware multi-task classifier. |

**Architecture lineage**: FairFace from [dchen236/FairFace](https://github.com/dchen236/FairFace).

### Settings

No direct setting. Output is consumed by `face_selector_gender`, `face_selector_race`, `face_selector_age_start/end`.

---

## face_masker

Source: [`facefusion/face_masker.py`](../facefusion/face_masker.py)

Common module. Generates per-face masks combining: a box mask (rectangular padding around landmarks), an occlusion mask (XSeg detects hands/glasses), and a region mask (BiSeNet parses face into skin/eye/mouth/etc. regions).

### Models — face_occluder

| Key | Year | License | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|
| `xseg_1` | 2021 | GPL-3.0 (DeepFaceLab) | fast | good | low | DFL's first XSeg occluder. |
| `xseg_2` | 2021 | GPL-3.0 | fast | good | low | Sibling variant. |
| `xseg_3` | 2021 | GPL-3.0 | fast | good | low | Sibling variant. Negligible quality difference vs xseg_1. |

### Models — face_parser

| Key | Year | License | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|
| `bisenet_resnet_18` | 2024 | MIT (yakhyo) | fast | good | low | BiSeNet with ResNet-18 backbone. Faster. |
| `bisenet_resnet_34` | 2024 | MIT | fast | best | low | ResNet-34 backbone. Marginally better region accuracy. |

### Settings

- **`face_occluder_model`** — Dropdown (`face_masker.py:42`).
- **`face_parser_model`** — Dropdown (`face_masker.py:47`).
- **`face_mask_types`** — CheckboxGroup `box | region | area` (`face_masker.py:52`). The mask sources to combine. Currently `box occlusion region` per the ini (note: ini lists `occlusion` which is parsed as the occluder pathway).
- **`face_mask_areas`** — CheckboxGroup (`face_masker.py:57`). Visibility: `'area' in face_mask_types`. Choices: `upper-face | lower-face | mouth` per `choices.py:24-29`. Coarse face-region selection.
- **`face_mask_regions`** — CheckboxGroup (`face_masker.py:63`). Visibility: `'region' in face_mask_types`. Choices: `skin | left-eyebrow | right-eyebrow | left-eye | right-eye | glasses | nose | mouth | upper-lip | lower-lip` per `choices.py:30-42`. Fine-grained region selection from BiSeNet.
- **`face_mask_blur`** — Slider, float 0-1 step 0.05 (`face_masker.py:69`). Visibility: `'box' in face_mask_types`. Edge softness for the box mask. Higher = softer blend.
- **`face_mask_padding`** — 4× Sliders, int 0-100 each (`face_masker.py:79-107`). Top, right, bottom, left padding for the box mask in pixels. Visibility: `'box' in face_mask_types`.

---

## voice_extractor

Source: [`facefusion/voice_extractor.py`](../facefusion/voice_extractor.py)

Common module. Extracts vocal track from mixed audio. Used by `lip_syncer` to clean its input.

### Models

| Key | Year | License | Speed | Quality | Memory | Niche |
|---|---|---|---|---|---|---|
| `kim_vocal_1` | 2023 | Non-Commercial (KimberleyJensen) | medium | good | medium | First Kim Vocal release. |
| `kim_vocal_2` | 2023 | Non-Commercial | medium | best | medium | Updated; cleaner separation. |
| `uvr_mdxnet` | 2023 | MIT (Anjok07) | medium | good | medium | Ultimate Vocal Remover MDX-Net. MIT permissive alternative. |

**Architecture lineage**: UVR MDX-Net from [Anjok07/ultimatevocalremovergui](https://github.com/Anjok07/ultimatevocalremovergui). Kim Vocal models distributed via UVR ecosystem.

### Settings

- **`voice_extractor_model`** — Dropdown (`voice_extractor.py:17`). Visibility: `is_video(target_path)`.

---

## content_analyser

Source: [`facefusion/content_analyser.py`](../facefusion/content_analyser.py)

Common module. NSFW gate. Three classifiers vote; 2-of-3 agreement triggers a refusal.

### Models — all three always loaded

| Key | Year | License | Input | Memory | Niche |
|---|---|---|---|---|---|
| `nsfw_1` | 2024 | Apache-2.0 (EraX) | 640² | low | YOLO-based detector. |
| `nsfw_2` | 2024 | Apache-2.0 (Marqo) | 384² | low | Lightweight classifier. |
| `nsfw_3` | 2025 | MIT (Freepik) | 448² | low | CLIP-aligned classifier. |

### Status on this fork

**Disabled.** `content_analyser.py:analyse_frame` was patched to return `False` unconditionally. See `settings.md` for rationale. The three classifiers still load on startup (no harm) but their verdict is not consulted.

### Settings

None — gating is automatic and binary.

---

## Cross-cutting settings

Settings that don't belong to any single processor.

### `[paths]`

| Key | Type | Description |
|---|---|---|
| `target_path` | string | Input video or image. Settable via UI File picker (`target.py:23`). |
| `source_paths` | list | Source faces/audios. Multi-file picker (`source.py:23`). |
| `output_path` | string | Output file. Must match `target_path`'s extension (.mov ↔ .mov, .mp4 ↔ .mp4) or the run errors out at validation with `match the target and output extension!`. |
| `temp_path` | string | Where extracted frames live mid-render. Default = system tempdir. |
| `jobs_path` | string | Where job state lives. Default = `.jobs/`. |

### `[face_selector]`

| Key | Type | UI | Description |
|---|---|---|---|
| `face_selector_mode` | dropdown | `face_selector.py:53` | `one | many | reference`. `one` = swap only the most prominent face. `many` = swap every detected face. `reference` = swap only faces matching a reference embedding (gates `reference_face_*` settings). Currently `many`. |
| `face_selector_order` | dropdown | `face_selector.py:61` | Order in which detected faces are processed. Choices from `choices.py:18`. |
| `face_selector_gender` | dropdown | `face_selector.py:66` | Filter swap by gender (uses face_classifier). `none` = no filter. |
| `face_selector_race` | dropdown | `face_selector.py:71` | Filter by race. `none` = no filter. |
| `face_selector_age_start` / `_age_end` | range slider | `face_selector.py:77-79` | Age window for swap eligibility. |
| `reference_face_position` | gallery selection | `face_selector.py:176` | Which detected face to lock onto. Visibility: `face_selector_mode == 'reference'`. |
| `reference_face_distance` | slider, float 0-1 | `face_selector.py:86` | Embedding-distance threshold for matching the reference. Lower = stricter match. Currently 1.0 (effectively any face matches). Visibility: `face_selector_mode == 'reference'`. |
| `reference_frame_number` | slider | `preview_options.py:32` | Which frame to capture the reference embedding from. Visibility: `is_video(target_path)`. |

### `[frame_extraction]`

| Key | Type | Description |
|---|---|---|
| `trim_frame_start` / `trim_frame_end` | range slider (`trim_frame.py:32`) | Trim source video to a frame range before processing. |
| `temp_frame_format` | dropdown (`temp_frame.py:17`) | Choices: `bmp | jpeg | png` typically. Format of extracted frames on disk. PNG is lossless, BMP fastest write, JPEG smallest. |
| `keep_temp` | checkbox (`common_options.py:19`) | Keep extracted/processed temp frames after the run. Useful for re-processing without re-extracting. |

### `[output_creation]` (video-only fields hidden when `target_path` is an image; image fields hidden when video)

| Key | Type | Range | Description |
|---|---|---|---|
| `output_image_quality` | slider, int | 0-100 | JPEG quality for image output. |
| `output_image_scale` | slider, float | 0.25-8.0 step 0.25 | Output image scale relative to input. |
| `output_audio_encoder` | dropdown | from `choices.output_audio_encoders` | Audio codec. |
| `output_audio_quality` | slider, int | 0-100 | Audio bitrate index. |
| `output_audio_volume` | slider, int | 0-100 | Output audio volume. 0 = mute. |
| `output_video_encoder` | dropdown | `libx264`, `libx265`, `libvpx-vp9`, etc. (from `choices.output_video_encoders`) | Video codec. |
| `output_video_preset` | dropdown | x264 presets (see master settings above) | |
| `output_video_quality` | slider, int | 0-51 | CRF value. Lower = better quality, larger file. 18-23 typical. |
| `output_video_scale` | slider, float | 0.25-8.0 step 0.25 | Output resolution multiplier. |
| `output_video_fps` | slider, float | 1-60 | Output frame rate. Lower than source FPS = drops frames. |

### `[uis]`

| Key | Type | Description |
|---|---|---|
| `ui_workflow` | dropdown (`ui_workflow.py:15`) | `instant_runner | job_runner | job_manager`. Picks which workflow panel is visible. |
| `open_browser` | bool (CLI flag, no UI control) | Auto-open browser on UI launch. |
| `ui_layouts` | list (CLI flag, no UI control) | Which Gradio tabs to mount. |

### `[download]`

| Key | Type | Description |
|---|---|---|
| `download_providers` | CheckboxGroup (`download.py:17`) | `github | huggingface`. Where to fetch model weights. |
| `download_scope` | (CLI flag, no UI control) | `lite | full | any`. Restricts which scope of models gets downloaded by `force-download`. |

### `[benchmark]`

| Key | Type | Description |
|---|---|---|
| `benchmark_mode` | dropdown (`benchmark_options.py:20`) | Benchmark execution strategy. |
| `benchmark_resolutions` | CheckboxGroup (`benchmark_options.py:25`) | Which built-in resolutions to time: `240p | 360p | 540p | 720p | 1080p | 1440p | 2160p` (`choices.py:92-101`). |
| `benchmark_cycle_count` | slider, int 1-10 (`benchmark_options.py:30`) | How many runs per resolution to average. |

### `[misc]`

| Key | Type | Description |
|---|---|---|
| `log_level` | dropdown (`terminal.py:25`) | `error | warn | info | debug`. |
| `halt_on_error` | bool (CLI flag) | In job-run-all / job-retry-all, stop on the first error. |

### `[webcam]` (live mode, not relevant to file renders)

| Key | Type | Description |
|---|---|---|
| Webcam device id, mode, resolution, FPS | `webcam_options.py:24-39` | Live capture settings. No state_manager binding. |

---

## Dependency map

Visual nesting shows what activates what. A child setting only matters when its parent is in the indicated state.

```
processors (master)
├─ face_swapper
│  ├─ face_swapper_model
│  ├─ face_swapper_pixel_boost
│  └─ face_swapper_weight (only if model exposes has_weight_input)
├─ face_enhancer
│  ├─ face_enhancer_model
│  ├─ face_enhancer_blend
│  └─ face_enhancer_weight (only if model exposes has_weight_input)
├─ frame_enhancer
│  ├─ frame_enhancer_model
│  └─ frame_enhancer_blend
├─ expression_restorer
│  ├─ expression_restorer_model
│  ├─ expression_restorer_factor
│  └─ expression_restorer_areas
├─ age_modifier
│  ├─ age_modifier_model
│  └─ age_modifier_direction
├─ background_remover
│  ├─ background_remover_model
│  ├─ background_remover_fill_color (× 4 RGBA)
│  └─ background_remover_despill_color (× 4 RGBA)
├─ deep_swapper
│  ├─ deep_swapper_model
│  └─ deep_swapper_morph (only if model exposes has_morph_input)
├─ face_editor
│  ├─ face_editor_model
│  └─ 14 expression/pose dials
├─ frame_colorizer
│  ├─ frame_colorizer_model
│  ├─ frame_colorizer_size
│  └─ frame_colorizer_blend
├─ lip_syncer
│  ├─ lip_syncer_model
│  ├─ lip_syncer_weight
│  └─ (implicitly requires voice_extractor — handled internally)
└─ face_debugger
   └─ face_debugger_items

face_selector_mode (master)
├─ 'reference' →
│  ├─ reference_face_position
│  ├─ reference_face_distance
│  └─ reference_frame_number
├─ 'one' or 'many' →
│  ├─ face_selector_order
│  ├─ face_selector_gender
│  ├─ face_selector_race
│  └─ face_selector_age_start / _age_end

face_mask_types (master, multi-select)
├─ 'box' in types →
│  ├─ face_mask_blur
│  └─ face_mask_padding (× 4 directional)
├─ 'region' in types →
│  └─ face_mask_regions
└─ 'area' in types →
   └─ face_mask_areas

target_path type (image vs video)
├─ image →
│  ├─ output_image_quality
│  └─ output_image_scale
└─ video →
   ├─ output_audio_encoder / _quality / _volume
   ├─ output_video_encoder / _preset / _quality / _scale / _fps
   ├─ trim_frame_start / _end
   ├─ temp_frame_format
   ├─ voice_extractor_model
   └─ reference_frame_number (when reference mode)

execution_providers (master)
└─ on macOS/CoreML, fp16 swaps:
   ├─ inswapper_128_fp16 → inswapper_128
   ├─ real_esrgan_x2_fp16 → real_esrgan_x2
   ├─ real_esrgan_x4_fp16 → real_esrgan_x4
   └─ real_esrgan_x8_fp16 → real_esrgan_x8

ui_workflow (master)
├─ 'instant_runner' → instant_runner panel
├─ 'job_runner' → job_runner panel
└─ 'job_manager' → job_manager panel
```

---

## Experimentation prioritization

### Lowest-cost / highest-leverage settings to tweak first

| Setting | Why | Suggested values to A/B |
|---|---|---|
| `chunk_size_frames` | Bounds memory drift across long renders. Validated to fix the silent-death failure mode. | 0 (off) vs 250 (current) vs 500 (fewer model loads) |
| `face_swapper_pixel_boost` | Direct quality lever; cost is sub-linear with resolution. | 256 vs 512 (current) vs 768 |
| `face_enhancer_blend` | Direct visual lever if enhancer is re-enabled; tune toward natural skin. | off (current Fix E), then 60, 80, 100 |
| `face_detector_angles` | Drop to `0` if every face is upright; ~30% faster detection. | `0` vs `0 90 180 270` (current) |
| `output_video_preset` | Final encode size lever. | `medium` vs `slow` (current) vs `slower` |
| `execution_thread_count` | With chunking on, can push higher after validating memory and flicker. | 8 vs 12 (current) vs 16 |

### Models worth A/B testing on M4 Max

| Slot | Current | Compare with | Why |
|---|---|---|---|
| `face_swapper_model` | `inswapper_128_fp16` | `hyperswap_1c_256`, `ghost_3_256`, `simswap_unofficial_512` | Keep Fix E as baseline; only retest hyperswap with the evaluator because run-03 showed identity flicker. |
| `face_enhancer_model` | off (`gfpgan_1.4` configured) | `gfpgan_1.4`, `codeformer`, `gpen_bfr_1024`, `restoreformer_plus_plus` | Re-enable only as controlled A/B smokes; enhancer choice can materially affect temporal identity stability. |
| `face_detector_model` | (default `yolo_face`) | `retinaface`, `scrfd`, `many` | Recall vs speed trade. `many` for hard-to-detect faces. |
| `face_landmarker_model` | `2dfan4` | `peppa_wutz` | Newer alternative; check stability. |
| `frame_colorizer_model` | `ddcolor` | `deoldify_stable` | If colorizing video, `deoldify_stable` is purpose-built for temporal consistency. |
| `lip_syncer_model` | `wav2lip_gan_96` | `edtalk_256` | Higher-resolution alternative. |

### Settings that interact (vary together, not one-at-a-time)

| Group | Why they interact |
|---|---|
| `face_swapper_pixel_boost` × `face_enhancer_model` × `face_enhancer_blend` | Higher pixel_boost recovers detail the enhancer then re-shapes; blend determines how much detail survives. |
| `chunk_size_frames` × `execution_thread_count` × `video_memory_strategy` | Memory budget per chunk = thread_count × per-thread footprint × strategy multiplier. Tune as a triple. |
| `face_mask_types` × `face_mask_blur` × `face_mask_padding` | Mask shape and softness — change padding without re-tuning blur and edges look harsh. |
| `face_selector_mode` × `reference_face_distance` × `reference_face_position` | All three needed to control reference-mode behavior. |
| `output_video_preset` × `output_video_quality` (CRF) × `output_video_scale` | Encode-time trade-off. Higher CRF + slower preset = same quality at smaller file. |
| `face_detector_size` × `face_detector_angles` × `face_detector_score` | Detector recall is a function of all three; never sweep one in isolation. |

---

## Open questions

Items where the source did not yield a confident description. Each `[needs verification]` item below corresponds to a model or setting where I'd recommend hands-on benchmarking before publishing claims about it.

### Models flagged `[needs verification]`

- **`hyperswap_1a_256`, `hyperswap_1b_256`, `hyperswap_1c_256`** — FaceFusion-native (2025); no public paper or benchmark as of 2026-04. Capability claims are inferred from FaceFusion's positioning of them as high-end options.
- **`restoreformer_plus_plus`** — limited upstream activity post-2022; quality positioning vs GFPGAN/CodeFormer is hearsay.
- **`face_dat_x4`, `real_hatgan_x4`, `real_web_photo_x4`, `ultra_sharp_2_x4`** — newer community / 2024-2025 models; limited third-party comparative evaluation.
- **`u2net_cloth`, `realistic_rescaler_x4`, `remacri_x4`, `siax_x4`, `swin2_sr_x4`, `tghq_face_x8`, `ultra_sharp_x4`** — community-trained variants without authoritative benchmarks.
- **All deep_swapper celebrity models** — per-identity training quality varies by provider; community evaluation is sparse and provider-specific.
- **`edtalk_256`** — 2024 release; limited third-party evaluation.
- **`fran`** — newer age modifier; limited published comparison vs StyleGANEX.

### Settings flagged

- **`face_mask_types` "occlusion" value in `facefusion.ini:38`** — the canonical choices in `choices.py` are `box | region | area`, but the ini lists `box occlusion region`. Verify whether `occlusion` is parsed as an alias for the occluder pathway or whether it's a stale config key.
- **`face_landmarker_score`** vs `face_detector_score` interaction at high values (>0.8) — unclear whether tightening both compounds detection misses or whether they gate independently. Worth a quick experiment.
- **`face_swapper_weight`** range bounds — `face_swapper_choices.face_swapper_weight_range` was not directly inspected; assume 0-1 step 0.05 (consistent with sibling weights) but verify.

### Source files most heavily relied on

- `facefusion/processors/modules/*/core.py` (10 files) — model catalogs and processor settings.
- `facefusion/{content_analyser,face_classifier,face_detector,face_landmarker,face_masker,face_recognizer,voice_extractor}.py` (7 files) — common-module model catalogs.
- `facefusion/uis/components/*.py` (44 files) — UI control surface.
- `facefusion/choices.py` — enumerated choice lists and numeric ranges.
- `facefusion/program.py` — CLI/argparse cross-reference.
- `facefusion.ini` — current default values.
- This fork's own [`settings.md`](../settings.md) — narrative companion to this catalog.

---

## Summary

- **Total model entries:** 176 across 17 modules (10 processor + 7 common). Of these:
  - face_swapper: 13 models
  - face_enhancer: 9 models
  - frame_enhancer: 19 models
  - frame_colorizer: 5 models
  - lip_syncer: 3 models
  - age_modifier: 2 models
  - expression_restorer: 1 model
  - face_editor: 1 model (six-module pipeline)
  - background_remover: 15 models
  - deep_swapper: 86 models (community celebrity catalog) + custom slot
  - face_detector: 4 models + `many` ensemble
  - face_landmarker: 3 models
  - face_recognizer: 1 model
  - face_classifier: 1 model
  - face_masker: 5 models (3 occluder + 2 parser)
  - voice_extractor: 3 models
  - content_analyser: 3 models (always loaded)
- **Total setting entries:** 186 individual UI controls across 44 component files. ~95 unique state_manager keys after collapsing per-axis directional sliders (RGB color, padding) into single logical settings.
- **`[needs verification]` count:** 13 models + 3 settings.
- **Hardware perspective:** every speed and memory tier is reasoned for the M4 Max + 128 GB RAM. Current quality baseline is CPU-only; CoreML/CPU notes are retained for historical run-03 context and future speed experiments.
