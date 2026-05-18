---
description: Resolve the plan for the current branch from beads, transition the feature bead in_progress → awaiting_review, and run /superpowers:executing-plans inline
---

Phase 2 driver — wraps `/superpowers:executing-plans` with bd-backed plan
resolution and feature-bead status transitions. Inline-only; for SDD use
`/superpowers:subagent-driven-development` directly (it doesn't need this
wrapper since SDD's per-task discipline already gates progress).

## Beads integration (optional)

If `bd status` exits 0 (beads is installed AND this worktree has `.beads/`),
the command resolves the plan from the feature bead and transitions its
status. Otherwise it falls back to asking the user for the plan path.

Detection one-liner:

    bd status >/dev/null 2>&1 || skip_beads=1

Every `bd ...` invocation below is guarded by `[ -z "$skip_beads" ]`. A
failure inside a guarded block **never** blocks the underlying workflow
step — log the error, continue.

## Step 1 — Resolve the plan

### With beads (default)

    branch=$(git symbolic-ref --short HEAD)
    feature_id=$(bd list --label "branch:$branch" --type feature \
      --json | jq -r '.[0].id // empty')

If `$feature_id` is empty, stop and tell the user: no feature bead carries
`branch:$branch` — they probably want to run `/mc:brainstorm-issue <N>`
first, or pass a plan path explicitly (see fallback below).

Read the `plan:` comment from the feature bead:

    plan_path=$(bd show "$feature_id" --json \
      | jq -r '.[0].comments[] | .text | select(test("^plan: ")) | sub("^plan: "; "")')

If `$plan_path` is empty, stop and tell the user: the feature bead has no
`plan:` comment — ask for the plan path explicitly.

Verify the plan file exists on disk before transitioning state. If
`$plan_path` doesn't resolve to a readable file, stop and tell the
user — do **not** transition the bead, since the recorded state
would then diverge from reality.

### Without beads (fallback)

If `$skip_beads` is set, ask the user for the plan path. Accept either a
full path (`.superpowers/plans/<slug>.md`) or a bare slug — derive the path
from the slug if the file exists under `.superpowers/plans/`.

## Step 2 — Transition feature bead in_progress

If beads is active:

    bd update "$feature_id" --status=in_progress

Print a one-line ack: `feature $feature_id → in_progress`. If beads is
inactive, skip silently.

## Step 3 — Run executing-plans inline

Invoke the Superpowers skill directly with the resolved plan path:

    /superpowers:executing-plans <plan_path>

This is **inline-only** — do not branch to SDD here. If the plan is SDD
flavoured (Phase 1 marked it as such), the user should invoke
`/superpowers:subagent-driven-development <plan_path>` themselves; this
command intentionally does not wrap that path because SDD's two-stage
review carries its own status discipline.

Follow `superpowers:executing-plans` exactly. Reminders that frequently
get skipped:

- Use `superpowers:verification-before-completion` as the done-gate before
  claiming the plan is finished.
- Tests pass locally before the smoke test.
- Smoke-test the feature before declaring done — type checking verifies
  *correctness*, not *feature correctness* (per project CLAUDE.md / the
  Phase 2 block in `/mc:workflow`).
- Pre-PR smoke bugs → fix inline in this same session, re-smoke, repeat
  until a pass yields zero new findings.

## Step 4 — Transition feature bead awaiting_review

Once the plan is executed and a clean smoke pass has happened:

    bd update "$feature_id" --status=awaiting_review

Print: `feature $feature_id → awaiting_review`.

If the plan execution stopped midway (user interrupted, a task surfaced
a design flaw warranting re-brainstorming, tests failed unrecoverably),
**do not** transition to `awaiting_review`. Leave the bead at `in_progress`
so a later `bd show` or `bd list` reflects that Phase 2 is still in
flight. Tell the user why the transition was skipped.

## Step 5 — Hand off to Phase 3

After the bead lands at `awaiting_review`, two manual steps:

    # Open the draft PR
    gh pr create --draft --title "<title>" --body "<body>"

    # Then in a fresh Opus session
    /mc:review-pr        # slug arg is optional — resolved from bead

Do not open the PR yourself from this command — Phase 2 owns the branch
and the smoke test; the PR-open step is the natural seam between Phase 2
and Phase 3.

## When the description is ambiguous

If neither beads nor a fallback plan path resolves, stop and ask the user
to clarify. Do not guess a plan slug from the branch name — branch and
slug often diverge (e.g., branch `42-fix-auth` for slug
`2026-05-18-auth-token-refresh`).

## Why this command exists

Three reasons:

1. **Single command per phase.** Phase 1 = `/mc:brainstorm-issue`, Phase
   3 = `/mc:review-pr`, Phase 4 = `/mc:fix`. Phase 2 used to require the
   user to remember `/superpowers:executing-plans <slug>` and run the bd
   transitions manually. This closes the gap.
2. **Bead transitions stay atomic with execution.** Forgetting to mark
   the feature `in_progress` or `awaiting_review` desynchronises bd from
   reality. The wrapper closes that gap so the bead always reflects
   where the feature actually is.
3. **Bd-absent repos still benefit.** The fallback to "ask for plan
   path" keeps the command useful in repos without `.beads/`, so the
   workflow has one consistent entrypoint regardless of bd availability.
