# Failure-report format

When any phase returns `BLOCKED:` or errors, the controller writes a one-page report at `.autonomo/<slug>-<RUN_TIMESTAMP>.md` using the template below. The branch / worktree and the structured log stay in place so the user can inspect, fix, and re-run.

`BLOCKED:` is the controlled-failure marker. Returns starting with that prefix are expected; anything else is uncontrolled and flagged in the report.

## Template

```
# Autonomo run blocked

- Phase: <brainstorm | plan | execute | pr>
- Task: <prompt verbatim>
- Branch / worktree: <branch name or worktree path>
- Log: `.autonomo/<slug>-<RUN_TIMESTAMP>.log` (full structured event history)
- Started: <iso8601>
- Stopped: <iso8601>

## Reason
<full subagent return value, or error trace; for budget bails: `Budget exceeded: <tokens|duration>; <total>/<max>`>

## Artifacts on disk
- spec: <path or "not produced">
- plan: <path or "not produced">
- commits: <git log --oneline since branch base, or "none">

## Suggested next step
<best-guess hint, e.g. "Run /autonomo again with a more specific prompt" or "Resume with /superpowers:executing-plans against .superpowers/plans/<plan>.md">
```

## Rules

- One report per bailed run. Filename includes the slug and the run timestamp so multiple runs in the same repo do not collide.
- No retry. No rollback. Bail on first failure.
- The report is a one-page summary; the log (`.autonomo/<slug>-<RUN_TIMESTAMP>.log`) is the full event history. Both stay on disk; the user inspects either, fixes input or environment, and re-runs.
- If `gh pr create` is the failing step, the branch and commits already exist locally — the report's "Suggested next step" should point the user at a manual `gh pr create` rather than asking them to start over.
- For a budget bail (`event=budget_exceeded`), `Phase` is the phase that just ran (not a separate `budget` phase) and `Reason` carries the breach in the `Budget exceeded: <tokens|duration>; <total>/<max>` form. If the bail came after `execute`, the work is on the local branch — the suggested next step should point at a manual `gh pr create` (same as the `pr` failure path) rather than re-running the whole pipeline.
