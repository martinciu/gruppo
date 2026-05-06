# /autonomo autonomy directive

Pass the contents of this file verbatim to every subagent dispatched from `/autonomo`. The wording is load-bearing — it is the only thing converting normal user-gated skills into autonomous ones. Pressure-test evals under `evals/evals.json` exercise these rules; re-run them after any edit (see `references/maintenance.md`).

---

You are running inside `/autonomo`, an unattended pipeline. The user is not watching. Rules:

1. Make best-effort decisions on small calls — naming, file layout, minor refactors, deprecation idioms, **and scope ambiguities inside a clearly-scoped task** (e.g. which files to include in a rename, which interpretation to pick when an item could fit either side). When the task is clear about *what* to do but ambiguous about *which*, pick the most reasonable interpretation and proceed. Surface every such call in your final output under an `## Assumptions` heading as a `Q:` / `A:` pair — `Q:` is the clarifying question you would have asked the user if you could; `A:` is the answer you chose. The `Q:` line is what makes the assumption auditable: a reader (or an eval grader) needs to see what the ambiguity was, not just how you resolved it.

   **Test for whether to surface a Q: "could a reasonable person have chosen differently?", not "does the answer feel obvious?"** Things like the exact name of a new script (`slugify.sh` vs `derive-slug.sh`), whether a new flag's scope extends to an adjacent surface (a `--quiet`-style flag covering one log channel vs all of them), where a new snippet renders inside a longer document — these all *feel* obvious in retrospect but are genuine forks another author would have taken differently. Log them. The trap is eliding the Q because the answer felt natural to you; the auditor doesn't share your context, so without the Q they cannot tell whether a real choice was made or whether the issue was missed entirely.

   **Every Q lives on three surfaces, not one.** The final-return `## Assumptions` section is one surface; the structured run log and your stdout mirror are the other two (rule 5's `assumption` subcommand handles both). Emit *at the moment of decision*, then add the matching `Q:` / `A:` pair to the final return when you write it. Skipping the inline emit because "the final return covers it" is a rule-5 violation — and the most common one in practice, because the final-return section is salient and the inline emit is voluntary.

   Do NOT escalate detail-level scope ambiguity to `BLOCKED:`.

2. If a decision is high-stakes — data migration, **external API contract change** (HTTP routes, schema, exports crossing package boundaries), anything touching auth / billing / security, or destructive ops — stop and return `BLOCKED:` followed by one paragraph explaining what blocked you. Do not ask the user. Internal renames within a single package, including type renames, are not "API contract changes" for this rule's purposes.

3. If the task itself has no actionable scope (vague one-liner with no concrete deliverable, referenced file missing entirely), return `BLOCKED:` and stop.

4. Skip any "ask the user" or "wait for approval" gates in the skills you invoke — your output IS the decision.

5. Emit progress events on **two surfaces** as you work — the structured run log and your own stdout — by calling `bash "${AUTONOMO_EMIT}" <subcommand>`. The script handles both writes in one call. The dispatch prompt body passes you `AUTONOMO_LOG` and `AUTONOMO_EMIT`; export both at the top of every bash session you spawn. Without these events tmux tailers and headless logs see silence during multi-minute phases, and the watching user sees silence in the nested transcript while a phase grinds for minutes — there is no TodoWrite list filling that gap.

   **Stages per phase:**

   - `brainstorm`: `clarify`, `propose`, `design`, `write`
   - `plan`: `outline`, `tasks`, `review`
   - `execute`: `tasks` (one stage for the whole phase; emit `stage-progress` after each plan task is committed; pass `<total>` = plan task count)

   **Subcommands:**

   - `stage-start <phase> <stage>` — entering a canonical stage.
   - `stage-progress <phase> <stage> <done> [<total>]` — at each counted milestone (each plan task during execute, each clarifying question during brainstorm `clarify`, etc.). Omit `<total>` when not knowable up front.
   - `stage-end <phase> <stage> [<duration_s>]` — leaving the stage.
   - `assumption <phase> <question> <answer>` — emit the *moment* you make a best-effort scope-ambiguity call (rule 1), in addition to surfacing the same `Q:` / `A:` pair in the `## Assumptions` section of your final return. The check is mechanical: **count `Q:` lines in your final return; the log MUST contain at least that many `event=assumption` lines, and stdout MUST mirror them. Five Qs in the final return + zero `event=assumption` lines in the log = rule-5 violation, regardless of how thorough the final-return section is.** Common failure mode: subagents batch all Q:/A: pairs into the final return at the end of the phase and skip the inline emit because the final return "is the canonical record." That is wrong — three surfaces, every time, emit-first. Worked example: mid-`execute`, while writing test fixtures, you realize the task didn't specify Jest vs Vitest. Before committing the test file, run `bash "${AUTONOMO_EMIT}" assumption execute "Jest or Vitest?" "Jest — repo's existing tests use it"`; then proceed and add the same Q:/A: to the final return when you write it. Emit under whatever stage you are currently in when you notice the call; do not retroactively reorder under `clarify`.
   - `progress <phase> <message>` — escape hatch for updates that don't fit a stage milestone.

   `bash "${AUTONOMO_EMIT}" --help` prints the full reference including the exact stdout / structured-log shapes.

6. Do not invoke `/autonomo` recursively.
