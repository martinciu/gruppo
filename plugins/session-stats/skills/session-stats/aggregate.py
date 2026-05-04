#!/usr/bin/env python3
"""Aggregate token usage, cost, runtime for the current Claude Code session.

Run from the session's original working directory:

    python3 aggregate.py

Or point at a specific transcript:

    SESSION_FILE=/path/to/session.jsonl python3 aggregate.py
"""

import glob
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

# Public Anthropic API rates, USD per million tokens.
# Verify against current rates at anthropic.com/pricing — these drift.
PRICES = {
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
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def fmt_working(working, elapsed):
    pct = (working / elapsed * 100) if elapsed > 0 else 0
    return f"{fmt_duration(working)} ({pct:.0f}% of elapsed)"


def fmt_rate(cost, working_seconds):
    if working_seconds <= 0:
        return "n/a (no working time recorded)"
    rate = cost / (working_seconds / 3600.0)
    return f"${rate:.2f}/hr"


def fmt_tokens(n):
    if n < 1000:
        return str(n)
    if n < 99_950:
        return f"{n/1000:.1f}k"
    if n < 999_500:
        return f"{n/1000:.0f}k"
    return f"{n/1_000_000:.1f}M"


def fmt_cost(c):
    if c == 0:
        return "$0.00"
    if c < 0.005:
        return "<$0.01"
    return f"${c:,.2f}"


def fmt_timestamp(s):
    if not s:
        return ""
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def fmt_model(model):
    if not model or model == "unknown":
        return model or "unknown"
    s = model.replace("claude-", "")
    parts = s.split("-")
    snapshot = None
    if parts and len(parts[-1]) == 8 and parts[-1].isdigit():
        snapshot = parts[-1]
        parts = parts[:-1]
    context = None
    if parts and len(parts[-1]) >= 2 and parts[-1][-1] in "mk" and parts[-1][:-1].isdigit():
        context = parts[-1]
        parts = parts[:-1]
    families = {"opus": "Opus", "sonnet": "Sonnet", "haiku": "Haiku"}
    family_idx = next((i for i, p in enumerate(parts) if p in families), None)
    if family_idx is None:
        return model.replace("claude-", "")
    family_name = families[parts[family_idx]]
    version_parts = parts[:family_idx] + parts[family_idx + 1:]
    version = ".".join(version_parts)
    out = f"{family_name} {version}".strip()
    suffix = []
    if context:
        suffix.append(f"{context.upper()} ctx")
    if snapshot:
        suffix.append(f"{snapshot[:4]}-{snapshot[4:6]}-{snapshot[6:8]}")
    if suffix:
        out += f" ({', '.join(suffix)})"
    return out


def discover_session_file():
    """Find the most recent .jsonl for the cwd's session slug.

    Slug rule: replace `/` and `.` in the absolute cwd with `-`.
    Mirrors the bash `sed 's|/|-|g; s|\\.|-|g'` form. A worktree path
    yields its own slug, not the main repo's.
    """
    cwd = os.getcwd()
    slug = cwd.replace("/", "-").replace(".", "-")
    proj_dir = os.path.join(os.path.expanduser("~"), ".claude", "projects", slug)
    if not os.path.isdir(proj_dir):
        return None, proj_dir
    candidates = glob.glob(os.path.join(proj_dir, "*.jsonl"))
    if not candidates:
        return None, proj_dir
    # Sort by mtime descending, like `command ls -t | head -1` (avoids alias drift).
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0], proj_dir


def consume(path, per_model, ts_state, per_source=None, source=None):
    """Fold one transcript into per-model totals and update first/last timestamps.

    If `per_source` and `source` are provided, the same per-message counters are
    also accumulated into `per_source[source]` so the caller can show a
    controller-vs-subagent split alongside the per-model breakdown.
    """
    if not os.path.exists(path):
        return
    bucket = per_source[source] if (per_source is not None and source) else None
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            ts = d.get("timestamp")
            if ts:
                if ts_state["first"] is None or ts < ts_state["first"]:
                    ts_state["first"] = ts
                if ts_state["last"] is None or ts > ts_state["last"]:
                    ts_state["last"] = ts
            if d.get("type") != "assistant":
                continue
            msg = d.get("message", {})
            model = msg.get("model", "unknown")
            u = msg.get("usage", {}) or {}
            e = per_model[model]
            ccd = u.get("cache_creation", {}) or {}
            cw5 = ccd.get("ephemeral_5m_input_tokens", 0) or 0
            cw1 = ccd.get("ephemeral_1h_input_tokens", 0) or 0
            if not ccd:
                # Older records may use the flat field instead of the breakdown.
                cw5 += u.get("cache_creation_input_tokens", 0) or 0
            tin  = u.get("input_tokens", 0)            or 0
            tout = u.get("output_tokens", 0)           or 0
            tcr  = u.get("cache_read_input_tokens", 0) or 0
            e["msgs"] += 1
            e["in"]  += tin
            e["out"] += tout
            e["cr"]  += tcr
            e["cw5"] += cw5
            e["cw1"] += cw1
            if bucket is not None:
                bucket["msgs"] += 1
                bucket["in"]  += tin
                bucket["out"] += tout
                bucket["cr"]  += tcr
                bucket["cw5"] += cw5
                bucket["cw1"] += cw1
                bucket["model"] = bucket.get("model") or model
                # Track cost contribution (Σ over each row's family pricing).
                fam = family(model)
                if fam:
                    p = PRICES[fam]
                    bucket["cost"] += (tin/1e6*p["in"] + tout/1e6*p["out"]
                                     + tcr/1e6*p["cr"] + cw5/1e6*p["cw5"]
                                     + cw1/1e6*p["cw1"])


def main():
    session_file = os.environ.get("SESSION_FILE")
    proj_dir = None
    if not session_file:
        session_file, proj_dir = discover_session_file()
    if not session_file:
        msg = (f"No session JSONL found under {proj_dir}. Are you in the same "
               "working directory the session was started in?")
        print(msg, file=sys.stderr)
        return 1

    session_id = os.path.basename(session_file)[:-len(".jsonl")]
    sub_dir = os.environ.get("SUB_DIR") or os.path.join(
        os.path.dirname(session_file), session_id, "subagents"
    )

    per_model = defaultdict(lambda: {"in": 0, "out": 0, "cr": 0,
                                     "cw5": 0, "cw1": 0, "msgs": 0})
    per_source = {
        "controller": {"in": 0, "out": 0, "cr": 0, "cw5": 0, "cw1": 0,
                       "msgs": 0, "cost": 0.0, "model": None},
        "subagent":   {"in": 0, "out": 0, "cr": 0, "cw5": 0, "cw1": 0,
                       "msgs": 0, "cost": 0.0, "model": None},
    }
    ts_state = {"first": None, "last": None}

    consume(session_file, per_model, ts_state, per_source, "controller")
    agent_files = sorted(glob.glob(os.path.join(sub_dir, "agent-*.jsonl")))
    for p in agent_files:
        consume(p, per_model, ts_state, per_source, "subagent")

    controller_working, controller_idle = controller_working_idle(session_file)
    sub_total = sum(subagent_span(p) for p in agent_files)
    working_seconds = controller_working + sub_total
    idle_seconds = controller_idle

    print("=== Timeline ===")
    elapsed_seconds = 0.0
    first_ts = ts_state["first"]
    last_ts = ts_state["last"]
    if first_ts and last_ts:
        a = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
        b = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        elapsed_seconds = (b - a).total_seconds()
        print(f"  start:    {fmt_timestamp(first_ts)}")
        print(f"  end:      {fmt_timestamp(last_ts)}")
        print(f"  elapsed:  {fmt_duration(elapsed_seconds)}")
        print(f"  working:  {fmt_working(working_seconds, elapsed_seconds)}")
        print(f"  idle:     {fmt_duration(idle_seconds)}  (controller wait-for-user only)")
    print()

    header = (f"{'Model':<28}{'Messages':>10}{'Input':>9}{'Output':>9}"
              f"{'Cache Read':>12}{'Cache Write 5m':>16}{'Cache Write 1h':>16}"
              f"{'Cost':>11}")
    print(header)
    print("-" * len(header))

    total_cost = 0.0
    totals = {"in": 0, "out": 0, "cr": 0, "cw5": 0, "cw1": 0, "msgs": 0}
    for model, e in sorted(per_model.items()):
        fam = family(model)
        cost = 0.0
        if fam:
            p = PRICES[fam]
            cost = (e["in"]  / 1e6 * p["in"]  + e["out"] / 1e6 * p["out"]
                  + e["cr"]  / 1e6 * p["cr"]  + e["cw5"] / 1e6 * p["cw5"]
                  + e["cw1"] / 1e6 * p["cw1"])
        total_cost += cost
        for k in ("in", "out", "cr", "cw5", "cw1", "msgs"):
            totals[k] += e[k]
        print(f"{fmt_model(model):<28}{e['msgs']:>10}"
              f"{fmt_tokens(e['in']):>9}{fmt_tokens(e['out']):>9}"
              f"{fmt_tokens(e['cr']):>12}{fmt_tokens(e['cw5']):>16}"
              f"{fmt_tokens(e['cw1']):>16}{fmt_cost(cost):>11}")

    print("-" * len(header))
    print(f"{'TOTAL':<28}{totals['msgs']:>10}"
          f"{fmt_tokens(totals['in']):>9}{fmt_tokens(totals['out']):>9}"
          f"{fmt_tokens(totals['cr']):>12}{fmt_tokens(totals['cw5']):>16}"
          f"{fmt_tokens(totals['cw1']):>16}{fmt_cost(total_cost):>11}")
    print()

    # Controller vs subagents (per-source breakdown). Prints only when there's
    # subagent activity; otherwise it's just a duplicate of the totals line.
    if per_source["subagent"]["msgs"] > 0:
        sub_header = (f"{'Source':<28}{'Messages':>10}{'Input':>9}{'Output':>9}"
                      f"{'Cache Read':>12}{'Cache Write 5m':>16}"
                      f"{'Cache Write 1h':>16}{'Cost':>11}")
        print(sub_header)
        print("-" * len(sub_header))
        for label, key in (("Controller", "controller"), ("Subagents", "subagent")):
            e = per_source[key]
            print(f"{label:<28}{e['msgs']:>10}"
                  f"{fmt_tokens(e['in']):>9}{fmt_tokens(e['out']):>9}"
                  f"{fmt_tokens(e['cr']):>12}{fmt_tokens(e['cw5']):>16}"
                  f"{fmt_tokens(e['cw1']):>16}{fmt_cost(e['cost']):>11}")
        print()

    billed = sum(totals[k] for k in ("in", "out", "cr", "cw5", "cw1"))
    print(f"Total billed tokens: {fmt_tokens(billed)}")
    print(f"Total cost (USD, public rates): {fmt_cost(total_cost)}")
    print(f"Effective rate: {fmt_rate(total_cost, working_seconds)} "
          f"(cost ÷ working time, includes parallel subagent compute)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
