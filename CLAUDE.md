# gruppo — Claude Code instructions

A marketplace repo. Each plugin under `plugins/<name>/` is self-contained.

## Conventions

- One plugin per theme. Don't bundle unrelated skills into a single plugin.
- Each plugin has its own `.claude-plugin/plugin.json` with a semver `version`.
  Bump on meaningful changes (skill content, shipped scripts). No bump for
  typos or README tweaks.
- No `bootstrap.sh` or install scripts in this repo — it's a publishable
  artifact, not personal infrastructure. Symlinks for live editing are
  handled by the developer manually.
- Dev edits go to the working tree. Never edit the cached marketplace copy
  at `~/.claude/plugins/marketplaces/gruppo/`.

## Plugin anatomy

Each plugin lives under `plugins/<name>/` with this structure:

```
plugins/<name>/
  .claude-plugin/plugin.json      # manifest (name, version, skills, commands, …)
  skills/<skill-name>/
    SKILL.md                      # skill content loaded by Claude Code
    references/                   # supporting docs referenced from SKILL.md
    scripts/                      # shell helpers invoked by the skill
    evals/                        # trigger JSONs + grading scripts for skill evals
    <skill-name>-workspace/       # eval run output (gitignored via plugins/*/skills/*-workspace/)
```

Minimal `plugin.json`:

```json
{
  "name": "my-plugin",
  "version": "0.1.0",
  "description": "One line.",
  "author": { "name": "martinciu", "email": "marcin.ciunelis@gmail.com" },
  "skills": ["./skills/my-skill"]
}
```

Supported manifest fields beyond `skills`: `commands`, `hooks`, `agents`.

## Adding a new plugin

1. Create `plugins/<name>/.claude-plugin/plugin.json` and content folders
   (`skills/`, `hooks/`, `agents/` as appropriate).
2. Add an entry to `.claude-plugin/marketplace.json`'s `plugins` array.
3. Add a row to the README's plugin table.
4. Open a PR. Never push to `main` directly.

## Commands

`.claude/commands/mc/` holds personal slash commands that are not shipped
with any plugin. They live here so they can be version-controlled and
symlinked from `~/.claude/commands/mc`. When adding a command:

- Drop the `.md` file into `.claude/commands/mc/` (or a subdirectory).
- Commands here are personal workflow helpers — keep them superpowers-skill
  agnostic where possible so they work across repos.
- Update the Commands table in README.md.
