---
description: Find your place in the Superpowers workflow and get the next 1–2 steps with model + effort
argument-hint: <phase>
---

Answer "what next?" by printing the matching phase block below. Phase
summaries are inlined — no file Read needed. The full reference lives
in `/mc:workflow`; this command is the slim navigator.

## Beads integration (optional)

If `bd status` exits 0 (beads is installed AND this worktree has `.beads/`),
the command additionally records per-feature state in beads. Otherwise the
command behaves exactly as documented below — no extra prompts, no banner.

Detection one-liner:

    bd status >/dev/null 2>&1 || skip_beads=1

Every `bd ...` invocation below is guarded by `[ -z "$skip_beads" ]`. A
failure inside a guarded block **never** blocks the underlying workflow
step — log the error, continue.

## Steps

0. **Optional beads-driven phase inference.**

   If `bd status` exits 0 AND `$ARGUMENTS` is empty:

       branch=$(git symbolic-ref --short HEAD)
       feature_id=$(bd list --label "branch:$branch" --type feature \
         --json | jq -r '.[0].id // empty')

   If `$feature_id` resolved:

       has_pr=$(bd show "$feature_id" --json \
         | jq -r '[.[0].comments[] | .text | select(test("^pr: "))] | length')
       outstanding=$(bd list --parent "$feature_id" \
         --status open,approved,in_progress,awaiting_review \
         --json | jq 'length')

   Decision tree:

   - No `pr:` comment yet, no outstanding findings → Phase 2.
   - `pr:` comment present, no outstanding findings → Phase 5.
   - `pr:` comment present, outstanding findings with status `open`
     only → Phase 3.
   - `pr:` comment present, any finding `approved` or `in_progress`
     or `awaiting_review` → Phase 4.
   - No `pr:` comment, no feature bead → fall through to the existing
     picker.

   Print the inferred phase as `Inferred phase from beads: N` then
   continue to step 1 with that phase as if it had been passed in
   `$ARGUMENTS`.

1. **Resolve the phase from `$ARGUMENTS`.** Match leniently:
   - `1` / `brainstorm` / `plan` / `spec` → Phase 1
   - `2` / `execute` / `exec` / `code` → Phase 2
   - `3` / `review` / `pr` → Phase 3
   - `4` / `fix` / `apply` / `dispatch` → Phase 4
   - `5` / `verify` / `merge` / `done` → Phase 5
   - `0` / `fresh` / `start` / `new` → Phase 1
   - empty or unrecognised → step 2

2. **Picker** (only when step 1 yields no phase). If beads inferred a
   phase in step 0, the picker is skipped. Ask:

   ```
   Which phase are you on?
     1. Brainstorm + plan
     2. Execute + smoke test
     3. PR review
     4. Apply fixes (review + manual testing)
     5. Verify + merge
     0. Starting fresh — no phase yet

   Reply with the number or a keyword.
   ```

   Apply step 1's mapping to the answer.

3. **Print the matching phase block from below verbatim.** Do not
   paraphrase, do not act on it, do not ask follow-ups. The user runs
   the command themselves and re-invokes `/mc:workflow-next <next>`
   when ready.

## Mid-cycle nuance

Phase 4 loops with smoke testing. If the user signals they just
applied a fix and are about to retest, print Phase 4 and remind them
the loop closes when a smoke pass yields zero new 🔴/🟡. If they
signal they just retested and found something, print Phase 4 again
with the fix-brief framing. Read which side of the loop they're on
from context.

---

## Phase 1 — Brainstorm + plan

**Session A (fresh) · Opus 4.7 · `/effort max`** (use `xhigh` default if
you'd rather not bump for one issue).

`ultrathink` on clarifying-question synthesis and design-shape selection
turns — the moments where one decision reshapes the whole spec.

```
/mc:brainstorm-issue <issue-number>
```

Drives the issue end-to-end in one session: `gh issue view` → skill load
→ context7 docs → brainstorm → spec → plan → review-note. Outputs three
artefacts under `.superpowers/` (specs / plans / review-notes — all
gitignored) and a paste-ready handoff command for Session B.

Next: `/mc:workflow-next 2` once the handoff command is printed.

---

## Phase 2 — Execute + smoke test

**Session B (fresh) · Sonnet 4.6 · `/effort high`** (drop to `low` /
`medium` on plans that are mostly mechanical).

`ultrathink` not typically needed here.

```
/superpowers:executing-plans .superpowers/plans/<slug>.md
```

…or, if SDD was recommended in Phase 1:

```
/superpowers:subagent-driven-development .superpowers/plans/<slug>.md
```

Walks the plan tasks. SDD dispatches per-task subagents — **Haiku 4.5**
for mechanical edits, **Sonnet 4.6** for multi-file logic, inline Opus
for architectural judgment. Use `superpowers:verification-before-completion`
as the done-gate. Smoke-test before opening the draft PR.

**Smoke bugs found here → fix inline in Session B**, then re-smoke
until clean. The Sonnet agent that wrote the code has fresh context
to fix it; no need to spawn Session C. Open the draft PR only when a
smoke pass yields zero new findings. Stop and surface to user only if
a bug suggests a design flaw (may warrant re-brainstorming).

Next: `/mc:workflow-next 3` once the draft PR is open.

---

## Phase 3 — PR review

**Session C (fresh) · Opus 4.7 · `/effort xhigh`** (bump to `max` for
diffs spanning many files, touching security/migration, or carrying a
long `Replaced by:` list).

`ultrathink` into the `Replaced by:` verification turn when reviewing
high-stakes rejected approaches — those are the easiest drift to miss.

```
/mc:review-pr <slug>
```

Reads `.superpowers/plans/<slug>.md` + `.superpowers/review-notes/<slug>.md`
+ the PR diff. Produces a structured findings report — globally
numbered, ordered 🔴 / 🟡 / 🟢, tagged `[drift]` / `[lens]`, each with
a `file:line` citation. Then stops with apply / group / defer / drop
recommendations and asks which subset to apply.

Next: `/mc:workflow-next 4` to dispatch the approved fixes.

---

## Phase 4 — Apply fixes (review + manual testing)

**Session C (continues) · Opus 4.7 dispatcher · `/effort xhigh`** →
typers **Haiku 4.5** / **Sonnet 4.6** / inline Opus.

Two input streams, same dispatcher: formal review findings (the subset
you approved in Phase 3) and **post-PR** manual testing observations
(mid-review pull-and-poke, post-fix regression, Phase 5 final pass).
Pre-PR smoke bugs were already fixed inline in Session B during
Phase 2 — they don't reach this dispatcher. Frame manual findings as
briefs: *file/target · observed vs expected · repro steps if
non-obvious*.

`ultrathink` into the inline-Opus turn when a single architectural
decision dominates the fix.

```
/mc:fix <description>
```

Routes each fix to the right tier — Haiku for mechanical, Sonnet for
judgment, inline Opus for architectural. Dispatcher reads each returned
diff, verifies intent, stages and commits inside Session C.

After the commit lands: switch back to **Session B** to push (Session C
doesn't own the branch). Smoke-test again — new findings loop back
here. Zero new 🔴/🟡 → Phase 5.

Next: `/mc:workflow-next 5` once the loop closes clean.

---

## Phase 5 — Verify + merge

**Session B (resumed) · Sonnet 4.6 · `/effort low`**

No `/mc:*` command drives this phase — manual checklist:

1. Pull fix commits if they landed in a separate working copy;
   otherwise already local.
2. Re-run the full test suite. Invoke
   `superpowers:verification-before-completion` as the "ready to merge"
   gate.
3. Final smoke test on the golden path + whatever Phase 4 changed.
   Typer-tier findings → fix inline in Session B and re-smoke.
   Architectural / mixed-tier findings → resume or respawn Session C
   for `/mc:fix`.
4. Push the branch.
5. Mark the PR ready (or self-merge if your workflow allows).
6. After merge: invoke `superpowers:finishing-a-development-branch` to
   handle cleanup — delete branch, prune worktree, etc.

Next: nothing — you're done. Open a fresh Session A on the next issue.
