#!/usr/bin/env bash
# budget.test.sh — unit tests for budget.sh.
#
# Each case sets up a fresh AUTONOMO_LOG / state-file pair so accumulators
# don't leak between cases, and points AUTONOMO_EMIT at the real emit.sh so
# breach paths exercise the full cross-script call.
#
# Run: bash scripts/tests/budget.test.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUDGET="${HERE}/../budget.sh"
EMIT="${HERE}/../emit.sh"

failures=0

# Reset env vars for each case. Tokens / duration ceilings are set
# permissively by default so individual cases can tighten them when probing
# breach behavior.
new_run() {
  local tmpdir
  tmpdir=$(mktemp -d)
  export AUTONOMO_LOG="${tmpdir}/run.log"
  export AUTONOMO_EMIT="$EMIT"
  export AUTONOMO_MAX_TOKENS=1000000
  export AUTONOMO_MAX_DURATION_S=1000000
  : > "$AUTONOMO_LOG"
}

pass() { printf '  ok  %s\n' "$1"; }
fail() {
  printf '  FAIL %s\n    %s\n' "$1" "$2"
  failures=$((failures + 1))
}
run_case() { printf '  ... %s\n' "$1"; }

# Case 1: under both ceilings -> exit 0, empty stdout.
run_case "under budget -> exit 0, empty stdout"
new_run
out=$("$BUDGET" check brainstorm 1 3 5000 30000)
if [ -z "$out" ]; then
  pass "under budget -> exit 0, empty stdout"
else
  fail "under budget -> exit 0, empty stdout" "stdout was '$out'"
fi

# Helper: reads the per-run bail-reason file for the current AUTONOMO_LOG.
read_bail() { cat "${AUTONOMO_LOG%.log}.bail" 2>/dev/null; }

# Case 2: tokens ceiling exceeded -> exit 1, reason in bail file.
run_case "tokens ceiling -> bail with tokens reason"
new_run
export AUTONOMO_MAX_TOKENS=4000
if "$BUDGET" check brainstorm 1 3 5000 1000 >/dev/null; then
  fail "tokens ceiling -> bail with tokens reason" "expected nonzero exit"
elif ! [[ "$(read_bail)" =~ ^Budget\ exceeded:\ tokens\;\ 5000/4000$ ]]; then
  fail "tokens ceiling -> bail with tokens reason" "bail was '$(read_bail)'"
elif ! grep -q 'event=budget_exceeded reason=tokens' "$AUTONOMO_LOG"; then
  fail "tokens ceiling -> bail with tokens reason" "log missing budget_exceeded line"
else
  pass "tokens ceiling -> bail with tokens reason"
fi

# Case 3: duration ceiling exceeded (tokens fine) -> exit 1, duration reason.
run_case "duration ceiling -> bail with duration reason"
new_run
export AUTONOMO_MAX_DURATION_S=10
# 15000 ms -> 15 s, over the 10 s ceiling.
if "$BUDGET" check execute 3 3 100 15000 >/dev/null; then
  fail "duration ceiling -> bail with duration reason" "expected nonzero exit"
elif ! [[ "$(read_bail)" =~ ^Budget\ exceeded:\ duration\;\ 15s/10s$ ]]; then
  fail "duration ceiling -> bail with duration reason" "bail was '$(read_bail)'"
elif ! grep -q 'event=budget_exceeded reason=duration' "$AUTONOMO_LOG"; then
  fail "duration ceiling -> bail with duration reason" "log missing budget_exceeded line"
else
  pass "duration ceiling -> bail with duration reason"
fi

# Case 4: both ceilings breached in the same call -> tokens wins (matches the
# if/elif precedence the inline block encoded).
run_case "both ceilings -> tokens wins"
new_run
export AUTONOMO_MAX_TOKENS=10
export AUTONOMO_MAX_DURATION_S=1
if "$BUDGET" check brainstorm 1 3 100 5000 >/dev/null; then
  fail "both ceilings -> tokens wins" "expected nonzero exit"
elif ! [[ "$(read_bail)" =~ ^Budget\ exceeded:\ tokens ]]; then
  fail "both ceilings -> tokens wins" "expected tokens reason, got '$(read_bail)'"
else
  pass "both ceilings -> tokens wins"
fi

# Case 5: accumulators persist across calls within a single run.
run_case "accumulators persist across calls"
new_run
"$BUDGET" check brainstorm 1 3 4000 60000 >/dev/null
"$BUDGET" check plan       2 3 4000 60000 >/dev/null
state="${AUTONOMO_LOG%.log}.budget"
read -r tt tdms < "$state"
if [ "$tt" = "8000" ] && [ "$tdms" = "120000" ]; then
  pass "accumulators persist across calls"
else
  fail "accumulators persist across calls" "state was '$tt $tdms', wanted '8000 120000'"
fi

# Case 6: breach is on the *accumulated* total, not just the current phase.
# Two clean phases, third phase alone is fine but pushes the sum over.
run_case "breach is on accumulated total, not single phase"
new_run
export AUTONOMO_MAX_TOKENS=10000
"$BUDGET" check brainstorm 1 3 4000 0 >/dev/null
"$BUDGET" check plan       2 3 4000 0 >/dev/null
if "$BUDGET" check execute 3 3 4000 0 >/dev/null; then
  fail "breach is on accumulated total, not single phase" "expected breach"
elif ! [[ "$(read_bail)" =~ ^Budget\ exceeded:\ tokens\;\ 12000/10000$ ]]; then
  fail "breach is on accumulated total, not single phase" "bail was '$(read_bail)'"
else
  pass "breach is on accumulated total, not single phase"
fi

# Case 7: missing required env -> exit 2 (usage error, distinct from breach).
run_case "missing AUTONOMO_LOG -> usage error"
unset AUTONOMO_LOG AUTONOMO_EMIT AUTONOMO_MAX_TOKENS AUTONOMO_MAX_DURATION_S
if "$BUDGET" check brainstorm 1 3 5000 30000 2>err_tmp; then
  fail "missing AUTONOMO_LOG -> usage error" "expected nonzero exit"
elif ! grep -q "AUTONOMO_LOG not set" err_tmp; then
  fail "missing AUTONOMO_LOG -> usage error" "stderr was: $(cat err_tmp)"
else
  pass "missing AUTONOMO_LOG -> usage error"
fi
rm -f err_tmp

# Case 8: wrong arg count -> usage error.
run_case "wrong arg count -> usage error"
new_run
if "$BUDGET" check brainstorm 1 3 5000 2>err_tmp; then
  fail "wrong arg count -> usage error" "expected nonzero exit"
elif ! grep -q "usage:" err_tmp; then
  fail "wrong arg count -> usage error" "stderr was: $(cat err_tmp)"
else
  pass "wrong arg count -> usage error"
fi
rm -f err_tmp

if [ "$failures" -gt 0 ]; then
  printf '\n%d test(s) failed\n' "$failures" >&2
  exit 1
fi
printf '\nall tests passed\n'
