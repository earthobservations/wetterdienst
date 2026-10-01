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
   * runs as the query and can wrap in a subquery. A text with a comment never closed is handed back
   * whole, `;` included, for DuckDB to refuse with its own error.
   */
  statement?: string
}

// How DuckDB's lexer reads a query (third_party/libpg_query/scan.l, as of DuckDB 1.5), as far as it
// tells where a statement ends: a `;` counts outside strings, quoted identifiers and comments only,
// and where those start depends on the token before them, as `a1e'` is an identifier and a string
// but `1e'` a number and an escape string, and `a$x$` an identifier but `1$x$` a number and a
// dollar-quoted string.
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

/**
 * Where the query's first statement ends, and whether a statement follows it. DuckDB-wasm runs
 * every statement of a query, so a text of several would run the ones after the first unchecked.
 * An empty statement, as a trailing `;` leaves, is none.
 */
function firstStatement(query: string): { end: number, more: boolean } {
  let end = 0
  let ended = false
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
      // a comment never closed, which DuckDB refuses: the statement keeps it, so the check tells why
      if (i === -1)
        return { end: query.length, more: false }
      continue
    }
    // a token from here
    if (char === ';') {
      ended = true
      i++
      continue
    }
    if (ended)
      return { end, more: true }
    if (char === '\'') {
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
    end = i
  }
  return { end, more: false }
}

/**
 * Validates a SQL query to ensure it's safe to execute
 * - Only allows SELECT statements
 * - Prevents DDL operations (CREATE, DROP, ALTER, etc.)
 * - Prevents DML operations (INSERT, UPDATE, DELETE, etc.)
 * - Prevents system operations (ATTACH, DETACH, etc.)
 */
export function validateQuery(query: string): QueryValidationResult {
  if (!query || query.trim().length === 0) {
    return {
      valid: false,
      errorKey: 'validation.queryEmpty',
    }
  }

  const normalizedQuery = query.trim().toUpperCase()

  // Remove comments (both single-line and multi-line)
  const withoutComments = normalizedQuery
    .replace(/--[^\n]*/g, '') // Remove single-line comments
    .replace(/\/\*[\s\S]*?\*\//g, '') // Remove multi-line comments
    .trim()

  // Check if query starts with SELECT (or WITH for CTEs)
  if (!withoutComments.startsWith('SELECT') && !withoutComments.startsWith('WITH')) {
    return {
      valid: false,
      errorKey: 'validation.onlySelect',
    }
  }

  // List of dangerous keywords that should not appear in the query
  const dangerousKeywords = [
    'CREATE',
    'DROP',
    'ALTER',
    'TRUNCATE',
    'INSERT',
    'UPDATE',
    'DELETE',
    'REPLACE',
    'MERGE',
    'ATTACH',
    'DETACH',
    'PRAGMA',
    'CALL',
    'EXECUTE',
    'EXEC',
    'GRANT',
    'REVOKE',
  ]

  // Check for dangerous keywords (but allow them in string literals)
  const dangerouskeywordPatterns = dangerousKeywords.map(
    kw => new RegExp(`\\b${kw}\\b`, 'i'),
  )

  for (const pattern of dangerouskeywordPatterns) {
    if (pattern.test(withoutComments)) {
      return {
        valid: false,
        errorKey: 'validation.disallowedOperation',
        params: { op: pattern.source.replace(/\\b/g, '') },
      }
    }
  }

  // One statement only: DuckDB-wasm runs each statement of a query, and the checks above take the
  // text for one, so `SELECT 1; SET threads = 1` changed a setting (GH-2139)
  const { end, more } = firstStatement(query)
  if (more) {
    return {
      valid: false,
      errorKey: 'validation.multipleStatements',
    }
  }
  const statement = query.slice(0, end)

  // Warning for queries without LIMIT
  if (!normalizedQuery.includes('LIMIT')) {
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
