#!/usr/bin/env bash
# slugify.sh — derive a branch/file slug from a freeform prompt.
#
# Usage:
#   slugify.sh "<freeform prompt>"
#
# Output: kebab-case slug on stdout. ASCII-only, lowercase, max 40 chars,
# truncated at the last word boundary inside the limit. Falls back to
# `auto-<unix-timestamp>` when the slugified result is empty (emoji-only,
# non-Latin script, punctuation-only, blank input).
#
# The prose form of this algorithm used to live inline in SKILL.md §3. It is
# now the single source — see scripts/tests/slugify.test.sh for the cases it
# must pass.

set -euo pipefail

INPUT="${1:-}"

# LC_ALL=C makes tr/sed treat input as bytes — multi-byte UTF-8 sequences
# (emoji, non-Latin scripts) are then guaranteed to fall outside [a-z0-9]
# and get collapsed into hyphens like any other separator.
slug=$(printf '%s' "$INPUT" \
  | LC_ALL=C tr '[:upper:]' '[:lower:]' \
  | LC_ALL=C sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')

if [ -z "$slug" ]; then
  printf 'auto-%s\n' "$(date +%s)"
  exit 0
fi

if [ "${#slug}" -gt 40 ]; then
  truncated="${slug:0:40}"
  # Back off to the last hyphen so we never break inside a word.
  if [[ "$truncated" == *-* ]]; then
    truncated="${truncated%-*}"
  fi
  # A single >40-char word leaves nothing after backing off — keep the hard
  # 40-char prefix in that case rather than falling back to auto-<ts>, since
  # the prefix is still a recognizable slug.
  if [ -z "$truncated" ]; then
    slug="${slug:0:40}"
  else
    slug="$truncated"
  fi
fi

printf '%s\n' "$slug"
