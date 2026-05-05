# Maintenance — re-running pressure scenarios

The autonomy directive at `references/autonomy-directive.md` is load-bearing prose. Small wording changes can over-trigger `BLOCKED:` (subagents bail on every ambiguity) or under-trigger it (subagents push past genuinely high-stakes calls). `pressure-scenarios/` holds one scenario per rule, each with a task input, a RED expectation (baseline behavior without the directive), and a GREEN expectation (behavior with the directive in place).

Re-run after any edit to the directive:

1. Pick a scenario file under `pressure-scenarios/`.
2. Dispatch a subagent (`Agent` tool, `subagent_type=general-purpose`) with the contents of `references/autonomy-directive.md` plus the scenario's "Task input". Set `AUTONOMO_LOG` and `AUTONOMO_EMIT` if the scenario exercises rule 5.
3. Compare the return against the scenario's GREEN expectation. If it matches, the directive still holds for that rule; if it matches RED, the directive regressed.

Each scenario lists its own "Rerun trigger" — at minimum re-run the scenarios whose rerun trigger covers the wording you touched.

When all relevant scenarios pass, bump `plugin.json` `version` (semver: minor for behavioral changes, patch for prose-only tightening).
