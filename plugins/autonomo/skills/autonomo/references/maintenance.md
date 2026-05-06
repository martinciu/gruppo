# Maintenance — re-running pressure-test evals

The autonomy directive at `references/autonomy-directive.md` is load-bearing prose. Small wording changes can over-trigger `BLOCKED:` (subagents bail on every ambiguity) or under-trigger it (subagents push past genuinely high-stakes calls). `evals/evals.json` holds one eval per rule, each with a `prompt`, `expectations` (machine-checkable assertions), `green_expectation` (with-directive target behavior), and `red_expectation` (no-directive baseline).

Re-run after any edit to the directive:

1. Open `evals/evals.json` and pick the eval whose `rerun_trigger` covers the wording you touched (each eval names the rule it pressures via `rule_under_test`).
2. Dispatch a subagent (`Agent` tool, `subagent_type=general-purpose`) with the contents of `references/autonomy-directive.md` plus the eval's `prompt`. Stage any `files` the eval lists into the subagent's workspace from `evals/fixtures/<eval-name>/` first. For the `progress-emission` eval, also follow `runner_notes` — pass `AUTONOMO_LOG` and `AUTONOMO_EMIT` and capture both the structured log and the nested-transcript stdout.
3. Score the return against `expectations`. All assertions passing = directive still holds for that rule. If the run instead matches `red_expectation`, the directive regressed; revert or rework the wording.

When all relevant evals pass, bump `plugin.json` `version` (semver: minor for behavioral changes, patch for prose-only tightening).
