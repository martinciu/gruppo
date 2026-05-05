---
name: autonomo
description: Use when the user types `/autonomo <prompt>` to autonomously turn a freeform task description into a pull request without supervision. For well-scoped, single-package tasks; not for high-stakes work (auth, billing, security, data migration, external API contracts).
---

# Autonomo

`/autonomo <prompt>` takes a freeform task description and runs the full `superpowers` pipeline — brainstorm a spec, write a plan, execute the plan, open a PR — without prompting the user. The user is not watching: subagents make best-effort decisions on small calls and bail with `BLOCKED:` only on high-stakes ambiguity. On success it prints a PR URL; on bail it leaves the branch and a one-page report at `.autonomo/<slug>-<timestamp>.md`.

**Runtime artifacts:** logs and bail reports go in `.autonomo/<slug>-<RUN_TIMESTAMP>.{log,md}`. Add `.autonomo/` to your repo's `.gitignore` — these files are per-run and never committed. (User preferences for artifact location override this default.)

## When to use

Use `/autonomo` for tasks that are well-scoped, single-package, and don't touch auth, billing, security, data migration, or external API contracts. Typical fits: typo fixes, internal renames, adding a small utility, fleshing out a clearly-described function, doc tweaks. A concrete actionable one-liner you'd otherwise paste into a fresh session.

Do NOT use it for:

- Multi-subsystem work, anything spanning packages or services.
- Tasks where the right answer depends on judgment calls the prompt doesn't resolve (the subagents will bail).
- Anything where you need to be in the loop — `/autonomo` is unattended by design. If you want to review the spec or plan before implementation, run the underlying `superpowers` skills directly.
- Starting from a dirty tree, or from a feature branch that already has commits ahead of `main`/`master`. The skill refuses both; clean up first or switch to `main`/`master` / a freshly cut branch.

## Run log

Every run writes a structured log to `.autonomo/<slug>-<RUN_TIMESTAMP>.log` and a parallel pretty stream to stdout. Both surfaces are written by `scripts/emit.sh`; the controller and every subagent emit through it. The full subcommand list, stdout shapes, structured-line format, and canonical stage vocabulary live in `references/run-log.md`.

The two surfaces feed three audiences with one artifact: the watching user (top-level + nested transcripts), a tmux tailer (`tail -f` on the log), and post-mortem grep against the structured lines. Skipping either surface defeats one audience.

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

**Capture skill paths.** The skill loader announces this skill's base directory at the top of the loaded content (`Base directory for this skill: <path>`). Capture it for use throughout the run:

```bash
SKILL_DIR="<base directory announced by the loader>"
AUTONOMO_EMIT="${SKILL_DIR}/scripts/emit.sh"
```

`AUTONOMO_EMIT` and `AUTONOMO_LOG` (set in step 3) are passed in every subagent dispatch prompt; subagents source the directive from `${SKILL_DIR}/references/autonomy-directive.md`.

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

**Open the run log.** Once `SLUG`, `RUN_TIMESTAMP`, and `BRANCH_NAME` exist:

```bash
mkdir -p .autonomo
export AUTONOMO_LOG=".autonomo/${SLUG}-${RUN_TIMESTAMP}.log"
bash "${AUTONOMO_EMIT}" run-start "${BRANCH_NAME}"
echo "  log:        ${AUTONOMO_LOG}"
echo "  tail live:  tail -f ${AUTONOMO_LOG}"
```

`AUTONOMO_LOG` and `AUTONOMO_EMIT` are referenced by every subsequent emission and passed to every subagent.

### 4. Dispatch phase subagents

Dispatch three subagents in sequence using the Agent tool. Each invocation passes the autonomy directive (verbatim — read from `${SKILL_DIR}/references/autonomy-directive.md`) plus the dispatch prompt. After each return, check whether the output starts with `BLOCKED:` — that is the controlled-failure marker. Anything else (subagent crash, tool error) is uncontrolled failure; treat both the same way. The PR-open phase is handled by the controller directly — see §5.

Every dispatch prompt body must include:

```
AUTONOMO_LOG=<absolute path>
AUTONOMO_EMIT=<absolute path>
```

so the subagent can `export` them at the top of every bash session it spawns.

The wrapper around each Agent call is the same three lines — phase-start before dispatch, phase-end on success (with duration and key artifacts), or phase-bail if the return starts with `BLOCKED:`. The script writes both surfaces; do not echo by hand.

#### 4.1. Brainstorm

```bash
PHASE_START=$(date +%s)
bash "${AUTONOMO_EMIT}" phase-start brainstorm 1 3
```

Dispatch the Agent tool with prompt: `"Run the superpowers:brainstorming skill on this task. Produce a spec. Task: <prompt>. AUTONOMO_LOG=${AUTONOMO_LOG}  AUTONOMO_EMIT=${AUTONOMO_EMIT}"` plus the autonomy directive (verbatim).

On a non-`BLOCKED:` return, parse `SPEC_PATH` and `ASSUMPTIONS_COUNT` from the subagent's output, then:

```bash
DURATION=$(( $(date +%s) - PHASE_START ))
bash "${AUTONOMO_EMIT}" phase-end brainstorm 1 3 ${DURATION} \
     spec=${SPEC_PATH} assumptions=${ASSUMPTIONS_COUNT}
```

If the return starts with `BLOCKED:`:

```bash
bash "${AUTONOMO_EMIT}" phase-bail brainstorm 1 3 "<reason>"
```

Then jump to §5 with the bail path. Do not proceed to §4.2.

#### 4.2. Plan

Identical scaffold to §4.1, with `phase=plan` and phase index `2 3`. Dispatch prompt: `"Run the superpowers:writing-plans skill against the spec at <SPEC_PATH>. AUTONOMO_LOG=${AUTONOMO_LOG}  AUTONOMO_EMIT=${AUTONOMO_EMIT}"` plus the directive. On non-`BLOCKED:` return, parse `PLAN_PATH` and pass `plan=${PLAN_PATH}` to `phase-end` in place of the brainstorm `spec=…` field.

#### 4.3. Execute

Identical scaffold to §4.1, with `phase=execute` and phase index `3 3`. Capture the branch base before dispatch:

```bash
BRANCH_BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD origin/master)
```

Dispatch prompt: `"Run the superpowers:executing-plans skill against the plan at <PLAN_PATH>. Commit each task as you go on the current branch. AUTONOMO_LOG=${AUTONOMO_LOG}  AUTONOMO_EMIT=${AUTONOMO_EMIT}"` plus the directive.

On non-`BLOCKED:` return, run `phase-end`, then echo each new commit:

```bash
for sha in $(git log "${BRANCH_BASE}..HEAD" --format='%H' --reverse); do
  msg=$(git show --no-patch --format='%s' "$sha")
  bash "${AUTONOMO_EMIT}" commit "$sha" "$msg"
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

Write `.autonomo/<slug>-<RUN_TIMESTAMP>.md`. Create the directory if needed. Use the report format under "## Failure handling". Do not push, do not open a PR. Print the report path to the user. Leave the branch / worktree in place.

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

## Bundled resources

- `references/autonomy-directive.md` — verbatim block passed to every dispatched subagent. The wording is load-bearing; pressure scenarios under `pressure-scenarios/` test the rules.
- `references/run-log.md` — full subcommand reference and structured-line shapes for `scripts/emit.sh`, plus the canonical stage vocabulary.
- `references/maintenance.md` — how to re-run pressure scenarios after editing the directive, and when to bump `plugin.json` `version`.
- `scripts/emit.sh` — the dual-write helper. `bash scripts/emit.sh --help` prints the subcommand list.
- `pressure-scenarios/` — one scenario per directive rule, each with RED (no-directive baseline) and GREEN (directive-in-place) expectations.
