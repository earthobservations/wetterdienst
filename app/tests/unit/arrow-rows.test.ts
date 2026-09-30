import type { ArrowField } from '../../app/utils/arrow-rows'
import { describe, expect, it } from 'vitest'
import { plainRows } from '../../app/utils/arrow-rows'

// the type strings Arrow 17 gives, as read off a DuckDB-wasm result's schema
function field(name: string, type: string): ArrowField {
  return { name, type: { toString: () => type } }
}

// one column's value, as the query panel hands it on
function plain(value: unknown, type: string): unknown {
  return plainRows([{ c: value }], [field('c', type)])[0]!.c
}

describe('plainRows', () => {
  it('writes a timestamp or a date as an ISO timestamp in UTC, not milliseconds since the epoch', () => {
    // a microsecond timestamp comes as fractional milliseconds, as DuckDB-wasm answers
    expect(plain(1577836800123.456, 'Timestamp<MICROSECOND>')).toBe('2020-01-01T00:00:00.123+00:00')
    expect(plain(1580515200000, 'Date32<DAY>')).toBe('2020-02-01T00:00:00.000+00:00')
  })

  it('floors a moment before 1970 rather than rounding it towards 1970', () => {
    expect(plain(-1.5, 'Timestamp<MICROSECOND>')).toBe('1969-12-31T23:59:59.998+00:00')
  })

  it('writes a date past what a Date holds as null, rather than failing or a stray number', () => {
    // DuckDB-wasm answers 'infinity'::DATE with 185542587100800000
    expect(plain(185542587100800000, 'Date32<DAY>')).toBeNull()
  })

  it('writes a BigInt the casts did not reach as a number', () => {
    expect(plain(42n, 'Int64')).toBe(42)
  })

  it('writes bytes as the list of them, not as an index map', () => {
    expect(plain(new Uint8Array([104, 105]), 'Binary')).toBe('[104,105]')
  })

  it('writes a nested value as its JSON text', () => {
    expect(plain({ a: 1, b: [2n] }, 'Struct<{a:Int32, b:List<Int64>}>')).toBe('{"a":1,"b":[2]}')
  })

  it('leaves plain values as they are, and a missing one as null', () => {
    expect(plain(1.5, 'Float64')).toBe(1.5)
    expect(plain('01048', 'Utf8')).toBe('01048')
    expect(plain(undefined, 'Float64')).toBeNull()
  })

  it('converts a name two columns share by the last of them, whose value the row holds', () => {
    // SELECT *, value::DECIMAL(10,2) AS value: toJSON keeps the second value, a double by the cast
    const fields = [field('value', 'Timestamp<MICROSECOND>'), field('value', 'Float64')]
    expect(plainRows([{ value: 12.34 }], fields)).toEqual([{ value: 12.34 }])
  })

  it('changes every row, in place', () => {
    const rows = [{ timestamp: 1577836800000, n: 3n }, { timestamp: 1577923200000, n: 4n }]
    const fields = [field('timestamp', 'Timestamp<MILLISECOND>'), field('n', 'Int64')]
    expect(plainRows(rows, fields)).toBe(rows)
    expect(rows).toEqual([
      { timestamp: '2020-01-01T00:00:00.000+00:00', n: 3 },
      { timestamp: '2020-01-02T00:00:00.000+00:00', n: 4 },
    ])
  })
})
