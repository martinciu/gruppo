# Spec: `wordcount` CLI command

Add a new subcommand `wordcount` to `bin/tool.js` that prints the number of whitespace-separated words in a given file to stdout.

## Interface

```
$ node bin/tool.js wordcount path/to/file.txt
42
```

- Single positional argument: file path.
- Reads the file synchronously with `fs.readFileSync(path, 'utf8')`.
- Splits the content on whitespace (`\s+`), filters out empty tokens, prints the count to stdout followed by a newline.
- Exits with code `0` on success.

## Errors

- If the path argument is missing, print `usage: tool wordcount <path>` to stderr and exit with code `2`.
- If the file does not exist or cannot be read, print `error: <message>` to stderr and exit with code `1`.

## Registration

The existing `bin/tool.js` registers commands in a `commands` object:

```js
const commands = {
  hello: helloCmd,
  // ...
};
```

Add `wordcount: wordcountCmd` to this object. Implement `wordcountCmd(args)` in the same file (no separate module).

## Out of scope

- Internationalization / locale-aware tokenization.
- Streaming for large files.
- Glob expansion or multiple file paths.
