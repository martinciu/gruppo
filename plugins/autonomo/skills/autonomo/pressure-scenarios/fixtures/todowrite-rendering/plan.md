# Plan: Implement `wordcount` CLI command in `bin/tool.js`

Implements the spec at `spec.md`. Three sequential tasks: implement the function, register it as a command, add a happy-path test.

## Task 1: Implement `wordcountCmd(args)` in `bin/tool.js`

Add a new function `wordcountCmd(args)` to `bin/tool.js` (above the `commands` object). Behavior:

- If `args[0]` is missing, write `usage: tool wordcount <path>\n` to `process.stderr` and `process.exit(2)`.
- Otherwise, read the file with `fs.readFileSync(args[0], 'utf8')`. If it throws, write `error: <err.message>\n` to stderr and exit `1`.
- Split the content on `/\s+/`, filter out empty strings, count the result, and write `<n>\n` to stdout.

## Task 2: Register the `wordcount` command

In the `commands` object in `bin/tool.js`, add a `wordcount: wordcountCmd` entry alongside the existing `hello` entry.

## Task 3: Add a happy-path test

Add a test in `test/wordcount.test.js` that creates a temp file with `"one two three\n"`, runs `wordcountCmd(['<path>'])` (capturing stdout), and asserts the captured output is `"3\n"`. Use only `node:test` and `node:assert` — no external test runners.
