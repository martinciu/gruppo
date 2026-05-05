#!/usr/bin/env bash
# slugify.test.sh — unit tests for slugify.sh.
#
# Run: bash scripts/tests/slugify.test.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SLUGIFY="${HERE}/../slugify.sh"

failures=0

check() {
  local desc="$1" input="$2" expected="$3"
  local actual
  actual=$("$SLUGIFY" "$input")
  if [ "$actual" = "$expected" ]; then
    printf '  ok  %s\n' "$desc"
  else
    printf '  FAIL %s\n    input:    %q\n    expected: %s\n    actual:   %s\n' \
      "$desc" "$input" "$expected" "$actual"
    failures=$((failures + 1))
  fi
}

check_matches() {
  local desc="$1" input="$2" pattern="$3"
  local actual
  actual=$("$SLUGIFY" "$input")
  if [[ "$actual" =~ $pattern ]]; then
    printf '  ok  %s\n' "$desc"
  else
    printf '  FAIL %s\n    input:    %q\n    pattern:  %s\n    actual:   %s\n' \
      "$desc" "$input" "$pattern" "$actual"
    failures=$((failures + 1))
  fi
}

# Happy path
check "simple ascii" "fix typo in readme" "fix-typo-in-readme"
check "uppercase lowercased" "Fix README" "fix-readme"
check "punctuation collapsed to single hyphens" "Fix the foo, bar! And baz?" "fix-the-foo-bar-and-baz"
check "leading/trailing whitespace stripped" "  hello world  " "hello-world"
check "multiple separators collapse" "a---b___c   d" "a-b-c-d"

# Length / word-boundary truncation
check "long input truncated at last word boundary" \
  "rename helper to util and add deprecation warning everywhere across the lib" \
  "rename-helper-to-util-and-add"
check "exactly 40 chars not truncated" \
  "twelve thirteen fourteen fifteen twentyt" \
  "twelve-thirteen-fourteen-fifteen-twentyt"
check "single >40-char word falls back to hard 40-char prefix" \
  "antidisestablishmentarianismsupercalifragilisticexpialidocious" \
  "antidisestablishmentarianismsupercalifra"

# Fallback cases — match shape, not value, since the timestamp varies.
check_matches "empty input → auto-fallback" "" '^auto-[0-9]+$'
check_matches "whitespace-only → auto-fallback" "   " '^auto-[0-9]+$'
check_matches "punctuation-only → auto-fallback" '!@#$%^&*()' '^auto-[0-9]+$'
check_matches "emoji-only → auto-fallback" "🎉🚀" '^auto-[0-9]+$'
check_matches "non-Latin script-only → auto-fallback" "日本語のタスク" '^auto-[0-9]+$'

if [ "$failures" -gt 0 ]; then
  printf '\n%d test(s) failed\n' "$failures" >&2
  exit 1
fi
printf '\nall tests passed\n'
