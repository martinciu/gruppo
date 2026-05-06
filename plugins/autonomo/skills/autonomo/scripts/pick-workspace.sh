#!/usr/bin/env bash
# pick-workspace.sh — implement SKILL.md §3 "Pick workspace" decision table.
# Inspects git state, refuses non-clean baselines, decides where the work goes,
# creates the branch if needed, and prints BRANCH_NAME on stdout. On a BLOCKED
# state, prints `BLOCKED: <reason>` on stderr and exits nonzero so the
# controller can propagate the message and stop.
#
# Usage:
#   pick-workspace.sh <slug>
#
# Decision table (top-down, first match wins; mirrors the SKILL.md prose):
#   1. Working tree dirty                                  -> BLOCKED
#   2. On default branch (origin/HEAD), clean              -> git checkout -b autonomo/<slug>
#   3. Inside a linked worktree, clean                     -> git checkout -b autonomo/<slug> in place
#   4. On feature branch, no commits ahead of default      -> reuse current branch
#   5. On feature branch, commits ahead of default         -> BLOCKED

set -euo pipefail

SLUG="${1:-}"
if [ -z "$SLUG" ]; then
  echo "pick-workspace.sh: missing <slug> argument" >&2
  exit 2
fi

# Dirty-tree check first — overrides every other case in the table.
if [ -n "$(git status --porcelain)" ]; then
  echo "BLOCKED: working tree dirty; stash or commit first" >&2
  exit 1
fi

# Default branch: prefer origin/HEAD's symbolic ref, fall back to "main" so the
# script still does something sensible in fresh / detached-origin repos.
DEFAULT=$(git symbolic-ref refs/remotes/origin/HEAD --short 2>/dev/null \
  | sed 's|^origin/||' || true)
DEFAULT=${DEFAULT:-main}

CURRENT=$(git rev-parse --abbrev-ref HEAD)

# Linked-worktree detection: git rev-parse --git-dir returns an absolute path
# ending in /.git/worktrees/<name> for worktrees and just ".git" for the
# primary checkout.
IN_WORKTREE=0
case "$(git rev-parse --git-dir)" in
  */.git/worktrees/*) IN_WORKTREE=1 ;;
esac

# Cases 2 + 3: cut autonomo/<slug>.
if [ "$CURRENT" = "$DEFAULT" ] || [ "$IN_WORKTREE" = "1" ]; then
  BRANCH="autonomo/${SLUG}"
  git checkout -b "$BRANCH" >/dev/null 2>&1
  printf '%s\n' "$BRANCH"
  exit 0
fi

# Cases 4 + 5: feature branch outside a worktree. Reuse iff no commits ahead of
# default; bail otherwise.
if [ -z "$(git log "origin/${DEFAULT}..HEAD" --oneline 2>/dev/null)" ]; then
  printf '%s\n' "$CURRENT"
  exit 0
fi

echo "BLOCKED: feature branch already has commits; start from main or a fresh branch" >&2
exit 1
