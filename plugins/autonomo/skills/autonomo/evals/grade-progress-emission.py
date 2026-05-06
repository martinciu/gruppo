#!/usr/bin/env python3
"""Grade eval-progress-emission (id=6 in evals.json).

Reads `<run_dir>/run.log` + `<run_dir>/stdout.log` (the AUTONOMO_LOG and
AUTONOMO_STDOUT_LOG files captured during dispatch) and writes
`<run_dir>/grading.json`. The 6 expectations come from evals.json id=6.

Usage:
    python3 grade-progress-emission.py <run_dir>

Where `<run_dir>` is the directory containing run.log and stdout.log —
typically `<workspace>/iteration-N/eval-progress-emission/with_skill/`.
"""

import argparse
import json
import re
import sys
from pathlib import Path


def grade(run_dir: Path) -> dict:
    log_path = run_dir / "run.log"
    stdout_path = run_dir / "stdout.log"

    log_lines = log_path.read_text().splitlines() if log_path.exists() else []
    stdout_lines = stdout_path.read_text().splitlines() if stdout_path.exists() else []

    expectations = []

    # 1. AUTONOMO_LOG contains >=1 stage_start stage=tasks for execute, with matching stage_end
    starts = [l for l in log_lines if "event=stage_start" in l and "stage=tasks" in l and "phase=execute" in l]
    ends = [l for l in log_lines if "event=stage_end" in l and "stage=tasks" in l and "phase=execute" in l]
    expectations.append({
        "text": "AUTONOMO_LOG contains >=1 `event=stage_start stage=tasks` line for execute, with a matching `event=stage_end stage=tasks`",
        "passed": len(starts) >= 1 and len(ends) >= 1,
        "evidence": f"start lines: {len(starts)}, end lines: {len(ends)}",
    })

    # 2. AUTONOMO_LOG contains >=5 stage_progress with done= 1..5 monotonic and total=5
    progress_pattern = re.compile(r"event=stage_progress.*stage=tasks.*done=(\d+).*total=(\d+)")
    dones, totals = [], []
    for line in log_lines:
        m = progress_pattern.search(line)
        if m:
            dones.append(int(m.group(1)))
            totals.append(int(m.group(2)))
    monotonic = dones == sorted(dones) and len(set(dones)) == len(dones)
    covers_1_to_5 = sorted(set(dones))[:5] == [1, 2, 3, 4, 5] if len(dones) >= 5 else False
    all_total_5 = all(t == 5 for t in totals)
    expectations.append({
        "text": "AUTONOMO_LOG contains >=5 `event=stage_progress stage=tasks` lines, with `done=` monotonic 1..5 and `total=5` on every line",
        "passed": len(dones) >= 5 and monotonic and covers_1_to_5 and all_total_5,
        "evidence": f"progress lines: {len(dones)}, dones: {dones}, totals: {totals}, monotonic: {monotonic}",
    })

    # 3. stdout contains >=1 "→ stage tasks" line
    stdout_starts = [l for l in stdout_lines if l.strip().startswith("→ stage tasks")]
    expectations.append({
        "text": "Stdout mirror contains >=1 `→ stage tasks` line",
        "passed": len(stdout_starts) >= 1,
        "evidence": f"matching lines: {len(stdout_starts)}; first: {stdout_starts[0] if stdout_starts else '(none)'}",
    })

    # 4. stdout contains >=5 "· stage tasks · K/5" with K monotonic 1..5
    progress_stdout_pattern = re.compile(r"·\s+stage\s+tasks\s+·\s+(\d+)/(\d+)")
    ks, denoms = [], []
    for line in stdout_lines:
        m = progress_stdout_pattern.search(line)
        if m:
            ks.append(int(m.group(1)))
            denoms.append(int(m.group(2)))
    stdout_monotonic = ks == sorted(ks) and len(set(ks)) == len(ks)
    stdout_covers = sorted(set(ks))[:5] == [1, 2, 3, 4, 5] if len(ks) >= 5 else False
    all_denom_5 = all(d == 5 for d in denoms)
    expectations.append({
        "text": "Stdout mirror contains >=5 `· stage tasks · K/5` lines with K monotonic 1..5",
        "passed": len(ks) >= 5 and stdout_monotonic and stdout_covers and all_denom_5,
        "evidence": f"progress lines: {len(ks)}, ks: {ks}, denominators: {denoms}, monotonic: {stdout_monotonic}",
    })

    # 5. stdout contains >=1 "✓ stage tasks" line
    stdout_ends = [l for l in stdout_lines if "✓ stage tasks" in l]
    expectations.append({
        "text": "Stdout mirror contains >=1 `✓ stage tasks` line",
        "passed": len(stdout_ends) >= 1,
        "evidence": f"matching lines: {len(stdout_ends)}; first: {stdout_ends[0] if stdout_ends else '(none)'}",
    })

    # 6. Every stage_* event in log has a matching pretty line in stdout, and vice versa.
    # The simplest 1:1 check: same count of stage_* events on both sides, in the same order.
    log_stage_events = []
    for line in log_lines:
        if "event=stage_start" in line and "stage=tasks" in line:
            log_stage_events.append(("start", None))
        elif "event=stage_progress" in line and "stage=tasks" in line:
            m = re.search(r"done=(\d+).*total=(\d+)", line)
            log_stage_events.append(("progress", (int(m.group(1)), int(m.group(2))) if m else None))
        elif "event=stage_end" in line and "stage=tasks" in line:
            log_stage_events.append(("end", None))

    stdout_stage_events = []
    for line in stdout_lines:
        if line.strip().startswith("→ stage tasks"):
            stdout_stage_events.append(("start", None))
        elif "✓ stage tasks" in line:
            stdout_stage_events.append(("end", None))
        else:
            m = progress_stdout_pattern.search(line)
            if m:
                stdout_stage_events.append(("progress", (int(m.group(1)), int(m.group(2)))))

    matched = log_stage_events == stdout_stage_events
    expectations.append({
        "text": "Every `event=stage_*` line in AUTONOMO_LOG has a matching pretty line in stdout (same kind + same done/total), and vice versa",
        "passed": matched,
        "evidence": f"log events: {len(log_stage_events)}, stdout events: {len(stdout_stage_events)}, equal: {matched}",
    })

    passed = sum(1 for e in expectations if e["passed"])
    return {
        "expectations": expectations,
        "summary": {
            "passed": passed,
            "failed": len(expectations) - passed,
            "total": len(expectations),
            "pass_rate": round(passed / len(expectations), 2) if expectations else 0.0,
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "run_dir",
        type=Path,
        help="Directory containing run.log and stdout.log (writes grading.json there)",
    )
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if not run_dir.is_dir():
        print(f"error: {run_dir} is not a directory", file=sys.stderr)
        sys.exit(2)
    out = grade(run_dir)
    out_path = run_dir / "grading.json"
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    sys.exit(0 if out["summary"]["failed"] == 0 else 1)
