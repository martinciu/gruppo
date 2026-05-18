---
description: Apply the described fix(es) by picking the right tier (Haiku / Sonnet / inline) — or surface that it needs a separate issue or brainstorm first
---

Apply the following fix(es). Description:

$ARGUMENTS

## Beads integration (optional)

If `bd status` exits 0 (beads is installed AND this worktree has `.beads/`),
the command additionally records per-feature state in beads. Otherwise the
command behaves exactly as documented below — no extra prompts, no banner.

Detection one-liner:

    bd status >/dev/null 2>&1 || skip_beads=1

Every `bd ...` invocation below is guarded by `[ -z "$skip_beads" ]`. A
failure inside a guarded block **never** blocks the underlying workflow
step — log the error, continue.

## 1. Decide what to do with each fix

For each fix in the description, walk this decision tree before any code
moves:

```
Is the brief mechanical (file path + exact bytes or behavioural target,
no judgment in what to do)?
├── Trivially so (single file, exact lines, no new test harness,
│   no pattern-matching against existing style)        → Haiku
├── Yes, but with judgment ("match existing pattern",
│   multi-file, new tests in an existing harness)      → Sonnet
└── Needs real judgment in what the fix should be      → go to step 2.
```

**Don't dispatch Opus to Opus.** If a brief needs Opus-tier reasoning to
type the fix, you are Opus — don't round-trip through a subagent. Go to
step 2 instead.

## 2. The "needs judgment" branches

When the brief needs judgment, do not dispatch. Pick one of three:

**A. Out of scope for the current PR/feature.** The judgment belongs to a
separate concern. Surface, do not act:

> This fix uncovers a separate concern: <one-sentence framing>. Recommend
> filing a new issue and brainstorming before touching it. Want me to file
> the issue?

Stop. Wait for explicit "yes" before running `gh issue create`. Never file
an issue silently.

**B. In scope, and you have a defensible decision.** A "defensible
decision" means you can write a one-line rationale and the user is likely
to nod — not ask three follow-up questions. Announce, then proceed inline:

> Decision: <one-line pick + rationale>. Doing this inline.

Do the work yourself. No subagent dispatch.

**C. In scope, but you are not confident in the decision.** Be honest:

> The right call here isn't obvious to me — <name the uncertainty in one
> sentence>. Recommend a brainstorm before we touch code. Want me to file
> an issue to anchor it?

Stop. Wait for explicit "yes" before filing. Same gate as branch A.

## 3. Dispatching a subagent (Haiku or Sonnet)

When step 1 picked Haiku or Sonnet:

1. If the description lists multiple independent fixes, dispatch **one
   subagent per fix** in parallel via multiple Agent tool calls in a
   single response. One fix → one subagent.

2. Each subagent call uses:
   - `subagent_type: "general-purpose"`
   - `model: "haiku"` or `"sonnet"` per step 1
   - A tight brief, ideally under ~500 tokens, containing:
     - The file path and line(s) to change
     - The exact change (or behavioural target, if the change is mechanical)
     - What to leave alone — explicit "do not refactor / do not touch
       unrelated code"
     - Whether tests are expected and where (and whether the test
       harness already exists)
     - Working directory (use the current repo root unless told otherwise)

3. Do **not** dump the whole review report, plan, or review-focus note into
   each subagent prompt. The subagent only needs the brief for *its* fix.

4. When subagents return their diffs, you (the caller) read each diff,
   verify it matches intent, and stage/commit. Do not push.

## 3a. Beads claim flow (when `bd status` exits 0)

For each fix being dispatched, identify the target finding bead. The
dispatcher (the calling Opus session) carries the feature ID from
`/mc:review-pr`'s context — or re-discovers it from the branch label if
context was lost:

    feature_id=$(bd list --label "branch:$(git symbolic-ref --short HEAD)" \
      --type feature --json | jq -r '.[0].id')

Then match the fix description to a child finding (best-effort —
substring match against finding titles is sufficient; the user can
always specify the finding ID explicitly in the fix description).

### Dispatcher actions (before Agent call)

Set `BEADS_ACTOR` in the subagent environment when invoking the Agent
tool. The tool's `env` parameter accepts a map; pass:

    BEADS_ACTOR=haiku-subagent   # for Haiku 4.5
    BEADS_ACTOR=sonnet-subagent  # for Sonnet 4.6

(If the Agent tool does not expose env passthrough, the dispatcher
explicitly threads `BEADS_ACTOR=<name>` as a leading clause in every
`bd` invocation inside the subagent's prompt, e.g.:
`BEADS_ACTOR=haiku-subagent bd update <id> --claim`.)

### Subagent prompt — add a beads block at the end

Append this block to the subagent's brief, byte-exact:

    ## Beads coordination

    The finding you are fixing is bead `<finding_id>`.

    Before starting:

        bd update <finding_id> --claim

    After producing the diff (do not commit — return the diff to the
    caller), set:

        bd update <finding_id> --status=awaiting_review
        bd comment <finding_id> "<one-line summary of the fix you typed>"

    If `bd status` exits non-zero (no beads in worktree), skip the bd
    ops above. The diff is the only required output.

### Dispatcher actions (after subagent returns)

When the subagent returns its diff:

1. Read the diff and verify intent (existing behaviour).
2. Stage and commit (existing behaviour).
3. Close the finding bead:

       bd close <finding_id> -r "fixed in <commit-sha>"

4. Print: `bead <finding_id> closed`.

### Parallel dispatch (existing §3 fans out N subagents)

Each subagent claims its own finding independently. The dispatcher
iterates the awaiting-review queue as completions return:

    bd list --parent "$feature_id" --status awaiting_review --json

## 4. Announcing the dispatch

Before kicking off subagent calls, print a one-line summary per fix so the
caller can see your tier picks:

> Dispatching: 3 fixes → 2× Haiku (mechanical), 1× Sonnet (multi-file).
> 1 fix kept inline (in-scope decision: <one-line rationale>).

If beads is active, the dispatch announcement also lists the finding IDs
being claimed.

The user can interrupt before the calls return if a tier pick looks wrong.

## When the description is ambiguous

If the description is too vague to even pick a tier (no file, no line, no
clear target behaviour), stop and ask the user to clarify before doing
anything. A vague brief produces vague code regardless of tier.

## Why this command exists

The "Opus decides, Sonnet/Haiku types" split is what makes the
SDD-with-Opus-reviewer workflow quota-efficient. Every fix typed by an
Opus session costs ~5× a Sonnet token and ~25× a Haiku token against the
Max quota. This command makes the tier decision part of the dispatch
reflex, not a separate one the caller has to make.

The "stay out of dispatch when the call needs judgment" branch is the
discipline gate — it catches "this looked mechanical but isn't" before a
wasted dispatch round, and it routes architectural decisions to brainstorm
instead of letting them slip into a quick `/mc:fix` by accident.

This command assumes the **dispatcher is the highest tier in the session**
(typically Opus). The tier picker relies on the dispatcher's judgment of
the brief; a lower-tier dispatcher would be less reliable at that
meta-judgment.
