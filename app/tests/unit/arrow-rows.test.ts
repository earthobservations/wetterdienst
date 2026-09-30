import type { ArrowField } from '../../app/utils/arrow-rows'
import { describe, expect, it } from 'vitest'
import { plainRows, plainValue } from '../../app/utils/arrow-rows'

// the type strings Arrow 17 gives, as read off a DuckDB result's schema
function field(name: string, type: string, scale?: number): ArrowField {
  return { name, type: { toString: () => type, scale } }
}

describe('plainValue', () => {
  it('writes a timestamp or a date as an ISO string, not milliseconds since the epoch', () => {
    expect(plainValue(1577836800000, field('month', 'Timestamp<MICROSECOND>'))).toBe('2020-01-01T00:00:00.000Z')
    expect(plainValue(1580515200000, field('day', 'Date32<DAY>'))).toBe('2020-02-01T00:00:00.000Z')
  })

  it('writes a BIGINT count as a number', () => {
    expect(plainValue(42n, field('count', 'Int64'))).toBe(42)
  })

  it('writes a DECIMAL as the number it stands for, scaled', () => {
    // Arrow holds 12.34 at scale 2 as the integer 1234; its number value is that integer
    const unscaled = { valueOf: () => 1234 }
    expect(plainValue(unscaled, field('total', 'Decimal[18e+2]', 2))).toBe(12.34)
  })

  it('writes a nested value as its JSON text', () => {
    expect(plainValue({ a: 1, b: [2n] }, field('s', 'Struct<{a:Int32, b:List<Int64>}>'))).toBe('{"a":1,"b":[2]}')
  })

  it('leaves plain values as they are, and a missing one as null', () => {
    expect(plainValue(1.5, field('value', 'Float64'))).toBe(1.5)
    expect(plainValue('01048', field('station_id', 'Utf8'))).toBe('01048')
    expect(plainValue(undefined, field('value', 'Float64'))).toBeNull()
  })
})

describe('plainRows', () => {
  it('turns every value of every row by its column', () => {
    const fields = [field('timestamp', 'Timestamp<MILLISECOND>'), field('count', 'Int64')]
    expect(plainRows([{ timestamp: 1577836800000, count: 3n }], fields)).toEqual([
      { timestamp: '2020-01-01T00:00:00.000Z', count: 3 },
    ])
  })
})
