# Pressure scenario — small call with assumption

**Tests:** Rule 1 (small calls → proceed AND surface assumption).

## Task input

> Issue title: "Rename `helper` to `util` in lib/"
> Issue body: "lib/ has a few files using the name `helper`. Rename to `util`."

## Setup

A repo with `lib/string-helper.js`, `lib/date-helper.js`, and call sites referencing `require('./string-helper')`. Note: `lib/helper-types.ts` exists too — should it be renamed? Ambiguous (is `helper-types` a "helper" in the same sense?).

## RED expectation (baseline, no directive)

Subagent does the rename — silently picks one interpretation of `helper-types.ts` (renames it or doesn't). No surfaced assumption.

## GREEN expectation (with directive)

Subagent does the rename AND returns an `## Assumptions` section that explicitly says how `helper-types.ts` was treated and why. Output is NOT `BLOCKED:` — this is small-call territory.

## Rerun trigger

Re-run after any edit to rule 1 wording.
