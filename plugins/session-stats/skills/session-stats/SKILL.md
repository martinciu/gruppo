---
name: session-stats
description: Use whenever session stats — token usage, cost, runtime, cache-read/cache-write split, or per-model breakdown for the current Claude Code session — are needed, whether the user asks directly ("show session cost", "how long has this run been going") or wants the numbers fed into another task (PR description, commit message, changelog, status report, Slack post). Trigger applies even when the top-level verb is about the destination ("add stats to PR", "include cost in changelog") rather than the stats themselves.
---

# Session Stats

Compute and report token usage, cost, runtime, and per-model breakdown for the
current Claude Code session by reading its on-disk JSONL transcripts.

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
isn't formatted for embedding elsewhere. Run the aggregation script.

### When NOT to fire

- Stats about something other than the current Claude Code session
  (e.g. Anthropic API usage at the org level, billing dashboards).
- A *past* session in a different working directory — the discovery uses
  `pwd`, so the user must be in the original session's cwd.
- The user explicitly says they only want `/cost` or `/status` output.

## How Claude Code stores session data

Each session writes a JSONL transcript to:

```
~/.claude/projects/<slug>/<session-id>.jsonl
```

`<slug>` is the session's working directory with `/` and `.` replaced by `-`
(e.g. `/Users/me/code/foo` → `-Users-me-code-foo`,
`/Users/me/code/foo/.git` → `-Users-me-code-foo--git`).

If the session dispatched subagents, their transcripts are at:

```
~/.claude/projects/<slug>/<session-id>/subagents/agent-*.jsonl
```

Each `assistant` record has a `message.usage` object with `input_tokens`,
`output_tokens`, `cache_read_input_tokens`, and a `cache_creation` object
split by TTL into `ephemeral_5m_input_tokens` and `ephemeral_1h_input_tokens`.
Each record also carries an ISO-8601 `timestamp` — first/last give the session
duration.

## Procedure

1. Compute `<slug>` from `pwd`. (If invoked from a git worktree, the slug
   reflects the worktree path, not the main repo.)
2. Pick the most recently modified `.jsonl` in `~/.claude/projects/<slug>/` —
   that's the current session.
3. Run the aggregation script below.
4. Present the results in the format under "Output", and add the caveats.

## Aggregation script

Run from the session's working directory:

```bash
SLUG=$(pwd | sed 's|/|-|g; s|\.|-|g')
PROJ_DIR="$HOME/.claude/projects/$SLUG"
# Use `command ls` to bypass user aliases (e.g. ls→eza), which can change -t semantics.
export SESSION_FILE=$(command ls -t "$PROJ_DIR"/*.jsonl 2>/dev/null | head -1)

if [ -z "$SESSION_FILE" ]; then
  echo "No session JSONL found under $PROJ_DIR. Are you in the same working" \
       "directory the session was started in?"
  exit 1
fi

SESSION_ID=$(basename "$SESSION_FILE" .jsonl)
export SUB_DIR="$PROJ_DIR/$SESSION_ID/subagents"

python3 <<'PY'
import json, glob, os
from collections import defaultdict
from datetime import datetime

# Public Anthropic API rates, USD per million tokens.
# Verify against current rates at anthropic.com/pricing — these drift.
prices = {
    "opus":   {"in": 15.0, "out": 75.0, "cw5": 18.75, "cw1": 30.0, "cr": 1.50},
    "sonnet": {"in":  3.0, "out": 15.0, "cw5":  3.75, "cw1":  6.0, "cr": 0.30},
    "haiku":  {"in":  1.0, "out":  5.0, "cw5":  1.25, "cw1":  2.0, "cr": 0.10},
}

def family(model):
    if not model:
        return None
    for k in ("opus", "sonnet", "haiku"):
        if k in model:
            return k
    return None


def is_real_user_message(record):
    if record.get("type") != "user":
        return False
    content = record.get("message", {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        return any(
            isinstance(b, dict) and b.get("type") != "tool_result"
            for b in content
        )
    return False


def parse_ts(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def controller_working_idle(path):
    working = 0.0
    idle = 0.0
    turn_user_ts = None
    last_assistant_ts = None
    if not os.path.exists(path):
        return working, idle
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            ts = parse_ts(d.get("timestamp"))
            if ts is None:
                continue
            if is_real_user_message(d):
                if turn_user_ts is not None and last_assistant_ts is not None:
                    working += (last_assistant_ts - turn_user_ts).total_seconds()
                    idle += (ts - last_assistant_ts).total_seconds()
                turn_user_ts = ts
                last_assistant_ts = None
            elif d.get("type") == "assistant":
                if turn_user_ts is not None:
                    last_assistant_ts = ts
    if turn_user_ts is not None and last_assistant_ts is not None:
        working += (last_assistant_ts - turn_user_ts).total_seconds()
    return working, idle


def subagent_span(path):
    first = None
    last = None
    if not os.path.exists(path):
        return 0.0
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            ts = parse_ts(d.get("timestamp"))
            if ts is None:
                continue
            if first is None or ts < first:
                first = ts
            if last is None or ts > last:
                last = ts
    if first is None or last is None or first == last:
        return 0.0
    return (last - first).total_seconds()


def fmt_duration(seconds):
    sec_int = int(round(seconds))
    h = sec_int // 3600
    m = (sec_int % 3600) // 60
    s = sec_int % 60
    minutes = sec_int / 60.0
    return f"{h}:{m:02d}:{s:02d} ({sec_int:,}s, {minutes:.1f} min)"


def fmt_working(working, elapsed):
    pct = (working / elapsed * 100) if elapsed > 0 else 0
    base = fmt_duration(working)
    return f"{base[:-1]}, {pct:.0f}% of elapsed)"


def fmt_rate(cost, working_seconds):
    if working_seconds <= 0:
        return "n/a (no working time recorded)"
    rate = cost / (working_seconds / 3600.0)
    return f"${rate:.2f}/hr"


session_file = os.environ["SESSION_FILE"]
sub_dir      = os.environ["SUB_DIR"]

per_model = defaultdict(lambda: {"in": 0, "out": 0, "cr": 0,
                                 "cw5": 0, "cw1": 0, "msgs": 0})
first_ts = None
last_ts  = None

def consume(path):
    global first_ts, last_ts
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            ts = d.get("timestamp")
            if ts:
                if first_ts is None or ts < first_ts: first_ts = ts
                if last_ts  is None or ts > last_ts:  last_ts  = ts
            if d.get("type") != "assistant":
                continue
            msg   = d.get("message", {})
            model = msg.get("model", "unknown")
            u     = msg.get("usage", {}) or {}
            e = per_model[model]
            e["msgs"] += 1
            e["in"]   += u.get("input_tokens", 0)            or 0
            e["out"]  += u.get("output_tokens", 0)           or 0
            e["cr"]   += u.get("cache_read_input_tokens", 0) or 0
            ccd = u.get("cache_creation", {}) or {}
            e["cw5"] += ccd.get("ephemeral_5m_input_tokens", 0) or 0
            e["cw1"] += ccd.get("ephemeral_1h_input_tokens", 0) or 0
            if not ccd:
                # Older records may use the flat field instead of the breakdown.
                e["cw5"] += u.get("cache_creation_input_tokens", 0) or 0

consume(session_file)
for p in sorted(glob.glob(os.path.join(sub_dir, "agent-*.jsonl"))):
    consume(p)

controller_working, controller_idle = controller_working_idle(session_file)
sub_total = 0.0
for p in sorted(glob.glob(os.path.join(sub_dir, "agent-*.jsonl"))):
    sub_total += subagent_span(p)
working_seconds = controller_working + sub_total
idle_seconds = controller_idle

print("=== Timeline ===")
elapsed_seconds = 0.0
if first_ts and last_ts:
    a = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
    b = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
    elapsed_seconds = (b - a).total_seconds()
    print(f"  start:    {first_ts}")
    print(f"  end:      {last_ts}")
    print(f"  elapsed:  {fmt_duration(elapsed_seconds)}")
    print(f"  working:  {fmt_working(working_seconds, elapsed_seconds)}")
    print(f"  idle:     {fmt_duration(idle_seconds)}")
print()

header = (f"{'Model':<28}{'Msgs':>6}{'Input':>9}{'Output':>9}"
          f"{'CacheR':>12}{'CW-5m':>10}{'CW-1h':>10}{'Cost USD':>11}")
print(header)
print("-" * len(header))

total_cost = 0.0
totals = {"in": 0, "out": 0, "cr": 0, "cw5": 0, "cw1": 0, "msgs": 0}
for model, e in sorted(per_model.items()):
    fam = family(model)
    cost = 0.0
    if fam:
        p = prices[fam]
        cost = (e["in"]  / 1e6 * p["in"]  + e["out"] / 1e6 * p["out"]
              + e["cr"]  / 1e6 * p["cr"]  + e["cw5"] / 1e6 * p["cw5"]
              + e["cw1"] / 1e6 * p["cw1"])
    total_cost += cost
    for k in ("in", "out", "cr", "cw5", "cw1", "msgs"):
        totals[k] += e[k]
    short = model.replace("claude-", "")
    print(f"{short:<28}{e['msgs']:>6}{e['in']:>9,}{e['out']:>9,}"
          f"{e['cr']:>12,}{e['cw5']:>10,}{e['cw1']:>10,}{cost:>11.4f}")

print("-" * len(header))
print(f"{'TOTAL':<28}{totals['msgs']:>6}{totals['in']:>9,}{totals['out']:>9,}"
      f"{totals['cr']:>12,}{totals['cw5']:>10,}{totals['cw1']:>10,}"
      f"{total_cost:>11.4f}")
print()
billed = sum(totals[k] for k in ("in", "out", "cr", "cw5", "cw1"))
print(f"Total billed tokens: {billed:,}")
print(f"Total cost (USD, public rates): ${total_cost:.4f}")
print(f"Effective rate: {fmt_rate(total_cost, working_seconds)} "
      f"(cost ÷ working time, includes parallel subagent compute)")
PY
```

## Output

Render the script's output to the user, then add a short caveat block.
Suggested formatting (markdown table over the raw text dump if the surface
supports it):

- **Timeline:** start / end / duration in human-friendly form.
- **Per-model breakdown:** messages, input, output, cache read,
  cache write 5m, cache write 1h, cost.
- **Totals:** sum of the per-model rows.
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

## Edge cases

- **No session file found.** The discovery uses `pwd`. If the user `cd`'d into
  a subdirectory after starting the session, the slug won't match. Ask them to
  run from the session's original working directory, or have them paste the
  slug / session ID.
- **Sessions with only a controller (no subagents).** The `subagents/`
  directory may not exist. The script handles that — `glob` returns an empty
  list and the script skips it.
- **Unknown model strings.** If a record uses a model the script doesn't
  recognize (e.g. a future Sonnet/Opus version), it falls through `family()`
  and the cost for that row is `0.0000`. Tokens still count toward totals,
  just without a price tag — flag this to the user if the row appears.
- **Multiple sessions in the same project.** `command ls -t | head -1` picks
  the most recently modified `.jsonl`. If the user wants stats for a different
  session, list `~/.claude/projects/<slug>/*.jsonl` and have them pick by ID.
- **Aliased `ls`.** The Bash tool runs through the user's shell, so aliases
  like `ls='eza …'` apply. `eza -t` is *not* sort-by-mtime (eza expects
  `-snew` / `-t modified`) and silently sorts alphabetically — picking the
  wrong session. The script uses `command ls -t` to bypass aliases. Don't
  drop the `command` prefix.
