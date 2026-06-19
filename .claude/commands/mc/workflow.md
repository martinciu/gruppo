---
description: End-to-end Superpowers workflow — brainstorm → execute → review → fix → merge, with model and effort picks per phase
---

> **When invoked as `/mc:workflow`:** print the reference below
> verbatim. Do not summarise, do not act on it, do not ask follow-up
> questions. The user is pulling the doc into their session as a
> quick-reference card.

---

# Superpowers workflow — issue to merge

The full path a piece of work travels, using the `/mc:*` commands plus
Superpowers skills. Three sessions, one model, tiered subagents, one PR.

## Model tiers

Sessions always run the **default model** — whatever the Claude Code
config selects. No `--model` flags, no `model:` frontmatter anywhere in
the `/mc:*` commands. Delegation downward happens only at the subagent
level, and only for work that doesn't need brainpower:

| Tier           | Meaning                                                          | Current alias |
|----------------|------------------------------------------------------------------|---------------|
| **default**    | the session model — all deciding, reviewing, architectural work  | *(none — inherit)* |
| **mid typer**  | judgment-laden typing: multi-file, pattern-matching              | `sonnet`      |
| **fast typer** | mechanical typing: single file, exact bytes                      | `haiku`       |

This table is the single place to update when the model lineup changes.
Everywhere else — this doc, `/mc:fix`, `/mc:review` — speaks in tier
labels.

## At a glance

| Phase           | Session | Model  | Effort         | Driver                                       |
|-----------------|---------|--------|----------------|----------------------------------------------|
| 1. Brainstorm + plan      | A         | default              | `max` (+ `ultrathink` on key turns)  | `/mc:brainstorm <N>`                   |
| 2. Execute + smoke test   | B (fresh) | default              | default ↓ `low`                      | `/mc:execute` (or `/superpowers:subagent-driven-development` for SDD plans) |
| 3. PR review              | C (fresh) | default              | default (+ `ultrathink` for big diffs) | `/mc:review` (slug optional — resolved from feature bead) |
| 4. Apply fixes (review + manual testing) | C | default → mid typer / fast typer | dispatcher default, typers vary | `/mc:fix <description>` (per approved/observed fix) |
| 5. Verify + merge         | B (resumed) | default            | `low`                                | run tests, push, merge                       |

Two streams feed Phase 4: formal **PR review findings** (Phase 3 output)
and **manual testing findings** (you driving the feature in a browser /
CLI / shell). Both funnel through `/mc:fix` so the tier discipline
applies regardless of origin.

### Effort vocabulary

`/effort` is the session-level dial. Supported levels vary by model —
run `/effort` in the session to see what the current model offers.
This doc names effort relatively: **max** (the highest supported
level), **default** (what the session starts at — calibrated for
coding work), **`low`** (the cheapest supported level).

- `max` typically applies to the current session only (unless set via
  `CLAUDE_CODE_EFFORT_LEVEL`); other levels persist across sessions.
- Setting an unsupported level falls back to the highest supported
  one. Fast-tier subagents may have no effort dial at all.
- For a per-turn reasoning boost that does not change the session
  effort, drop the `ultrathink` keyword into the prompt — see
  [§ The `ultrathink` keyword](#the-ultrathink-keyword) below.
- Subagent / skill frontmatter can set `effort:` to override the
  session level when that subagent or skill is active — useful for SDD
  per-task tiering.
- Calibration: outside Phase 1, default is the right session setting.
  Raising effort on routine turns mostly buys latency and
  over-deliberation, not better output, so reach for `ultrathink` per
  turn before reaching for the dial. Reserve a session-level `max` for
  the brainstorm — where it has outsized leverage on the eventual
  diff — or a genuinely hard, latency-insensitive deliberation.

Why three sessions: fresh sessions keep divergent (brainstorm) and
convergent (review) phases from contaminating each other — different
cognitive modes shouldn't share context. The cost economy lives at the
subagent level: default-tier tokens cost a large multiple of typer-tier
tokens, so spend them on *deciding* and let typer tiers do the *typing*.

---

## The `ultrathink` keyword

A per-turn reasoning boost that stacks on top of `/effort`. Include
the literal string `ultrathink` anywhere in a prompt; Claude Code's
preprocessor detects it and injects an in-context instruction asking
the model to reason more deeply on that turn. **The `/effort` level
sent to the API is unchanged** — `ultrathink` is orthogonal to the
session dial, not a substitute for it. Under adaptive reasoning, the
model decides how much extra deliberation the instruction warrants.

Two controls, two scopes:

| Control       | Scope            | Persistence                        |
|---------------|------------------|------------------------------------|
| `/effort`     | Whole session    | Persists across sessions (all levels below `max`); session-only for `max` |
| `ultrathink`  | Single turn      | Per-prompt; reverts immediately afterwards |

### Where the boost earns its tokens

- **Phase 1, highest-stakes clarifying turn** — the question whose
  answer reshapes the whole spec.
- **Phase 1, design-shape selection** — when the brainstorm narrows
  to two or three approaches and you ask "which?".
- **Phase 3, reviewing a high-risk `Replaced by:` clause** — cases
  where a missing replacement could silently work coherently without
  the rejected approach (the easiest drift to miss).
- **Phase 4, inline architectural fix** — when `/mc:fix` keeps a fix
  inline because it needs default-tier reasoning, drop `ultrathink` into the
  fix prompt's decision turn.
- Any moment you would otherwise raise `/effort` to `max` for one
  question and lower it after — `ultrathink` saves the round-trip.

### Where it does *not* earn its tokens

- Mechanical edits, file scaffolding, test runs, format-fix typing —
  no decision surface for extra reasoning to grip on.
- Routine status / clarifying / lookup turns — overthinking burns
  latency without changing the answer.
- Sessions already on `/effort max` — the keyword still injects the
  instruction, but cannot exceed the adaptive ceiling; diminishing
  returns set in fast.
- Fast-tier subagents — no effort dial; the keyword has no hook to
  amplify.

### Not to be confused with

`ultrathink` is the **only** in-prompt keyword Claude Code recognises.
Phrases like *"think"*, *"think hard"*, *"think harder"*, *"think
more"*, and *"megathink"* are passed through as ordinary prompt text
— they may influence the model the way any instruction would, but the
preprocessor does not treat them specially. Earlier guides that
listed those as tiered triggers reflect pre-adaptive-reasoning
behaviour.

### Caveats

- Available only in Claude Code CLI. claude.ai web chat and direct
  Anthropic API calls do not recognise the keyword.
- Re-introduced in Claude Code v2.1.68 (2026-03-04) after a brief
  deprecation in early 2026. Documentation older than that may
  contradict current behaviour.

---

## Phase 1 — Brainstorm + plan

**Session A · default model · `/effort max` · `ultrathink`
on key brainstorm turns**

Open a fresh session in the repo. Run:

```
/mc:brainstorm <issue-number>
```

The command drives seven steps without stopping in the middle:

1. **Fetch the issue** via `gh issue view`.
2. **Classify surfaces** (language, framework, libraries, subsystem) and
   load the relevant skills via the `Skill` tool *before* proposing
   design. If the issue touches a third-party library, ground
   recommendations with `mcp__plugin_context7_context7__resolve-library-id`
   + `query-docs`. Load `superpowers:brainstorming` last.
3. **Brainstorm → spec** following `superpowers:brainstorming` exactly.
   One clarifying question at a time. No code, no design, no plan until
   intent is locked. Spec saves to `.superpowers/specs/`.
4. **Write the plan** via `superpowers:writing-plans`. Plan saves to
   `.superpowers/plans/`. Reference the spec path and issue number in
   frontmatter. State chosen execution mode (inline vs SDD) and reason
   in the plan.
5. **Pin feature state in beads** (when `bd` is on PATH). The feature bead's
   id mirrors the issue number (`<prefix>-<N>`); `bd create --id` plus comments
   pinning `slug:`, `spec:`, `plan:`, `review-note:` so downstream commands
   resolve their inputs from the bead. (No `github-issue:` comment — the id
   suffix and `external_ref` URL already encode the issue.)
6. **Hand off.** Print the three artefact paths, recommend inline vs
   SDD with a one-line reason, and emit a paste-ready slash command
   for Session B.
7. **Review-note** via `/mc:review-note <slug>` (must be last —
   invoking a slash command via the `Skill` tool tends to end the
   session, so anything that has to land deterministically — bd
   create, handoff — runs *before* it). Saves to
   `.superpowers/review-notes/<slug>.md`.

**Effort:** raise the session to `/effort max` for the brainstorm — this
is the phase where compute-spent-thinking has the most leverage on the
eventual diff. Drop the `ultrathink` keyword into the prompt on specific
high-stakes turns (clarifying-question synthesis, design-shape
selection) for a per-turn boost on top of the session level. Drop the
session back to default before Phase 2.

**Output of phase:** spec, plan, review-note on disk, all under
`.superpowers/` (gitignored, never committed).

---

## Phase 2 — Execute + smoke test

**Session B · default model · default effort → drop to `low` /
`medium` for mechanical runs**

Start a *new* session (`claude` in a fresh terminal).
For inline execution (the common case), paste:

```
/mc:execute
```

`/mc:execute` resolves the plan path from the feature bead (created by
`/mc:brainstorm` in Phase 1, with the plan path pinned as a
comment), transitions the bead `open → in_progress`, runs
`/superpowers:executing-plans` inline, and transitions
`in_progress → awaiting_review` on a clean smoke pass. In repos
without `.beads/`, it falls back to asking for the plan path
explicitly. The slug argument is never needed — the wrapper figures
out what to run from the current branch.

…or, if SDD was recommended in Phase 1:

```
/superpowers:subagent-driven-development .superpowers/plans/<slug>.md
```

SDD intentionally bypasses `/mc:execute` because its per-task
two-stage review carries its own status discipline; wrapping it would
duplicate the gating.

### Inline vs SDD — pick once, in Phase 1

- **Inline** (`/mc:execute` → `executing-plans`) — most tasks are
  mechanical/byte-exact (config, dotfiles, TOML/YAML/HTML fragments,
  cheatsheets). Skips per-task review token overhead.
- **SDD** (`subagent-driven-development`) — most tasks are real code
  with logic and judgment (~50–300 LOC/task, multi-file integration).
  Two-stage review (spec compliance, then code quality) earns its cost.
- **Mixed plans:** start inline, switch to SDD only if subsequent
  tasks are heavier than the first.

### Subagent tiers inside SDD

SDD dispatches one subagent per task. Match the *subagent's* model and
effort to the task, not the controller's:

| Task profile                                 | Subagent tier  | Effort                |
|----------------------------------------------|----------------|-----------------------|
| Mechanical, single file, exact lines         | fast typer     | n/a (no effort dial)  |
| Multi-file integration, branching logic      | mid typer      | `medium` or `high`    |
| Architectural / cross-cutting judgment       | Inline (default-model controller) | session default |

Set `model:` and `effort:` in the subagent prompt frontmatter (or as
arguments to the dispatch tool) so the override applies only while
that subagent runs.

### Smoke test before opening the PR

Type checking and test suites verify code *correctness*, not feature
*correctness*. Before opening the PR, drive the feature yourself:

- **Frontend changes** — start the dev server, exercise the golden
  path and the obvious edge cases in a browser. Watch the network tab
  and console for regressions.
- **CLI / shell** — run the command on at least one realistic input;
  check exit codes, stderr, and any side effects (files written,
  state mutated).
- **Backend / API** — hit the endpoint with `curl` / `httpie` against
  the happy path and one failure mode.

Most pre-PR smoke bugs are trivial — the session that just wrote
them can fix them inline in Session B. Edit the code, re-smoke,
repeat until a pass yields zero new findings, *then* open the
PR. Don't open the PR with known smoke failures.

Stop and surface to user only if a bug suggests a design flaw — that
may warrant returning to Phase 1 brainstorming rather than papering
over with a quick fix.

If you cannot test the UI (no dev env, external dependency missing),
say so explicitly in the PR body; don't claim it works.

### End-of-phase checklist

- All plan tasks marked complete.
- Tests pass locally.
- Use `superpowers:verification-before-completion` before claiming done.
- Smoke test passes (or its absence is explicitly flagged).
- Commit on a feature branch; open the PR.

---

## Phase 3 — PR review

**Session C · default model · default effort · `ultrathink` for
large or high-stakes diffs**

Start a *new* session — fresh eyes, no Phase 1 brainstorm in
context. Run:

```
/mc:review <slug>
```

The command reads three inputs:

1. `.superpowers/plans/<slug>.md`
2. `.superpowers/review-notes/<slug>.md`
3. The PR diff (`gh pr diff <N>`)

It produces a structured report:

- **Findings** — numbered globally, ordered by severity (🔴 🟡 🟢),
  tagged `[drift]` or `[lens]`, each with a file:line citation.
- **Clear** — what landed correctly so a follow-up reviewer can skip
  those.
- **Recommendations** — *apply / group / defer / drop*, referencing
  finding numbers only.

Then it **stops** and asks which findings to apply. Nothing auto-fixes.

**Effort:** the session default is calibrated for coding work and is
usually enough — a whole-session `max` tends to buy latency and
over-deliberation, not catch-rate. For a diff that spans many files or
carries a long `Replaced by:` list to verify (each clause is a per-line
verification check), drop `ultrathink` into the prompt that invokes
`/mc:review`; reserve a session-level bump for genuinely hard,
latency-insensitive reviews.

**Security-surface diffs:** some models ship cybersecurity safety
classifiers that can refuse benign security-focused review analysis. If
`/mc:review` on a security-heavy diff hits a safety refusal, re-run the
review session on a different model (`claude --model <other>`) rather
than re-prompting around the refusal.

---

## Phase 4 — Apply fixes (review + manual testing)

**Session C (continues) · default-model dispatcher →
fast typer / mid typer / inline**

Two input streams feed this phase. Treat them identically — same
dispatcher, same tier picker, same command.

### Stream A — formal review findings

Reply to the Phase 3 review prompt with the approved subset:

```
1, 3, 5
1-4
accept recommendations
issue: 6, 8        # spin those off as follow-ups instead of fixing
none
```

### Stream B — post-PR manual testing findings

Bring observations from any *post-PR* manual testing pass — mid-review
pull-and-poke, post-fix regression check, Phase 5 final sanity pass.
**Pre-PR smoke bugs do not reach this dispatcher** — they're fixed
inline in Session B during Phase 2 (see Phase 2 § Smoke test).

Frame each finding as a fix brief the dispatcher can route: file path
or feature target, observed vs expected behaviour, reproduction steps
if non-obvious. Severity is your call; 🔴 must-fix gates merge,
🟡 should-fix is judgement, 🟢 is a nit.

Example brief:

> Frontend: `src/components/Chart.tsx` — toggling unit while a hover
> tooltip is open keeps the stale unit string visible until next
> mouse-move. Expected: tooltip text updates immediately. Repro: hover
> any bar, click unit toggle, do not move mouse.

### Dispatching the fix

For each approved or observed fix, invoke:

```
/mc:fix <description>
```

The command runs a decision tree per fix:

```
Brief is mechanical?
├── Trivially mechanical (single file, exact bytes)        → fast typer subagent
├── Mechanical with judgment ("match pattern", multi-file) → mid typer subagent
└── Needs real judgment                                    → inline (default model)
```

If a fix needs default-tier reasoning, the dispatcher does it inline — no
round-trip through a lower-tier subagent. If a fix surfaces an
out-of-scope concern, `/mc:fix` proposes filing a new issue and
**waits for explicit "yes"** before running `gh issue create`.

**Effort per fix:**
- Fast-typer subagent: n/a — no effort dial, the brief just
  carries the exact bytes.
- Mid-typer subagent: `medium` (pattern-matching against existing
  style needs some reasoning but not the full session default).
- Inline (default model): keep the session at its default effort. Drop
  the `ultrathink`
  keyword into the inline-fix prompt for a per-turn boost when a single
  decision dominates the fix (e.g. picking a data-shape change) or the
  fix has architectural ramifications.

**End of phase:** dispatcher reads each returned diff, verifies intent,
stages and commits. Does **not** push from Session C — leave the
controller's commit to the execution session that owns the branch.

**Iterate, don't linger.** A manual-testing fix often surfaces another
behaviour worth poking. Cycle Phase 4 ↔ smoke test as many rounds as
needed before promoting to Phase 5; each round should shrink the
finding list. Stop when a smoke pass yields zero new 🔴/🟡 findings.

---

## Phase 5 — Verify and merge

**Session B (resumed) · default model · `/effort low`**

Switch back to the execution session (the one that owns the branch):

1. Pull the fix commits from Phase 4 if they landed via a separate
   working copy; otherwise they are already local.
2. Re-run the full test suite. `superpowers:verification-before-completion`
   gates the "ready to merge" claim.
3. **Final smoke test.** One more manual pass on the golden path plus
   anything Phase 4 changed. Trivial findings → fix inline in
   Session B and re-smoke. Architectural / mixed-tier findings →
   resume or respawn Session C and dispatch via `/mc:fix`.
4. Push the branch.
5. Mark the PR ready for review (or self-merge if the workflow allows).
6. Once merged, `superpowers:finishing-a-development-branch` handles
   cleanup decisions (delete branch, prune worktree, etc.).

**Effort:** `low`. Test runs and `git push` need no reasoning budget;
`low` is the cheapest effort setting.

---

## Decision quick-reference

### When to spawn a new session

- **Always new** between Phase 1 (brainstorm) and Phase 2 (execute) —
  different cognitive modes.
- **Always new** between Phase 2 and Phase 3 — fresh-eyes review is the
  whole point. The Phase 3 session has the plan and review-note,
  not the brainstorm transcript.
- **Same session** for Phase 3 → Phase 4 — the reviewer dispatches
  fixes; sharing context is the win.
- **Resume** Phase 2's session for Phase 5 — it owns the branch state
  and the test environment.

### Where manual testing fits

Smoke testing is interleaved, not a discrete phase. Three natural
checkpoints — and where each fix lands depends on whether the PR is
open yet:

1. **End of Phase 2**, before opening the PR — caught in Session B.
   **Fix inline in Session B** (same session that wrote the
   buggy code). Re-smoke until clean, *then* open the PR.
2. **Between Phase 3 and Phase 4 (optional)** — caught while
   Session C is active. **Send findings to `/mc:fix`** in Session C
   alongside the review-driven fixes.
3. **End of Phase 5**, before marking the PR ready — caught in
   Session B. **Fix inline in Session B** for trivial bugs;
   escalate to Session C (resume or respawn) only if a bug needs
   dispatcher reasoning (architectural, mixed-tier).

Principle: **the session that's currently active is where the fix
happens.** Session B handles pre-PR smoke fixes inline; Session C
(the dispatcher via `/mc:fix`) handles fixes that benefit from tier
routing — typically batches of post-review findings.

### When to stay inline vs SDD

State the choice in the plan in one sentence:

- *"Inline — tasks are byte-exact TOML/HTML edits."*
- *"SDD — each task is ~150 LOC of TS with branching logic."*

Forces honesty about the call.

### Model + effort cheat-sheet

| Activity                      | Tier       | `/effort`        | One-off keyword         |
|-------------------------------|------------|------------------|-------------------------|
| Brainstorm / spec             | default    | `max`            | `ultrathink` on key turns |
| Plan writing                  | default    | default          | —                       |
| Review-note distillation      | default    | default          | —                       |
| Inline execution (mechanical) | default    | `low`            | —                       |
| Inline execution (logic)      | default    | default          | —                       |
| SDD subagent (mechanical)     | fast typer | n/a              | —                       |
| SDD subagent (multi-file)     | mid typer  | `medium`–`high`  | —                       |
| PR review                     | default    | default          | `ultrathink` for big diffs |
| Fix dispatch (decision)       | default    | default          | —                       |
| Fix typing (mechanical)       | fast typer | n/a              | —                       |
| Fix typing (judgment)         | mid typer  | `medium`         | —                       |
| Fix typing (architectural)    | default, inline | default     | `ultrathink`            |
| Verify + merge                | default    | `low`            | —                       |

Set effort with `/effort <level>` in the session, with `--effort
<level>` on launch, or via `effort:` frontmatter on a skill or subagent
to scope the override to that role. The `CLAUDE_CODE_EFFORT_LEVEL` env
var beats all of those when set.

### Artefact locations (gitignored)

- `.superpowers/specs/<slug>.md`
- `.superpowers/plans/<slug>.md`
- `.superpowers/review-notes/<slug>.md`

None of these are committed. The PR carries the diff; the review-note
carries the deliberation.

---

## Beads as the per-feature state spine (optional)

When `.beads/` is initialised in the worktree, the `/mc:*` commands
additionally pin per-feature state to bd:

- `/mc:brainstorm` creates a feature bead **whose id mirrors the GitHub issue
  number** (`<prefix>-<N>`, e.g. `gruppo-42`), with a `branch:<name>` label and
  four comments: `slug:`, `spec:`, `plan:`, `review-note:` (the last three
  pinning the artefact paths so downstream commands don't re-derive them from
  the slug). Child finding beads from `/mc:review` keep hash ids — they have no
  issue to mirror — and stay parented to `<prefix>-<N>`.
- `/mc:execute` resolves the plan from the feature bead's `plan:`
  comment, transitions the feature `open → in_progress` at start, runs
  `/superpowers:executing-plans` inline, transitions
  `in_progress → awaiting_review` on a clean smoke pass.
- `/mc:review` looks up the feature bead by branch label (slug arg
  optional), adds a `pr: #N` comment, and creates one child finding
  bead per review entry.
- `/mc:fix` runs a four-state claim flow per finding (claim →
  awaiting_review → close) with `BEADS_ACTOR` distinguishing the
  subagent from the controller in `bd history`.

### Feature-bead lifecycle

```
open  ──/mc:brainstorm──▶  open        (plan / spec / note paths pinned)
                                  │
                                  └──/mc:execute──▶  in_progress
                                                          │
                                                          └──plan complete + smoke clean──▶  awaiting_review  ↺
                                                                                                    │      (PR + /mc:review +
                                                                                                    │       /mc:fix + re-smoke;
                                                                                                    │       bead stays here)
                                                                                                    │
                                                                                                    └──merge, manual `bd close <fid>`──▶  closed
```

The `↺` marks the self-loop: the bead stays `awaiting_review` through
the entire Phase 3 → Phase 4 → re-smoke cycle. Finding-level state
(per-finding `claim → awaiting_review → close`) carries the granular
review/fix progress; the feature bead is the coarse "is Phase 2 done?"
gate.

`/mc:execute` is the *only* command that transitions the feature
bead's status. `/mc:review` and `/mc:fix` operate on child finding
beads, never on the feature bead's status.

In repos without `.beads/`, none of this fires — every `/mc:*` command
behaves exactly as documented above.

### Setup (one-time per repo)

    cd /path/to/main-worktree
    bd init --stealth --non-interactive --prefix <repo-name>-
    bd config set status.custom "awaiting_review"

The feature bead's id is `<prefix>-<N>` (configured `issue_prefix` + GitHub
issue number). Both entry paths choose the id at creation time via
`bd create --id`. **Never `bd create --id` an id that may already exist** — bd
treats that as a silent upsert that overwrites every field (no error, no
duplicate row). `/mc:brainstorm` and `i` both `bd show <id>` first and adopt
the existing bead instead. bd ids are otherwise immutable: there is no
per-bead rename, only `bd rename-prefix` (which rewrites *all* ids).

`--prefix` is **critical** — `bd init` otherwise derives the issue
prefix from the current directory's basename. Run from inside a
worktree (e.g. `198-nord/`) and every bead gets `bd_198-nord-XXX`
permanently, even after the worktree is removed. Pass the primary
repo's basename explicitly with a trailing hyphen (bd's validator
requires ≤8 chars, lowercase letters / digits / hyphens, starting
with a letter, ending with `-`). Examples: `ccpulse-`, `dot-`,
`gruppo-`. If a previous init already baked in the wrong prefix:

    bd rename-prefix <new-prefix>-

`bd init --stealth` adds `.beads/` to `.git/info/exclude` (local-only,
never committed). Does NOT modify `.claude/settings.json`. Collaborators
on a public repo see nothing.

`status.custom = awaiting_review` is the bead state `/mc:execute`
transitions to on plan completion — without it `bd update --status`
errors at that step.

**`/mc:*` commands never run `bd init` themselves** — historically
they did, and the worktree-basename trap above bit hard enough to
make this a deliberate setup step. If `bd status` exits non-zero in
a /mc:* invocation, the beads-pinning paths simply skip.

Also add `Bash(bd *)` to the allow array in `~/.claude/settings.json`
so subagent fix dispatch can run `bd update --claim` and friends
without prompting.

### Why CLI-only, not a plugin

Default `bd init` (non-stealth) registers `SessionStart` and `PreCompact`
Claude Code hooks that inject `bd prime` output. That output contains the
directive *"Prohibited: Do NOT use TodoWrite, TaskCreate, or markdown
files for task tracking"* — which would actively contradict the
Superpowers + `.superpowers/` markdown workflow. Stealth mode skips the
hook registration entirely. The `/mc:*` commands are the explicit
load-state surface; hooks would be redundant.

### bd v2.0 — JSON envelope migration (heads-up)

`bd --json` will change format in bd v2.0 (current command-output
footer: *"bd --json output format will change in v2.0. Set
BD_JSON_ENVELOPE=1 to opt in early. See docs/JSON_SCHEMA.md for
migration details."*). The shape today across v1.x:

- `bd create --json` → object (use `.id`)
- `bd show <id> --json` → array of one (use `.[0]…`)
- `bd list --json` → array (use `.[0]…`)

The jq paths in `brainstorm.md` / `review.md` / `fix.md` / `execute.md`
are written for the v1.x shapes above. `bd create` uses defensive
`.id // .[0].id` so a misread by the executing model still resolves.
When bd v2.0 ships the envelope by default, every jq path in the
`/mc:*` docs needs revisiting — likely a `.data.id` / `.data[0]…`
sweep, or a small `bd-jq()` wrapper. Track via the corresponding
gruppo issue rather than firefighting at upgrade time.

## Why this shape works

- **Divergent vs convergent split.** Brainstorm explores; review
  converges. Different sessions keep their context shapes from
  contaminating each other.
- **The default model decides, typer tiers type.** The expensive tokens go to
  the decisions; the cheap tokens go to the typing. `/mc:fix` makes
  the tier pick a reflex, not a per-fix question.
- **Review-note as the distillation interface.** The reviewer doesn't
  re-read the brainstorm — that's the whole point. `Replaced by:`
  clauses turn rejected approaches into greppable invariants in the
  diff.
- **Fresh review-session eyes.** A reviewer who watched the
  brainstorm rationalises the same misses. A reviewer with only the
  plan + note + diff catches drift.
- **Two complementary fix streams, routed by session.** Formal review
  catches structural drift the diff makes visible; manual testing
  catches behavioural drift the diff makes invisible. Pre-PR smoke
  fixes happen inline in Session B (the session that wrote the bug
  fixes it); post-PR fixes go through `/mc:fix` in Session C (the
  dispatcher routes by tier). Session locality wins over uniform
  routing.
