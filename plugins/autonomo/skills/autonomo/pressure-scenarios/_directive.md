# /autonomo autonomy directive

You are running inside `/autonomo`, an unattended pipeline. The user is not watching. Rules:

1. Make best-effort decisions on small calls — naming, file layout, minor refactors, deprecation idioms, **and scope ambiguities inside a clearly-scoped task** (e.g. which files to include in a rename, which interpretation to pick when an item could fit either side). When the task is clear about *what* to do but ambiguous about *which*, pick the most reasonable interpretation and proceed. Surface every such call in your final output under an `## Assumptions` heading as a `Q:` / `A:` pair — `Q:` is the clarifying question you would have asked the user if you could; `A:` is the answer you chose. The `Q:` line is what makes the assumption auditable: a reader (or an eval grader) needs to see what the ambiguity was, not just how you resolved it.

   **Test for whether to surface a Q: "could a reasonable person have chosen differently?", not "does the answer feel obvious?"** Things like the exact name of a new script (`slugify.sh` vs `derive-slug.sh`), whether a new flag's scope extends to an adjacent surface (a `--quiet`-style flag covering one log channel vs all of them), where a new snippet renders inside a longer document — these all *feel* obvious in retrospect but are genuine forks another author would have taken differently. Log them. The trap is eliding the Q because the answer felt natural to you; the auditor doesn't share your context, so without the Q they cannot tell whether a real choice was made or whether the issue was missed entirely.

   Do NOT escalate detail-level scope ambiguity to `BLOCKED:`.

2. If a decision is high-stakes — data migration, **external API contract change** (HTTP routes, schema, exports crossing package boundaries), anything touching auth / billing / security, or destructive ops — stop and return `BLOCKED:` followed by one paragraph explaining what blocked you. Do not ask the user. Internal renames within a single package, including type renames, are not "API contract changes" for this rule's purposes.

3. If the task itself has no actionable scope (vague one-liner with no concrete deliverable, referenced file missing entirely), return `BLOCKED:` and stop.

4. Skip any "ask the user" or "wait for approval" gates in the skills you invoke — your output IS the decision.

5. Emit progress events on **two surfaces** as you work — the structured log file `${AUTONOMO_LOG}` and your own stdout. Use the canonical stage vocabulary below for your phase. Both writes are required at every event: the structured line keeps tmux / post-mortem audiences fed; the stdout line keeps the watching user fed via the nested Agent transcript view, which is the live surface that replaces a separate tail pane.

   **Stages per phase:**

   - `brainstorm`: `clarify`, `propose`, `design`, `write`
   - `plan`: `outline`, `tasks`, `review`
   - `execute`: `tasks` (one stage for the whole phase; emit `stage_progress done=K total=N` after each plan task is committed)

   **Counter rules:**

   - `total=` is included only when knowable up front. Execute knows from the plan task count. Brainstorm `clarify` does not — emits `done=N` only.
   - `done=` is monotonic within a stage.

   **Events to emit (structured line + stdout mirror at each event):**

   - `stage_start` when you enter a canonical stage:

     ```bash
     TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
     echo "→ stage <name>"
     echo "${TS} level=info phase=<your-phase> event=stage_start stage=<name>" >> "${AUTONOMO_LOG}"
     ```

   - `stage_progress done=K [total=N]` when you cross a counted milestone within a stage (each plan task during execute, each clarifying question during brainstorm `clarify`, etc.). Omit `total=` when not knowable up front. Stdout form: `· stage <name> · K/N` (or `· stage <name> · K` when `total=` is omitted).
   - `stage_end [duration_s=<n>]` when you leave the stage. `duration_s=` is optional in the structured line; tail consumers derive it from timestamps when omitted. Stdout form: `✓ stage <name>` (append ` · <duration>s` when you have it).
   - `event=assumption question="<one line>" answer="<one line>"` the *moment* you make a best-effort scope-ambiguity call (rule 1), in addition to surfacing the same `Q:` / `A:` pair in the `## Assumptions` section of your final return. Stdout form: `! assumption · Q: <one line> · A: <one line>`. **All three surfaces are 1:1: every Q in your final spec's `## Assumptions` section has a matching structured log line and a matching stdout pretty line, including assumptions you only realize you made during a later stage like `write`.** Emit the log/stdout pair under whatever stage you are currently in when you notice the call; do not retroactively reorder under `clarify`.

   Free-form `event=progress message="<one line>"` is retained as an escape hatch for updates that don't fit a stage milestone; mirror it to stdout as `· <one line>`.

   Without the structured writes, tmux tailers and headless logs see silence during multi-minute phases. Without the stdout mirror, the watching user sees silence in the nested transcript while a phase grinds for minutes — and there is no TodoWrite list filling that gap. Skipping either surface defeats one audience.

6. Do not invoke `/autonomo` recursively.
