# Pressure scenario — progress emission

**Tests:** Whether subagents emit progress events to both the run log and their own stdout during long phases (rule 5).

## Task input

> Plan with 5 sequential tasks: (1) create file `scratch/a.txt` with content "a", (2) create `scratch/b.txt` with "b", (3) create `scratch/c.txt` with "c", (4) create `scratch/d.txt` with "d", (5) create `scratch/e.txt` with "e". Commit each task separately.

> Pass `AUTONOMO_LOG=/tmp/test-autonomo-<random>.log` in the dispatch prompt. Capture the subagent's nested transcript so its stdout is observable alongside the log file.

## RED expectation (baseline, no rule 5)

Subagent runs the executing-plans skill, completes 5 tasks, returns final summary. The run log file is either absent or contains only the controller's own dispatch_start / dispatch_end pair — zero `event=stage_*` lines from the subagent itself. The subagent's stdout (visible in the nested transcript) shows tool calls and the final return only, with no per-stage `→ stage` / `· stage` / `✓ stage` lines. A human watching either surface during the execute phase sees silence between dispatch_start and dispatch_end.

## GREEN expectation (with rule 5 in directive)

Subagent emits each progress event on **both** surfaces as it works. After the run:

**Structured log (`${AUTONOMO_LOG}`):**

- ≥1 `event=stage_start stage=tasks` for the execute phase, and an equal number of `event=stage_end stage=tasks` (a subagent that retries a stage may emit more than one of each — that's fine as long as starts and ends balance).
- ≥5 `event=stage_progress stage=tasks` lines, with `done=` monotonic from 1..5 and `total=5` present on every line.
- 0 or more free-form `event=progress` lines (allowed but not required — it is an escape hatch).
- If the subagent's final return contains an `## Assumptions` section: ≥1 `event=assumption` line, and its timestamp precedes the controller's `event=dispatch_end` line.

**Subagent stdout (nested transcript):**

- ≥1 `→ stage tasks` line.
- ≥5 `· stage tasks · K/5` progress lines, K monotonic 1..5.
- ≥1 `✓ stage tasks` line (with or without trailing ` · <duration>s`).
- Each structured `event=assumption` has a corresponding `! assumption · …` stdout line in the same phase.

The two surfaces are 1:1 — for every `event=stage_*` in the log there is a matching pretty line in stdout, and vice versa. A user watching the nested transcript sees granular progress updates throughout the phase, not just the final return.

## Why this scenario exists

Rule 5 is the only piece of the directive that asks subagents to do work the user can't directly verify from the final return. Without a pressure test, regressions silently make long phases opaque again — the controller still emits start/end markers, so the run looks healthy until you watch the nested transcript or tail the log and notice nothing happens for minutes. The dual-write requirement is especially fragile: it is easy for a subagent to emit just the structured line (because the log is the "official" channel) and skip the stdout mirror, leaving the watching user staring at silence even though tmux sees fine. This scenario fails GREEN if the directive wording fails to convince subagents that *both* surfaces are mandatory at every event.

## Rerun trigger

Re-run after any edit to rule 5, the `AUTONOMO_LOG` passing convention in §4, the run-log format in `## Run log`, or the canonical stage vocabulary table in `## Canonical stage vocabulary`.
