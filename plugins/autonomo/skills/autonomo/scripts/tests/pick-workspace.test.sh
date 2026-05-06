#!/usr/bin/env bash
# pick-workspace.test.sh — unit tests for pick-workspace.sh.
#
# Each case spins up a throwaway git repo + bare "origin" remote so the script
# can exercise origin/HEAD detection, "commits ahead of default" checks, and
# the linked-worktree branch — without touching the real working repo.
#
# Run: bash scripts/tests/pick-workspace.test.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PICK="${HERE}/../pick-workspace.sh"

failures=0

# Per-case scratch path for captured stderr. Lives outside any throwaway repo
# so it doesn't show up as an untracked file in `git status --porcelain` and
# trip the script's dirty-tree check.
ERR=$(mktemp)
trap 'rm -f "$ERR"' EXIT

# Build a fresh (working-repo, bare-origin) pair with one commit on `main` and
# origin/HEAD set so the script's default-branch detection has something to
# read. Echoes the working-repo path on stdout.
make_repo() {
  local root work bare
  root=$(mktemp -d)
  work="${root}/work"
  bare="${root}/origin.git"

  git init -q --bare "$bare"

  git init -q -b main "$work"
  (
    cd "$work"
    git config user.email "test@example.com"
    git config user.name "Test"
    git commit -q --allow-empty -m "initial"
    git remote add origin "$bare"
    git push -q origin main
    git remote set-head origin main >/dev/null
  )

  printf '%s\n' "$work"
}

run_case() {
  local desc="$1"
  printf '  ... %s\n' "$desc"
}

pass() {
  printf '  ok  %s\n' "$1"
}

fail() {
  printf '  FAIL %s\n    %s\n' "$1" "$2"
  failures=$((failures + 1))
}

# Case 1: clean tree, on default branch -> autonomo/<slug>
run_case "on main, clean -> autonomo/<slug>"
repo=$(make_repo)
(
  cd "$repo"
  out=$("$PICK" "fix-typo" 2>"$ERR") || { echo "exit nonzero: $(cat "$ERR")"; exit 1; }
  [ "$out" = "autonomo/fix-typo" ] || { echo "stdout was '$out'"; exit 1; }
  [ "$(git rev-parse --abbrev-ref HEAD)" = "autonomo/fix-typo" ] \
    || { echo "branch not switched"; exit 1; }
) && pass "on main, clean -> autonomo/<slug>" \
  || fail "on main, clean -> autonomo/<slug>" "see above"

# Case 2: dirty tree -> BLOCKED
run_case "dirty tree -> BLOCKED"
repo=$(make_repo)
(
  cd "$repo"
  echo "dirt" > untracked.txt
  if out=$("$PICK" "fix-typo" 2>"$ERR"); then
    echo "expected nonzero exit, got '$out'"; exit 1
  fi
  grep -q "^BLOCKED: working tree dirty" "$ERR" \
    || { echo "stderr was: $(cat "$ERR")"; exit 1; }
) && pass "dirty tree -> BLOCKED" \
  || fail "dirty tree -> BLOCKED" "see above"

# Case 3: feature branch with no commits ahead -> reuse it
run_case "feature branch, no commits ahead -> reuse"
repo=$(make_repo)
(
  cd "$repo"
  git checkout -q -b feature/wip
  out=$("$PICK" "fix-typo" 2>"$ERR") || { echo "exit nonzero: $(cat "$ERR")"; exit 1; }
  [ "$out" = "feature/wip" ] || { echo "stdout was '$out'"; exit 1; }
  [ "$(git rev-parse --abbrev-ref HEAD)" = "feature/wip" ] \
    || { echo "branch changed unexpectedly"; exit 1; }
) && pass "feature branch, no commits ahead -> reuse" \
  || fail "feature branch, no commits ahead -> reuse" "see above"

# Case 4: feature branch with commits ahead -> BLOCKED
run_case "feature branch, commits ahead -> BLOCKED"
repo=$(make_repo)
(
  cd "$repo"
  git checkout -q -b feature/wip
  git commit -q --allow-empty -m "ahead"
  if out=$("$PICK" "fix-typo" 2>"$ERR"); then
    echo "expected nonzero exit, got '$out'"; exit 1
  fi
  grep -q "^BLOCKED: feature branch already has commits" "$ERR" \
    || { echo "stderr was: $(cat "$ERR")"; exit 1; }
) && pass "feature branch, commits ahead -> BLOCKED" \
  || fail "feature branch, commits ahead -> BLOCKED" "see above"

# Case 5: inside a linked worktree, on a feature branch with commits ahead ->
# still cuts autonomo/<slug>. The "in a worktree" rule wins over "feature
# branch with commits ahead" because the worktree itself is the disposable
# workspace.
run_case "in worktree -> autonomo/<slug>"
repo=$(make_repo)
(
  cd "$repo"
  git commit -q --allow-empty -m "second"
  wt_root=$(mktemp -d)
  wt="${wt_root}/wt"
  git worktree add -q -b feature/wt "$wt" HEAD
  cd "$wt"
  git commit -q --allow-empty -m "wt-only commit"
  out=$("$PICK" "fix-typo" 2>"$ERR") || { echo "exit nonzero: $(cat "$ERR")"; exit 1; }
  [ "$out" = "autonomo/fix-typo" ] || { echo "stdout was '$out'"; exit 1; }
  [ "$(git rev-parse --abbrev-ref HEAD)" = "autonomo/fix-typo" ] \
    || { echo "branch not switched in worktree"; exit 1; }
) && pass "in worktree -> autonomo/<slug>" \
  || fail "in worktree -> autonomo/<slug>" "see above"

# Case 6: missing slug arg -> usage error (exit 2, distinct from BLOCKED).
run_case "missing slug -> usage error"
if "$PICK" 2>"$ERR"; then
  fail "missing slug -> usage error" "expected nonzero exit"
elif ! grep -q "missing <slug>" "$ERR"; then
  fail "missing slug -> usage error" "stderr was: $(cat "$ERR")"
else
  pass "missing slug -> usage error"
fi

if [ "$failures" -gt 0 ]; then
  printf '\n%d test(s) failed\n' "$failures" >&2
  exit 1
fi
printf '\nall tests passed\n'
