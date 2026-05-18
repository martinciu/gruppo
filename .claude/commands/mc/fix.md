---
description: Apply the described fix(es) by picking the right tier (Haiku / Sonnet / inline) — or, without arguments, list open child findings for the current feature bead
argument-hint: [<description>]    # optional; without args, lists open findings
---

Apply the following fix(es). Description:

$ARGUMENTS

## Mode

`$ARGUMENTS` above is the user's input. Two behaviours:

- **Non-empty** → **dispatch mode**. Walk Step 1's decision tree to
  pick a tier for each fix in the description and dispatch.
- **Empty AND `bd status` exits 0** → **list mode**. Run "List mode
  (no arguments)" below to enumerate open child findings of the
  current feature bead, then stop. Do not dispatch anything.
- **Empty AND no bd** → stop and ask the user for a description.
  See "When the description is ambiguous" at the bottom.

## Beads integration (optional)

If `bd status` exits 0 (beads is installed AND this worktree has `.beads/`),
the command additionally records per-feature state in beads. Otherwise the
command behaves exactly as documented below — no extra prompts, no banner.

Detection one-liner:

    bd status >/dev/null 2>&1 || skip_beads=1

Every `bd ...` invocation below is guarded by `[ -z "$skip_beads" ]`. A
failure inside a guarded block **never** blocks the underlying workflow
step — log the error, continue.

## List mode (no arguments)

Runs only when `$ARGUMENTS` is empty AND `bd status` exits 0. In any
other case, skip this section and continue to Step 1.

Resolve the feature bead by branch label:

    branch=$(git symbolic-ref --short HEAD)
    feature_id=$(bd list --label "branch:$branch" --type feature \
      --json | jq -r '.[0].id // empty')

If `$feature_id` is empty, stop and tell the user: no feature bead
exists for the current branch — run `/mc:brainstorm-issue <N>` first.

Otherwise enumerate every child finding not yet closed, sorted so
in-flight items rise to the top (`approved` → `in_progress` →
`awaiting_review` → `open`):

    bd list --parent "$feature_id" \
      --status open,approved,in_progress,awaiting_review --json \
      | jq -r 'sort_by(
          ({"approved":0,"in_progress":1,"awaiting_review":2,"open":3})[.status],
          .id
        ) | .[] | "\(.id)\t[\(.status)]\t\(.title)"'

Render as a compact table — three columns: bd ID, status, title. If
no rows, say: "no open child findings for `<feature_id>` — run
`/mc:review-pr` to generate some, or all approved findings have
already been dispatched and closed."

Then **stop**. End with:

> Re-invoke `/mc:fix <description>` to dispatch — copy a finding
> title from the list above, or pass a bd ID directly (e.g.
> `/mc:fix bd-abc123`). The dispatcher routes each fix through the
> tier-picker (Haiku / Sonnet / inline) per Step 1.

## 0. Resolve `$ARGUMENTS` to a concrete brief

Before walking Step 1's decision tree, normalise `$ARGUMENTS` into a
brief the dispatcher can route.

**bd-ID input (preferred path in bd-active repos):** if `$ARGUMENTS`
contains one or more bd IDs AND `bd status` exits 0, fetch each
finding's full record.

*Detecting bd IDs:* treat any whitespace-separated token matching
`^[a-z]+-[a-z0-9]{3,}$` as a candidate. The prefix varies per repo
(`bd-`, `gruppo-`, etc. — bd configures it at init time); the
suffix is at least three alphanumeric chars. **Confirm each
candidate with `bd show <token> --json` before treating it as a
finding ID** — fail closed if `bd show` errors (the token was just
a word that happened to match the shape, e.g. `mc-execute`,
`api-v2`).

For each confirmed bd-ID:

    bd show <id> --json \
      | jq -r '.[0] | "## \(.title)\n\n\(.description)"'

The bead's `title` + `description` becomes the **primary brief** for
that fix. Per `/mc:review-pr`'s self-containment contract, the
description carries `[drift]/[lens]` origin tag, `file:line`,
Observed / Expected / Reproduction / Test rigor — everything the
tier-picker in Step 1 needs. A fresh Claude session running
`/mc:fix bd-XXXX` has no other context, and doesn't need it.

Any free-text alongside the ID (e.g. `/mc:fix bd-abc123 also bump
the version`) is *supplementary* — append to the brief, do not
replace.

**Free-text input:** if `$ARGUMENTS` has no bd ID, use it directly
as the brief. Optionally substring-match against open child finding
titles to identify the corresponding bead (used by §3a for the
claim-flow). If no match, dispatch without a bead claim.

**Multiple bd IDs in one invocation** (e.g. `/mc:fix bd-aaa bd-bbb`):
treat each as a separate fix — Step 1 picks a tier per fix, §3 fans
out one subagent per fix in parallel.

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

**Tier-pick prior from the origin tag** (when Step 0 resolved from a
bd-ID, the bead description's first line carries `[drift]` or `[lens]`):

- `[drift]` findings usually have a concrete `file:line` and exact
  `Expected:` value — lean toward Haiku.
- `[lens]` findings usually pattern-match against project style or
  span multiple files — lean toward Sonnet.

The decision tree above still wins if the brief surfaces judgment
beyond what the tag suggests. See `/mc:review-pr` § "Self-containment
checklist" for where the tag is set.

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
   - A tight brief, ideally under ~500 tokens. Two assembly paths:
     - **Resolved from a bead** (Step 0 bd-ID path): pass the bead's
       `title + description` verbatim as the brief body. It already
       carries `file:line`, Observed, Expected, Reproduction, and
       (when set) Test rigor — that's exactly the subagent input
       contract. Add only: "What to leave alone — do not refactor /
       do not touch unrelated code" and "Working directory: <repo
       root>".
     - **Free-text input**: build the brief from `$ARGUMENTS` and
       any context the dispatcher has. Include the file path /
       line(s), exact change or behavioural target, what to leave
       alone, test expectations if any, working directory.

3. Do **not** dump the whole review report, plan, or review-focus note into
   each subagent prompt. The subagent only needs the brief for *its* fix
   — which is the bead's description (resolved path) or `$ARGUMENTS`
   (free-text path), nothing else.

4. When subagents return their diffs, you (the caller) read each diff,
   verify it matches intent, and stage/commit. Do not push.

## 3a. Beads claim flow (when `bd status` exits 0)

The dispatcher needs `$feature_id` for child-finding claim ops. Three
resolution paths, in priority order:

1. **Step 0 bd-ID path** (fresh-session-friendly): when `$ARGUMENTS`
   resolved to one or more bd-IDs, derive `$feature_id` from any
   child finding's `parent_id`:

       feature_id=$(bd show <first_finding_id> --json \
         | jq -r '.[0].parent_id')

2. **Continuing Phase 3 session**: the dispatcher carries
   `$feature_id` in context from `/mc:review-pr`'s child-bead
   creation.

3. **Re-discover from branch label** (fallback when both above
   fail — e.g. free-text dispatch without a Phase 3 predecessor):

       feature_id=$(bd list --label "branch:$(git symbolic-ref --short HEAD)" \
         --type feature --json | jq -r '.[0].id')

Identifying the target finding bead per fix:

- If path (1) — Step 0 — the bd-ID is already the finding ID; no
  matching needed.
- If path (2) or (3) — `$ARGUMENTS` was free-text — substring-match
  the description against child finding titles (best-effort). If no
  match, dispatch without a bead claim.

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

Two separate cases:

- **`$ARGUMENTS` is empty**: handled by the mode selector at the top.
  In bd-active repos, list mode prints the open child findings and
  stops. In bd-absent repos, stop here and ask the user for a fix
  description.
- **`$ARGUMENTS` is non-empty but too vague to pick a tier** (no file,
  no line, no clear target behaviour): stop and ask the user to
  clarify before doing anything. A vague brief produces vague code
  regardless of tier.

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
