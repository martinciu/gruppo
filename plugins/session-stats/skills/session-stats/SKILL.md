---
name: session-stats
description: Use when the user asks for current Claude Code session stats — token usage, cost, runtime, or per-model breakdown — either directly ("show session cost", "how long has this been running") or as numbers to embed elsewhere ("add stats to the PR description", "include cost in changelog", "post token usage to Slack"). Trigger applies even when the top-level verb names the destination rather than the stats.
---

# Session Stats

Compute token usage, cost, runtime, and per-model breakdown for the current
Claude Code session by reading its on-disk JSONL transcripts.

## Quick reference

1. Run the aggregator from the session's original working directory — chain
   the `cd` into the same shell call so it isn't lost between turns:

   ```bash
   cd <session-original-cwd> && python3 <skill-dir>/aggregate.py
   ```

   The script discovers the transcript via `pwd`. If you don't know the
   session's original cwd, ask the user.
2. Reformat the script's output as markdown tables (timeline, per-model
   breakdown, totals) — don't also paste the raw text dump.
3. Append the caveats from below.

## When to use

### Direct asks

The user wants stats reported back to them. Examples:

- "What's my session cost so far?"
- "Show token usage for this session."
- "How long has this run been going?"
- "How many tokens has the controller burned vs. the subagents?"

If the user only wants the headline number, suggest `/cost` and `/status`
first — those are built-in and don't require reading disk. Use this skill
when the user wants the per-model breakdown, runtime, or cache-read /
cache-write split that those built-ins don't show.

### Embedded use (stats as input to another task)

The user wants the numbers as content for something else. The action verb
points at the destination, but the data dependency is session stats.
Examples:

- "Add session stats to the PR description."
- "Include the cost in the commit message."
- "Append a per-model breakdown to the changelog."
- "Post token usage to Slack."
- "Drop the runtime + cost into the status update."

In these cases the skill still fires — it produces the numbers. Formatting
for the destination and the downstream write (editing the PR, posting to
Slack, etc.) are separate steps you handle after the aggregator returns.

`/cost` and `/status` are *not* substitutes here, because their output
isn't formatted for embedding elsewhere. Run `aggregate.py`.

### When NOT to fire

- Stats about something other than the current Claude Code session
  (e.g. Anthropic API usage at the org level, billing dashboards).
- A *past* session in a different working directory — the discovery uses
  `pwd`, so the user must be in the original session's cwd.
- The user explicitly says they only want `/cost` or `/status` output.

## Procedure

Run `aggregate.py` from the session's original working directory:

```bash
python3 <skill-dir>/aggregate.py
```

The script:

1. Computes the session slug from `pwd` (a worktree's slug is the worktree
   path, not the main repo's).
2. Picks the most recently modified `.jsonl` under
   `~/.claude/projects/<slug>/`.
3. Folds in any subagent transcripts at
   `<session-id>/subagents/agent-*.jsonl`.
4. Prints the timeline, per-model table, totals, and effective hourly rate.

To override discovery (e.g. inspect a specific transcript), set
`SESSION_FILE` and optionally `SUB_DIR` before running.

For details on the on-disk schema (only relevant if Claude Code changes the
JSONL shape), see `references/jsonl-format.md`.

## Output

Reformat the script's output as markdown tables (don't also paste the raw
text dump). The user sees two tables plus the caveats:

- **Summary:** two-column key/value table with blank header cells
  (`| | |` followed by `|---|---|`) so the markdown parses without a
  visible header. Combines timeline (start, end, elapsed, working,
  idle) and totals (total billed tokens, total cost, effective rate).
  Elapsed is wall-clock; working excludes wait-for-user gaps and
  includes summed subagent spans (so heavy parallelism can push
  `working > elapsed` — keep the percentage as-is when that happens).
  Effective rate = `cost ÷ working time`.
- **Per-model breakdown:** messages, input, output, cache read,
  cache write 5m, cache write 1h, cost.
- **Notes:** caveats from below.

## Caveats to include with results

- **Public-rate estimate.** Cost is computed against published Anthropic API
  prices. They change. Verify at anthropic.com/pricing if precision matters.
- **Plan billing differs.** Claude Max / Pro / Team / Enterprise plans bundle
  usage; the user's incremental cost may be effectively $0 within plan limits.
  Public-rate numbers are useful as a relative guide, not as an invoice.
- **Cache reads dominate.** Most sessions show cache reads as the largest token
  category. That's normal — prompt caching re-uses the system prompt and prior
  turns at ~10% of base input price.
- **Subagent attribution.** Subagent costs are aggregated by model, not by the
  task they served. To map agent IDs to tasks, peek at the matching
  `agent-<id>.meta.json` files in the subagents directory.
- **Live session.** If the session is still running, "end" is the timestamp of
  the most recent entry, not a true end-of-run.
- **Working time.** Controller active turns + summed subagent spans
  (parallel subagents can push working > elapsed). Effective rate = cost ÷
  working time. Plan billing still applies.

## Edge cases

- **No session file found.** The discovery uses `pwd`. If the user `cd`'d into
  a subdirectory after starting the session, the slug won't match. Ask them to
  run from the session's original working directory, or set `SESSION_FILE`
  explicitly.
- **Sessions with only a controller (no subagents).** The `subagents/`
  directory may not exist. The script handles that — `glob` returns an empty
  list and the script skips it.
- **Unknown model strings.** If a record uses a model the script doesn't
  recognize (e.g. a future Sonnet/Opus version), it falls through `family()`
  and the cost for that row is `$0.00`. Tokens still count toward totals,
  just without a price tag — flag this to the user if the row appears.
- **Multiple sessions in the same project.** The script picks the most
  recently modified `.jsonl`. If the user wants stats for a different
  session, list `~/.claude/projects/<slug>/*.jsonl` and pass the chosen path
  via `SESSION_FILE`.
- **Zero working time.** If the transcript has no real user messages
  *and* no subagents, working time is 0. The script prints
  `Effective rate: n/a (no working time recorded)` instead of dividing
  by zero. Tokens still total normally.
- **Synthetic user records (tool results).** Records with
  `type: "user"` whose `message.content` is a list of only
  `tool_result` blocks are produced by Claude Code, not the human.
  They must not close a turn. The script's `is_real_user_message`
  helper filters them out — if you see suspiciously low working time,
  check that this filter still matches the JSONL shape (Claude Code
  may evolve the structure).
- **Open turn at EOF.** If the session was killed before the last
  turn's assistant reply, that turn contributes 0 to working time —
  the runtime past the last observable timestamp is unobservable.
