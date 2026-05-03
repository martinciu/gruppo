#!/usr/bin/env python3
"""Smoke tests for aggregate.py formatters.

Run: python3 test_aggregate.py
"""

from aggregate import (
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


def main():
    tests = [
        test_fmt_tokens,
        test_fmt_cost,
        test_fmt_model,
        test_fmt_duration,
        test_fmt_working,
        test_fmt_rate,
        test_fmt_timestamp,
    ]
    for t in tests:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(tests)} test groups passed.")


if __name__ == "__main__":
    main()
