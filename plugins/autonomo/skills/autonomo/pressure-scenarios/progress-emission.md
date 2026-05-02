# Pressure scenario — progress emission

**Tests:** Whether subagents emit progress events to the run log during long phases (rule 5).

## Task input

> Plan with 5 sequential tasks: (1) create file `scratch/a.txt` with content "a", (2) create `scratch/b.txt` with "b", (3) create `scratch/c.txt` with "c", (4) create `scratch/d.txt` with "d", (5) create `scratch/e.txt` with "e". Commit each task separately.

> Pass `AUTONOMO_LOG=/tmp/test-autonomo-<random>.log` in the dispatch prompt.

## RED expectation (baseline, no rule 5)

Subagent runs the executing-plans skill, completes 5 tasks, returns final summary. The run log file is either absent or contains only the controller's own dispatch_start / dispatch_end pair — zero `event=progress` lines from the subagent itself. A human tailing the log during the execute phase sees silence between dispatch_start and dispatch_end.

## GREEN expectation (with rule 5 in directive)

Subagent emits structured stage events to `${AUTONOMO_LOG}` as it works. After the run, the log satisfies all of:

- Exactly one `event=stage_start stage=tasks` and one matching `event=stage_end stage=tasks` for the execute phase.
- ≥5 `event=stage_progress stage=tasks` lines, with `done=` monotonic from 1..5 and `total=5` present on every line.
- 0 or more free-form `event=progress` lines (allowed but not required — it is an escape hatch).
- If the subagent's final return contains an `## Assumptions` section: ≥1 `event=assumption` line, and its timestamp precedes the controller's `event=dispatch_end` line.

A tailing human sees updates throughout the phase.

## Why this scenario exists

Rule 5 is the only piece of the directive that asks subagents to do work the user can't directly verify from the final return. Without a pressure test, regressions silently make long phases opaque again — the controller still emits start/end markers, so the run looks healthy until you tail the log and notice nothing happens for minutes. This scenario fails GREEN if the directive wording fails to convince subagents that progress emission is mandatory.

## Rerun trigger

Re-run after any edit to rule 5, the `AUTONOMO_LOG` passing convention in §4, the run-log format in `## Run log`, or the canonical stage vocabulary table in `## Canonical stage vocabulary`.
