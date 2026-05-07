# gruppo

A coordinated set of Claude Code plugins — skills, hooks, and helpers
that I use day-to-day. Install one, all, or none.

## Install

    /plugin marketplace add martinciu/gruppo
    /plugin install <plugin-name>

## Plugins

| Plugin          | What it does                                              |
|-----------------|-----------------------------------------------------------|
| session-stats   | Token usage, cost, runtime, per-model breakdown           |
| autonomo        | Turn a freeform task description into a PR unattended via superpowers |
| session-finder  | Find and recover past sessions; produces the right resume command incl. worktree restore |

## Development

Plugins in this repo are authored as plain files (Markdown skills,
JSON manifests, occasional shell scripts). To work on one with live
reload, symlink it into your user-global skills directory:

    git clone https://github.com/martinciu/gruppo ~/code/gruppo

    ln -s ~/code/gruppo/plugins/session-stats/skills/session-stats \
          ~/.claude/skills/session-stats

Edits in the repo are picked up immediately — Claude Code loads the
skill via the user-global path. No install step, no reload.

To verify the **plugin install path** (what consumers see) before
publishing a change, register the working tree as a local marketplace:

    /plugin marketplace add ~/code/gruppo
    /plugin install <plugin-name>

After verification, remove it: `/plugin marketplace remove gruppo`.

## License

MIT
