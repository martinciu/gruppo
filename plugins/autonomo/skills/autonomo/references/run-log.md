# Run log format

`/autonomo` opens a run log at `.autonomo/<slug>-<RUN_TIMESTAMP>.log` at the start of every run. The log grows monotonically and serves three audiences with one artifact:

- **Live main session** — the controller and each subagent both echo a pretty line to stdout for every event. Controller lines (`→ Phase K/3 …`) appear in the top-level transcript; subagent lines (`→ stage <name>`, `· stage <name> · K/N`, …) appear inside the nested Agent transcript view while a phase is running. Together they give the watching user granular per-stage progress without needing a tail.
- **tmux tailer** — `tail -f .autonomo/<slug>-<RUN_TIMESTAMP>.log` from another pane shows structured events as they happen. Useful when the user is not watching the Claude Code session live.
- **Headless / post-mortem** — the structured format is grep-friendly for after-the-fact inspection. The on-bail report (see SKILL.md "Failure handling") is a derived summary; the log is the canonical artifact.

All emission goes through `scripts/emit.sh` — the script writes both surfaces in one call. Use `bash "${AUTONOMO_EMIT}" <subcommand>` rather than echoing by hand; the dual-write requirement is the whole point of having a script. Emitting only the structured line leaves the live and nested-transcript audiences staring at silence; emitting only the pretty line leaves tmux tailers and post-mortem readers blind.

## Subcommands and their shapes

| Call | Pretty stdout | Structured log line |
|---|---|---|
| `phase-start <p> <i> <n>` | `→ Phase i/n · p · dispatching` | `<ts> level=info phase=p event=dispatch_start` |
| `phase-end <p> <i> <n> <d> [k=v ...]` | `✓ Phase i/n · p · ds · k=v · …` | `<ts> level=info phase=p event=dispatch_end duration_s=d k=v …` |
| `phase-bail <p> <i> <n> <reason>` | `✗ Phase i/n · p · BLOCKED · <reason>` | `<ts> level=warn phase=p event=blocked reason="<reason>"` |
| `stage-start <p> <s>` | `→ stage s` | `<ts> level=info phase=p event=stage_start stage=s` |
| `stage-progress <p> <s> <done> [<total>]` | `· stage s · done/total` (or `· stage s · done`) | `<ts> level=info phase=p event=stage_progress stage=s done=… [total=…]` |
| `stage-end <p> <s> [<duration_s>]` | `✓ stage s` (`· ds` when given) | `<ts> level=info phase=p event=stage_end stage=s [duration_s=…]` |
| `assumption <p> <q> <a>` | `! assumption · Q: q · A: a` | `<ts> level=info phase=p event=assumption question="q" answer="a"` |
| `commit <sha> <subject>` | `  · commit <sha[0:7]> · subject` | `<ts> level=info phase=execute event=commit sha=<sha> subject="…"` |
| `progress <p> <message>` | `· message` | `<ts> level=info phase=p event=progress message="…"` |
| `run-start <branch>` | `→ /autonomo · run started · branch=…` | `<ts> level=info phase=preflight event=run_start branch=…` |

`<ts>` is ISO-8601 UTC. Each structured line is exactly one log line — embedded newlines and double quotes in user text are sanitized by the script.

## Canonical stage vocabulary

| Phase | Stages |
|-------|--------|
| `brainstorm` | `clarify`, `propose`, `design`, `write` |
| `plan` | `outline`, `tasks`, `review` |
| `execute` | `tasks` (single stage; per-task progress comes via `stage-progress done=K total=N` after each plan-task commit) |

Execute uses one stage rather than per-task sub-stages because the existing top-level `event=commit` already marks each task's completion, and the developer's motivating signal is task-level (`4/10`). The `phase=execute stage=tasks` collision with `phase=plan stage=tasks` is intentional and acceptable — `phase=` disambiguates.

## Counter and timing rules

- `total=` is included only when knowable up front. Execute knows from the plan task count; brainstorm `clarify` does not — emits `done=N` only.
- `done=` is monotonic within a stage.
- Tail consumers derive durations from `stage_start` / `stage_end` timestamps. Passing `<duration_s>` to `stage-end` is convenience, not required.
