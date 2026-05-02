---
name: autonomo
description: Use when the user types `/autonomo <input>` to autonomously turn a GitHub issue into a pull request — accepts an issue number, issue URL, or freeform task description. Runs the full superpowers pipeline (brainstorm → plan → execute → PR) without user interaction. For relatively simple tasks; refuses to proceed on a feature branch or with a dirty tree.
---

# Autonomo

<TBD task 9: one-paragraph what-this-does>

## When to use

<TBD task 9: trigger conditions, when NOT to use>

## Procedure

### 1. Preflight

**Recursion guard.** Before doing anything else, check the `AUTONOMO_RUNNING` environment variable.

```bash
if [ "${AUTONOMO_RUNNING:-0}" = "1" ]; then
  echo "BLOCKED: /autonomo invoked recursively. Inner subagents must not call /autonomo."
  exit 1
fi
export AUTONOMO_RUNNING=1
```

Set `AUTONOMO_RUNNING=1` for the rest of the run. Subagents inherit it; if any of them tries to invoke `/autonomo`, that nested run sees the variable set and refuses.

**Dependency check.** Confirm `gh` is authenticated and `git` is available. Either missing → exit before any branch is created.

```bash
command -v gh >/dev/null 2>&1 || { echo "BLOCKED: gh CLI not installed"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "BLOCKED: git not installed"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "BLOCKED: gh not authenticated; run 'gh auth login'"; exit 1; }
```

The `superpowers` plugin is also a hard requirement, but plugin presence isn't shell-checkable — the dispatcher will surface it when the first Agent tool call fails.

### 2. Parse input

<TBD task 4: input parser>

### 3. Pick workspace

<TBD task 5: workspace manager>

### 4. Dispatch phase subagents

<TBD task 6: dispatcher loop, autonomy directive>

### 5. Open PR or write report

<TBD task 7: PR opener and report writer>

## The autonomy directive

<TBD task 6: directive verbatim>

## PR body template

<TBD task 7: PR body template>

## Failure handling

<TBD task 7: failure table, bail-and-report contract>

## Pressure scenarios

<TBD task 8: brief pointer to pressure-scenarios/ folder and how to rerun>
