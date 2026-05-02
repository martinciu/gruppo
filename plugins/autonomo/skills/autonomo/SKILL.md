---
name: autonomo
description: Use when the user types `/autonomo <input>` to autonomously turn a GitHub issue into a pull request — accepts an issue number, issue URL, or freeform task description. Runs the full superpowers pipeline (brainstorm → plan → execute → PR) without user interaction. For relatively simple tasks; reuses the current worktree or feature branch when clean, refuses on a dirty tree or a branch already carrying commits.
---

# Autonomo

`/autonomo <input>` takes a GitHub issue (number, URL) or a freeform task description and runs the full `superpowers` pipeline — brainstorm a spec, write a plan, execute the plan, open a PR — without prompting the user. The user is not watching: subagents make best-effort decisions on small calls and bail with `BLOCKED:` only on high-stakes ambiguity. On success it prints a PR URL; on bail it leaves the branch and a one-page report at `tmp/autonomo/<slug>-<timestamp>.md`.

## When to use

Use `/autonomo` for issues that are well-scoped, single-package, and don't touch auth, billing, security, data migration, or external API contracts. Typical fits: typo fixes, internal renames, adding a small utility, fleshing out a clearly-described function, doc tweaks. Either an issue with a concrete actionable body, or a freeform one-liner you'd otherwise paste into a fresh session.

Do NOT use it for:

- Multi-subsystem work, anything spanning packages or services.
- Tasks where the right answer depends on judgment calls the issue doesn't resolve (the subagents will bail).
- Anything where you need to be in the loop — `/autonomo` is unattended by design. If you want to review the spec or plan before implementation, run the underlying `superpowers` skills directly.
- Starting from a dirty tree, or from a feature branch that already has commits ahead of `main`/`master`. The skill refuses both; clean up first or switch to `main`/`master` / a freshly cut branch.

## Run log

Every `/autonomo` run writes a structured log to `tmp/autonomo/<slug>-<RUN_TIMESTAMP>.log`. The log opens at the start of the run (not only on bail) and grows monotonically. It serves three audiences with one artifact:

- **Live main session** — the controller prints pretty lines to stdout in parallel; the user sees those.
- **tmux tailer** — `tail -f tmp/autonomo/<slug>-<RUN_TIMESTAMP>.log` from another pane shows structured events as they happen.
- **Headless / post-mortem** — the structured format is grep-friendly for after-the-fact inspection. The on-bail report (see "Failure handling") becomes a derived summary; the log is the canonical artifact.

**Stdout format (pretty):**

- `→ Phase K/3 · <name> · <verb>` — start / in-progress
- `✓ Phase K/3 · <name> · <duration> · <key=value …>` — completion
- `✗ Phase K/3 · <name> · BLOCKED · <reason>` — bail

**Log file format (structured):**

Each line is `<iso8601-utc> level=<info|warn|error> phase=<name> event=<verb> [key=value …]`. One event per line.

**Emission pattern.** At every emission point, write both surfaces:

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "→ Phase 1/3 · brainstorm · dispatching"
echo "${TS} level=info phase=brainstorm event=dispatch_start" >> "${AUTONOMO_LOG}"
```

Both writes are required. Skipping the structured write breaks tmux/headless surfaces; skipping the pretty write breaks the live session.

## Canonical stage vocabulary

Closed enum of stage names per phase. Subagents append structured events to `${AUTONOMO_LOG}` using these names — see autonomy directive rule 5.

**Stage event format:**

```
<ts> level=info phase=<name> event=stage_start    stage=<canonical-name>
<ts> level=info phase=<name> event=stage_progress stage=<canonical-name> done=<n> [total=<n>]
<ts> level=info phase=<name> event=stage_end      stage=<canonical-name> [duration_s=<n>]
```

**Assumption event format** (separate from stages):

```
<ts> level=info phase=<name> event=assumption    message="<one line>"
```

**Stages per phase:**

| Phase | Canonical stages |
|-------|------------------|
| `brainstorm` | `clarify`, `propose`, `design`, `write` |
| `plan` | `outline`, `tasks`, `review` |
| `execute` | `tasks` (one stage for the whole phase; emit `stage_progress done=K total=N` after each plan task is committed) |

Execute uses a single stage rather than per-task sub-stages because the existing top-level `event=commit` already marks each task's completion, and the developer's motivating signal is task-level (`4/10`). The `phase=execute stage=tasks` collision with `phase=plan stage=tasks` is intentional and acceptable — `phase=` disambiguates.

**Counter rules:**

- `total=` is included only when the total is knowable up front. Execute knows from the plan task count. Brainstorm `clarify` does not — emits `done=N` only.
- `done=` is monotonic within a stage.

**Sub-step timing:** Tail consumers derive durations from `stage_start` / `stage_end` timestamps. `stage_end` may carry `duration_s=<n>` for convenience but is not required to.

## TodoWrite progress display

Subagents and the controller render their progress as TodoWrite lists for the live UI display, alongside the structured log emissions in autonomy directive rule 5. The log is for tail / post-mortem (machine-readable); TodoWrite is the live display the user watches.

Two surfaces produce TodoWrite lists during a run:

- The **controller** renders a 3-item top-level phase list once at the end of §3 ("Pick workspace"), then updates it between phases (see §4 emission scaffolding).
- Each **subagent** renders its own phase-specific list while it runs. The Agent tool's nested view shows the subagent's TodoWrite while the phase is active; between phases the controller's list is what the user sees.

**Controller list** (3 items, fixed):

| Subject | Lifecycle |
|---------|-----------|
| `Phase 1/3: Brainstorm` | `pending` initially → `in_progress` before §4.1 dispatch → `completed` on non-`BLOCKED:` return |
| `Phase 2/3: Plan` | `pending` initially → `in_progress` before §4.2 dispatch → `completed` on non-`BLOCKED:` return |
| `Phase 3/3: Execute` | `pending` initially → `in_progress` before §4.3 dispatch → `completed` on non-`BLOCKED:` return |

On a `BLOCKED:` return, the in-progress phase item is left untouched. TodoWrite has no `failed` state — the existing `✗ Phase K/3 · BLOCKED · <reason>` stdout line and `event=blocked` log entry carry the failure signal.

**Subagent lists** (per phase):

| Phase | Items |
|-------|-------|
| `brainstorm` | `Clarify scope`, `Propose approaches`, `Design the spec`, `Write spec to disk` (4 items, one per canonical stage) |
| `plan` | `Outline plan structure`, `Enumerate plan tasks`, `Self-review plan` (3 items, one per canonical stage) |
| `execute` | One item per task in the plan; subject = the plan's task title verbatim (e.g. `Task 1: Add --flag option`) |

Each subagent marks its own items `in_progress` when entering them, `completed` when finishing. Brainstorm and plan **override** the default TodoWrite usage of `superpowers:brainstorming` / `superpowers:writing-plans` (which would otherwise render their own internal checklists). Execute **aligns** with `superpowers:executing-plans`' natural one-task-per-item behavior, so no override is needed there.

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

**Decision table** (evaluated top-down — first matching row wins):

| Current state | Action |
|---------------|--------|
| On `main` / `master`, working tree clean | `git checkout -b autonomo/<slug>` |
| Inside a worktree, working tree clean | Reuse the current worktree: `git checkout -b autonomo/<slug>` in place. Do not spawn a sibling worktree. |
| On a feature branch with no commits ahead of `main`/`master`, working tree clean | Reuse the current branch as-is. Do not create `autonomo/<slug>`; the existing branch name is what gets pushed. |
| On a feature branch with commits ahead of `main`/`master`, working tree clean | exit `BLOCKED: feature branch already has commits; start from main or a fresh branch` |
| Working tree dirty (any uncommitted changes) | exit `BLOCKED: working tree dirty; stash or commit first` |

**Detecting "inside a worktree":** `git rev-parse --git-dir` ends in `/.git/worktrees/<name>` for linked worktrees; for the main repo it's `.git`. Use this to distinguish.

**Detecting "no commits ahead of default":**

```bash
DEFAULT=$(git symbolic-ref refs/remotes/origin/HEAD --short 2>/dev/null | sed 's|^origin/||')
DEFAULT=${DEFAULT:-main}
if [ -z "$(git log "origin/${DEFAULT}..HEAD" --oneline)" ]; then
  # branch has no commits ahead of default — safe to reuse
fi
```

Store the resulting branch name as `BRANCH_NAME` — the PR opener step uses it. In the new-branch cases this is `autonomo/<slug>`; in the reuse-existing-branch case it's the current branch name.

**Open the run log.** Once `SLUG` and `RUN_TIMESTAMP` exist and the branch is created, open the log file. Subsequent emissions (phase markers, artifact echoes, errors) write to both stdout and this file:

```bash
mkdir -p tmp/autonomo
AUTONOMO_LOG="tmp/autonomo/${SLUG}-${RUN_TIMESTAMP}.log"
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "${TS} level=info phase=preflight event=run_start branch=${BRANCH_NAME}" >> "${AUTONOMO_LOG}"
echo "→ /autonomo · run started"
echo "  log:        ${AUTONOMO_LOG}"
echo "  tail live:  tail -f ${AUTONOMO_LOG}"
```

`AUTONOMO_LOG` is referenced by every subsequent emission in this skill.

### 4. Dispatch phase subagents

Dispatch three subagents in sequence using the Agent tool. Each invocation passes the autonomy directive (verbatim, see below) plus phase-specific context. After each return, check whether the output starts with `BLOCKED:` — that is the controlled-failure marker. Anything else (subagent crash, tool error) is uncontrolled failure; treat both the same way. The PR-open phase is handled by the controller directly — see §5.

Each phase wraps the Agent call in identical emission scaffolding: a phase-start marker before dispatch, a phase-end marker after a successful return (with duration and key artifacts), or a bail marker if the return starts with `BLOCKED:`. All three surfaces (stdout pretty + structured log) are written at every emission point — see `## Run log` for the format.

Each Agent prompt below inlines `AUTONOMO_LOG=<path>` literally — Agent-tool subagents don't inherit the controller's environment, so the path the directive's rule 5 references must be passed in the prompt body.

#### 4.1. Brainstorm

```bash
PHASE_START=$(date +%s)
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "→ Phase 1/3 · brainstorm · dispatching"
echo "${TS} level=info phase=brainstorm event=dispatch_start" >> "${AUTONOMO_LOG}"
```

Dispatch the Agent tool with prompt: `"Run the superpowers:brainstorming skill on this task. Produce a spec. Issue title: <title>. Issue body: <body>. AUTONOMO_LOG=${AUTONOMO_LOG}"` plus the autonomy directive (verbatim). Substitute the actual log path from the controller's `$AUTONOMO_LOG` at dispatch time.

On a non-`BLOCKED:` return, parse `SPEC_PATH` and `ASSUMPTIONS_COUNT` from the subagent's output, then emit:

```bash
PHASE_END=$(date +%s); DURATION=$((PHASE_END - PHASE_START))
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "✓ Phase 1/3 · brainstorm · ${DURATION}s · spec=${SPEC_PATH} · ${ASSUMPTIONS_COUNT} assumptions"
echo "${TS} level=info phase=brainstorm event=dispatch_end duration_s=${DURATION} spec=${SPEC_PATH} assumptions=${ASSUMPTIONS_COUNT}" >> "${AUTONOMO_LOG}"
```

If the return starts with `BLOCKED:`, emit instead:

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "✗ Phase 1/3 · brainstorm · BLOCKED · <reason>"
echo "${TS} level=warn phase=brainstorm event=blocked reason=\"<reason>\"" >> "${AUTONOMO_LOG}"
```

Then jump to §5 with the bail path. Do not proceed to §4.2.

#### 4.2. Plan

Identical scaffold to §4.1, with `phase=plan` and `Phase 2/3` in the markers. Dispatch prompt: `"Run the superpowers:writing-plans skill against the spec at <SPEC_PATH>. AUTONOMO_LOG=${AUTONOMO_LOG}"` plus the autonomy directive. On non-`BLOCKED:` return, parse `PLAN_PATH` and emit `plan=${PLAN_PATH}` in the dispatch_end line in place of the brainstorm `spec=…` field.

#### 4.3. Execute

Identical scaffold to §4.1, with `phase=execute` and `Phase 3/3` in the markers. Capture the branch base before dispatch:

```bash
BRANCH_BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD origin/master)
```

Dispatch prompt: `"Run the superpowers:executing-plans skill against the plan at <PLAN_PATH>. Commit each task as you go on the current branch. AUTONOMO_LOG=${AUTONOMO_LOG}"` plus the autonomy directive.

On non-`BLOCKED:` return, emit the dispatch_end line, then echo each new commit:

```bash
for sha in $(git log "${BRANCH_BASE}..HEAD" --format='%H'); do
  msg=$(git show --no-patch --format='%s' "$sha")
  TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  echo "  · commit ${sha:0:7} · ${msg}"
  echo "${TS} level=info phase=execute event=commit sha=${sha} subject=\"${msg}\"" >> "${AUTONOMO_LOG}"
done
```

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
4. Print the PR URL to the user, then echo the log path so post-mortem has it handy:

   ```bash
   echo "  log: ${AUTONOMO_LOG}"
   ```

   Done.

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
> 5. Emit structured stage events to `${AUTONOMO_LOG}` as you work. Use the canonical stage vocabulary defined under "Canonical stage vocabulary" in the `/autonomo` SKILL for your phase.
>
>     - `stage_start` when you enter a canonical stage:
>
>       ```bash
>       TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
>       echo "${TS} level=info phase=<your-phase> event=stage_start stage=<name>" >> "${AUTONOMO_LOG}"
>       ```
>
>     - `stage_progress done=K [total=N]` when you cross a counted milestone within a stage (each plan task during execute, each clarifying question during brainstorm `clarify`, etc.). Omit `total=` when not knowable up front.
>     - `stage_end [duration_s=<n>]` when you leave the stage. `duration_s=` is optional; tail consumers derive it from timestamps when omitted.
>     - `event=assumption message="<one line>"` the *moment* you make a best-effort scope-ambiguity call (rule 1), in addition to surfacing it in the `## Assumptions` section of your final return.
>
>     Free-form `event=progress message="<one line>"` is retained as an escape hatch for updates that don't fit a stage milestone.
>
>     Without these, tmux tailers and headless logs see silence during multi-minute phases.
> 6. Do not invoke `/autonomo` recursively.
> 7. Render your phase's progress as a TodoWrite list using the items defined under "## TodoWrite progress display" in the `/autonomo` SKILL — use those item subjects exactly, marking each `in_progress` when you enter it and `completed` when you finish. Override the default TodoWrite usage of any inner skill you invoke. The structured log emissions in rule 5 are still required (the log serves tail / post-mortem consumers; TodoWrite is the live display).

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
| Workspace | dirty tree, branch already has commits ahead of default, branch creation fails | exit before any subagent runs; print one-line cause and suggested fix |
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
- Log: `tmp/autonomo/<slug>-<RUN_TIMESTAMP>.log` (full structured event history)
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

No retry. No rollback. Bail on first failure. Leave artifacts in place — the report is a one-page summary, the log is the full event history. The user inspects either, fixes input or environment, and re-runs.

## Pressure scenarios

The autonomy directive is load-bearing prose — every word converts user-gated skills into autonomous ones, and small wording changes can over-trigger `BLOCKED:` (subagents bail on every ambiguity) or under-trigger it (subagents push past genuinely high-stakes calls). `pressure-scenarios/` holds one scenario per rule, each with a task input, a RED expectation (baseline behavior without the directive), and a GREEN expectation (behavior with the directive in place).

Re-run them after any edit to the directive:

1. Pick a scenario file under `pressure-scenarios/`.
2. Dispatch a subagent (`Agent` tool, `subagent_type=general-purpose`) with the directive block from this SKILL plus the scenario's "Task input".
3. Compare the return against the scenario's GREEN expectation. If it matches, the directive still holds for that rule; if it matches RED, the directive regressed.

Each scenario lists its own "Rerun trigger" — at minimum re-run the scenarios whose rerun trigger covers the wording you touched.
