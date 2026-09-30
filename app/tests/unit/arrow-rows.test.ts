import type { ArrowField } from '../../app/utils/arrow-rows'
import { describe, expect, it } from 'vitest'
import { plainRows, plainValue } from '../../app/utils/arrow-rows'

// the type strings Arrow 17 gives, as read off a DuckDB result's schema
function field(name: string, type: string, scale?: number): ArrowField {
  return { name, type: { toString: () => type, scale } }
}

// Arrow 17's DecimalBigNum as it behaves: its string is the unscaled integer, and `valueOf(scale)` the
// number it stands for, throwing where that is past exact -- as checked against apache-arrow 17 itself
function decimal(unscaled: bigint) {
  return {
    toString: () => unscaled.toString(),
    valueOf: (s: number) => {
      const number = Number(unscaled) / 10 ** s
      if (!Number.isSafeInteger(Math.trunc(number)))
        throw new TypeError(`${unscaled} is not safe to convert to a number.`)
      return number
    },
  }
}

describe('plainValue', () => {
  it('writes a timestamp or a date as the REST API writes a timestamp, not milliseconds since the epoch', () => {
    expect(plainValue(1577836800000, field('month', 'Timestamp<MICROSECOND>'))).toBe('2020-01-01T00:00:00.000000+00:00')
    expect(plainValue(1580515200000, field('day', 'Date32<DAY>'))).toBe('2020-02-01T00:00:00.000000+00:00')
  })

  it('leaves a date past what a Date holds as it came, rather than failing the query', () => {
    // DuckDB's 'infinity'::DATE
    expect(plainValue(9.3e15, field('day', 'Date32<DAY>'))).toBe(9.3e15)
  })

  it('writes a BIGINT as a number while exact, and as its digits past that', () => {
    expect(plainValue(42n, field('count', 'Int64'))).toBe(42)
    expect(plainValue(18446744073709551615n, field('h', 'Uint64'))).toBe('18446744073709551615')
  })

  it('writes a DECIMAL as the number it stands for, scaled, negative ones included', () => {
    expect(plainValue(decimal(1234n), field('total', 'Decimal[18e+2]', 2))).toBe(12.34)
    expect(plainValue(decimal(-1234n), field('total', 'Decimal[18e+2]', 2))).toBe(-12.34)
    // unscaled past 2^53, scaled well within: Number() on the object throws here, valueOf(scale) does not
    expect(plainValue(decimal(10n ** 16n), field('value', 'Decimal[38e+10]', 10))).toBe(1000000)
  })

  it('writes a DECIMAL past where a number is exact as its digits', () => {
    expect(plainValue(decimal(123456789012345678901234n), field('sum', 'Decimal[38e+2]', 2))).toBe('1234567890123456789012.34')
    expect(plainValue(decimal(-5n), field('d', 'Decimal[38e+3]', 3))).toBe(-0.005)
  })

  it('writes bytes as the list of them, not as an index map', () => {
    expect(plainValue(new Uint8Array([104, 105]), field('b', 'Binary'))).toBe('[104,105]')
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
      { timestamp: '2020-01-01T00:00:00.000000+00:00', count: 3 },
    ])
  })
})
