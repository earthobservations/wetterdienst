// Data as the text of a JavaScript module, for the search index's virtual modules (GH-4340). Nothing here builds code from
// data by hand: the data is written as JSON, which is a string literal's text, and the characters that a literal or a page
// that embeds the module could misread are written as `\uXXXX` escapes, which the literal evaluates back to the same
// characters. `JSON.stringify` already escapes quotes, backslashes and control characters; it leaves `<`, `>`, `&`, `/`
// and the two line separators U+2028 and U+2029 as they are, and those are the ones escaped here (`</script>` and `<!--`
// would end or open a script element, and the separators ended a string literal before ES2019).
const UNSAFE = /[<>&/\u2028\u2029]/g

function escapeUnsafe(text: string): string {
  return text.replace(UNSAFE, character => `\\u${character.charCodeAt(0).toString(16).padStart(4, '0')}`)
}

/** `value` as a JavaScript expression that evaluates to the same data. */
export function toJsLiteral(value: unknown): string {
  return escapeUnsafe(JSON.stringify(value))
}

/**
 * `value` as an expression that is `JSON.parse` of a string, which the engine reads faster than the same data as a
 * literal of that size.
 */
export function toJsonParseExpression(value: unknown): string {
  return `JSON.parse(${escapeUnsafe(JSON.stringify(JSON.stringify(value)))})`
}
