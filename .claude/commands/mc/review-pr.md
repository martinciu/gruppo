---
description: Review the PR for a finished plan using its review-focus note. Stops after the report — does not auto-apply fixes
argument-hint: [<slug>]    # optional; resolved from the feature bead by default
---

## Beads integration (optional)

If `bd status` exits 0 (beads is installed AND this worktree has `.beads/`),
the command additionally records per-feature state in beads. Otherwise the
command behaves exactly as documented below — no extra prompts, no banner.

Detection one-liner:

    bd status >/dev/null 2>&1 || skip_beads=1

Every `bd ...` invocation below is guarded by `[ -z "$skip_beads" ]`. A
failure inside a guarded block **never** blocks the underlying workflow
step — log the error, continue.

## Step 0 — Resolve the feature, slug, and input paths

With beads (default — `bd status` exits 0): always look up the feature
bead by branch label. It carries the slug and the artefact paths as
comments — pinned by `/mc:brainstorm-issue` at creation time.

    branch=$(git symbolic-ref --short HEAD)
    feature_id=$(bd list --label "branch:$branch" --type feature \
      --json | jq -r '.[0].id // empty')

If `$feature_id` resolved, read the pinned paths:

    slug=$(bd show "$feature_id" --json \
      | jq -r '.[0].comments[] | .text | select(test("^slug: ")) | sub("^slug: "; "")')
    plan_path=$(bd show "$feature_id" --json \
      | jq -r '.[0].comments[] | .text | select(test("^plan: ")) | sub("^plan: "; "")')
    note_path=$(bd show "$feature_id" --json \
      | jq -r '.[0].comments[] | .text | select(test("^review-note: ")) | sub("^review-note: "; "")')

`$ARGUMENTS`, if non-empty, **overrides** the slug from the bead (use
when reviewing a different feature than the current branch suggests).
When `$ARGUMENTS` is set, derive the paths from the slug rather than
the bead's pinned comments — the user is asking for a different feature.

**Status check:** the feature bead is expected to be `awaiting_review`
here (`/mc:execute` transitions it on plan completion). If it's still
`in_progress`, warn: "feature bead is `in_progress` — Phase 2 may not
have finished; the diff may not reflect the full plan." Continue
anyway; do not block.

Without beads, or `$feature_id` is empty: use `$ARGUMENTS`. If
`$ARGUMENTS` is also empty, stop and ask the user for a slug. Do not
fall back silently.

Read three inputs in order:

1. `$plan_path` (or `.superpowers/plans/$slug.md`) — the plan.
2. `$note_path` (or `.superpowers/review-notes/$slug.md`) — the
   review-focus note (deliberation context: decisions to verify,
   rejected approaches, invariants, deferred work).
3. The PR diff. If a PR is open for the current branch, use `gh pr view
   --json number,title,headRefName,body` to locate it and `gh pr diff
   <number>` for the diff; if not, ask which PR number to review.

If any of the three inputs is missing, stop and tell the user which one
— don't proceed on partial context.

## Pin PR number to the feature bead (optional)

If `bd status` exits 0, record the PR number on the feature bead. The
idempotency check avoids duplicate `pr:` comments on re-invocations.

    pr_number=$(gh pr view --json number -q .number)
    if ! bd show "$feature_id" --json \
         | jq -e --arg pr "pr: #$pr_number" \
           '.[0].comments[] | select(.text == $pr)' >/dev/null; then
      bd comment "$feature_id" "pr: #$pr_number"
    fi

## Review focus

Use the review-focus note's sections as the structure of your review:

- For each **decision worth verifying** in the note, confirm the diff reflects it.
  Cite the file:line where you verified or where it drifted.
- For each **rejected approach**, scan the diff for signs it slipped back in.
  Then verify the note's `**Replaced by:**` clause matches reality — that
  whatever fills the rejected approach's slot in the implementation actually
  exists in the diff. If the note has no `Replaced by:` (or it reads
  "nothing — deferred behaviour"), check that the feature still works
  coherently without it; a silent gap (e.g. an existing keybinding becoming
  a no-op in the new mode) is drift, severity 🟡 should-fix at minimum.
- For each **invariant**, treat it as a grep target across the diff.
- For each **edge case**, check the diff has a test or a guard.
- For each **deferred item**, suppress yourself — do not flag as missing.
- For each **risk to probe**, look harder than usual and either clear it or
  raise it as a question.

Beyond the note, apply this project's standing review protocol if one exists.
Check `CLAUDE.md` and `CLAUDE.local.md` (in the project root) for instructions
about review lenses, parallel skill-lensed subagent dispatch, security passes,
or language-specific review skills. Follow whatever the project specifies. If
the project has no standing review protocol, just review on intent and code
quality and skip this paragraph.

## Output format

Produce a single review report with two sections:

1. **Findings** — one flat list of every proposed change, numbered globally
   starting at 1 and never restarting. The number is the only handle used
   to reference a finding. Each entry carries:
   - a severity marker (🔴 must-fix / 🟡 should-fix / 🟢 nit) as metadata,
     not as a sort key or numbering axis,
   - an origin tag — `[drift]` for divergences from the plan or
     review-focus note, `[lens]` for output from project-specific reviewers
     (if the project has a review protocol per above) — also metadata only,
   - a file:line citation.

   Order entries by severity (🔴 → 🟡 → 🟢), then by origin within a tier,
   but the numbers are global and unique across the whole list. Example:
   `1. 🔴 [drift] ...`, `2. 🔴 [lens] ...`, `3. 🟡 [drift] ...`,
   `4. 🟢 [drift] ...`.
2. **Clear** — short summary of what the note told you to verify that *did*
   land correctly. Useful so a follow-up reviewer (you or me) can skip those.
   Not numbered.
3. **Recommendations** — your judgment call on what to do with the findings.
   Reference findings by number only (never re-cite file:line here). Cover:
   - **Apply to satisfy intent** — the minimum subset of findings that must
     land for this PR to actually deliver on the plan / review-focus note.
     The "if I had to ship today, these block the merge" set.
   - **Group together** — findings that share a file, a function, or a
     reasoning thread and should be fixed in one pass rather than separately.
     Format: `Group A: 1, 4, 7 — same regex in <file>`. One-line rationale
     per group. Skip the section if nothing naturally groups.
   - **Defer to a follow-up issue** — findings that are real but out of
     scope for this PR (orthogonal refactor, broader cleanup, deferred work
     the note already flagged, anything that would balloon the diff). For
     each, propose a one-line `gh issue create` title. Don't open the issue
     here — just recommend.
   - **Drop** — findings you'd skip entirely (nits that aren't worth the
     churn, false positives on a second look). Optional; omit if empty.

   A given finding number appears in at most one of these buckets. If a
   finding doesn't appear in any, the user will infer "apply, no grouping,
   no follow-up needed" — which is fine for the common case.

## Pin findings as child beads (optional)

If `bd status` exits 0, for each finding in the report:

    bd create \
      --parent "$feature_id" \
      --type bug \
      --priority P2 \
      "<severity emoji> <one-line finding title>" \
      --description "$(cat <<EOF
file:line — <citation>

Observed: <what we saw>
Expected: <what the note prescribed>

Reproduction: <if non-obvious>
EOF
)" --json | jq -r '.id'

Print `bead bd-XXXX created` per finding as a footer.

Children automatically inherit the feature's `branch:<name>` label
(verified during pre-flight).

## Stop here — wait for approval before any fix is applied

After producing the report, **stop**. Do not dispatch any subagents. Do not
edit any files. Do not commit anything.

End the response with a single explicit prompt for the user:

> Which findings should I apply? Reply with the numbers (e.g. "1, 3, 5",
> a range like "1-4", "accept recommendations" to take the Recommendations
> section as-is, "issue: 6, 8" to spin those off as follow-up `gh` issues
> instead of applying, "none", or describe a different action. Use
> `/mc:fix <description>` to apply each approved fix at the right tier
> (Haiku / Sonnet / inline, picked by `/mc:fix`).

The user picks the subset; nothing is auto-applied.

When the user replies, do **not** type the fix yourself — use `/mc:fix` per
approved finding (one invocation per fix is fine; the command parses multiple
fixes per invocation if the description lists them). Opus decides what to
fix; `/mc:fix` picks the right typing tier (Haiku for mechanical, Sonnet
for judgment-laden, or inline when the fix needs Opus reasoning). Spending
Opus tokens on the typing is quota wasted at roughly 5× Sonnet and 25×
Haiku rates.

## Transition finding beads on user reply (optional)

If `bd status` exits 0, mirror the user's approval decision onto the
finding beads created above:

- **User approves a subset** (e.g. "1, 3, 5", "1-4", "accept
  recommendations"): for each approved finding bead, run

      bd update "$fid" --status=approved

  before dispatching `/mc:fix`.

- **User replies `issue: 6, 8`** to defer findings to GitHub: after
  `gh issue create` for each, close the bead with the new issue ref:

      bd close "$fid" -r "deferred to gh#$new_issue_number"

- **User replies `none`**: no transitions. Leave the finding beads at
  `open` so a future re-invocation can re-surface them.

## What to skip

- Do not re-read the brainstorm transcript. The review-focus note is the
  whole point of this workflow.
- Do not cite `.superpowers/...` paths in the PR review comment or commit
  messages — those paths are gitignored and never appear in shared text.
