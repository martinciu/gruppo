---
description: Review the PR for a finished plan using its review-focus note. Stops after the report — does not auto-apply fixes
argument-hint: [<slug>]    # optional; resolved from the feature bead by default
---

## Beads integration (optional)

If `bd status` exits 0 (beads is installed AND this worktree has `.beads/`),
the command additionally records per-feature state in beads. Otherwise the
command behaves exactly as documented below — no extra prompts, no banner.

Detection one-liner:

    bd status >/dev/null 2>&1 || skip_beads=1

Every `bd ...` invocation below is guarded by `[ -z "$skip_beads" ]`. A
failure inside a guarded block **never** blocks the underlying workflow
step — log the error, continue.

## Step 0 — Resolve the feature, slug, and input paths

With beads (default — `bd status` exits 0): always look up the feature
bead by branch label. It carries the slug and the artefact paths as
comments — pinned by `/mc:brainstorm` at creation time.

    branch=$(git symbolic-ref --short HEAD)
    feature_id=$(bd list --label "branch:$branch" --type feature \
      --json | jq -r '.[0].id // empty')

If `$feature_id` resolved, read the pinned paths:

    slug=$(bd show "$feature_id" --json \
      | jq -r '.[0].comments[] | .text | select(test("^slug: ")) | sub("^slug: "; "")')
    plan_path=$(bd show "$feature_id" --json \
      | jq -r '.[0].comments[] | .text | select(test("^plan: ")) | sub("^plan: "; "")')
    note_path=$(bd show "$feature_id" --json \
      | jq -r '.[0].comments[] | .text | select(test("^review-note: ")) | sub("^review-note: "; "")')

`$ARGUMENTS`, if non-empty, **overrides** the slug from the bead (use
when reviewing a different feature than the current branch suggests).
When `$ARGUMENTS` is set, derive the paths from the slug rather than
the bead's pinned comments — the user is asking for a different feature.

**Status check:** the feature bead is expected to be `awaiting_review`
here (`/mc:execute` transitions it on plan completion). If it's still
`in_progress`, warn: "feature bead is `in_progress` — Phase 2 may not
have finished; the diff may not reflect the full plan." Continue
anyway; do not block.

Without beads, or `$feature_id` is empty: use `$ARGUMENTS`. If
`$ARGUMENTS` is also empty, stop and ask the user for a slug. Do not
fall back silently.

Read three inputs in order:

1. `$plan_path` (or `.superpowers/plans/$slug.md`) — the plan.
2. `$note_path` (or `.superpowers/review-notes/$slug.md`) — the
   review-focus note (deliberation context: decisions to verify,
   rejected approaches, invariants, deferred work).
3. The PR diff. If a PR is open for the current branch, use `gh pr view
   --json number,title,headRefName,body` to locate it and `gh pr diff
   <number>` for the diff; if not, ask which PR number to review.

If any of the three inputs is missing, stop and tell the user which one
— don't proceed on partial context.

## Pin PR number to the feature bead (optional)

If `bd status` exits 0, record the PR number on the feature bead. The
idempotency check avoids duplicate `pr:` comments on re-invocations.

    pr_number=$(gh pr view --json number -q .number)
    if ! bd show "$feature_id" --json \
         | jq -e --arg pr "pr: #$pr_number" \
           '.[0].comments[] | select(.text == $pr)' >/dev/null; then
      bd comment "$feature_id" "pr: #$pr_number"
    fi

## Review focus

Use the review-focus note's sections as the structure of your review:

- For each **decision worth verifying** in the note, confirm the diff reflects it.
  Cite the file:line where you verified or where it drifted.
- For each **rejected approach**, scan the diff for signs it slipped back in.
  Then verify the note's `**Replaced by:**` clause matches reality — that
  whatever fills the rejected approach's slot in the implementation actually
  exists in the diff. If the note has no `Replaced by:` (or it reads
  "nothing — deferred behaviour"), check that the feature still works
  coherently without it; a silent gap (e.g. an existing keybinding becoming
  a no-op in the new mode) is drift, severity 🟡 should-fix at minimum.
- For each **invariant**, treat it as a grep target across the diff.
- For each **edge case**, check the diff has a test or a guard.
- For each **deferred item**, suppress yourself — do not flag as missing.
- For each **risk to probe**, look harder than usual and either clear it or
  raise it as a question.

Beyond the note, apply this project's standing review protocol if one exists.
Check `CLAUDE.md` and `CLAUDE.local.md` (in the project root) for instructions
about review lenses, parallel skill-lensed subagent dispatch, security passes,
or language-specific review skills. Follow whatever the project specifies. If
the project has no standing review protocol, just review on intent and code
quality and skip this paragraph.

## Output format

Coverage contract: report every issue you find, including ones you are
uncertain about or consider low-severity. Do not pre-filter for
importance or confidence at the finding stage — the **Recommendations**
section below is the filter (that is what its Drop bucket is for). A
finding that never gets written down can't be triaged.

Produce a single review report with two sections:

1. **Findings** — one flat list of every proposed change, numbered globally
   starting at 1 and never restarting. The number is the only handle used
   to reference a finding. Each entry carries:
   - a severity marker (🔴 must-fix / 🟡 should-fix / 🟢 nit) as metadata,
     not as a sort key or numbering axis,
   - an origin tag — `[drift]` for divergences from the plan or
     review-focus note, `[lens]` for output from project-specific reviewers
     (if the project has a review protocol per above) — also metadata only,
   - a file:line citation.

   Order entries by severity (🔴 → 🟡 → 🟢), then by origin within a tier,
   but the numbers are global and unique across the whole list. Example:
   `1. 🔴 [drift] ...`, `2. 🔴 [lens] ...`, `3. 🟡 [drift] ...`,
   `4. 🟢 [drift] ...`.
2. **Clear** — short summary of what the note told you to verify that *did*
   land correctly. Useful so a follow-up reviewer (you or me) can skip those.
   Not numbered.
3. **Recommendations** — your judgment call on what to do with the findings.
   Reference findings by number only (never re-cite file:line here). Cover:
   - **Apply to satisfy intent** — the minimum subset of findings that must
     land for this PR to actually deliver on the plan / review-focus note.
     The "if I had to ship today, these block the merge" set.
   - **Group together** — findings that share a file, a function, or a
     reasoning thread and should be fixed in one pass rather than separately.
     Format: `Group A: 1, 4, 7 — same regex in <file>`. One-line rationale
     per group. Skip the section if nothing naturally groups.
   - **Defer to a follow-up issue** — findings that are real but out of
     scope for this PR (orthogonal refactor, broader cleanup, deferred work
     the note already flagged, anything that would balloon the diff). For
     each, propose a one-line `gh issue create` title. Don't open the issue
     here — just recommend.
   - **Drop** — findings you'd skip entirely (nits that aren't worth the
     churn, false positives on a second look). Optional; omit if empty.

   A given finding number appears in at most one of these buckets. If a
   finding doesn't appear in any, the user will infer "apply, no grouping,
   no follow-up needed" — which is fine for the common case.

## Pin findings as child beads (optional)

If `bd status` exits 0, for each finding in the report, create a
child bead whose description is **self-contained** — a fresh
`/mc:fix bd-XXXX` session in a separate Claude window must be able
to dispatch the fix from this description alone, without re-reading
the plan, review-note, or this report.

In the template below, lines beginning with `#` are model-only
directives that gate the field beneath them. When the condition is
false, **omit both the `#` line and the field line that follows**;
do not include the `#` directives in the actual bd description.

Set `--priority` from the finding's severity emoji: 🔴 must-fix → `P1`,
🟡 should-fix → `P2`, 🟢 nit → `P3`. P0 stays reserved for genuine
security / data-loss / broken-build findings — bump a 🔴 to `P0` only
when it clears that bar.

    bd create \
      --parent "$feature_id" \
      --type bug \
      --priority <P1|P2|P3 per severity emoji> \
      "<severity emoji> <one-line finding title>" \
      --description "$(cat <<EOF
[<origin tag — drift|lens>] file:line — <citation>

Observed: <what we saw>
Expected: <what the note or project lens prescribed>

# Include only if the issue isn't obvious from reading the diff:
Reproduction: <steps>

# Include only if the review-note pinned a rigor expectation:
Test rigor: <unit | integration>
EOF
)" --json | jq -r '.id // .[0].id'

Print `bead bd-XXXX created` per finding as a footer.

Children automatically inherit the feature's `branch:<name>` label
(verified during pre-flight).

### Self-containment checklist

Before creating each bead, verify:

- Severity emoji in title (🔴 / 🟡 / 🟢), and `--priority` matches it
  (🔴 → P1, 🟡 → P2, 🟢 → P3).
- Origin tag (`[drift]` or `[lens]`) on the first line of the
  description — `/mc:fix` reads this as a tier-picking signal
  (`[lens]` findings are usually pattern-matching against project
  style, leaning the mid typer; `[drift]` findings are often a single
  concrete line, leaning the fast typer).
- `file:line` citation that resolves in the current diff.
- Concrete `Observed` line (what's actually in the code right now).
- Concrete `Expected` line (what should be there — exact bytes if
  mechanical, behaviour description otherwise).
- `Reproduction` only when the issue isn't obvious from reading the
  diff (omit the field entirely if not needed; do not write
  "Reproduction: N/A").
- `Test rigor` only when the review-note pinned an expectation
  (omit if not).
- **No report-relative references** — do not write "finding #3" or
  "see #5 above"; the numbers don't survive across sessions.
- **No `.superpowers/` path citations** — those are gitignored and
  the fresh /mc:fix session may not have them.
- **No "as we discussed" references** — write out the substance.

## Mirror findings into a live Hunk session (optional)

If a live [Hunk](https://github.com/modem-dev/hunk) session is showing this
same repo, mirror each finding onto the diff line it cites, so the findings
can be read *on the code* rather than only as a list in this pane. Guarded
exactly like the beads integration: present when a session matches, a
silent no-op otherwise. Never a hard dependency.

Session selection is by repo root and session id through Hunk's loopback
daemon — never by TTY, pane, or PID. The step works when Hunk runs in
another window, another tmux server, or no tmux at all.

### Detection

    repo=$(git rev-parse --show-toplevel)
    # `.sessions[]` and `.repoRoot` are load-bearing. The obvious-looking
    # `.[] | select(.repo == $r)` exits 5 (cannot iterate over an object),
    # which trips the guard unconditionally and turns this whole step into
    # a permanent silent no-op that looks exactly like "no session running".
    sid=$(hunk session list --json 2>/dev/null \
      | jq -r --arg r "$repo" \
          '[.sessions[] | select(.repoRoot == $r)]
           | sort_by(.launchedAt, .sessionId) | last | .sessionId // empty')
    [ -n "$sid" ] || skip_hunk=1

A missing `hunk` binary, a dead daemon, and a repo mismatch all leave
`$sid` empty — no separate `command -v` check is needed. Every `hunk ...`
call below is guarded by `[ -z "$skip_hunk" ]`, and a failure inside the
guarded block **never** blocks the review: log the error, continue.

Resolving an explicit `$sid` (rather than passing `--repo`) is deliberate:
with two Hunk windows on one repo, `--repo` refuses with "Multiple active
sessions match ...; specify sessionId instead". Most-recently-launched
wins, but sessions opened in quick succession can share a `launchedAt`,
so the `.sessionId` tiebreak keeps the pick deterministic — the footer's
`(session <id>)` tells the human which window received the notes.

### Finding → note mapping

The report format needs no changes — every finding already carries a
`file:line` citation.

| Note field | Source |
|---|---|
| `filePath` | repo-relative path from the finding's citation; must match a `files[].path` in the loaded review |
| `newLine` / `oldLine` / `hunk` | exactly one — `newLine` by default, `oldLine` when the finding is about removed code, `hunk` when snapping (below) |
| `summary` | `#<N> <severity emoji> [<origin>] <title>` — the **global report number**, so a later "apply 1, 3, 5" still resolves |
| `rationale` | the `Observed:` / `Expected:` pair already written for the child bead |
| `author` | `mc:review` — renders in the note header and enables `comment list --type agent` filtering |

`comment apply` validates that the target line falls **inside a diff
hunk**, not merely that the file is loaded — and it validates the whole
batch before mutating anything, so a single bad item applies *zero* notes.
Findings routinely cite lines that are not in a hunk (a function signature,
the place a missing guard belongs, a line from `gh pr diff` that does not
match what the human loaded). So the payload is built by the program below
rather than by hand:

- cited line inside a hunk → note lands exactly there;
- file loaded but line outside every hunk → note **snaps to the nearest
  hunk** and its summary is marked `(near line N)`;
- file not in the loaded diff → not mirrored, and reported.

### Mapping program

Write your findings to a scratch file as JSON — one object per finding with
`n`, `emoji`, `origin`, `file`, `line`, `side` (`"new"` or `"old"`),
`title`, `rationale`:

    {"findings":[
      {"n":1,"emoji":"🔴","origin":"drift",
       "file":"src/thing.ts","line":42,"side":"new",
       "title":"guard dropped on the empty case",
       "rationale":"Observed: …\nExpected: …"}
    ]}

Write this program to a scratch file verbatim — do not paraphrase it, and
do not "simplify" the two commented lines:

```jq
$review[0].review.files as $files
| [ .findings[]
    | . as $f
    | ($f.side // "new") as $side
    # map|first, NOT `$files[] | select(...)`: the generator form yields
    # nothing for a non-matching file, silently dropping the finding
    # instead of routing it to `unmapped`.
    | ($files | map(select(.path == $f.file)) | first) as $entry
    | ( if $entry == null then null
        else [ $entry.hunks[]
               | (if $side == "old" then .oldRange else .newRange end) as $r
               | select($r[0] <= $f.line and $f.line <= $r[1]) ] | first
        end ) as $exact
    | ( if $entry == null then null
        else ( $entry.hunks
               | map( . as $h
                      | (if $side == "old" then .oldRange else .newRange end) as $r
                      | { index: $h.index,
                          d: (if $f.line < $r[0] then $r[0] - $f.line
                              elif $f.line > $r[1] then $f.line - $r[1]
                              else 0 end) } )
               # .index tiebreak keeps selection deterministic for a line
               # sitting equidistant between two hunks.
               | sort_by(.d, .index) | first )
        end ) as $near
    | if $entry == null then
        { kind: "unmapped", n: $f.n, file: $f.file, line: $f.line,
          reason: "file not in loaded diff" }
      elif $exact != null then
        { kind: "exact", n: $f.n,
          comment: ( { filePath: $f.file,
                       summary: "#\($f.n) \($f.emoji) [\($f.origin)] \($f.title)",
                       rationale: $f.rationale,
                       author: "mc:review" }
                     + (if $side == "old" then { oldLine: $f.line }
                        else { newLine: $f.line } end) ) }
      elif $near != null then
        { kind: "snapped", n: $f.n, line: $f.line, hunk: ($near.index + 1),
          comment: { filePath: $f.file,
                     hunk: ($near.index + 1),
                     summary: "#\($f.n) \($f.emoji) [\($f.origin)] \($f.title) (near line \($f.line))",
                     rationale: $f.rationale,
                     author: "mc:review" } }
      else
        { kind: "unmapped", n: $f.n, file: $f.file, line: $f.line,
          reason: "file has no hunks in loaded diff" }
      end ]
| { comments: [ .[] | select(.comment) | .comment ],
    snapped:  [ .[] | select(.kind == "snapped") | { n, line, hunk } ],
    unmapped: [ .[] | select(.kind == "unmapped") | { n, file, line, reason } ] }
```

`hunk`'s per-item hunk target is **1-based** while `review --json` reports
`index` **0-based** — hence `$near.index + 1`. `newRange` / `oldRange` are
`[start, end]` **inclusive**, and the two sides differ (a real hunk measured
`old=[17,37]` / `new=[17,76]`), which is why the side selects the range.

### Apply

`$findings_json` and `$map_jq` are scratch files you write for this step
(your findings, and the program above verbatim); `$review_json`,
`$mapped_json`, and `$applied_json` are intermediates. Put all five in a
scratch directory — nothing here is written into the repo.

    hunk session review "$sid" --json > "$review_json"
    jq --slurpfile review "$review_json" -f "$map_jq" "$findings_json" > "$mapped_json"

    # Idempotency: bare `clear` removes all agent notes in the session
    # (no --author filter, so another tool's notes go too). Verified:
    # with a human TUI note present it reports removedUserNoteCount 0 and
    # leaves that note rendered. NEVER pass --include-user or --all — those
    # would delete the human's own notes.
    hunk session comment clear "$sid" --yes >/dev/null

    # One batch. The guard is load-bearing: `apply` with an empty list is an
    # error ("Session comment apply expected at least one comment.", exit 1),
    # not a no-op — so a review with zero findings, or one where every finding
    # was unmapped, would otherwise end on a spurious error line.
    if [ "$(jq '.comments | length' "$mapped_json")" -gt 0 ]; then
      jq -c '{comments}' "$mapped_json" \
        | hunk session comment apply "$sid" --stdin --json > "$applied_json"
    fi

Verified: on any bad item — a line the diff moved off since `$review_json`
was captured — `comment apply` exits nonzero, prints a plain-text error,
and applies nothing; no JSON reaches stdout and `$applied_json` stays
empty. The whole batch is atomic, so the footer below must read
`$applied_json`, not `$mapped_json` — see the next section.

Do **not** pass `--focus`. The batch lands when the review finishes, which
may be long after the human last looked; focusing would yank their viewport
mid-scroll.

Run `clear` even when there are no findings, so a clean re-review removes
the previous run's notes.

### Footer

Print a short footer after the report:

    mirrored 6/8 findings into Hunk (session a787990a)
      #2 snapped to hunk 1 (cited line 90 is outside any hunk)
      #3 not mirrored — src/does-not-exist.ts: file not in loaded diff
      #5 not mirrored — src/other.ts: file has no hunks in loaded diff
      notes are hidden — press `a` in Hunk to show them

The numerator is `.result.applied | length` from `$applied_json`, never a
count derived from `$mapped_json` — `comment apply` validates the batch
atomically, so a diff that moved between mapping and apply drops every
note, and only the apply result reflects what actually landed. A
non-empty `$mapped_json` batch with an empty `$applied_json` is that
failure: report `mirrored 0/N — batch rejected, diff changed since
mapping` instead of printing the mapped count. When the batch sent to
`comment apply` was itself empty (the guard above stayed false), the
footer also reports 0 mirrored, with no rejection line — there was
nothing to send.

Emit one line per entry in `.snapped` and `.unmapped`; each `.unmapped`
line echoes that entry's `reason` field verbatim, so "file not in loaded
diff" (the Hunk session is on a different diff range) and "file has no
hunks in loaded diff" (file is loaded, but the finding cites unchanged
code) read as the distinct problems they are.

The last line appears **only** when `$review_json` — captured before
`clear`/`apply` ran — reports `.review.showAgentNotes == false`. A fresh
`hunk diff` hides agent notes and applying one does not reveal them, so
the pre-apply capture stays accurate; there is no CLI toggle, and without
this hint the first use looks broken.

Hunk renders notes in **diff order** while the report is severity-ordered,
so scrolling top-to-bottom may reach #7 before #2; the `#N` prefix is the
handle. Several notes on one line are paginated by Hunk itself
(`mc:review note 1/4 - …`).

This step writes to the review surface only. It applies no fix, edits no
file, and does not weaken the gate below.

## Stop here — wait for approval before any fix is applied

After producing the report, **stop**. Do not dispatch any subagents. Do not
edit any files. Do not commit anything.

End the response with a single explicit prompt for the user:

> Which findings should I apply? Reply with the numbers (e.g. "1, 3, 5",
> a range like "1-4", "accept recommendations" to take the Recommendations
> section as-is, "issue: 6, 8" to spin those off as follow-up `gh` issues
> instead of applying, "none", or describe a different action. Use
> `/mc:fix <description>` to apply each approved fix at the right tier
> (fast typer / mid typer / inline, picked by `/mc:fix`).

The user picks the subset; nothing is auto-applied.

When the user replies, do **not** type the fix yourself — use `/mc:fix` per
approved finding (one invocation per fix is fine; the command parses multiple
fixes per invocation if the description lists them). The reviewer (default
model) decides what to fix; `/mc:fix` picks the right typing tier (fast
typer for mechanical, mid typer for judgment-laden, or inline when the fix
needs default-tier reasoning). Spending default-tier tokens on the typing
wastes quota.

## Transition finding beads on user reply (optional)

If `bd status` exits 0, mirror the user's approval decision onto the
finding beads created above:

- **User approves a subset** (e.g. "1, 3, 5", "1-4", "accept
  recommendations"): for each approved finding bead, run

      bd update "$fid" --status=approved

  before dispatching `/mc:fix`.

- **User replies `issue: 6, 8`** to defer findings to GitHub: after
  `gh issue create` for each, close the bead with the new issue ref:

      bd close "$fid" -r "deferred to gh#$new_issue_number"

- **User replies `none`**: no transitions. Leave the finding beads at
  `open` so a future re-invocation can re-surface them.

## What to skip

- Do not re-read the brainstorm transcript. The review-focus note is the
  whole point of this workflow.
- Do not cite `.superpowers/...` paths in the PR review comment or commit
  messages — those paths are gitignored and never appear in shared text.
