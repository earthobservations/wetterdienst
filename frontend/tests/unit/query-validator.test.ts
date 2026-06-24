import { describe, expect, it } from 'vitest'
import { validateColumns, validateQuery } from '../../app/utils/query-validator'

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
        ['station_id', 'value', 'date'],
        ['station_id', 'value', 'date'],
      )
      expect(result.valid).toBe(true)
      expect(result.messageKey).toBeUndefined()
    })

    it('should reject when expected columns are missing from the result', () => {
      // Query returns fewer columns than expected, so required columns are missing.
      const result = validateColumns(
        ['station_id', 'value'],
        ['station_id', 'value', 'date', 'quality'],
      )
      expect(result.valid).toBe(false)
      expect(result.messageKey).toBe('validation.missingColumns')
      expect(result.params?.missing).toContain('date')
    })

    it('should reject missing required columns', () => {
      const result = validateColumns(
        ['station_id', 'temperature'],
        ['station_id', 'value', 'date'],
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
