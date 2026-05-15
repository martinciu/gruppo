---
description: Distill brainstorm context into a one-page review-focus note for a future Opus reviewer
---

Write a one-page "review focus" note to `.superpowers/review-notes/$ARGUMENTS.md`.

Audience: a fresh Opus session that will review the PR for this plan. It
has the plan file and the diff, but not this brainstorm. The note's job is
to inject only the deliberation context that affects how to read the diff.

Length: ~1 page. Prefer specificity over completeness. If a section has
nothing worth saying, omit it — empty headings waste tokens.

Frontmatter: `issue: <num>` only (omit entirely if there is no issue). Do
not add `spec:` or `plan:` pointers, and do not link to those files in
the body. The reviewer already has the plan (planning and review happen
in the same worktree) — linking from the note tempts under-distillation
("they can read the spec if they care"), which defeats the one-page
self-contained design. If something from the plan matters for the
review, lift it into the note as a sentence.

Sections, in this order:

1. **Decisions worth verifying.** Non-obvious choices the brainstorm
   landed on, where the diff should reflect them. Name the file/function/
   flag if you can. Example: "Bucket alignment uses local midnight via
   SQLite `'localtime'` modifier. Reviewer: confirm we did not regress
   to UTC `strftime('%s', ts)`."

2. **Explicitly rejected approaches.** The shapes we considered and
   discarded, with one-line reasons. The reviewer's job is to flag if
   the implementation slipped back into any of these. Be specific —
   "we rejected X because Y" beats "we considered X."

   Every entry MUST include a `**Replaced by:** <one line>` clause
   naming what fills the rejected approach's slot in the implementation.
   If nothing fills it, write `**Replaced by:** nothing — feature ships
   without this dimension; treat as deferred behaviour`. Rejected
   approaches without a replacement silently become feature gaps (e.g.
   "we rejected bucketing by zoom" with no replacement → zoom becomes
   a no-op in the new mode and nobody notices until a user does).
   Making the absence explicit is the way to defer without surprise —
   the reviewer treats missing `Replaced by:` as drift.

3. **Edge cases the brainstorm called out.** DST days, empty inputs,
   timezone offsets, integer overflow, whatever surfaced. Reviewer
   checks these are covered (test or guard).

4. **Invariants that must hold.** Things that should be greppable in
   the diff. "All `time.Time` values written to the cache stay UTC."
   "No new `_ = err` swallows." "Y-label slot stays 5 columns."

5. **Deferred / out of scope.** What we agreed *not* to do in this PR
   so the reviewer doesn't flag it as missing. Link follow-up issues
   if any.

6. **Risks to probe.** Areas where the brainstorm wasn't fully certain
   and the reviewer should look harder. Frame as questions:
   "Does the new path race with the watcher debounce?" not "There may
   be a race."

7. **Test rigor expected.** One line. So the reviewer can flag if the
   diff has unit tests only when integration was agreed.

Tone: terse, technical, no padding, no 'we'. Bullets over prose. Name
files, line numbers, flags, and identifiers wherever possible — the
reviewer should be able to grep the note's terms in the diff.

Do not include process narrative (what we discussed, in what order),
emotional context, or alternatives we never seriously considered.
Just the distilled output a reviewer needs.

When you're done, save to `.superpowers/review-notes/$ARGUMENTS.md`
and print the path.
