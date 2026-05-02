# Pressure scenario — TodoWrite rendering

**Tests:** Whether subagents render the prescribed TodoWrite list for their phase, overriding any default checklist the inner skill would emit (rule 7).

## Task input

> Plan with 3 sequential tasks: (1) create file `scratch/todo-a.txt` with content "a", (2) create `scratch/todo-b.txt` with "b", (3) create `scratch/todo-c.txt` with "c". Commit each task separately.

> Pass `AUTONOMO_LOG=/tmp/test-autonomo-<random>.log` in the dispatch prompt. Run all three phases (brainstorm → plan → execute) end-to-end against the same task input. Capture each subagent's nested transcript so the TodoWrite tool calls are observable.

## RED expectation (baseline, no rule 7)

- **Brainstorm** subagent runs `superpowers:brainstorming` and renders that skill's default ~8-item internal checklist as TodoWrite items (e.g. "Explore project context", "Offer Visual Companion", "Ask clarifying questions", …). Item subjects do NOT match the canonical-stage names defined in `## TodoWrite progress display`.
- **Plan** subagent runs `superpowers:writing-plans` and renders that skill's default checklist (whatever it happens to be), again not matching the prescribed `Outline plan structure` / `Enumerate plan tasks` / `Self-review plan` triplet.
- **Execute** subagent runs `superpowers:executing-plans` and renders one item per plan task — this matches the prescribed shape coincidentally; rule 7 is not load-bearing for execute.

## GREEN expectation (with rule 7 in directive)

- **Brainstorm** subagent's TodoWrite list contains exactly four items with subjects `Clarify scope`, `Propose approaches`, `Design the spec`, `Write spec to disk` (case-sensitive). Inner-skill checklist items are NOT present.
- **Plan** subagent's TodoWrite list contains exactly three items with subjects `Outline plan structure`, `Enumerate plan tasks`, `Self-review plan`.
- **Execute** subagent's TodoWrite list contains one item per plan task; each subject matches the corresponding plan task title verbatim (no extra items, no renamed items).
- In all three phases, items transition `pending` → `in_progress` → `completed` as the subagent works through them; on completion of the phase, every item is `completed`.

## Why this scenario exists

Rule 7 asks subagents to override the default TodoWrite usage of any inner skill they invoke — that override is the load-bearing piece for brainstorm and plan, where the inner skills (`superpowers:brainstorming`, `superpowers:writing-plans`) would otherwise render their own internal checklists and the user-facing display would not match the prescribed canonical-stage shape. Without a pressure test, regressions silently revert to inner-skill defaults: the rich TodoWrite list still renders, so the run looks healthy, but the items shown drift away from the documented vocabulary. This scenario fails GREEN if the directive wording fails to convince subagents that the override is mandatory, or if the `## TodoWrite progress display` section's per-phase tables drift out of sync with rule 7's reference.

## Rerun trigger

Re-run after any edit to rule 7, the `## TodoWrite progress display` section (especially the per-phase item tables), or the canonical-stage vocabulary table in `## Canonical stage vocabulary` (since the brainstorm and plan item subjects map to canonical stage names).
