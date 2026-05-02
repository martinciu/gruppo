---
name: autonomo
description: Use when the user types `/autonomo <input>` to autonomously turn a GitHub issue into a pull request — accepts an issue number, issue URL, or freeform task description. Runs the full superpowers pipeline (brainstorm → plan → execute → PR) without user interaction. For relatively simple tasks; refuses to proceed on a feature branch or with a dirty tree.
---

# Autonomo

`/autonomo <input>` takes a GitHub issue (number, URL) or a freeform task description and runs the full `superpowers` pipeline — brainstorm a spec, write a plan, execute the plan, open a PR — without prompting the user. The user is not watching: subagents make best-effort decisions on small calls and bail with `BLOCKED:` only on high-stakes ambiguity. On success it prints a PR URL; on bail it leaves the branch and a one-page report at `tmp/autonomo/<slug>-<timestamp>.md`.

## When to use

Use `/autonomo` for issues that are well-scoped, single-package, and don't touch auth, billing, security, data migration, or external API contracts. Typical fits: typo fixes, internal renames, adding a small utility, fleshing out a clearly-described function, doc tweaks. Either an issue with a concrete actionable body, or a freeform one-liner you'd otherwise paste into a fresh session.

Do NOT use it for:

- Multi-subsystem work, anything spanning packages or services.
- Tasks where the right answer depends on judgment calls the issue doesn't resolve (the subagents will bail).
- Anything where you need to be in the loop — `/autonomo` is unattended by design. If you want to review the spec or plan before implementation, run the underlying `superpowers` skills directly.
- Starting from a feature branch or a dirty tree. The skill refuses both; switch to `main`/`master` (or a clean worktree) first.

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

The `<input>` argument from `/autonomo <input>` resolves to one of three shapes. The controller picks based on syntax:

| Shape | Match | Resolution |
|-------|-------|------------|
| Issue number | `^\d+$` or `^#\d+$` | `gh issue view <N> --json title,body,number` against the current repo |
| Issue URL | matches `github.com/.+/issues/\d+` | `gh issue view <url> --json title,body,number` |
| Freeform | anything else (non-empty) | `{title: <input>, body: "", source: "freeform"}` — no `gh` call |
| Empty | `<input>` is empty / whitespace only | exit `BLOCKED: usage: /autonomo <issue-number \| issue-url \| "task description">` |

Store the resolved task object as `TASK` for the rest of the run. For issue inputs, also store `ISSUE_NUMBER` (used later in the PR body's `Closes #N` line). For freeform, leave `ISSUE_NUMBER` empty.

If `gh issue view` fails (network, auth, nonexistent issue, no read access), surface the error one-line and exit. Do not proceed.

### 3. Pick workspace

Inspect git state, decide where the work goes. Refuse to start from a non-clean baseline.

**Slug derivation.** Compute `<slug>` once, used for both the branch name and the report filename:

- For issue inputs: kebab-case the issue title, ASCII-only, max 40 chars (truncate at the last word boundary inside the limit).
- For freeform inputs: `auto-<unix-timestamp>`.
- If the slugified issue title comes out empty (emoji-only, all non-Latin script): fall back to `auto-<unix-timestamp>`.

Capture `RUN_TIMESTAMP=$(date +%s)` once at this point — used later for the report filename if the run bails.

**Decision table:**

| Current state | Action |
|---------------|--------|
| On `main` / `master`, working tree clean | `git checkout -b autonomo/<slug>` |
| Inside a worktree, working tree clean | If `wt` CLI is available, `wt new autonomo/<slug>`. Else `git worktree add ../<slug> -b autonomo/<slug>` and `cd` into it. |
| On a feature branch (any branch other than `main`/`master`, not in a worktree) | exit `BLOCKED: not running on a feature branch; switch to main or a clean worktree first` |
| Working tree dirty (any uncommitted changes) | exit `BLOCKED: working tree dirty; stash or commit first` |

**Detecting "inside a worktree":** `git rev-parse --git-dir` ends in `/.git/worktrees/<name>` for linked worktrees; for the main repo it's `.git`. Use this to distinguish.

Store the decision (`mode=branch` or `mode=worktree`) and the resulting branch name as `BRANCH_NAME` — the PR opener step uses both.

### 4. Dispatch phase subagents

Dispatch four subagents in sequence using the Agent tool. Each invocation passes the autonomy directive (verbatim, see below) plus phase-specific context. After each return, check whether the output starts with `BLOCKED:` — that is the controlled-failure marker. Anything else (subagent crash, tool error) is uncontrolled failure; treat both the same way.

| Phase | Subagent prompt (in addition to the autonomy directive) | Side effect | Return |
|-------|--------------------------------------------------------|-------------|--------|
| 1. Brainstorm | "Run the `superpowers:brainstorming` skill on this task. Produce a spec. Issue title: `<title>`. Issue body: `<body>`." | spec file written | spec path + 1-paragraph summary, OR `BLOCKED: <reason>` |
| 2. Plan | "Run the `superpowers:writing-plans` skill against the spec at `<spec-path>`." | plan file written | plan path + summary, OR `BLOCKED: <reason>` |
| 3. Execute | "Run the `superpowers:executing-plans` skill against the plan at `<plan-path>`. Commit each task as you go on the current branch." | code changes + commits on `<BRANCH_NAME>` | commit list + summary, OR `BLOCKED: <reason>` |
| 4. PR open | (no subagent — the controller handles PR creation; see "Open PR or write report" below) | — | — |

If any return starts with `BLOCKED:` or the subagent errors out, jump to the report writer. Do not proceed to the next phase. Do not retry.

### 5. Open PR or write report

**On success** (all three subagents returned non-`BLOCKED:`):

1. Determine the remote branch name:
   - If `BRANCH_NAME` starts with `worktree-`, strip that prefix. (The `worktrunk` / `EnterWorktree` workflow adds it locally; remote should see the clean name.)
   - Otherwise push the local name as-is.
2. `git push -u origin <remote-branch-name>`.
3. `gh pr create --title "<issue title or freeform input>" --body "$(cat <<'EOF'
   ...PR body, see template below...
   EOF
   )"` — single command, base branch is the repo default (usually `main`).
4. Print the PR URL to the user. Done.

If the push or `gh pr create` fails, fall through to the report writer with phase = `pr` — the branch and commits exist locally; the human can retry the PR open manually.

**On bail** (any phase returned `BLOCKED:` or errored):

Write `tmp/autonomo/<slug>-<RUN_TIMESTAMP>.md`. Create the directory if needed. Use the report format under "Failure handling". Do not push, do not open a PR. Print the report path to the user. Leave the branch / worktree in place.

## The autonomy directive

Pass this block verbatim to every dispatched subagent. The wording is load-bearing — it is the only thing converting normal user-gated skills into autonomous ones.

> You are running inside `/autonomo`, an unattended pipeline. The user is not watching. Rules:
>
> 1. Make best-effort decisions on small calls — naming, file layout, minor refactors, deprecation idioms, **and scope ambiguities inside a clearly-scoped task** (e.g. which files to include in a rename, which interpretation to pick when an item could fit either side). When the issue is clear about *what* to do but ambiguous about *which*, pick the most reasonable interpretation and proceed. Surface every assumption you made in your final output under an `## Assumptions` heading. Do NOT escalate detail-level scope ambiguity to `BLOCKED:`.
> 2. If a decision is high-stakes — data migration, **external API contract change** (HTTP routes, schema, exports crossing package boundaries), anything touching auth / billing / security, or destructive ops — stop and return `BLOCKED:` followed by one paragraph explaining what blocked you. Do not ask the user. Internal renames within a single package, including type renames, are not "API contract changes" for this rule's purposes.
> 3. If the issue itself has no actionable scope (empty body and an unspecific title, referenced file missing entirely), return `BLOCKED:` and stop.
> 4. Skip any "ask the user" or "wait for approval" gates in the skills you invoke — your output IS the decision.
> 5. Do not invoke `/autonomo` recursively.

The pressure scenarios in `pressure-scenarios/` exist to verify these rules under realistic conditions. Re-run them before bumping the skill's `version`.

## PR body template

```
Closes #<ISSUE_NUMBER>

## Summary
<1-3 bullets, lifted from the execute-plan subagent's summary>

## Spec
<link to spec file in repo if committed there, else inline content>

## Plan
<link to plan file in repo if committed there, else inline content>

## Assumptions
<concatenation of every subagent's `## Assumptions` section, deduplicated>

## Test plan
<from executing-plans subagent's output>

🤖 Opened by /autonomo
```

For freeform input (no `ISSUE_NUMBER`), omit the `Closes #...` line entirely. The rest of the template stays the same.

## Failure handling

| Phase | Failure mode | Autonomo response |
|-------|--------------|-------------------|
| Input parse | empty input, malformed `#NN`, unreachable URL, `gh` auth missing | exit before any branch created; print one-line cause |
| Workspace | dirty tree, on a feature branch, branch creation fails, worktree path collision | exit before any subagent runs; print one-line cause and suggested fix |
| Brainstorm | returns `BLOCKED:`, errors, no spec path | write report, leave artifacts, exit |
| Plan | same | same |
| Execute | same; OR completes but tests / lint fail | same — no auto-retry, no auto-fix |
| PR open | push rejected, `gh pr create` fails | branch + commits exist locally; report points user at manual `gh pr create` |

`BLOCKED:` is the controlled-failure marker. Returns starting with that prefix are expected; anything else is uncontrolled and flagged in the report.

**Report format** (`tmp/autonomo/<slug>-<RUN_TIMESTAMP>.md`):

```
# Autonomo run blocked

- Phase: <brainstorm | plan | execute | pr>
- Issue: <#NN or freeform title>
- Branch / worktree: <branch name or worktree path>
- Started: <iso8601>
- Stopped: <iso8601>

## Reason
<full subagent return value, or error trace>

## Artifacts on disk
- spec: <path or "not produced">
- plan: <path or "not produced">
- commits: <git log --oneline since branch base, or "none">

## Suggested next step
<best-guess hint, e.g. "Run /autonomo again after clarifying issue body" or "Resume with /superpowers:executing-plans against tmp/plans/<plan>.md">
```

No retry. No rollback. Bail on first failure. Leave artifacts in place. The user inspects the report, fixes input or environment, and re-runs.

## Pressure scenarios

The autonomy directive is load-bearing prose — every word converts user-gated skills into autonomous ones, and small wording changes can over-trigger `BLOCKED:` (subagents bail on every ambiguity) or under-trigger it (subagents push past genuinely high-stakes calls). `pressure-scenarios/` holds one scenario per rule, each with a task input, a RED expectation (baseline behavior without the directive), and a GREEN expectation (behavior with the directive in place).

Re-run them after any edit to the directive:

1. Pick a scenario file under `pressure-scenarios/`.
2. Dispatch a subagent (`Agent` tool, `subagent_type=general-purpose`) with the directive block from this SKILL plus the scenario's "Task input".
3. Compare the return against the scenario's GREEN expectation. If it matches, the directive still holds for that rule; if it matches RED, the directive regressed.

Each scenario lists its own "Rerun trigger" — at minimum re-run the scenarios whose rerun trigger covers the wording you touched.
