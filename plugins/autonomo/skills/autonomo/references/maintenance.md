# Maintenance — re-running pressure-test evals

The autonomy directive at `references/autonomy-directive.md` is load-bearing prose. Small wording changes can over-trigger `BLOCKED:` (subagents bail on every ambiguity) or under-trigger it (subagents push past genuinely high-stakes calls). `evals/evals.json` holds one eval per rule, each with a `prompt`, `expectations` (machine-checkable assertions), `green_expectation` (with-directive target behavior), and `red_expectation` (no-directive baseline).

## Re-run after any edit to the directive

1. Open `evals/evals.json` and pick the eval whose `rerun_trigger` covers the wording you touched (each eval names the rule it pressures via `rule_under_test`).
2. Dispatch a subagent (`Agent` tool, `subagent_type=general-purpose`) with the contents of `references/autonomy-directive.md` plus the eval's `prompt`. Stage any `files` the eval lists into the subagent's workspace from `evals/fixtures/<eval-name>/` first. For the `progress-emission` eval, also follow `runner_notes` — pass `AUTONOMO_LOG` and `AUTONOMO_EMIT` and capture both the structured log and the nested-transcript stdout.
3. Score the return against `expectations`. All assertions passing = directive still holds for that rule. If the run instead matches `red_expectation`, the directive regressed; revert or rework the wording.

When all relevant evals pass, bump `plugin.json` `version` (semver: minor for behavioral changes, patch for prose-only tightening).

## Multi-run guidance

A single dispatch per eval is enough for the obvious cases — a clear pass on every assertion or a clear regression to the RED baseline. For borderline returns (some assertions flake, the answer drifts on rerun, or the eval was historically non-discriminating), run **N≥3 dispatches per arm** and report the pass rate. Treat anything below 100% with-directive on its rule's eval as a regression: a directive that "usually" surfaces an `## Assumptions` block is not load-bearing.

## Exercising the full controller path

The per-eval dispatch above runs the directive against a single phase in isolation, which is what `evals.json` is designed for. To exercise the full `/autonomo` pipeline (preflight → brainstorm → plan → execute, with phase handoffs and the controller's own logic), invoke `/autonomo --dry-run "<task>"` against a real task. The pipeline runs end-to-end and produces spec, plan, and commits locally, but skips `git push` and `gh pr create` — see `SKILL.md` `## When to use`. Useful when the edit affects controller behavior (e.g. dispatch-prompt wording, phase wrapping) rather than directive prose alone.

## Workspace convention for benchmark-grade evaluation

When you need a benchmark-grade run (parallel with-directive vs baseline, timing capture, qualitative grading), use the `/skill-creator` evaluation workflow. Working runs are kept under `plugins/autonomo/skills/autonomo-workspace/iteration-N/` — the directory is gitignored (`plugins/*/skills/*-workspace/` in the repo root `.gitignore`), so each iteration lives only on the machine that ran it. The `with_skill/` and `without_skill/` per-eval subdirectories, `timing.json`, `grading.json`, and `benchmark.json` schema follow the `/skill-creator` convention; see that skill's `SKILL.md` for the full pipeline.
