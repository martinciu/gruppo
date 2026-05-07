#!/usr/bin/env python3
"""List, search, and inspect stored Claude Code sessions.

Sessions are JSONL files at ~/.claude/projects/<encoded-cwd>/<session-uuid>.jsonl.
Each line is a structured event (user, assistant, system, last-prompt, etc.).
The original cwd and git branch are preserved on every user/assistant event,
so we can recover them without decoding the directory name.

Default output is a compact table sorted by recency. Filters can be combined.
For one session, --inspect prints full detail plus a resume command tailored
to whether the original path is a worktree, a plain directory, or orphaned.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

PROJECTS_DIR = Path.home() / ".claude" / "projects"
WORKTREE_RE = re.compile(r"/\.claude/worktrees/([^/]+)(?:/|$)")


@dataclass
class Session:
    session_id: str
    path: Path
    mtime: float
    size_bytes: int
    cwd: str | None = None
    git_branch: str | None = None
    first_user_prompt: str | None = None
    last_prompt: str | None = None
    away_summary: str | None = None
    user_msg_count: int = 0
    assistant_msg_count: int = 0
    first_event_ts: str | None = None
    last_event_ts: str | None = None
    version: str | None = None
    keyword_hit: str | None = None  # populated when --keyword matches

    @property
    def short_id(self) -> str:
        return self.session_id[:8]

    @property
    def is_worktree(self) -> bool:
        return bool(self.cwd and WORKTREE_RE.search(self.cwd))

    @property
    def worktree_branch(self) -> str | None:
        if not self.cwd:
            return None
        m = WORKTREE_RE.search(self.cwd)
        return m.group(1) if m else None

    @property
    def cwd_exists(self) -> bool:
        return bool(self.cwd) and Path(self.cwd).is_dir()

    @property
    def is_orphaned(self) -> bool:
        # A session is orphaned when its original cwd no longer exists.
        # Most relevant for worktree sessions, but also catches plain dirs
        # the user has since deleted.
        return bool(self.cwd) and not self.cwd_exists

    @property
    def total_messages(self) -> int:
        return self.user_msg_count + self.assistant_msg_count


def parse_session(path: Path, scan_keyword: str | None = None) -> Session | None:
    """Read a session jsonl and extract metadata.

    Reads the whole file because user_msg_count and away_summary need full
    enumeration. Files are typically small (< 5 MB); the cost is negligible
    for listing a few hundred sessions.
    """
    try:
        stat = path.stat()
    except OSError:
        return None

    sess = Session(
        session_id=path.stem,
        path=path,
        mtime=stat.st_mtime,
        size_bytes=stat.st_size,
    )

    keyword_lower = scan_keyword.lower() if scan_keyword else None

    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue

                t = ev.get("type")
                ts = ev.get("timestamp")
                if ts:
                    if not sess.first_event_ts:
                        sess.first_event_ts = ts
                    sess.last_event_ts = ts

                if not sess.cwd and ev.get("cwd"):
                    sess.cwd = ev["cwd"]
                if not sess.git_branch and ev.get("gitBranch"):
                    sess.git_branch = ev["gitBranch"]
                if not sess.version and ev.get("version"):
                    sess.version = ev["version"]

                if t == "user":
                    sess.user_msg_count += 1
                    msg = ev.get("message", {})
                    content = msg.get("content")
                    if sess.first_user_prompt is None and isinstance(content, str):
                        sess.first_user_prompt = content
                elif t == "assistant":
                    sess.assistant_msg_count += 1
                elif t == "last-prompt":
                    lp = ev.get("lastPrompt")
                    if isinstance(lp, str):
                        sess.last_prompt = lp
                elif t == "system":
                    if ev.get("subtype") == "away_summary":
                        c = ev.get("content")
                        if isinstance(c, str):
                            sess.away_summary = c

                if keyword_lower and not sess.keyword_hit:
                    if keyword_lower in line.lower():
                        # Extract a short snippet around the hit for context.
                        idx = line.lower().find(keyword_lower)
                        start = max(0, idx - 40)
                        end = min(len(line), idx + len(keyword_lower) + 40)
                        sess.keyword_hit = line[start:end]
    except OSError:
        return None

    return sess


def discover_sessions() -> Iterator[Path]:
    if not PROJECTS_DIR.is_dir():
        return iter([])
    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl in project_dir.glob("*.jsonl"):
            yield jsonl


def parse_date(s: str) -> datetime:
    """Accept YYYY-MM-DD or full ISO timestamp."""
    s = s.strip()
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise SystemExit(f"Invalid date: {s!r} ({e})")


def humanize_age(mtime: float, now: float) -> str:
    delta = max(0.0, now - mtime)
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta / 60)}m ago"
    if delta < 86400:
        return f"{int(delta / 3600)}h ago"
    if delta < 86400 * 30:
        return f"{int(delta / 86400)}d ago"
    if delta < 86400 * 365:
        return f"{int(delta / (86400 * 30))}mo ago"
    return f"{int(delta / (86400 * 365))}y ago"


def humanize_size(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f}K"
    return f"{n / (1024 * 1024):.1f}M"


def shorten_dir(cwd: str | None) -> str:
    if not cwd:
        return "?"
    home = str(Path.home())
    if cwd.startswith(home):
        cwd = "~" + cwd[len(home):]
    return cwd


def location_label(sess: Session) -> str:
    """Compact 'where was this' label for the table."""
    if not sess.cwd:
        return "?"
    cwd = shorten_dir(sess.cwd)
    branch = sess.git_branch or ""
    if sess.is_worktree:
        m = WORKTREE_RE.search(cwd)
        if m:
            repo = cwd[: m.start()]
            repo_name = Path(repo).name or repo
            tag = "[orph]" if sess.is_orphaned else "[wt]"
            return f"{repo_name}:{sess.worktree_branch} {tag}"
    label = cwd
    if branch and branch != "HEAD":
        label = f"{label} ({branch})"
    if sess.is_orphaned:
        label = f"{label} [missing]"
    return label


def truncate(s: str | None, n: int) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def filter_session(
    sess: Session,
    *,
    dir_query: str | None,
    branch_query: str | None,
    keyword: str | None,
    since: datetime | None,
    until: datetime | None,
    only_orphaned: bool,
    only_worktrees: bool,
) -> bool:
    if dir_query and (not sess.cwd or dir_query.lower() not in sess.cwd.lower()):
        return False
    if branch_query:
        b = (sess.git_branch or "") + " " + (sess.worktree_branch or "")
        if branch_query.lower() not in b.lower():
            return False
    if keyword and not sess.keyword_hit:
        return False
    if since or until:
        when = datetime.fromtimestamp(sess.mtime, tz=timezone.utc)
        if since and when < since:
            return False
        if until and when > until:
            return False
    if only_orphaned and not sess.is_orphaned:
        return False
    if only_worktrees and not sess.is_worktree:
        return False
    return True


def render_table(sessions: list[Session], limit: int, show_keyword_hits: bool) -> str:
    now = datetime.now().timestamp()
    rows = []
    rows.append(("ID", "AGE", "WHERE", "MSGS", "SIZE", "PROMPT"))
    for s in sessions[:limit]:
        prompt = s.last_prompt or s.first_user_prompt or s.away_summary or ""
        rows.append(
            (
                s.short_id,
                humanize_age(s.mtime, now),
                truncate(location_label(s), 44),
                str(s.total_messages),
                humanize_size(s.size_bytes),
                truncate(prompt, 60),
            )
        )

    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    out_lines = []
    for i, r in enumerate(rows):
        line = "  ".join(str(r[j]).ljust(widths[j]) for j in range(len(r)))
        out_lines.append(line.rstrip())
        if i == 0:
            out_lines.append("  ".join("-" * widths[j] for j in range(len(r))))

    if show_keyword_hits:
        out_lines.append("")
        out_lines.append("Keyword matches:")
        for s in sessions[:limit]:
            if s.keyword_hit:
                out_lines.append(f"  {s.short_id}  …{s.keyword_hit.strip()}…")

    if len(sessions) > limit:
        out_lines.append("")
        out_lines.append(f"({len(sessions) - limit} more — pass --limit {len(sessions)} to see all)")

    return "\n".join(out_lines)


def render_json(sessions: list[Session], limit: int) -> str:
    out = []
    for s in sessions[:limit]:
        out.append(
            {
                "session_id": s.session_id,
                "short_id": s.short_id,
                "path": str(s.path),
                "mtime": datetime.fromtimestamp(s.mtime, tz=timezone.utc).isoformat(),
                "size_bytes": s.size_bytes,
                "cwd": s.cwd,
                "git_branch": s.git_branch,
                "is_worktree": s.is_worktree,
                "worktree_branch": s.worktree_branch,
                "is_orphaned": s.is_orphaned,
                "user_msg_count": s.user_msg_count,
                "assistant_msg_count": s.assistant_msg_count,
                "first_event_ts": s.first_event_ts,
                "last_event_ts": s.last_event_ts,
                "first_user_prompt": s.first_user_prompt,
                "last_prompt": s.last_prompt,
                "away_summary": s.away_summary,
                "version": s.version,
                "keyword_hit": s.keyword_hit,
            }
        )
    return json.dumps(out, indent=2, ensure_ascii=False)


def resume_command(sess: Session) -> tuple[str, list[str]]:
    """Return (command, notes). Command is the suggested shell to run.

    Three cases:
      1. Plain dir, exists  → `cd <cwd> && claude --resume <uuid>`
      2. Worktree, exists   → `wt switch <branch> && claude --resume <uuid>`
         (wt switch is preferred over cd because of worktrunk hooks.)
      3. Worktree, gone (orphaned) → `wt switch --create <branch> && claude --resume <uuid>`
         Note: requires running from inside the parent repo so wt knows
         which repo to add the worktree to. The branch must still exist
         in git history (or wt will create it from the default base).
      4. Plain dir, gone → no clean resume. Surface the issue.
    """
    notes: list[str] = []
    uuid = sess.session_id

    if sess.is_worktree:
        branch = sess.worktree_branch or sess.git_branch or "<branch>"
        if sess.cwd_exists:
            cmd = f"wt switch {branch} && claude --resume {uuid}"
        else:
            cmd = f"wt switch --create {branch} && claude --resume {uuid}"
            notes.append(
                "Worktree directory is missing. `wt switch --create` recreates "
                "it at the same path so the session can resume. Run from inside "
                "the parent repo (the original repo this worktree was attached to)."
            )
            if sess.cwd:
                # Help the user identify the parent repo.
                m = WORKTREE_RE.search(sess.cwd)
                if m:
                    parent = sess.cwd[: m.start()]
                    notes.append(f"Parent repo path: {parent}")
        return cmd, notes

    # Plain (non-worktree) directory
    if sess.cwd_exists:
        return f"cd {sess.cwd!r} && claude --resume {uuid}", notes

    notes.append(
        "Original directory no longer exists. Claude Code resolves session "
        "files by encoded cwd path, so resuming requires recreating that "
        "exact path or copying the .jsonl into the new project's slug dir."
    )
    notes.append(f"Original cwd: {sess.cwd}")
    return f"# original dir missing\nclaude --resume {uuid}  # may not find session", notes


def render_inspect(sess: Session) -> str:
    out = []
    out.append(f"Session {sess.session_id}")
    out.append(f"  short id      {sess.short_id}")
    out.append(f"  file          {sess.path}")
    out.append(f"  size          {humanize_size(sess.size_bytes)}  ({sess.size_bytes} bytes)")
    out.append(f"  cwd           {sess.cwd or '?'}")
    if sess.is_worktree:
        flag = "[orphaned — directory missing]" if sess.is_orphaned else "[exists]"
        out.append(f"  worktree      {sess.worktree_branch}  {flag}")
    elif sess.is_orphaned:
        out.append(f"  status        [orphaned — directory missing]")
    out.append(f"  git branch    {sess.git_branch or '?'}")
    out.append(f"  version       {sess.version or '?'}")
    out.append(f"  first event   {sess.first_event_ts or '?'}")
    out.append(f"  last event    {sess.last_event_ts or '?'}")
    out.append(f"  user msgs     {sess.user_msg_count}")
    out.append(f"  asst msgs     {sess.assistant_msg_count}")
    if sess.first_user_prompt:
        out.append("")
        out.append("First user prompt:")
        out.append("  " + truncate(sess.first_user_prompt, 400))
    if sess.last_prompt and sess.last_prompt != sess.first_user_prompt:
        out.append("")
        out.append("Last user prompt:")
        out.append("  " + truncate(sess.last_prompt, 400))
    if sess.away_summary:
        out.append("")
        out.append("Away summary:")
        out.append("  " + truncate(sess.away_summary, 400))

    cmd, notes = resume_command(sess)
    out.append("")
    out.append("Resume command:")
    out.append(f"  {cmd}")
    for n in notes:
        out.append(f"  note: {n}")
    return "\n".join(out)


def find_by_short_id(sessions: list[Session], q: str) -> Session | None:
    q = q.lower()
    matches = [s for s in sessions if s.session_id.lower().startswith(q)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        ids = ", ".join(s.short_id for s in matches[:6])
        raise SystemExit(f"Ambiguous id {q!r}: matches {ids}…  Use a longer prefix.")
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dir", dest="dir_query", help="Substring match on original cwd")
    p.add_argument("--branch", help="Substring match on git branch or worktree name")
    p.add_argument("--keyword", help="Full-text search across session JSONL (slower)")
    p.add_argument("--since", help="Only sessions modified on/after this date (YYYY-MM-DD or ISO)")
    p.add_argument("--until", help="Only sessions modified on/before this date (YYYY-MM-DD or ISO)")
    p.add_argument("--only-orphaned", action="store_true", help="Only show sessions whose cwd no longer exists")
    p.add_argument("--only-worktrees", action="store_true", help="Only show worktree sessions")
    p.add_argument("--limit", type=int, default=50, help="Max rows to show in table (default 50)")
    p.add_argument("--format", choices=["table", "json"], default="table")
    p.add_argument("--inspect", help="Show full detail + resume command for one session (id or short id)")
    args = p.parse_args(argv)

    since = parse_date(args.since) if args.since else None
    until = parse_date(args.until) if args.until else None
    # Date-only --until should cover the whole day, not just midnight.
    # Otherwise `--until 2026-05-06` excludes everything after 00:00:00 UTC
    # that day, which is almost always wrong for "yesterday"-style queries.
    if until and "T" not in args.until:
        until = until.replace(hour=23, minute=59, second=59, microsecond=999999)

    sessions: list[Session] = []
    for path in discover_sessions():
        s = parse_session(path, scan_keyword=args.keyword)
        if s is not None:
            sessions.append(s)
    sessions.sort(key=lambda s: s.mtime, reverse=True)

    if args.inspect:
        match = find_by_short_id(sessions, args.inspect)
        if not match:
            print(f"No session matches {args.inspect!r}.", file=sys.stderr)
            return 1
        print(render_inspect(match))
        return 0

    filtered = [
        s
        for s in sessions
        if filter_session(
            s,
            dir_query=args.dir_query,
            branch_query=args.branch,
            keyword=args.keyword,
            since=since,
            until=until,
            only_orphaned=args.only_orphaned,
            only_worktrees=args.only_worktrees,
        )
    ]

    if args.format == "json":
        print(render_json(filtered, args.limit))
    else:
        if not filtered:
            print("No sessions matched.")
            return 0
        print(render_table(filtered, args.limit, show_keyword_hits=bool(args.keyword)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
