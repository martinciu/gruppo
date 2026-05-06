# PR body template

The controller's success path (SKILL.md §5) composes the PR body from the template below, then runs `gh pr create --body "<composed>"`.

## Template

```
## Summary
<1-3 bullets, lifted from the execute-plan subagent's summary>

## Spec
[<basename of SPEC_PATH>](<SPEC_PATH>)

## Plan
[<basename of PLAN_PATH>](<PLAN_PATH>)

## Assumptions
<concatenation of every subagent's `## Assumptions` section, deduplicated>

## Test plan
<from executing-plans subagent's output>

🤖 Opened autonomously by [/autonomo](https://github.com/martinciu/gruppo/blob/main/plugins/autonomo/skills/autonomo/SKILL.md) — no human in the loop.
```

## Composition rules

- The `## Spec` and `## Plan` sections render **only when their file is tracked in git** (`git ls-files --error-unmatch <path>` returns 0). Otherwise drop the entire section — both the heading and the body. No placeholder, no path-only line.
- `SPEC_PATH` and `PLAN_PATH` are written as relative paths. GitHub renders relative links in PR descriptions against the head branch, so a tracked spec at `.superpowers/specs/foo.md` shows up as a working link in the PR.
- The footer link points at the published `autonomo` SKILL.md in the gruppo repo. It is hardcoded — `/autonomo` does not derive its own source URL.
