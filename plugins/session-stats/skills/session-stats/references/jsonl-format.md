# Claude Code session JSONL on-disk format

`aggregate.py` already knows this layout — read this file only if the script
breaks because Claude Code changed the schema, or if you need to extract
something the script doesn't surface.

## Paths

Each session writes a JSONL transcript to:

```
~/.claude/projects/<slug>/<session-id>.jsonl
```

`<slug>` is the session's working directory with `/` and `.` replaced by `-`
(e.g. `/Users/me/code/foo` → `-Users-me-code-foo`,
`/Users/me/code/foo/.git` → `-Users-me-code-foo--git`).

Subagent transcripts (when the session dispatched any) live at:

```
~/.claude/projects/<slug>/<session-id>/subagents/agent-*.jsonl
```

Per-agent metadata sits next to each `agent-<id>.jsonl` as
`agent-<id>.meta.json` — useful for mapping an agent ID back to the task
the controller dispatched it for.

## Record shape

Each line is a JSON object. Relevant types:

- `type: "assistant"` — has `message.model`, `message.usage`, `timestamp`.
- `type: "user"` — has `message.content` (string or list of blocks). When the
  list contains only `tool_result` blocks, the record is synthetic (Claude
  Code feeding tool output back in), not a real user turn.

`message.usage` carries:

- `input_tokens`, `output_tokens`, `cache_read_input_tokens`
- `cache_creation` object split by TTL into `ephemeral_5m_input_tokens` and
  `ephemeral_1h_input_tokens`
- Older records may use the flat `cache_creation_input_tokens` field instead
  of the breakdown.

`timestamp` is ISO-8601. First/last timestamps across the controller plus
all subagents give the wall-clock elapsed time.

## Working-time computation gotchas

`aggregate.py`'s working-time calculation has two filters worth knowing
about if you're debugging a suspiciously low number:

- **Synthetic user records.** `type: "user"` records whose `message.content`
  is a list of only `tool_result` blocks are produced by Claude Code, not
  the human — they must not close a turn. The `is_real_user_message`
  helper filters them out. If Claude Code evolves the structure, this
  filter is the first thing to check.
- **Open turn at EOF.** If the session was killed before the last turn's
  assistant reply, that turn contributes 0 to working time — runtime past
  the last observable timestamp is unobservable.
