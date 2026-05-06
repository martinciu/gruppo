#!/usr/bin/env bash
# budget.sh — accumulate per-phase token/duration spend across a single
# /autonomo run, check against the ceilings, and bail when a ceiling is
# breached. Replaces the inline accumulator block that used to live in
# SKILL.md §4 — the controller now calls this once after each `phase-end`.
#
# Usage:
#   budget.sh check <phase> <phase_index> <phase_total> <phase_tokens> <phase_duration_ms>
#
# Required env:
#   AUTONOMO_LOG         — absolute path to the run log; used to derive a
#                          per-run state file (`${AUTONOMO_LOG%.log}.budget`)
#                          so two concurrent runs don't share accumulators.
#   AUTONOMO_EMIT        — absolute path to scripts/emit.sh; called on a breach
#                          to write the `event=budget_exceeded` line.
#   AUTONOMO_MAX_TOKENS  — integer; sum-of-phase-tokens ceiling.
#   AUTONOMO_MAX_DURATION_S — integer; sum-of-phase-duration ceiling, in
#                          seconds.
#
# Behavior:
#   - Reads accumulators from the state file (defaults to "0 0" if missing —
#     i.e. first call of the run).
#   - Adds <phase_tokens> and <phase_duration_ms> to the accumulators and
#     persists.
#   - Checks tokens first, then duration (matching the if/elif precedence the
#     inline block used to encode).
#   - On a breach: emits `budget-exceeded` via $AUTONOMO_EMIT (its pretty line
#     reaches the controller's stdout untouched), writes a one-line
#     `Budget exceeded: <kind>; <total>/<max>` reason to
#     `${AUTONOMO_LOG%.log}.bail` for the controller to read into the failure
#     report, and exits 1. Splitting emit-output (stdout) from bail-reason
#     (file) lets the controller capture the reason without swallowing the
#     emit pretty line that the watching user needs to see.
#   - On a clean accumulator: exits 0 with empty stdout.

set -euo pipefail

usage() {
  echo "budget.sh: usage: budget.sh check <phase> <phase_index> <phase_total> <phase_tokens> <phase_duration_ms>" >&2
  exit 2
}

cmd="${1:-}"
[ "$cmd" = "check" ] || usage
shift

[ "$#" -eq 5 ] || usage
phase="$1"; phase_index="$2"; phase_total="$3"
phase_tokens="$4"; phase_duration_ms="$5"

for var in AUTONOMO_LOG AUTONOMO_EMIT AUTONOMO_MAX_TOKENS AUTONOMO_MAX_DURATION_S; do
  if [ -z "${!var:-}" ]; then
    echo "budget.sh: ${var} not set" >&2
    exit 2
  fi
done

# State and bail files live next to the run log so they're per-run by
# construction.
STATE="${AUTONOMO_LOG%.log}.budget"
BAIL="${AUTONOMO_LOG%.log}.bail"

# Read prior accumulators (or start at zero on first call).
if [ -f "$STATE" ]; then
  read -r total_tokens total_duration_ms < "$STATE"
else
  total_tokens=0
  total_duration_ms=0
fi

total_tokens=$(( total_tokens + phase_tokens ))
total_duration_ms=$(( total_duration_ms + phase_duration_ms ))
total_duration_s=$(( total_duration_ms / 1000 ))

# Persist before the breach check so a re-invocation after a non-fatal error
# still sees the most recent totals.
printf '%d %d\n' "$total_tokens" "$total_duration_ms" > "$STATE"

# Tokens take precedence over duration when both breach in the same call,
# matching the if/elif ordering the inline block used.
if [ "$total_tokens" -gt "$AUTONOMO_MAX_TOKENS" ]; then
  bash "$AUTONOMO_EMIT" budget-exceeded "$phase" "$phase_index" "$phase_total" tokens \
       "$total_tokens" "$AUTONOMO_MAX_TOKENS" \
       "$total_duration_s" "$AUTONOMO_MAX_DURATION_S"
  printf 'Budget exceeded: tokens; %d/%d\n' "$total_tokens" "$AUTONOMO_MAX_TOKENS" > "$BAIL"
  exit 1
fi

if [ "$total_duration_s" -gt "$AUTONOMO_MAX_DURATION_S" ]; then
  bash "$AUTONOMO_EMIT" budget-exceeded "$phase" "$phase_index" "$phase_total" duration \
       "$total_tokens" "$AUTONOMO_MAX_TOKENS" \
       "$total_duration_s" "$AUTONOMO_MAX_DURATION_S"
  printf 'Budget exceeded: duration; %ds/%ds\n' "$total_duration_s" "$AUTONOMO_MAX_DURATION_S" > "$BAIL"
  exit 1
fi

exit 0
