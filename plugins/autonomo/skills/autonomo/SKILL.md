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

<TBD task 3: env recursion guard, dependency check>

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
