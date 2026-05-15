---
description: Drive a GitHub issue from brainstorm → spec → plan → review-note, grounded in project skills and context7 docs
argument-hint: <issue-number>
model: claude-opus-4-7
---

You are driving GitHub issue **#$ARGUMENTS** in the current repo from brainstorm all the way to a saved plan and review-note. Do not stop after the spec — continue through `superpowers:writing-plans` and `/mc:review-note`, and finish only once all three artifacts (spec, plan, review-note) are on disk.

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

## Step 5 — Review note

Once the plan file has been written and saved (confirm on disk before continuing), invoke the `/mc:review-note` slash command.

**Argument format — critical:** `$ARGUMENTS` becomes the filename. Pass the **bare slug only** — no directory prefix, no `.md` extension. Derive it from the plan filename:

- Plan path: `.superpowers/plans/2026-05-14-chart-colors-per-unit.md`
- Slug to pass: `2026-05-14-chart-colors-per-unit`
- Resulting note path: `.superpowers/review-notes/2026-05-14-chart-colors-per-unit.md`

Do **not** pass the full plan path — that produces a nested `.superpowers/review-notes/.superpowers/plans/<file>.md.md` directory mess.

`/mc:review-note` handles frontmatter on its own — do not post-process the generated note to add `spec:` or `plan:` pointers (that contradicts the command's distillation rule).

## Step 6 — Finish

The plan will be executed by **Sonnet** in a separate session (Opus types at
~5× the per-token cost of Sonnet — keep Opus for design/review, not for
typing diffs). Your job here is to hand off cleanly.

Confirm to the user:

1. The spec path under `.superpowers/specs/`.
2. The plan path under `.superpowers/plans/`.
3. The review-note path produced in Step 5.
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

Do not start implementation yourself. Stop here.

Begin now with Step 1.
