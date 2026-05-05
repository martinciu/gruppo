---
name: autonomo
description: Use when the user types `/autonomo <prompt>` to autonomously turn a freeform task description into a pull request without supervision. For well-scoped, single-package tasks; not for high-stakes work (auth, billing, security, data migration, external API contracts).
---

# Autonomo

`/autonomo <prompt>` takes a freeform task description and runs the full `superpowers` pipeline — brainstorm a spec, write a plan, execute the plan, open a PR — without prompting the user. The user is not watching: subagents make best-effort decisions on small calls and bail with `BLOCKED:` only on high-stakes ambiguity. On success it prints a PR URL; on bail it leaves the branch and a one-page report at `.autonomo/<slug>-<timestamp>.md`.

**Runtime artifacts:** Logs and bail reports go in `.autonomo/<slug>-<RUN_TIMESTAMP>.{log,md}`. Add `.autonomo/` to your repo's `.gitignore` — these files are per-run and never committed.
- (User preferences for artifact location override this default.)

## When to use

Use `/autonomo` for tasks that are well-scoped, single-package, and don't touch auth, billing, security, data migration, or external API contracts. Typical fits: typo fixes, internal renames, adding a small utility, fleshing out a clearly-described function, doc tweaks. A concrete actionable one-liner you'd otherwise paste into a fresh session.

Do NOT use it for:

- Multi-subsystem work, anything spanning packages or services.
- Tasks where the right answer depends on judgment calls the prompt doesn't resolve (the subagents will bail).
- Anything where you need to be in the loop — `/autonomo` is unattended by design. If you want to review the spec or plan before implementation, run the underlying `superpowers` skills directly.
- Starting from a dirty tree, or from a feature branch that already has commits ahead of `main`/`master`. The skill refuses both; clean up first or switch to `main`/`master` / a freshly cut branch.

## Run log

Every `/autonomo` run writes a structured log to `.autonomo/<slug>-<RUN_TIMESTAMP>.log`. The log opens at the start of the run (not only on bail) and grows monotonically. It serves three audiences with one artifact:

- **Live main session** — both the controller and each subagent print pretty lines to stdout. Controller lines (`→ Phase K/3 …`) appear in the top-level transcript; subagent lines (`→ stage <name>`, `· stage <name> · K/N`, …) appear inside the nested Agent transcript view while a phase is running. Together they give the watching user granular per-stage progress without needing a tail.
- **tmux tailer** — `tail -f .autonomo/<slug>-<RUN_TIMESTAMP>.log` from another pane shows structured events as they happen. Useful when the user is not watching the Claude Code session live.
- **Headless / post-mortem** — the structured format is grep-friendly for after-the-fact inspection. The on-bail report (see "Failure handling") becomes a derived summary; the log is the canonical artifact.

**Controller stdout format (pretty, top-level transcript):**

- `→ Phase K/3 · <name> · <verb>` — start / in-progress
- `✓ Phase K/3 · <name> · <duration> · <key=value …>` — completion
- `✗ Phase K/3 · <name> · BLOCKED · <reason>` — bail

**Subagent stdout format (pretty, nested transcript):** see autonomy directive rule 5 for the per-event shape.

**Log file format (structured):**

Each line is `<iso8601-utc> level=<info|warn|error> phase=<name> event=<verb> [key=value …]`. One event per line.

**Emission pattern.** At every emission point, write both surfaces — pretty stdout *and* structured log line:

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "→ Phase 1/3 · brainstorm · dispatching"
echo "${TS} level=info phase=brainstorm event=dispatch_start" >> "${AUTONOMO_LOG}"
```

Both writes are required at every event. The structured line keeps the tmux / post-mortem audiences fed; the stdout line keeps the live audience fed. Subagents follow the same dual-write rule for their `stage_*` and `assumption` events (rule 5).

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
<ts> level=info phase=<name> event=assumption    question="<one line>" answer="<one line>"
```

`question=` is the clarifying question the subagent would have asked the user; `answer=` is the call it made instead. Both fields are required — the question is what makes the assumption auditable.

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

The `<input>` argument from `/autonomo <input>` is a freeform task description. The only check is non-emptiness:

| Shape | Match | Resolution |
|-------|-------|------------|
| Prompt | non-empty input | `{title: <input>, body: ""}` — pass through verbatim |
| Empty | `<input>` is empty / whitespace only | exit `BLOCKED: usage: /autonomo "<task description>"` |

Store the resolved task object as `TASK` for the rest of the run.

### 3. Pick workspace

Inspect git state, decide where the work goes. Refuse to start from a non-clean baseline.

**Slug derivation.** Compute `<slug>` once, used for both the branch name and the report filename:

- Kebab-case the prompt, ASCII-only, max 40 chars (truncate at the last word boundary inside the limit).
- If the slugified prompt comes out empty (emoji-only, all non-Latin script, punctuation-only): fall back to `auto-<unix-timestamp>`.

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
AUTONOMO_LOG_DIR=".autonomo"
mkdir -p "$AUTONOMO_LOG_DIR"
AUTONOMO_LOG="$AUTONOMO_LOG_DIR/${SLUG}-${RUN_TIMESTAMP}.log"
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "${TS} level=info phase=preflight event=run_start branch=${BRANCH_NAME}" >> "${AUTONOMO_LOG}"
echo "→ /autonomo · run started"
echo "  log:        ${AUTONOMO_LOG}"
echo "  tail live:  tail -f ${AUTONOMO_LOG}"
```

`AUTONOMO_LOG` is referenced by every subsequent emission in this skill.

### 4. Dispatch phase subagents

Dispatch three subagents in sequence using the Agent tool. Each invocation passes the autonomy directive (verbatim, see below) plus phase-specific context. After each return, check whether the output starts with `BLOCKED:` — that is the controlled-failure marker. Anything else (subagent crash, tool error) is uncontrolled failure; treat both the same way. The PR-open phase is handled by the controller directly — see §5.

Each phase wraps the Agent call in identical emission scaffolding: a phase-start marker before dispatch, a phase-end marker after a successful return (with duration and key artifacts), or a bail marker if the return starts with `BLOCKED:`. Both surfaces (pretty stdout + structured log) are written at every emission point — see `## Run log` for the format.

Each Agent prompt below inlines `AUTONOMO_LOG=<path>` literally — Agent-tool subagents don't inherit the controller's environment, so the path the directive's rule 5 references must be passed in the prompt body.

#### 4.1. Brainstorm

```bash
PHASE_START=$(date +%s)
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "→ Phase 1/3 · brainstorm · dispatching"
echo "${TS} level=info phase=brainstorm event=dispatch_start" >> "${AUTONOMO_LOG}"
```

Dispatch the Agent tool with prompt: `"Run the superpowers:brainstorming skill on this task. Produce a spec. Task: <prompt>. AUTONOMO_LOG=${AUTONOMO_LOG}"` plus the autonomy directive (verbatim). Substitute the actual log path from the controller's `$AUTONOMO_LOG` at dispatch time.

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
3. Compose the PR body from the template under "## PR body template". For each of `## Spec` and `## Plan`, include the section (heading + link) only if `git ls-files --error-unmatch "<path>"` returns 0; otherwise drop the entire section — no placeholder stub, no path-only line. Then run `gh pr create --title "<task prompt, truncated to ~70 chars at a word boundary>" --body "<composed-body>"` — single command, base branch is the repo default (usually `main`).
4. Print the PR URL to the user, then echo the log path so post-mortem has it handy:

   ```bash
   echo "  log: ${AUTONOMO_LOG}"
   ```

   Done.

If the push or `gh pr create` fails, fall through to the report writer with phase = `pr` — the branch and commits exist locally; the human can retry the PR open manually.

**On bail** (any phase returned `BLOCKED:` or errored):

Write `.autonomo/<slug>-<RUN_TIMESTAMP>.md`. Create the directory if needed. Use the report format under "Failure handling". Do not push, do not open a PR. Print the report path to the user. Leave the branch / worktree in place.

## The autonomy directive

Pass this block verbatim to every dispatched subagent. The wording is load-bearing — it is the only thing converting normal user-gated skills into autonomous ones.

> You are running inside `/autonomo`, an unattended pipeline. The user is not watching. Rules:
>
> 1. Make best-effort decisions on small calls — naming, file layout, minor refactors, deprecation idioms, **and scope ambiguities inside a clearly-scoped task** (e.g. which files to include in a rename, which interpretation to pick when an item could fit either side). When the task is clear about *what* to do but ambiguous about *which*, pick the most reasonable interpretation and proceed. Surface every such call in your final output under an `## Assumptions` heading as a `Q:` / `A:` pair — `Q:` is the clarifying question you would have asked the user if you could; `A:` is the answer you chose. The `Q:` line is what makes the assumption auditable: a reader (or an eval grader) needs to see what the ambiguity was, not just how you resolved it.
>
>     **Test for whether to surface a Q: "could a reasonable person have chosen differently?", not "does the answer feel obvious?"** Things like the exact name of a new script (`slugify.sh` vs `derive-slug.sh`), whether a new flag's scope extends to an adjacent surface (a `--quiet`-style flag covering one log channel vs all of them), where a new snippet renders inside a longer document — these all *feel* obvious in retrospect but are genuine forks another author would have taken differently. Log them. The trap is eliding the Q because the answer felt natural to you; the auditor doesn't share your context, so without the Q they cannot tell whether a real choice was made or whether the issue was missed entirely.
>
>     Do NOT escalate detail-level scope ambiguity to `BLOCKED:`.
> 2. If a decision is high-stakes — data migration, **external API contract change** (HTTP routes, schema, exports crossing package boundaries), anything touching auth / billing / security, or destructive ops — stop and return `BLOCKED:` followed by one paragraph explaining what blocked you. Do not ask the user. Internal renames within a single package, including type renames, are not "API contract changes" for this rule's purposes.
> 3. If the task itself has no actionable scope (vague one-liner with no concrete deliverable, referenced file missing entirely), return `BLOCKED:` and stop.
> 4. Skip any "ask the user" or "wait for approval" gates in the skills you invoke — your output IS the decision.
> 5. Emit progress events on **two surfaces** as you work — the structured log file and your own stdout. Use the canonical stage vocabulary defined under "Canonical stage vocabulary" in the `/autonomo` SKILL for your phase. Both writes are required at every event: the structured line keeps tmux / post-mortem audiences fed; the stdout line keeps the watching user fed via the nested Agent transcript view, which is the live surface that replaces a separate tail pane.
>
>     - `stage_start` when you enter a canonical stage:
>
>       ```bash
>       TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
>       echo "→ stage <name>"
>       echo "${TS} level=info phase=<your-phase> event=stage_start stage=<name>" >> "${AUTONOMO_LOG}"
>       ```
>
>     - `stage_progress done=K [total=N]` when you cross a counted milestone within a stage (each plan task during execute, each clarifying question during brainstorm `clarify`, etc.). Omit `total=` when not knowable up front. Stdout form: `· stage <name> · K/N` (or `· stage <name> · K` when `total=` is omitted).
>     - `stage_end [duration_s=<n>]` when you leave the stage. `duration_s=` is optional in the structured line; tail consumers derive it from timestamps when omitted. Stdout form: `✓ stage <name>` (append ` · <duration>s` when you have it).
>     - `event=assumption question="<one line>" answer="<one line>"` the *moment* you make a best-effort scope-ambiguity call (rule 1), in addition to surfacing the same `Q:` / `A:` pair in the `## Assumptions` section of your final return. Stdout form: `! assumption · Q: <one line> · A: <one line>`. **All three surfaces are 1:1: every Q in your final spec's `## Assumptions` section has a matching structured log line and a matching stdout pretty line, including assumptions you only realize you made during a later stage like `write`.** Emit the log/stdout pair under whatever stage you are currently in when you notice the call; do not retroactively reorder under `clarify`.
>
>     Free-form `event=progress message="<one line>"` is retained as an escape hatch for updates that don't fit a stage milestone; mirror it to stdout as `· <one line>`.
>
>     Without the structured writes, tmux tailers and headless logs see silence during multi-minute phases. Without the stdout mirror, the watching user sees silence in the nested transcript while a phase grinds for minutes — and there is no TodoWrite list filling that gap. Skipping either surface defeats one audience.
> 6. Do not invoke `/autonomo` recursively.

The pressure scenarios in `pressure-scenarios/` exist to verify these rules under realistic conditions. Re-run them before bumping the skill's `version`.

## PR body template

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

Notes:

- The `## Spec` and `## Plan` sections render **only when their file is tracked in git** (`git ls-files --error-unmatch <path>` returns 0). Otherwise both the heading and body are dropped — no placeholder, no path-only line.
- Link path is the relative `SPEC_PATH` / `PLAN_PATH`; GitHub renders relative links in PR descriptions against the head branch.
- The footer link points at the published autonomo SKILL.md in the gruppo repo. It is hardcoded — autonomo does not derive its own source URL.

## Failure handling

| Phase | Failure mode | Autonomo response |
|-------|--------------|-------------------|
| Input parse | empty input, `gh` auth missing | exit before any branch created; print one-line cause |
| Workspace | dirty tree, branch already has commits ahead of default, branch creation fails | exit before any subagent runs; print one-line cause and suggested fix |
| Brainstorm | returns `BLOCKED:`, errors, no spec path | write report, leave artifacts, exit |
| Plan | same | same |
| Execute | same; OR completes but tests / lint fail | same — no auto-retry, no auto-fix |
| PR open | push rejected, `gh pr create` fails | branch + commits exist locally; report points user at manual `gh pr create` |

`BLOCKED:` is the controlled-failure marker. Returns starting with that prefix are expected; anything else is uncontrolled and flagged in the report.

**Report format** (`.autonomo/<slug>-<RUN_TIMESTAMP>.md`):

```
# Autonomo run blocked

- Phase: <brainstorm | plan | execute | pr>
- Task: <prompt verbatim>
- Branch / worktree: <branch name or worktree path>
- Log: `.autonomo/<slug>-<RUN_TIMESTAMP>.log` (full structured event history)
- Started: <iso8601>
- Stopped: <iso8601>

## Reason
<full subagent return value, or error trace>

## Artifacts on disk
- spec: <path or "not produced">
- plan: <path or "not produced">
- commits: <git log --oneline since branch base, or "none">

## Suggested next step
<best-guess hint, e.g. "Run /autonomo again with a more specific prompt" or "Resume with /superpowers:executing-plans against tmp/plans/<plan>.md">
```

No retry. No rollback. Bail on first failure. Leave artifacts in place — the report is a one-page summary, the log is the full event history. The user inspects either, fixes input or environment, and re-runs.

## Pressure scenarios

The autonomy directive is load-bearing prose — every word converts user-gated skills into autonomous ones, and small wording changes can over-trigger `BLOCKED:` (subagents bail on every ambiguity) or under-trigger it (subagents push past genuinely high-stakes calls). `pressure-scenarios/` holds one scenario per rule, each with a task input, a RED expectation (baseline behavior without the directive), and a GREEN expectation (behavior with the directive in place).

Re-run them after any edit to the directive:

1. Pick a scenario file under `pressure-scenarios/`.
2. Dispatch a subagent (`Agent` tool, `subagent_type=general-purpose`) with the directive block from this SKILL plus the scenario's "Task input".
3. Compare the return against the scenario's GREEN expectation. If it matches, the directive still holds for that rule; if it matches RED, the directive regressed.

Each scenario lists its own "Rerun trigger" — at minimum re-run the scenarios whose rerun trigger covers the wording you touched.
