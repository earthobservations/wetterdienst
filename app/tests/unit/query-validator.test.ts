import type { DuckDBConnection } from '@duckdb/duckdb-wasm/blocking'
import { beforeAll, describe, expect, it } from 'vitest'
import { validateColumns, validateQuery } from '../../app/utils/query-validator'
import { nodeDuckDB } from '../duckdb-node'

describe('query-validator', () => {
  describe('validateQuery', () => {
    it('should accept valid SELECT query', () => {
      const result = validateQuery('SELECT * FROM data LIMIT 100')
      expect(result.valid).toBe(true)
      expect(result.errorKey).toBeUndefined()
    })

    it('should accept SELECT query with WHERE clause', () => {
      const result = validateQuery('SELECT station_id, value FROM data WHERE value > 10 LIMIT 50')
      expect(result.valid).toBe(true)
    })

    it('should accept CTE queries with WITH', () => {
      const result = validateQuery('WITH filtered AS (SELECT * FROM data WHERE value > 0) SELECT * FROM filtered LIMIT 100')
      expect(result.valid).toBe(true)
    })

    it('should reject empty query', () => {
      const result = validateQuery('')
      expect(result.valid).toBe(false)
      expect(result.errorKey).toBe('validation.queryEmpty')
    })

    it('should reject INSERT queries', () => {
      const result = validateQuery('INSERT INTO data VALUES (1, 2, 3)')
      expect(result.valid).toBe(false)
      // INSERT does not start with SELECT/WITH, so it is rejected up front.
      expect(result.errorKey).toBe('validation.onlySelect')
    })

    it('should reject UPDATE queries', () => {
      const result = validateQuery('UPDATE data SET value = 0')
      expect(result.valid).toBe(false)
      expect(result.errorKey).toBeDefined()
    })

    it('should reject DELETE queries', () => {
      const result = validateQuery('DELETE FROM data')
      expect(result.valid).toBe(false)
      expect(result.errorKey).toBeDefined()
    })

    it('should reject DROP queries', () => {
      const result = validateQuery('DROP TABLE data')
      expect(result.valid).toBe(false)
      expect(result.errorKey).toBeDefined()
    })

    it('should reject CREATE queries', () => {
      const result = validateQuery('CREATE TABLE test (id INT)')
      expect(result.valid).toBe(false)
      expect(result.errorKey).toBeDefined()
    })

    it('should flag dangerous keywords with the operation name', () => {
      const result = validateQuery('SELECT * FROM data; DROP TABLE data')
      expect(result.valid).toBe(false)
      expect(result.errorKey).toBe('validation.disallowedOperation')
      expect(result.params?.op).toBe('DROP')
    })

    it('should warn about missing LIMIT', () => {
      const result = validateQuery('SELECT * FROM data')
      expect(result.valid).toBe(true)
      expect(result.warningKey).toBe('validation.noLimit')
    })

    it('should handle queries with comments', () => {
      const result = validateQuery('-- This is a comment\nSELECT * FROM data LIMIT 100')
      expect(result.valid).toBe(true)
    })

    it('should handle queries with multi-line comments', () => {
      const result = validateQuery('/* Multi-line\ncomment */\nSELECT * FROM data LIMIT 100')
      expect(result.valid).toBe(true)
    })
  })

  describe('validateColumns', () => {
    it('should accept matching columns', () => {
      const result = validateColumns(
        ['station_id', 'value', 'timestamp'],
        ['station_id', 'value', 'timestamp'],
      )
      expect(result.valid).toBe(true)
      expect(result.messageKey).toBeUndefined()
    })

    it('should reject when expected columns are missing from the result', () => {
      // Query returns fewer columns than expected, so required columns are missing.
      const result = validateColumns(
        ['station_id', 'value'],
        ['station_id', 'value', 'timestamp', 'quality'],
      )
      expect(result.valid).toBe(false)
      expect(result.messageKey).toBe('validation.missingColumns')
      expect(result.params?.missing).toContain('timestamp')
    })

    it('should reject missing required columns', () => {
      const result = validateColumns(
        ['station_id', 'temperature'],
        ['station_id', 'value', 'timestamp'],
      )
      expect(result.valid).toBe(false)
      expect(result.messageKey).toBe('validation.missingColumns')
    })

    it('should note extra columns', () => {
      const result = validateColumns(
        ['station_id', 'value', 'extra_col'],
        ['station_id', 'value'],
      )
      expect(result.valid).toBe(true)
      expect(result.messageKey).toBe('validation.extraColumns')
      expect(result.params?.extra).toContain('extra_col')
    })

    it('should reject empty result columns', () => {
      const result = validateColumns([], ['station_id', 'value'])
      expect(result.valid).toBe(false)
      expect(result.messageKey).toBe('validation.noColumns')
    })
  })
})

describe('validateQuery statements', () => {
  it.each([
    'SELECT * FROM data LIMIT 1; SET threads = 1',
    'SELECT * FROM data LIMIT 1; COPY data FROM \'https://example.org/rows.csv\'',
    'SELECT 1; INSTALL httpfs',
    'SELECT 1; LOAD httpfs',
    'SELECT 1;\n-- then\nSET threads = 1;',
  ])('refuses %j, of more than one statement', (sql) => {
    // DuckDB-wasm ran each statement, the ones after the first unchecked
    expect(validateQuery(sql)).toEqual({ valid: false, errorKey: 'validation.multipleStatements' })
  })

  it.each([
    ['SELECT * FROM data LIMIT 10;', 'SELECT * FROM data LIMIT 10'],
    ['SELECT * FROM data LIMIT 10 ;; ', 'SELECT * FROM data LIMIT 10'],
    ['SELECT * FROM data LIMIT 10; -- the last ten', 'SELECT * FROM data LIMIT 10'],
    ['SELECT * FROM data LIMIT 10 /* the last ten */', 'SELECT * FROM data LIMIT 10'],
    ['-- the last ten\nSELECT * FROM data LIMIT 10', '-- the last ten\nSELECT * FROM data LIMIT 10'],
    ['SELECT * FROM data WHERE parameter = \'a;b\' LIMIT 10', 'SELECT * FROM data WHERE parameter = \'a;b\' LIMIT 10'],
    // a comment never closed, which DuckDB refuses, kept for the check to tell
    ['SELECT * FROM data /* WHERE value > 0 LIMIT 10', 'SELECT * FROM data /* WHERE value > 0 LIMIT 10'],
    ['SELECT * FROM data LIMIT 10; /* done', 'SELECT * FROM data LIMIT 10; /* done'],
  ])('lets %j through as the one statement %j', (sql, statement) => {
    expect(validateQuery(sql)).toMatchObject({ valid: true, statement })
  })
})

describe('validateQuery statements, as DuckDB reads them', () => {
  let conn: DuckDBConnection

  beforeAll(async () => {
    conn = (await nodeDuckDB()).connect()
  })

  // whether DuckDB, running the text, ran a statement after its first: each case's sets `ran`
  function ranLater(sql: string): boolean {
    conn.query('RESET VARIABLE ran')
    try {
      conn.query(sql)
    }
    catch {
      // a statement that failed, which the case's own expectation tells
    }
    return conn.query('SELECT getvariable(\'ran\') AS ran').toArray()[0]!.toJSON().ran === 1
  }

  function rowsOf(sql: string) {
    return conn.query(sql).toArray().map(row => row.toJSON())
  }

  it.each([
    'SELECT 1; SET VARIABLE ran = 1',
    // a comment DuckDB lets nest, and ends at a carriage return too
    'SELECT 1 /* a /* b */ */ ; SET VARIABLE ran = 1',
    'SELECT 1 /* //* */ */ ; SET VARIABLE ran = 1',
    'SELECT 1 -- a\r; SET VARIABLE ran = 1',
    // a backslash that escapes a quote in an escape string only, there across a continuation too
    'SELECT E\'\\\'\'; SET VARIABLE ran = 1; SELECT \'\'',
    'SELECT E\'\\\' ; \' ; SET VARIABLE ran = 1',
    'SELECT \'a\\\'; SET VARIABLE ran = 1; --\'',
    'SELECT E\'a\'\n\'\\\' ; \' ; SET VARIABLE ran = 1',
    'SELECT E\'a\' -- b\n -- c\n\'\\\' ; \' ; SET VARIABLE ran = 1',
    'SELECT E\'a\'\n\'\\\'\' ; SET VARIABLE ran = 1',
    'SELECT E\'a\'\'\\\'\' ; SET VARIABLE ran = 1',
    // quotes doubled in a string and in an identifier
    'SELECT \'a\'\';\' ; SET VARIABLE ran = 1',
    'SELECT 1 AS "a"";" ; SET VARIABLE ran = 1',
    // a dollar sign in an identifier, which opens no dollar-quoted string there
    'SELECT 1 AS a$b$, 2; SET VARIABLE ran = 1',
  ])('refuses %j, whose later statement DuckDB runs', (sql) => {
    expect(ranLater(sql)).toBe(true)
    expect(validateQuery(sql).errorKey).toBe('validation.multipleStatements')
  })

  it.each([
    'SELECT 1;',
    'SELECT 1;; -- done',
    'SELECT 1 -- ; SET VARIABLE ran = 1',
    'SELECT 1 /* a /* b */ ; SET VARIABLE ran = 1; SELECT 2 */',
    'SELECT \'a;\' -- b\n\'; SET VARIABLE ran = 1\'',
    'SELECT E\'\\\' ; SET VARIABLE ran = 1\'',
    'SELECT "a;" FROM (SELECT 1 AS "a;")',
    'SELECT $$ ; SET VARIABLE ran = 1; $$',
    'SELECT $x$ ; $$ ; SET VARIABLE ran = 1; $x$',
    'SELECT 1 +/* ; */ 2',
    // a dynamic PIVOT, which DuckDB runs as several statements of its own
    'SELECT * FROM (PIVOT (SELECT \'x\' AS p, 1 AS a) ON p USING first(a))',
  ])('lets %j through as one statement, which runs as the text does', (sql) => {
    expect(ranLater(sql)).toBe(false)
    const result = validateQuery(sql)
    expect(result.valid).toBe(true)
    expect(rowsOf(result.statement!)).toEqual(rowsOf(sql))
  })
})
