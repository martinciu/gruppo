---
name: session-finder
description: Use when the user wants to find, list, or recover a PAST Claude Code session — "list my sessions", "find that session where I worked on X", "what did I do yesterday in the dotfiles repo", "I had a long chat about JWT auth last week, can you find it", "resume the autonomo eval session", "I deleted that worktree, how do I get back into the conversation". Fires on natural phrasing — the user names what they remember (date, repo, branch, topic, what they typed) without having to recall the session ID. Also fires for orphaned worktrees the user wants to recreate, and for plain non-worktree sessions. Do NOT trigger for stats about THIS session (cost, tokens, runtime — that's the session-stats skill), for `claude -c` style "continue the most recent session in this dir" (built-in), or for general shell history / git log style questions.
---

# Session Finder

List, search, and recover past Claude Code sessions stored on disk.
Sessions live in `~/.claude/projects/<encoded-cwd>/<uuid>.jsonl` — one
file per session, one JSON event per line. The user usually doesn't
remember the UUID; they remember the topic, the repo, or roughly when.
This skill bridges that gap.

## When to use

The user is looking for a session that already happened. Common shapes:

- **List / browse**: "list my sessions", "show me what I worked on
  yesterday", "what's been going on in the gruppo repo?"
- **Find specific**: "find the session where I was debugging the
  autonomo dry-run flag", "I had a long chat about session-stats
  triggering — can you find it?"
- **Recover orphaned**: "I removed that worktree but I want the
  conversation back", "the autonomo-eval-more branch is gone,
  can I get the session?"
- **Get a resume command**: "give me the command to jump back into
  that session", "how do I resume this one?"

### When NOT to fire

- Stats about the **current** session (cost, tokens, runtime) →
  `session-stats` skill.
- The user wants to continue the *most recent* session in the *current*
  directory → that's `claude -c` (built-in), no skill needed.
- The user is asking about git history, shell history, or files they
  edited — those aren't Claude sessions.

## How sessions are stored

Quick orientation so the output makes sense:

- One directory per encoded cwd: `~/.claude/projects/<slug>/`. The slug
  is the cwd with `/` and `.` both replaced by `-` (so `/.` becomes
  `--`).
- One file per session: `<uuid>.jsonl`.
- Each line is an event: `user`, `assistant`, `system`, `attachment`,
  `last-prompt`, `permission-mode`, `file-history-snapshot`. The
  `cwd`, `gitBranch`, `timestamp`, and `version` fields appear on
  every `user`/`assistant`/`system` event — the original working
  directory and branch are preserved verbatim, no decoding needed.
- `last-prompt` events store the most recent user prompt as a
  top-level `lastPrompt` field — that's the cheapest way to get a
  one-liner for a session.
- `system` events with `subtype: away_summary` are Claude's own
  summary of what happened. Use as the description if present.

## The procedure

There's one bundled script that does discovery, parsing, filtering,
and command generation. **Don't reinvent it inline** — just call it.

```bash
python3 <skill-dir>/scripts/list_sessions.py [filters]
```

`<skill-dir>` is the directory containing this SKILL.md.

### Step 1: Translate the user's ask into filters

Read the request and decide which flags to pass. Combine freely.

| User says                              | Flag                              |
|----------------------------------------|-----------------------------------|
| "in gruppo", "in ~/code/dotfiles"      | `--dir <substring>`               |
| "yesterday", "last week", "since Apr"  | `--since YYYY-MM-DD` (and/or `--until`) |
| "on the autonomo branch", "worktree X" | `--branch <substring>`            |
| "about JWT auth", "where I touched X"  | `--keyword "<phrase>"` (slower)   |
| "the orphaned ones", "deleted worktrees" | `--only-orphaned`               |
| "worktree sessions", "tmp dirs"        | `--only-worktrees`                |
| "more results", "show me all"          | `--limit <N>` (default 50)        |

Convert relative dates to absolute before passing (`yesterday` →
today's date minus 1, etc.). The script accepts `YYYY-MM-DD` or full
ISO timestamps — not "yesterday".

### Step 2: Run the listing and present the table

Default output is a compact table sorted by recency:

```
ID        AGE      WHERE                              MSGS  SIZE  PROMPT
--------  -------  ---------------------------------  ----  ----  --------
3627ee4f  7m ago   ~/code/gruppo (gemini-search-…)    91    215K  I was recovering this repo from…
7d7ed71b  1d ago   gruppo:autonomo-eval-more [orph]   1317  4.8M  ! pwd
0851889c  23h ago  dotfiles:abd [orph]                25    72K   curl script
```

Reproduce the table verbatim. The columns are short on purpose —
they're meant to fit in a terminal pane.

Markers in the WHERE column:

- `repo:branch [wt]` — worktree session, directory still exists
- `repo:branch [orph]` — worktree session, directory deleted
- `<path> [missing]` — plain (non-worktree) directory, no longer exists
- otherwise the cwd + git branch in parens

### Step 2.5: When several candidates match, compare before picking

A keyword search will often return multiple sessions that all contain the
phrase — same word lives in different conversations. Don't just pick the
top hit. The user described a topic; that topic lives in the *content*
of the session, not just the keyword density.

When the table has more than one candidate that plausibly fits:

1. Run `--inspect` on each top candidate (cheap — it's already parsed).
2. Compare the **away summary** and **last user prompt** against what
   the user actually described. The away summary is Claude's own
   one-paragraph recap of what the session was about — it's the single
   best signal for "is this the conversation they meant?"
3. Pick the one whose summary matches the user's description, not the
   one with the most keyword hits.
4. If two are genuinely close, surface both with their summaries and
   ask the user which one they meant — don't guess.

Why: keyword presence is a coarse filter. A session about "session-stats
the skill" and a session about "lines-of-code in session-stats" both
match `--keyword session-stats`, but only one matches the user's intent.
Mismatching here wastes the user's time and (if they actually run the
resume command) drops them into the wrong context.

### Step 3: When the user wants details on one session

Inspect by short ID (the 8-char prefix from the table) or by full UUID:

```bash
python3 <skill-dir>/scripts/list_sessions.py --inspect <short-id>
```

The detail view includes the full UUID, file path, byte size, message
counts, original cwd, git branch, version, first event timestamp, last
event timestamp, the first user prompt, the last user prompt (if
different), the away summary (if present), and a **resume command**
tailored to the session's situation.

### Step 4: Present the resume command

The script picks the right command based on three cases. Pass it
through to the user as-is — they will run it themselves; **do not run
it for them**, because resuming a session inside another Claude Code
session would either spawn a child process or exit the current one.

Cases the script handles:

- **Plain directory, exists**:
  `cd <cwd> && claude --resume <uuid>`
- **Worktree, exists**:
  `wt switch <branch> && claude --resume <uuid>` — `wt switch` is
  preferred over `cd` because of worktrunk hooks (`post-start`
  copies gitignored content like `.superpowers/`, `.autonomo/`,
  `.claude/settings.local.json` into the worktree). Plain `cd` skips
  those.
- **Worktree, missing (orphaned)**:
  `wt switch --create <branch> && claude --resume <uuid>`. The script
  notes that this must run from inside the parent repo so `wt` knows
  which repo to recreate the worktree against. As long as the branch
  name is the same, the recreated worktree path encodes to the same
  slug, so Claude Code finds the existing session file.
- **Plain directory, missing**: no clean resume — the script flags
  this and prints the original cwd. Recovering would mean recreating
  that exact path or relocating the .jsonl into a new project's slug
  dir. Surface this as a caveat; don't bury it.

### Step 5: Worktrees aren't required

Everything above also works for plain-directory sessions. The skill
shouldn't push worktree workflows on a user who isn't using them. If
no `[wt]` markers appear in the listing, just present the `cd …`
resume commands. Likewise, if `wt` isn't installed and the user wants
to resume a worktree session, fall back to `cd <cwd> && claude
--resume <uuid>` — it'll work; it just skips the worktrunk hooks.

## Filters in detail

### `--dir <substring>`
Substring match against the original `cwd` (case-insensitive). Useful
because the cwd is the truth — encoded slug names are noisy.

### `--branch <substring>`
Matches against the git branch and the worktree name (the segment after
`/.claude/worktrees/` in the path). So `--branch autonomo` finds both
sessions on the `autonomo` branch and worktrees named `autonomo-eval`.

### `--keyword "<phrase>"`
Full-text scan of the JSONL bodies. Slower (reads every line of every
session) but catches things the metadata filters miss. The output adds
a "Keyword matches" section showing a snippet around each hit. Use
sparingly — for a focused dir/branch first, then keyword.

### `--since` / `--until`
Filter by file mtime (last activity). Accept `YYYY-MM-DD` or full ISO
timestamps. mtime is a good proxy for "when I was last in this
session" because every event appended to the JSONL bumps it.

### `--only-orphaned`
Only sessions whose original cwd no longer exists on disk. The
recovery candidates the user usually cares about.

### `--only-worktrees`
Only sessions whose cwd lives under `/.claude/worktrees/`.

### `--limit <N>`
Hard cap on rows in the table. Defaults to 50. The script reports
how many were truncated.

### `--format json`
Same data, machine-readable. Useful if the user wants to pipe through
`jq` or build a shell pipeline.

## Output style

Reproduce the script's output verbatim — don't reformat the table or
re-summarize the inspect view. The widths are tuned for terminal
display, and rewording loses signal (esp. the `[wt]` / `[orph]` /
`[missing]` markers).

If many sessions match, lead with the table, then offer to narrow:
"Want me to filter by branch, date, or content?" Don't paginate or
dump 1000 rows by default — `--limit 50` is usually plenty.

## Common patterns

**"What was I working on yesterday?"**

```bash
python3 <skill-dir>/scripts/list_sessions.py --since 2026-05-06 --until 2026-05-06
```

(Translate "yesterday" to today minus 1.)

**"Find the session about session-stats triggering."**

```bash
python3 <skill-dir>/scripts/list_sessions.py --keyword "session-stats triggering"
```

If no hits, broaden: drop a word, try synonyms (the user remembers the
gist, not their exact phrasing).

**"I removed the autonomo-eval-more worktree, can I get it back?"**

```bash
python3 <skill-dir>/scripts/list_sessions.py --only-orphaned --branch autonomo-eval-more
```

Then `--inspect <short-id>` to get the `wt switch --create` resume
command.

**"List the longest sessions in the gruppo repo."**

The script doesn't sort by size, but `--format json` + `jq` handles it:

```bash
python3 <skill-dir>/scripts/list_sessions.py --dir gruppo --format json \
  | jq 'sort_by(-.size_bytes) | .[:10]'
```

## Caveats

- **Session resume is path-pinned.** Claude Code finds session files
  by encoded cwd. If you `cd` to a different absolute path and run
  `claude --resume <uuid>`, it won't see the session. The resume
  commands the script generates respect this — don't rewrite them.
- **mtime ≠ start time.** "Age" in the table is "time since last
  event," which is what users usually want. To see a session's start,
  use `--inspect` (`first event`).
- **Tokens / cost are not in this skill.** Counting tokens requires
  parsing assistant message `usage` blocks; that's the
  `session-stats` skill's job. This skill stops at message counts.
- **JSONL format may evolve.** Event types and field names are stable
  in current Claude Code (2.x), but if a future version moves things,
  the script will silently miss the new fields. The script is
  defensive — unknown event types are ignored, missing fields fall
  back to None — so listings keep working at reduced fidelity.
