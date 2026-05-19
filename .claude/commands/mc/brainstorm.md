---
description: Drive a GitHub issue from brainstorm → spec → plan → review-note, grounded in project skills and context7 docs
argument-hint: <issue-number>
model: claude-opus-4-7
---

You are driving GitHub issue **#$ARGUMENTS** in the current repo from brainstorm all the way to a saved plan and review-note. Do not stop after the spec — continue through `superpowers:writing-plans` and `/mc:review-note`, and finish only once all three artifacts (spec, plan, review-note) are on disk.

## Beads integration (optional)

If `bd` is on PATH (beads is installed — `.beads/` does NOT need to exist
yet; Step 5 will create it on first use), the command additionally
records per-feature state in beads. Otherwise the command behaves exactly
as documented below — no extra prompts, no banner.

Unlike the read-side `/mc:*` commands (which require `.beads/` to already
exist via `bd status`), this command is the *bootstrap* — it's the only
command that ever runs `bd init`.

Detection one-liner:

    command -v bd >/dev/null 2>&1 || skip_beads=1

Every `bd ...` invocation below is guarded by `[ -z "$skip_beads" ]`. A
failure inside a guarded block **never** blocks the underlying workflow
step — log the error, continue.

## Step 1 — Fetch the issue

Run:

```sh
gh issue view $ARGUMENTS --json number,title,body,labels,comments
```

Read the title, body, and any comments carefully. If the issue does not exist or `$ARGUMENTS` is empty, stop and tell the user.

## Step 2 — Classify the work surface and load skills

Based on the issue content, decide which surfaces it touches (language, framework, libraries, subsystem). Then:

1. Check the project's `CLAUDE.md` (and `CLAUDE.local.md`) for any project-specific skill conventions or required-skill mappings — projects often pin a bundle like `samber/cc-skills-golang:*`, a Rails skill set, etc. with a surface→skill table. Follow whatever the project specifies.
2. Load each identified skill via the `Skill` tool **before** proposing any design. Loading skill content as design inputs is the whole point — don't skim, don't defer.
3. If the issue references a third-party library, framework, SDK, or CLI tool, call `mcp__plugin_context7_context7__resolve-library-id` + `mcp__plugin_context7_context7__query-docs` to ground recommendations in current docs. Do this **before** proposing a design that depends on the library, not after.
4. Load `superpowers:brainstorming` last — it drives the rest of the session.

State your classification in one sentence ("Issue touches cache + CLI surfaces — loading `<skill-a>` and `<skill-b>`"). If the project has no skill conventions and the issue is pure UX/copy/config, say so and skip skill loading.

## Step 3 — Brainstorm → spec

Follow `superpowers:brainstorming` exactly. Reminders that frequently get skipped:

- **One clarifying question at a time.** No bundles, no shortcuts, even in auto mode.
- **No code, no design, no plan** until intent is locked in.
- The spec goes under `.superpowers/specs/` — never `docs/superpowers/`, never committed.
- Reference issue #$ARGUMENTS in the spec frontmatter so it can be traced.

Do **not** stop here. Once the spec is written and the user has confirmed it captures intent, continue to Step 4.

## Step 4 — Write the plan

Load `superpowers:writing-plans` and follow it to convert the spec into an implementation plan.

- Plan file goes under `.superpowers/plans/` (gitignored — never `docs/superpowers/`, never committed).
- Reference both the spec path and issue #$ARGUMENTS in the plan frontmatter.
- Keep skill context loaded — task breakdowns should reflect the idiomatic patterns from the skills loaded in Step 2, not retrofit them later.
- Apply the inline-vs-SDD guidance from `~/.claude/CLAUDE.md` when shaping tasks: state the chosen execution mode and reason in the plan.

## Step 5 — Pin feature state in beads (optional)

If `bd` is on PATH (`command -v bd` exits 0), pin per-feature state.
Otherwise skip.

1. **Ensure bd has a reachable database.** Test with `bd status`, which
   walks up from CWD looking for a `.beads/` (main repo, parent
   worktree, anywhere up the tree). If reachable, skip init — bd is
   already shared across worktrees per its default topology.

       if ! bd status >/dev/null 2>&1; then
         bd init --stealth --quiet --non-interactive
         bd config set status.custom "awaiting_review"
       fi

   Why `bd status` and not `[ ! -d .beads ]`: in a worktree, the
   local directory rarely has its own `.beads/` (the user-level
   `[step.copy-ignored] exclude = [".beads/"]` keeps it out, and
   `bd init --stealth` would abort against the parent's DB anyway
   with "workspace already initialized"). The walk-up check is the
   correct signal — bd is "ready" if any ancestor has been
   initialized, regardless of where exactly.

   The init branch fires only on the very first
   `/mc:brainstorm` run in a project (no `.beads/` anywhere up
   the tree). Subsequent runs — same project, any worktree — skip
   straight to step 2.

2. Create the feature bead:

       branch=$(git symbolic-ref --short HEAD)
       feature_id=$(bd create \
         --type feature \
         --priority P1 \
         --labels "branch:$branch" \
         --description "<one-sentence summary>" \
         "<gh issue title>" \
         --json | jq -r '.id // .[0].id')
       bd comment "$feature_id" "github-issue: #$ARGUMENTS"
       bd comment "$feature_id" "slug: <slug>"
       bd comment "$feature_id" "spec: .superpowers/specs/<slug>.md"
       bd comment "$feature_id" "plan: .superpowers/plans/<slug>.md"
       bd comment "$feature_id" "review-note: .superpowers/review-notes/<slug>.md"

   The three artefact-path comments let `/mc:execute` and `/mc:review`
   resolve their inputs without re-parsing the slug. Substitute the
   actual slug; do not leave the literal `<slug>` token.

   **`--description` is a single sentence** distilled from the spec
   you just wrote — what this feature *does*, in plain prose. Not the
   issue title verbatim, not a multi-paragraph summary. One sentence,
   declarative, no trailing period required. Example: "Wire beads as
   the per-feature state spine across the `/mc:*` workflow."

3. Print a one-line footer ack:

       echo "bead $feature_id created"

Failure handling: each sub-step is independent. If step 1's `bd init`
fails unexpectedly (e.g., permissions, disk full), still attempt
step 2 — `bd create` will tell you whether bd is actually usable. If
step 2 fails (bd unreachable, schema error), log the error and skip
step 3; the spec and plan remain on disk and the workflow continues
to Step 6 (handoff) and Step 7 (review note). **Do not let one bd
failure cascade into skipping the rest of Step 5** — that loses the
feature bead even when bd is otherwise healthy.

## Step 6 — Finish

The plan will be executed by **Sonnet** in a separate session (Opus types at
~5× the per-token cost of Sonnet — keep Opus for design/review, not for
typing diffs). Your job here is to hand off cleanly.

Confirm to the user:

1. The spec path under `.superpowers/specs/`.
2. The plan path under `.superpowers/plans/`.
3. The review-note path that will be written in Step 7:
   `.superpowers/review-notes/<slug>.md` (substitute the actual slug).
4. **Execution-mode recommendation.** Based on the plan's task profile and
   the inline-vs-SDD guidance in `~/.claude/CLAUDE.md`, recommend one:
   - **Inline** (`/superpowers:executing-plans`) — cheaper when most tasks
     are mechanical/byte-exact (TOML/YAML/HTML/config edits, dotfiles,
     cheatsheets). Skips SDD's per-task review token overhead.
   - **SDD** (`/superpowers:subagent-driven-development`) — worth the
     review-token overhead when tasks are real code with logic and
     judgment (~50–300 LOC per task, multi-file integration).

   State the reason in one sentence ("Inline — all tasks are byte-exact
   TOML edits" / "SDD — each task is ~150 LOC of TS with branching
   logic").

5. **Paste-ready command** for the Sonnet session. Print the exact slash
   command in a fenced code block so it is one-click copyable. Format:

   ````
   ```
   /superpowers:executing-plans .superpowers/plans/<slug>.md
   ```
   ````

   …or the `subagent-driven-development` equivalent if SDD was chosen.
   Substitute the actual plan path. Remind the user to start the Sonnet
   session first (e.g. `claude --model sonnet` in a fresh terminal or via
   the model-picker) before pasting.

Do not start implementation yourself.

## Step 7 — Review note (must be last)

Only **after** Steps 5 (bd-create) and 6 (handoff summary) have both
completed, invoke the `/mc:review-note` slash command.

**Argument format — critical:** the argument becomes the filename. Pass
the **bare slug only** — no directory prefix, no `.md` extension. Derive
it from the plan filename:

- Plan path: `.superpowers/plans/2026-05-14-chart-colors-per-unit.md`
- Slug to pass: `2026-05-14-chart-colors-per-unit`
- Resulting note path: `.superpowers/review-notes/2026-05-14-chart-colors-per-unit.md`

Do **not** pass the full plan path — that produces a nested
`.superpowers/review-notes/.superpowers/plans/<file>.md.md` directory
mess.

`/mc:review-note` handles frontmatter on its own — do not post-process
the generated note to add `spec:` or `plan:` pointers (that contradicts
the command's distillation rule).

> **Why this step is last.** Invoking a slash command via the `Skill`
> tool loads that command's instructions as the active context. When
> the invoked skill finishes, the assistant frequently treats the whole
> workflow as done and stops — silently skipping any remaining steps of
> `/mc:brainstorm`. (Observed on `243-schema-missmatch` 2026-05-19: bd
> create and handoff summary both got dropped.) Placing
> `/mc:review-note` last makes this exit benign — the bead is already
> in beads, the handoff is already on screen, and the review note
> landing on disk is the natural end of the workflow.

Stop here.

Begin now with Step 1.
