# AGENTS.md — facefusion (personal fork)

Pointer-only cross-agent entrypoint. Keep this thin; substance lives in the linked files.

## What this is

Personal fork of [facefusion/facefusion](https://github.com/facefusion/facefusion) at **v3.8.2**, running locally on Apple **M4 Max** (128 GB, no CUDA). Quality-first face-swap pipeline with resilience patches for long renders on Apple Silicon.

Merged onto upstream **v3.8.2** while keeping fork patches (chunking, skip/retry, NSFW gate off, UI subprocess). Smoke verification is still pending.

## Start here

| Doc | Purpose |
|-----|---------|
| [`WORKLOG.md`](WORKLOG.md) | Live workstreams, scoreboard, session log, next actions |
| [`settings.md`](settings.md) | Config-of-record: every non-default `facefusion.ini` key + rationale |
| [`docs/architecture.md`](docs/architecture.md) | System pipeline, directory map, fork abstractions |
| [`docs/MODELS_AND_SETTINGS.md`](docs/MODELS_AND_SETTINGS.md) | Full model + UI control catalog |
| [`settings/`](settings/) | Dated config registry (known-good and rejected runs) |
| [`.loop/README.md`](.loop/README.md) | Autonomous fix-and-retry loop pattern |

## Runtime

- Conda env: `facefusion`
- Python: `/opt/anaconda3/envs/facefusion/bin/python` — **never bare `python`**
- Config: `facefusion.ini` (Fix E baseline: CPU-only, `inswapper_128_fp16`, no enhancer, chunking=250, `workflow_strategy=disk`)
- Headless invocation pattern is in `settings.md` §CLI invocation pattern

## Fork patches (not in upstream)

- **Subprocess chunking** — `chunk-run` CLI + `facefusion/workflows/chunk_runner.py`; disk-strategy hook in `to_video.process_disk_frames()`; rollback via `chunk_size_frames = 0`
- **Frame-tolerant processing** — per-frame skip + serial retry in `to_video.py`
- **UI subprocess decoupling** — Gradio spawns `job-run` worker via `uis/ui_subprocess.py`
- **NSFW gate disabled** — `content_analyser.analyse_frame` always returns `False`
- **Diagnostic probes** — signal/atexit/heartbeat logging in `exit_helper.py`

Do not revert these silently when editing upstream-touched files.

## Quality scoreboard

Per-frame identity stability is measured with [`tools/evaluate_swap.py`](tools/evaluate_swap.py) (ArcFace cosine distance). Targets and current numbers are in `WORKLOG.md` §Face-swap output quality.

Known-good baseline: Fix E — `settings/2026-05-27-run-04-fix-e-known-good.md`.

## Active work (as of 2026-08-18)

1. **Face-swap output quality** — visual review of Kail 60s output (`output/intensity-60-kail-run-03-kail1-kail3-boxmask-pb256.mp4`)
2. **Find better** (paused) — CoreML EP config dead end; pivot options in `WORKLOG.md` and `settings/2026-07-23-find-better-research.md`
3. **Frame resilience** (testing) — synthetic-failure verification pending
4. **Upgrade to 3.8.2** (merged, smoke pending) — fork patches ported onto upstream 3.8.2; see `WORKLOG.md`

## Safety boundaries

- Ask before killing active renders or deleting `.temp/` extracted frames during recovery
- Target and output file extensions **must match** (`.mov` → `.mov`, `.mp4` → `.mp4`)
- No force-push; no pushing to upstream (`facefusion/facefusion`) — use writable `origin` remote
- Do not commit model weights (`.assets/`), caches (`.caches/`), or render outputs unless explicitly requested
- Update `WORKLOG.md` when closing a workstream or shipping a config change worth preserving

## Git remotes

- `upstream` → `https://github.com/facefusion/facefusion.git` (read-only)
- `origin` → `https://github.com/jordjones/facefusion.git` (writable fork)

Sync: `git fetch upstream` then merge/rebase on an upgrade branch.
