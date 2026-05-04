---
name: session-stats
description: Use when the user asks about THIS Claude Code session's metrics — cost so far, token usage, runtime/elapsed/working time, per-model split (Opus/Sonnet/Haiku), or controller-vs-subagent breakdown. Fires whether they want the numbers shown directly ("how much has this cost", "how long has this been running", "what's my token usage") or formatted to embed elsewhere (PR body, commit message, changelog, Slack, standup, status update — e.g. "give me a markdown block of session stats", "drop the cost into the PR description"). Trigger on intent, not verb — show, share, include, append, post, drop, paste, give me all qualify. Skip for: Anthropic API list pricing, console.anthropic.com / org billing dashboards, plan-tier comparisons (Pro vs Max), lines-of-code or git diff stats, prompt benchmarking, or sessions in a different working directory.
---

# Session Stats

Compute token usage, cost, runtime, and per-model breakdown for the current
Claude Code session by reading its on-disk JSONL transcripts.

## When to use

### Direct asks

The user wants stats reported back. Examples:

- "What's my session cost so far?"
- "Show token usage for this session."
- "How long has this run been going?"
- "How many tokens has the controller burned vs. the subagents?"

If the user only wants the headline number, suggest `/cost` and `/status`
first — those are built-in and don't read disk. Use this skill when the
user wants the per-model breakdown, runtime, or cache-read / cache-write
split that the built-ins don't show.

### Embedded use (stats as input to another task)

The user wants the numbers as content for something else. The verb points
at the destination, but the data dependency is session stats:

- "Add session stats to the PR description."
- "Include the cost in the commit message."
- "Append a per-model breakdown to the changelog."
- "Post token usage to Slack."

The skill produces the numbers. **Tailor the format to the destination** —
GitHub/PR bodies render markdown tables and `## headings`; Slack does not
(use `*bold*`, bullets, or fenced code blocks). Editing the PR or posting
to Slack is a separate downstream step.

`/cost` and `/status` are not substitutes here — their output isn't
formatted for embedding.

### When NOT to fire

- Stats about something other than the current session (org-level Anthropic
  usage, billing dashboards).
- A *past* session in a different working directory — discovery uses
  `pwd`, so the user must be in the original session's cwd.
- The user explicitly says they only want `/cost` or `/status`.

## Procedure

Run the aggregator from the session's original working directory. Chain
the `cd` into the same shell call so it isn't lost between turns:

```bash
cd <session-original-cwd> && python3 <skill-dir>/aggregate.py
```

The script:

1. Computes the session slug from `pwd` (a worktree's slug is the worktree
   path, not the main repo's).
2. Picks the most recently modified `.jsonl` under
   `~/.claude/projects/<slug>/`.
3. Folds in any subagent transcripts at
   `<session-id>/subagents/agent-*.jsonl`.
4. Prints the timeline, per-model table, controller-vs-subagent split
   (when subagents fired), totals, and effective hourly rate.

To target a specific transcript (e.g. an older session in the same
project), set `SESSION_FILE` and optionally `SUB_DIR` before running. If
you don't know the session's original cwd, ask the user.

For the on-disk JSONL schema (only relevant if Claude Code changes the
shape), see `references/jsonl-format.md`.

## Output format

Reformat the aggregator's output as markdown — don't also paste the raw
text dump. Default layout (good for chat, PR bodies, GitHub issues):

- **Summary table** — two-column key/value with blank header cells
  (`| | |` then `|---|---|`) so the markdown parses without a visible
  header. Combines timeline (start, end, elapsed, working, idle) and
  totals (total billed tokens, total cost, effective rate). Elapsed is
  wall-clock; working excludes wait-for-user gaps and includes summed
  subagent spans (parallel subagents can push `working > elapsed` — keep
  the percentage as-is). Effective rate = `cost ÷ working time`.
- **Per-model breakdown** — messages, input, output, cache read,
  cache write 5m, cache write 1h, cost.
- **Controller vs subagents** — same columns, two rows. Only render when
  subagents fired (the script omits the section otherwise). Useful when
  the user asks about controller-vs-subagent splits or "where did the
  subagents go".
- **Notes** — caveats below.

When the destination doesn't render markdown tables (Slack), use the same
data with bullets, `*bold*`, or a fenced code block instead — and skip
`##` headings, since Slack shows them literally.

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

For tight contexts (PR body, Slack), it's fine to keep only the most
relevant 2–4 caveats — typically public-rate, plan billing, and cache
reads.

## Edge cases

- **No session file found.** Discovery uses `pwd`. If the user `cd`'d into
  a subdirectory after starting the session, the slug won't match. Ask
  them to run from the original cwd, or set `SESSION_FILE` explicitly.
- **Sessions with only a controller (no subagents).** The `subagents/`
  directory may not exist; the script handles that.
- **Unknown model strings.** A future Sonnet/Opus version the script
  doesn't recognize falls through `family()` and prices that row at $0.00.
  Tokens still count toward totals — flag the row to the user if it
  appears.
- **Multiple sessions in the same project.** The script picks the most
  recently modified `.jsonl`. To target a different one, list
  `~/.claude/projects/<slug>/*.jsonl` and pass the chosen path via
  `SESSION_FILE`.
- **Zero working time.** If the transcript has no real user messages and
  no subagents, working time is 0. The script prints
  `Effective rate: n/a (no working time recorded)` rather than dividing
  by zero.

For deeper script-internals notes (synthetic-user-record filtering,
open-turn-at-EOF handling), see `references/jsonl-format.md`.
