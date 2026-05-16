---
description: Find your place in the Superpowers workflow and get the next 1–2 steps with model + effort
argument-hint: <phase>
---

You are helping the user navigate the Superpowers workflow described
in `.claude/commands/mc/workflow.md`. Source-of-truth content lives
in that file — load it on every invocation so any updates flow
through automatically.

## Steps

1. **Load the workflow.** Use the `Read` tool on
   `.claude/commands/mc/workflow.md` so you have the full phase
   content, model + effort picks, and `/mc:*` command references in
   context.

2. **Determine the phase.** `$ARGUMENTS` may carry a phase identifier
   (number `1`–`5`, a phase name like `brainstorm` / `execute` /
   `review` / `fix` / `verify`, or `fresh` / `start` / `0` to mean
   "no phase yet, starting from scratch"). Parse it leniently — match
   on intent, not strict format.

   If `$ARGUMENTS` is empty or you cannot confidently parse it, ask:

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

   Treat "starting fresh" / "0" as Phase 1.

3. **Return a tight summary for that phase.** Include only:
   - Session (A / B / C; fresh or resumed) and whether to spawn a
     new Claude Code session for it.
   - Model + `/effort` level, drawn directly from the doc's cheat-sheet.
   - Whether `ultrathink` is worth dropping into specific turns within
     that phase.
   - The exact `/mc:*` command to run, paste-ready in a fenced code
     block. Substitute concrete arguments where you can infer them
     from the conversation; otherwise leave `<placeholder>`.
   - One sentence on what that command does.
   - Pointer to the next phase, including the `/mc:workflow-next <N>`
     invocation that would advance the user.

   Keep the response **under 15 lines.** Distill — do not quote long
   passages from the doc verbatim. If the phase needs no `/mc:*`
   command (e.g. Phase 5 verify + merge is mostly running tests and
   `git push`), say so plainly with the 3–4 concrete actions.

4. **Stop.** Do not auto-advance into the next phase. Do not start
   running the command yourself. The user invokes the command when
   they are ready, then re-runs `/mc:workflow-next` for the next
   summary.

## What to skip

- Don't print the entire workflow doc back — that's what
  `/mc:workflow` is for.
- Don't restate the rationale for the workflow's shape (three
  sessions, divergent vs convergent, etc.); the user has the doc.
  Just answer "what next?".
- Don't ask process-meta questions ("should I include effort
  guidance?"). Always include the bullets listed in step 3 — that is
  the shape.

## When the phase is mid-cycle

Phase 4 ↔ smoke test cycles between "apply a fix" and "retest." If
the user says they just applied a fix and are about to retest, the
right summary is Phase 4 with a closing pointer to Phase 5 once
testing yields zero new findings. If they say they just retested and
found something, the right summary is Phase 4 again with the fix-brief
template. Read which side of the loop they're on from context.
