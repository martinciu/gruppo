---
description: Apply the described fix(es) by picking the right tier (Haiku / Sonnet / inline) — or surface that it needs a separate issue or brainstorm first
---

Apply the following fix(es). Description:

$ARGUMENTS

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

## 4. Announcing the dispatch

Before kicking off subagent calls, print a one-line summary per fix so the
caller can see your tier picks:

> Dispatching: 3 fixes → 2× Haiku (mechanical), 1× Sonnet (multi-file).
> 1 fix kept inline (in-scope decision: <one-line rationale>).

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
