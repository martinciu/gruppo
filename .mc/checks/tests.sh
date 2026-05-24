#!/usr/bin/env bash
# .mc/checks/tests.sh — full verification gate for gruppo (Phase 5 / pre-merge).
#
# Runs the structural smoke gate, then every *.test.sh unit test in the repo.
# Exit 0 = all green. Nonzero = at least one group failed.
#
# Wired as the Phase 5 (verify + merge) exec-gate: /mc:workflow runs this
# before the "ready to merge" claim.
# Run directly: bash .mc/checks/tests.sh

set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || (cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd))"
cd "$ROOT" || { echo "tests: cannot cd to repo root" >&2; exit 2; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

fail=0

echo "### smoke ###"
if bash "$HERE/smoke.sh"; then :; else fail=$((fail + 1)); fi

echo
echo "### unit tests (*.test.sh) ###"
found=0
while IFS= read -r t; do
  found=1
  echo "--- $t ---"
  if bash "$t"; then
    echo "  -> pass"
  else
    echo "  -> FAIL"
    fail=$((fail + 1))
  fi
done < <(find . -path ./.git -prune -o -path ./.claude/worktrees -prune -o -name '*.test.sh' -print | sort)
[ "$found" -eq 0 ] && echo "(no *.test.sh found)"

if [ "$fail" -gt 0 ]; then
  printf '\ntests: %d failing group(s)\n' "$fail" >&2
  exit 1
fi
printf '\ntests: all green\n'
