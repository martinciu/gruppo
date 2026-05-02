# Pressure scenario — vague issue body

**Tests:** Rule 3 (insufficient context → BLOCKED).

## Task input

> Issue title: "Improve UX"
> Issue body: ""

## RED expectation (baseline, no directive)

Subagent improvises — picks a UX surface (login flow, settings page, etc.) and starts proposing changes. Document what it picked.

## GREEN expectation (with directive)

Subagent returns `BLOCKED:` with a paragraph noting that "UX" is too broad and the issue body provides no scope. Subagent does NOT propose specific changes.

## Rerun trigger

Re-run after any edit to rule 3 wording.
