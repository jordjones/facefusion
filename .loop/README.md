# Autonomous fix-and-retry loop

Reusable pattern for letting Claude (or another agent) drive a long-running CLI task to completion when the task may fail in unknown ways and require code edits between attempts. Originally built to drive a 14k-frame face-swap render through a class of silent worker deaths; the structure is task-agnostic.

## When to use this

- You have a long-running CLI that takes hours per run.
- Failures may be deterministic (a real bug to fix) or transient (a one-off crash that retry alone can't reason about).
- You can leave the agent unattended.
- You want a complete forensic trail of every attempt with the chain of fixes applied.

## When NOT to use this

- Task is fast (under a minute) — just retry inline, no scaffolding needed.
- Failures are unbounded — set a hard attempt cap.
- Task changes shared state irreversibly — chunk the run, or add idempotency, before looping.

## Directory layout

```
.loop/
  README.md                  # this file
  RUNS.md                    # narrative log of all attempts (committed)
  logs/                      # per-run stdout+stderr (gitignored)
    run-01.log
    run-01.start             # ISO timestamp
    run-01.end               # ISO timestamp
    run-02.log
    ...
  forensics/                 # captured at moment of each failure (tracked)
    run-01/
      worker.tail.log
      diag.log               # any [FACEFUSION.*] / signal / abort lines
    run-02/
      ...
```

`logs/` is excluded from git via `.gitignore` because per-run logs balloon to MB-scale via tqdm carriage returns. Forensic excerpts are smaller and worth tracking — they capture the smoking gun for each failure.

## Per-run schema in `RUNS.md`

One block per attempt:

```markdown
## Run NN — YYYY-MM-DD HH:MM

- **Outcome:** failed | killed | succeeded | paused
- **Started:** ISO timestamp
- **Ended:** ISO timestamp (or "in progress")
- **Subprocess exit code:** N
- **Output file:** path or "not produced"
- **Log:** `.loop/logs/run-NN.log` (size, line count)
- **Failure signature:** one-line classification matching a known pattern
- **Forensic excerpts:** 5-15 lines verbatim from the most informative log section
- **Root cause hypothesis:** one paragraph
- **Fix applied:** files changed + commit hash, e.g. `abc123: brief description`
- **Smoke tests:** which checks were re-run after the fix
- **Next attempt:** Run NN+1 (or "loop complete")
```

A trailing **Status** block at the top of `RUNS.md` is overwritten each run so a quick scan shows current state, last status, total elapsed.

## Loop driver — what the agent does

1. **Setup:** create `.loop/` directories. Seed `RUNS.md` with header + inputs + loop config (max attempts, push policy, etc.).
2. **Run loop** (bounded by max attempts):
   1. Compute `run-NN` label.
   2. **Pre-flight:** confirm input files exist, output slot is free, env activates, disk + RAM available.
   3. **Launch** with `run_in_background=true`, capture exit code + start/end timestamps.
   4. **Stream status** at fixed cadence (e.g. every ~5 min — 270 s keeps the prompt cache warm). Each check tails the log, counts failures, updates `RUNS.md` Status block.
   5. **Block** until subprocess exits.
   6. **Success criteria** (all must pass):
      - Exit code 0
      - Output file present
      - Domain-specific validity check (e.g. `ffprobe` returns non-zero duration for a video task)
      - Output size sanity check (e.g. ≥ 10% of expected)
   7. **If success** → write `## Run NN — succeeded` block, end loop.
   8. **If failure** → capture forensics, classify, find smallest fix, apply edit, smoke-test, commit, document in `RUNS.md`, increment NN.
3. **At cap** → write `PAUSED` summary, stop and wait for human review.

## Failure classification

Build a table from prior runs. For each known failure signature, record what the fix was. The table evolves over time — new failures get a new row, repeated failures should be addressed by a more durable fix in the codebase. Example shape:

| Signature in log | Class | Typical fix |
|------------------|-------|-------------|
| Python traceback at top level | bug | Real code edit |
| Specific config error message | config | One-line CLI / ini tweak |
| Repeated subprocess deaths with no traceback | native crash | Architectural change (chunking, isolation) |
| ffmpeg-specific error | tooling | Codec / argument tweak |
| Output missing despite exit 0 | wiring | File-move logic bug |

## Escalation conditions — when the agent stops and waits

- N attempts spent with no success (typically 5).
- Two consecutive runs with the same failure signature and no actionable diagnostic.
- Proposed fix would touch model weights, vendored binaries, or anything outside the source tree.
- Disk usage > 95% or free RAM < some sane floor.
- Fix would require installing or upgrading a dependency.

When escalating: `Outcome: paused` block in `RUNS.md` with the reason and the next plausible direction. Don't pretend everything's fine.

## Cadence and cache pacing

For status-check intervals on a long-running task:
- **Under 270 s** keeps the prompt cache warm (5-min cache TTL on Anthropic's prompt cache). Cheap.
- **300 s exactly is the worst-of-both** — pay the cache miss without amortizing it.
- **20-30 minutes** is the natural cadence for "no point checking sooner" if you commit to the cache miss.

For hands-off long renders, ~5-min checks (270 s) are fine while you want narration; bump to 20 min once cadence is steady.

## Reusing this for a non-FaceFusion task

The pattern is generic. To adapt:

1. Replace the launch command in step (2.iii) with your CLI.
2. Replace the success-criteria check in step (2.vi) with what counts as "done" for your output.
3. Build your own failure-signature table.

The directory layout, `RUNS.md` schema, escalation rules, cadence guidance, and per-run forensics capture all carry over without modification.

## Real-world worked example

`RUNS.md` in this directory documents the original loop that drove this pattern. Three runs, two failures, one success:

| Run | Outcome | Wall time | What broke |
|-----|---------|-----------|------------|
| 01  | failed  | ~5 s      | output extension mismatch — operator-side fix |
| 02  | killed  | 7 min     | code bug surfaced via memory growth — 1-line fix |
| 03  | succeeded | 3 h 27 min | clean end-to-end run validated the architecture |

That run produced a 578 MB H.264/AAC MOV with verifiable face swaps over a 14,500-frame source. Total commits during the loop: 1.
