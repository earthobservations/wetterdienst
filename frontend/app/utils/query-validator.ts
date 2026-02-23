/**
 * Query validation utility for DuckDB SQL queries
 * Ensures only safe SELECT queries are executed
 */

export interface QueryValidationResult {
  valid: boolean
  error?: string
  warning?: string
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
      error: 'Query cannot be empty',
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
      error: 'Only SELECT queries are allowed. Query must start with SELECT or WITH.',
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
        error: `Query contains disallowed operation: ${pattern.source.replace(/\\b/g, '')}`,
      }
    }
  }

  // Warning for queries without LIMIT
  if (!normalizedQuery.includes('LIMIT')) {
    return {
      valid: true,
      warning: 'Query does not contain a LIMIT clause. Large result sets may impact performance.',
    }
  }

  return {
    valid: true,
  }
}

/**
 * Validates that query results have the expected columns
 */
export function validateColumns(
  resultColumns: string[],
  expectedColumns: string[],
): { valid: boolean, message?: string } {
  if (resultColumns.length === 0) {
    return {
      valid: false,
      message: 'Query returned no columns',
    }
  }

  // Check if all expected columns are present
  const missingColumns = expectedColumns.filter(col => !resultColumns.includes(col))

  if (missingColumns.length > 0) {
    return {
      valid: false,
      message: `Query results are missing expected columns: ${missingColumns.join(', ')}. Expected columns: ${expectedColumns.join(', ')}`,
    }
  }

  // Check for extra columns (warning only)
  const extraColumns = resultColumns.filter(col => !expectedColumns.includes(col))
  if (extraColumns.length > 0) {
    return {
      valid: true,
      message: `Query results contain additional columns: ${extraColumns.join(', ')}`,
    }
  }

  return { valid: true }
}
