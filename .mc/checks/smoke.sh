#!/usr/bin/env bash
# .mc/checks/smoke.sh — fast structural sanity gate for gruppo.
#
# Exit 0 = clean. Nonzero = a problem a PR must not introduce.
# Fast, offline, no LLM: JSON manifests parse, marketplace <-> plugin
# consistency, declared plugin paths exist, shell scripts parse.
#
# Wired as the Phase 2 (execute) exec-gate: /mc:execute runs this before
# flipping the feature bead to awaiting_review / opening the draft PR.
# Run directly: bash .mc/checks/smoke.sh

set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || (cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd))"
cd "$ROOT" || { echo "smoke: cannot cd to repo root" >&2; exit 2; }

command -v jq >/dev/null 2>&1 || { echo "smoke: jq is required but not on PATH" >&2; exit 2; }

fail=0
err() { printf '  FAIL %s\n' "$1" >&2; fail=$((fail + 1)); }
ok()  { printf '  ok   %s\n' "$1"; }

# find(1) prefix that skips .git and any worktree checkouts (per global rule).
PRUNE=(-path ./.git -prune -o -path ./.claude/worktrees -prune -o)

echo "== JSON manifests parse =="
while IFS= read -r f; do
  if jq empty "$f" >/dev/null 2>&1; then ok "$f"; else err "invalid JSON: $f"; fi
done < <(find . "${PRUNE[@]}" \( -name plugin.json -o -name marketplace.json \) -print)

echo "== marketplace <-> plugin consistency =="
MKT=".claude-plugin/marketplace.json"
if [ ! -f "$MKT" ]; then
  err "missing $MKT"
else
  # Every marketplace entry: source dir exists, has a plugin.json, name matches.
  while IFS=$'\t' read -r name source; do
    dir="${source#./}"
    if [ ! -d "$dir" ]; then err "marketplace plugin '$name' source missing: $source"; continue; fi
    pj="$dir/.claude-plugin/plugin.json"
    if [ ! -f "$pj" ]; then err "marketplace plugin '$name' has no $pj"; continue; fi
    pjname="$(jq -r '.name // empty' "$pj")"
    if [ "$pjname" != "$name" ]; then
      err "name mismatch: marketplace='$name' plugin.json='$pjname' ($pj)"
    else
      ok "$name -> $source"
    fi
  done < <(jq -r '.plugins[] | [.name, .source] | @tsv' "$MKT")

  # Every plugin dir with a plugin.json is registered in the marketplace.
  while IFS= read -r pj; do
    dir="$(dirname "$(dirname "$pj")")"   # plugins/<name>
    src="./$dir"
    if ! jq -e --arg s "$src" '.plugins[] | select(.source == $s)' "$MKT" >/dev/null; then
      err "plugin not registered in $MKT: $src"
    fi
  done < <(find plugins -maxdepth 3 -name plugin.json -print 2>/dev/null)
fi

echo "== plugin.json declared paths exist =="
while IFS= read -r pj; do
  dir="$(dirname "$(dirname "$pj")")"
  while IFS= read -r rel; do
    [ -z "$rel" ] && continue
    p="$dir/${rel#./}"
    if [ -e "$p" ]; then ok "$pj -> $rel"; else err "$pj references missing path: $rel"; fi
  done < <(jq -r '(.skills // []) + (.commands // []) + (.agents // []) | .[] | select(type == "string")' "$pj" 2>/dev/null)
done < <(find plugins -maxdepth 3 -name plugin.json -print 2>/dev/null)

echo "== shell script syntax (bash -n) =="
while IFS= read -r s; do
  if bash -n "$s" 2>/dev/null; then ok "$s"; else err "syntax error: $s"; fi
done < <(find . "${PRUNE[@]}" -name '*.sh' -print)

if [ "$fail" -gt 0 ]; then
  printf '\nsmoke: %d problem(s)\n' "$fail" >&2
  exit 1
fi
printf '\nsmoke: clean\n'
