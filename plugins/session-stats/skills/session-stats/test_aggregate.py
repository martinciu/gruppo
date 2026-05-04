#!/usr/bin/env python3
"""Smoke tests for aggregate.py formatters.

Run: python3 test_aggregate.py
"""

import json
import os
import tempfile
from collections import defaultdict

from aggregate import (
    PRICES,
    consume,
    family,
    fmt_cost,
    fmt_duration,
    fmt_model,
    fmt_rate,
    fmt_timestamp,
    fmt_tokens,
    fmt_working,
)


def check(label, got, want):
    assert got == want, f"{label}: got {got!r}, want {want!r}"


def test_fmt_tokens():
    cases = [
        (0, "0"),
        (999, "999"),
        (1000, "1.0k"),
        (1234, "1.2k"),
        (45678, "45.7k"),
        (99949, "99.9k"),
        (99950, "100k"),
        (100000, "100k"),
        (230000, "230k"),
        (999499, "999k"),
        (999500, "1.0M"),
        (1234567, "1.2M"),
        (12345678, "12.3M"),
    ]
    for n, want in cases:
        check(f"fmt_tokens({n})", fmt_tokens(n), want)


def test_fmt_cost():
    cases = [
        (0, "$0.00"),
        (0.001, "<$0.01"),
        (0.0049, "<$0.01"),
        (0.0051, "$0.01"),
        (0.01, "$0.01"),
        (1.234, "$1.23"),
        (1234.567, "$1,234.57"),
    ]
    for c, want in cases:
        check(f"fmt_cost({c})", fmt_cost(c), want)


def test_fmt_model():
    cases = [
        ("claude-opus-4-7", "Opus 4.7"),
        ("claude-sonnet-4-6", "Sonnet 4.6"),
        ("claude-haiku-4-5-20251001", "Haiku 4.5 (2025-10-01)"),
        ("claude-3-5-sonnet-20241022", "Sonnet 3.5 (2024-10-22)"),
        ("claude-sonnet-4-5-1m", "Sonnet 4.5 (1M ctx)"),
        ("claude-sonnet-4-5-1m-20250929", "Sonnet 4.5 (1M ctx, 2025-09-29)"),
        ("claude-sonnet-4-5-200k", "Sonnet 4.5 (200K ctx)"),
        ("claude-haiku-4-5-1m-20251001", "Haiku 4.5 (1M ctx, 2025-10-01)"),
        ("unknown", "unknown"),
        ("", "unknown"),
        ("claude-something-weird", "something-weird"),
    ]
    for m, want in cases:
        check(f"fmt_model({m!r})", fmt_model(m), want)


def test_fmt_duration():
    cases = [
        (0, "0s"),
        (5, "5s"),
        (59, "59s"),
        (60, "1m 0s"),
        (125, "2m 5s"),
        (3600, "1h 0m"),
        (3725, "1h 2m"),
        (7200, "2h 0m"),
    ]
    for s, want in cases:
        check(f"fmt_duration({s})", fmt_duration(s), want)


def test_fmt_working():
    check("fmt_working(0, 0)", fmt_working(0, 0), "0s (0% of elapsed)")
    check("fmt_working(60, 120)", fmt_working(60, 120), "1m 0s (50% of elapsed)")
    # Parallel subagents can push working > elapsed; percentage stays as-is.
    check("fmt_working(180, 60)", fmt_working(180, 60), "3m 0s (300% of elapsed)")


def test_fmt_rate():
    check("fmt_rate(0, 0)", fmt_rate(0, 0), "n/a (no working time recorded)")
    check("fmt_rate(1, -1)", fmt_rate(1, -1), "n/a (no working time recorded)")
    check("fmt_rate(10, 3600)", fmt_rate(10, 3600), "$10.00/hr")
    check("fmt_rate(5, 1800)", fmt_rate(5, 1800), "$10.00/hr")


def test_fmt_timestamp():
    check("fmt_timestamp ''", fmt_timestamp(""), "")
    check("fmt_timestamp None", fmt_timestamp(None), "")
    check(
        "fmt_timestamp Z",
        fmt_timestamp("2026-05-03T14:23:45.123Z"),
        "2026-05-03 14:23 UTC",
    )
    check(
        "fmt_timestamp +offset",
        fmt_timestamp("2026-05-03T14:23:45+00:00"),
        "2026-05-03 14:23 UTC",
    )


def _assistant_record(model, ts, **usage):
    u = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0,
         "cache_creation": {"ephemeral_5m_input_tokens": 0,
                            "ephemeral_1h_input_tokens": 0}}
    cw5 = usage.pop("cw5", 0)
    cw1 = usage.pop("cw1", 0)
    u["cache_creation"]["ephemeral_5m_input_tokens"] = cw5
    u["cache_creation"]["ephemeral_1h_input_tokens"] = cw1
    u.update({"input_tokens": usage.get("tin", 0),
              "output_tokens": usage.get("tout", 0),
              "cache_read_input_tokens": usage.get("tcr", 0)})
    return {"type": "assistant", "timestamp": ts,
            "message": {"model": model, "usage": u}}


def _write_jsonl(records):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return path


def test_consume_multi_model():
    # Synthetic transcript with two model families. Verifies the per-model
    # bucket separates by raw model string and that the per_source bucket
    # sums per-family pricing across them — the path real multi-model
    # sessions exercise (e.g. Opus controller + Sonnet subagent).
    path = _write_jsonl([
        _assistant_record("claude-opus-4-7", "2026-05-01T10:00:00Z",
                          tin=100, tout=1000, tcr=50000, cw1=8000),
        _assistant_record("claude-sonnet-4-6", "2026-05-01T10:01:00Z",
                          tin=50, tout=500, tcr=20000, cw5=2000),
        _assistant_record("claude-opus-4-7", "2026-05-01T10:02:00Z",
                          tin=200, tout=2000, tcr=70000),
    ])
    try:
        per_model = defaultdict(lambda: {"in": 0, "out": 0, "cr": 0,
                                         "cw5": 0, "cw1": 0, "msgs": 0})
        per_source = {"controller": {"in": 0, "out": 0, "cr": 0,
                                     "cw5": 0, "cw1": 0, "msgs": 0,
                                     "cost": 0.0, "model": None},
                      "subagent":   {"in": 0, "out": 0, "cr": 0,
                                     "cw5": 0, "cw1": 0, "msgs": 0,
                                     "cost": 0.0, "model": None}}
        ts = {"first": None, "last": None}
        consume(path, per_model, ts, per_source, "controller")

        # Two distinct model rows must survive, with correct message counts.
        check("opus msgs", per_model["claude-opus-4-7"]["msgs"], 2)
        check("sonnet msgs", per_model["claude-sonnet-4-6"]["msgs"], 1)
        check("opus input", per_model["claude-opus-4-7"]["in"], 300)
        check("opus cw1", per_model["claude-opus-4-7"]["cw1"], 8000)
        check("sonnet cw5", per_model["claude-sonnet-4-6"]["cw5"], 2000)

        # The per-source bucket cost must use *each row's* family pricing,
        # not a single mixed rate. Compute the expected directly here.
        op = PRICES["opus"]
        sn = PRICES["sonnet"]
        expect = (300/1e6 * op["in"] + 3000/1e6 * op["out"]
                  + 120000/1e6 * op["cr"] + 8000/1e6 * op["cw1"]
                  + 50/1e6 * sn["in"] + 500/1e6 * sn["out"]
                  + 20000/1e6 * sn["cr"] + 2000/1e6 * sn["cw5"])
        got = per_source["controller"]["cost"]
        assert abs(got - expect) < 1e-9, f"controller cost: got {got}, want {expect}"
        check("controller msgs", per_source["controller"]["msgs"], 3)
    finally:
        os.unlink(path)


def test_family_handles_bare_and_versioned():
    # Both bare strings (sometimes seen on background/summarization rows)
    # and versioned ones must classify into the same family bucket.
    check("family claude-opus-4-7", family("claude-opus-4-7"), "opus")
    check("family claude-sonnet-4-6", family("claude-sonnet-4-6"), "sonnet")
    check("family bare sonnet", family("sonnet"), "sonnet")
    check("family bare haiku", family("haiku"), "haiku")
    check("family unknown", family("gpt-4"), None)
    check("family None", family(None), None)


def main():
    tests = [
        test_fmt_tokens,
        test_fmt_cost,
        test_fmt_model,
        test_fmt_duration,
        test_fmt_working,
        test_fmt_rate,
        test_fmt_timestamp,
        test_consume_multi_model,
        test_family_handles_bare_and_versioned,
    ]
    for t in tests:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(tests)} test groups passed.")


if __name__ == "__main__":
    main()
