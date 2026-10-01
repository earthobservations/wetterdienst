/**
 * Query validation utility for DuckDB SQL queries
 * Ensures only safe SELECT queries are executed
 */

export interface QueryValidationResult {
  valid: boolean
  /** i18n key for an error message, translated at the display site. */
  errorKey?: string
  /** i18n key for a warning message, translated at the display site. */
  warningKey?: string
  /** Interpolation params for the error/warning message. */
  params?: Record<string, string>
  /**
   * The one statement a valid query holds, without the `;` and the comments after it, which DuckDB
   * runs as the query and can wrap in a subquery, its Unicode spaces turned plain as DuckDB turns
   * them. A text with a comment never closed is handed back whole, `;` included, for DuckDB to
   * refuse with its own error.
   */
  statement?: string
}

// How DuckDB's lexer reads a query (third_party/libpg_query/scan.l, as of DuckDB 1.5), as far as it
// tells where a statement ends and which bare words it holds, the keywords the checks look for: a
// `;` or a word counts outside strings, quoted identifiers and comments only, and where those start
// depends on the token before them, as `a1e'` is an identifier and a string but `1e'` a number and
// an escape string, and `a$x$` an identifier but `1$x$` a number and a dollar-quoted string.
const SPACE = /[ \t\n\r\f]/
// a line comment, which ends at a carriage return as at a newline
const LINE_COMMENT = /--[^\n\r]*/y
const IDENT_START = /[A-Z_\u0080-\uFFFF]/i
const IDENT = /[A-Z_\u0080-\uFFFF][\w$\u0080-\uFFFF]*/iy
const NUMBER = /(?:\d(?:_?\d)*(?:\.(?!\.)(?:\d(?:_?\d)*)?)?|\.\d(?:_?\d)*)(?:e[-+]?\d(?:_?\d)*)?/iy
const PARAM = /\$\d(?:_?\d)*/y
const DOLLAR_QUOTE = /\$(?:[A-Z_\u0080-\uFFFF][\w\u0080-\uFFFF]*)?\$/iy
// the rest of a string literal continued on a later line (`'a'\n'b'` is 'ab'), up to its next quote:
// spaces and comments with a newline among them, where a comment runs to the end of its line
const CONTINUATION = /[ \t\f]*(?:--[^\n\r]*)?[\n\r](?:[ \t\n\r\f]|--[^\n\r]*[\n\r])*'/y

function matchAt(pattern: RegExp, text: string, at: number): string | undefined {
  pattern.lastIndex = at
  return pattern.exec(text)?.[0]
}

// The end of the string literal whose opening quote is at `at`, where `escapes` lets a backslash
// escape the next character, as in E'...', throughout its continuations too
function stringEnd(text: string, at: number, escapes: boolean): number {
  let i = at + 1
  while (i < text.length) {
    if (escapes && text[i] === '\\') {
      i += 2
    }
    else if (text[i] !== '\'') {
      i++
    }
    else if (text[i + 1] === '\'') {
      i += 2
    }
    else {
      const continued = matchAt(CONTINUATION, text, i + 1)
      if (continued === undefined)
        return i + 1
      i += 1 + continued.length
    }
  }
  return text.length
}

// The end of the comment opened at `at`, which DuckDB lets nest, or -1 when it is never closed
function blockCommentEnd(text: string, at: number): number {
  let depth = 0
  let i = at + 2
  while (i < text.length) {
    if (text.startsWith('/*', i)) {
      depth++
      i += 2
    }
    else if (text.startsWith('*/', i)) {
      if (depth === 0)
        return i + 2
      depth--
      i += 2
    }
    else {
      i++
    }
  }
  return -1
}

function isDollarTagStart(byte: number): boolean {
  return (byte >= 0x41 && byte <= 0x5A) || (byte >= 0x61 && byte <= 0x7A) || byte === 0x5F || byte >= 0x80
}

function isDollarTagChar(byte: number): boolean {
  return isDollarTagStart(byte) || (byte >= 0x30 && byte <= 0x39)
}

function holdsAt(bytes: Uint8Array, at: number, part: Uint8Array): boolean {
  return part.every((byte, k) => bytes[at + k] === byte)
}

/**
 * The query as DuckDB's lexer gets it. Before it lexes a query, DuckDB turns the Unicode spaces
 * U+00A0, U+2000 to U+200B, U+202F, U+205F, U+2060, U+3000 and U+FEFF into plain ones
 * (Parser::StripUnicodeSpaces, src/parser/parser.cpp, as of DuckDB 1.5), outside what a reading of
 * its own takes for quoted text and line comments. That reading knows no block comment, escape
 * string or identifier, so a `'` in a comment, or the `$x$` of `a$x$`, opens a quote to it, and the
 * spaces up to that quote's end stay what they are, which the lexer then reads as a word's
 * characters. Ported as DuckDB runs it, on the text's UTF-8 bytes and with its bounds, so the same
 * spaces turn; each is one UTF-16 code unit, so a position in the text stays.
 */
function stripUnicodeSpaces(query: string): string {
  const bytes = new TextEncoder().encode(query)
  const size = bytes.length
  const spaces: { at: number, length: number }[] = []
  // where DuckDB's loops stand, each a state here; the bounds are its own
  let state: 'regular' | 'tag' | 'quote' | 'dollar' | 'comment' = 'regular'
  let quote = 0
  let tagStart = 0
  let tag = new Uint8Array()
  let pos = 0
  while (true) {
    if (state === 'regular') {
      if (pos + 2 >= size)
        break
      const [byte, next, after] = [bytes[pos]!, bytes[pos + 1]!, bytes[pos + 2]!]
      if (byte === 0xC2 && next === 0xA0) {
        spaces.push({ at: pos, length: 2 })
      }
      if (byte === 0xE2) {
        if ((next === 0x80 && ((after >= 0x80 && after <= 0x8B) || after === 0xAF))
          || (next === 0x81 && (after === 0x9F || after === 0xA0))) {
          spaces.push({ at: pos, length: 3 })
        }
      }
      else if (byte === 0xE3) {
        if (next === 0x80 && after === 0x80)
          spaces.push({ at: pos, length: 3 })
      }
      else if (byte === 0xEF) {
        if (next === 0xBB && after === 0xBF)
          spaces.push({ at: pos, length: 3 })
      }
      else if (byte === 0x22 || byte === 0x27) {
        quote = byte
        state = 'quote'
      }
      else if (byte === 0x24 && (next === 0x24 || isDollarTagStart(next))) {
        tagStart = pos + 1
        state = 'tag'
      }
      else if (byte === 0x2D && next === 0x2D) {
        state = 'comment'
        continue
      }
      pos++
    }
    else if (state === 'tag') {
      if (pos + 2 >= size)
        break
      if (bytes[pos] === 0x24) {
        tag = bytes.subarray(tagStart, pos)
        state = 'dollar'
      }
      // no tag after all: read on from this byte
      else if (!isDollarTagChar(bytes[pos]!)) {
        state = 'regular'
      }
      else {
        pos++
      }
    }
    else if (state === 'quote') {
      if (pos + 1 >= size)
        break
      if (bytes[pos] !== quote) {
        pos++
      }
      // a doubled quote is one
      else if (bytes[pos + 1] === quote) {
        pos += 2
      }
      else {
        pos++
        state = 'regular'
      }
    }
    else if (state === 'dollar') {
      // from the `$` that ends the opening tag, as DuckDB reads on
      if (pos + 2 >= size)
        break
      if (bytes[pos] === 0x24 && size - (pos + 1) >= tag.length + 1 && bytes[pos + tag.length + 1] === 0x24
        && holdsAt(bytes, pos + 1, tag)) {
        pos += tag.length + 1
        state = 'regular'
      }
      else {
        pos++
      }
    }
    else {
      if (pos >= size)
        break
      if (bytes[pos] === 0x0A || bytes[pos] === 0x0D)
        state = 'regular'
      else
        pos++
    }
  }
  if (spaces.length === 0)
    return query
  // each space starts and ends on a character's bytes, so the parts between decode apart
  const decoder = new TextDecoder()
  let stripped = ''
  let from = 0
  for (const { at, length } of spaces) {
    stripped += `${decoder.decode(bytes.subarray(from, at))} `
    from = at + length
  }
  return stripped + decoder.decode(bytes.subarray(from))
}

interface Token {
  /** a bare word, as a keyword or an identifier is, a `;`, or any other token */
  kind: 'word' | ';' | 'other'
  start: number
  end: number
}

/**
 * The query's tokens, as DuckDB reads them: a space or a comment is none, and a string or a quoted
 * identifier is one token, not a word, whatever it holds. A comment never closed, which DuckDB
 * refuses, ends the tokens and sets `unclosed`.
 */
function tokenize(query: string): { tokens: Token[], unclosed: boolean } {
  const tokens: Token[] = []
  let i = 0
  while (i < query.length) {
    const char = query[i]!
    if (SPACE.test(char)) {
      i++
      continue
    }
    if (query.startsWith('--', i)) {
      i += matchAt(LINE_COMMENT, query, i)!.length
      continue
    }
    if (query.startsWith('/*', i)) {
      i = blockCommentEnd(query, i)
      if (i === -1)
        return { tokens, unclosed: true }
      continue
    }
    // a token from here
    const start = i
    let kind: Token['kind'] = 'other'
    if (char === ';') {
      kind = ';'
      i++
    }
    else if (char === '\'') {
      i = stringEnd(query, i, false)
    }
    else if ((char === 'e' || char === 'E') && query[i + 1] === '\'') {
      i = stringEnd(query, i + 1, true)
    }
    else if (char === '"') {
      // a quoted identifier, where a doubled quote reads as its end and the next one's start,
      // which span the same text as the one identifier DuckDB reads
      const close = query.indexOf('"', i + 1)
      i = close === -1 ? query.length : close + 1
    }
    else if (IDENT_START.test(char)) {
      kind = 'word'
      i += matchAt(IDENT, query, i)!.length
    }
    else if (/\d/.test(char) || (char === '.' && /\d/.test(query[i + 1] ?? ''))) {
      i += matchAt(NUMBER, query, i)!.length
    }
    else if (char === '$') {
      const delimiter = matchAt(DOLLAR_QUOTE, query, i)
      if (delimiter !== undefined) {
        const close = query.indexOf(delimiter, i + delimiter.length)
        i = close === -1 ? query.length : close + delimiter.length
      }
      else {
        i += matchAt(PARAM, query, i)?.length ?? 1
      }
    }
    else {
      i++
    }
    tokens.push({ kind, start, end: i })
  }
  return { tokens, unclosed: false }
}

// Keywords of statements that change data, the schema or the database, which a query may not hold.
// Not REPLACE, which names the read-only replace() and SELECT * REPLACE (...): each statement it
// joins, CREATE OR REPLACE and INSERT OR REPLACE, is refused by its first keyword.
const DISALLOWED_KEYWORDS = new Set([
  'CREATE',
  'DROP',
  'ALTER',
  'TRUNCATE',
  'INSERT',
  'UPDATE',
  'DELETE',
  'MERGE',
  'ATTACH',
  'DETACH',
  'PRAGMA',
  'CALL',
  'EXECUTE',
  'EXEC',
  'GRANT',
  'REVOKE',
])

/**
 * Validates a SQL query to ensure it's safe to execute
 * - Only allows SELECT statements
 * - Prevents DDL operations (CREATE, DROP, ALTER, etc.)
 * - Prevents DML operations (INSERT, UPDATE, DELETE, etc.)
 * - Prevents system operations (ATTACH, DETACH, etc.)
 *
 * The checks read the query's tokens as DuckDB's lexer does, so a comment or a string hides no
 * keyword from them, nor does a keyword inside one trip them.
 */
export function validateQuery(query: string): QueryValidationResult {
  if (!query || query.trim().length === 0) {
    return {
      valid: false,
      errorKey: 'validation.queryEmpty',
    }
  }

  const text = stripUnicodeSpaces(query)
  const { tokens, unclosed } = tokenize(text)
  // a word upper-cased in ASCII only, as DuckDB matches its keywords: `ſelect` is no SELECT to it
  const wordOf = (token: Token) => text.slice(token.start, token.end).replace(/[a-z]+/g, ascii => ascii.toUpperCase())

  // no token at all, as DuckDB reads it: a nested comment can hide a SELECT
  if (tokens.length === 0 && !unclosed) {
    return {
      valid: false,
      errorKey: 'validation.queryEmpty',
    }
  }

  // Check if query starts with SELECT (or WITH for CTEs)
  const first = tokens[0]
  const firstWord = first?.kind === 'word' ? wordOf(first) : undefined
  if (firstWord !== 'SELECT' && firstWord !== 'WITH') {
    return {
      valid: false,
      errorKey: 'validation.onlySelect',
    }
  }

  // Check for dangerous keywords, outside strings, quoted identifiers and comments
  const words = tokens.filter(token => token.kind === 'word').map(wordOf)
  const disallowed = words.find(word => DISALLOWED_KEYWORDS.has(word))
  if (disallowed !== undefined) {
    return {
      valid: false,
      errorKey: 'validation.disallowedOperation',
      params: { op: disallowed },
    }
  }

  // One statement only: DuckDB-wasm runs each statement of a query, and the checks above take the
  // text for one, so `SELECT 1; SET threads = 1` changed a setting (GH-2139). An empty statement, as
  // a trailing `;` leaves, is none.
  const semicolon = tokens.findIndex(token => token.kind === ';')
  if (semicolon !== -1 && tokens.slice(semicolon).some(token => token.kind !== ';')) {
    return {
      valid: false,
      errorKey: 'validation.multipleStatements',
    }
  }
  // the first token is the SELECT or WITH, so the statement has one; a text with a comment never
  // closed is kept whole, so DuckDB's check tells why
  const last = semicolon === -1 ? tokens.at(-1)! : tokens[semicolon - 1]!
  const statement = unclosed ? text : text.slice(0, last.end)

  // Warning for queries without LIMIT
  if (!words.includes('LIMIT')) {
    return {
      valid: true,
      warningKey: 'validation.noLimit',
      statement,
    }
  }

  return {
    valid: true,
    statement,
  }
}

/**
 * Validates that query results have the expected columns
 */
export function validateColumns(
  resultColumns: string[],
  expectedColumns: string[],
): { valid: boolean, messageKey?: string, params?: Record<string, string> } {
  if (resultColumns.length === 0) {
    return {
      valid: false,
      messageKey: 'validation.noColumns',
    }
  }

  // Check if all expected columns are present
  const missingColumns = expectedColumns.filter(col => !resultColumns.includes(col))

  if (missingColumns.length > 0) {
    return {
      valid: false,
      messageKey: 'validation.missingColumns',
      params: { missing: missingColumns.join(', '), expected: expectedColumns.join(', ') },
    }
  }

  // Check for extra columns (warning only)
  const extraColumns = resultColumns.filter(col => !expectedColumns.includes(col))
  if (extraColumns.length > 0) {
    return {
      valid: true,
      messageKey: 'validation.extraColumns',
      params: { extra: extraColumns.join(', ') },
    }
  }

  return { valid: true }
}
