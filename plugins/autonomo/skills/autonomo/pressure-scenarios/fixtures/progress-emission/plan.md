# Plan: Add five string utility functions to lib/strutil.js

Each task adds one exported function to `lib/strutil.js`, with a corresponding test in `test/strutil.test.js`. Tasks are independent and can be implemented in order.

## Task 1: Add `reverse(s)` returning the reversed string

Implement `reverse(s)` in `lib/strutil.js` that returns the input string with characters reversed. Add a test in `test/strutil.test.js` asserting `reverse("abc") === "cba"`.

## Task 2: Add `capitalize(s)` returning the string with the first letter uppercased

Implement `capitalize(s)` in `lib/strutil.js` that returns the input with its first character uppercased and the rest unchanged. Add a test asserting `capitalize("hello") === "Hello"`.

## Task 3: Add `truncate(s, n)` returning the string truncated to n chars

Implement `truncate(s, n)` in `lib/strutil.js` that returns `s` if `s.length <= n`, else the first `n` characters. Add a test asserting `truncate("abcdef", 3) === "abc"`.

## Task 4: Add `repeat(s, n)` returning the string repeated n times

Implement `repeat(s, n)` in `lib/strutil.js` that returns `s` concatenated with itself `n` times. Add a test asserting `repeat("ab", 3) === "ababab"`.

## Task 5: Add `countWords(s)` returning the number of whitespace-separated tokens

Implement `countWords(s)` in `lib/strutil.js` that splits on whitespace and returns the count of non-empty tokens. Add a test asserting `countWords("one two three") === 3`.
