import type { DuckDBConnection } from '@duckdb/duckdb-wasm/blocking'
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { beforeAll, describe, expect, it } from 'vitest'
import { plainRows } from '../../app/utils/arrow-rows'
import { fieldText, valuesToCsv, valuesToJson } from '../../app/utils/values-export'
import { nodeDuckDB } from '../duckdb-node'

let conn: DuckDBConnection

beforeAll(async () => {
  conn = (await nodeDuckDB()).connect()
})

// the plain rows of a query
function rows(sql: string): Record<string, unknown>[] {
  return plainRows(conn.query(sql))
}

// the one value of a query of one row and one column
function value(sql: string): unknown {
  return Object.values(rows(sql)[0]!)[0]
}

describe('plainRows', () => {
  it('writes a timestamp or a date as the REST API writes a timestamp, to the microsecond', () => {
    expect(value('SELECT TIMESTAMP \'2020-01-01 00:00:00.123456\'')).toBe('2020-01-01T00:00:00.123456+00:00')
    expect(value('SELECT TIMESTAMPTZ \'2020-01-01 01:00:00+01\'')).toBe('2020-01-01T00:00:00.000000+00:00')
    expect(value('SELECT DATE \'2020-02-01\'')).toBe('2020-02-01T00:00:00.000000+00:00')
    expect(value('SELECT TIMESTAMP_S \'2020-01-01 00:00:01\'')).toBe('2020-01-01T00:00:01.000000+00:00')
    expect(value('SELECT TIMESTAMP_MS \'2020-01-01 00:00:01.5\'')).toBe('2020-01-01T00:00:01.500000+00:00')
  })

  it('writes a nanosecond timestamp to the microsecond, as the REST API writes one', () => {
    expect(value('SELECT TIMESTAMP_NS \'2020-01-01 00:00:00.123456789\'')).toBe('2020-01-01T00:00:00.123456+00:00')
    expect(value('SELECT TIMESTAMP_NS \'1969-12-31 23:59:59.999999999\'')).toBe('1969-12-31T23:59:59.999999+00:00')
  })

  it('writes a moment before 1970 as it is, not rounded towards 1970', () => {
    expect(value('SELECT TIMESTAMP \'1969-12-31 23:59:59.998500\'')).toBe('1969-12-31T23:59:59.998500+00:00')
  })

  it('keeps the microseconds far from 1970, where a double of milliseconds loses them', () => {
    expect(value('SELECT TIMESTAMP \'0001-01-01 00:00:00.000001\'')).toBe('0001-01-01T00:00:00.000001+00:00')
    expect(value('SELECT TIMESTAMP \'2500-01-01 00:00:00.000001\'')).toBe('2500-01-01T00:00:00.000001+00:00')
    expect(value('SELECT TIMESTAMP \'9999-12-31 23:59:59.999999\'')).toBe('9999-12-31T23:59:59.999999+00:00')
  })

  it('writes a moment a Date cannot hold as null, rather than failing the query', () => {
    expect(value('SELECT \'infinity\'::DATE')).toBeNull()
    expect(value('SELECT \'-infinity\'::TIMESTAMP')).toBeNull()
    // the nanosecond ones fall within a Date's range
    expect(value('SELECT \'infinity\'::TIMESTAMP_NS')).toBeNull()
    expect(value('SELECT \'-infinity\'::TIMESTAMP_NS')).toBeNull()
  })

  it('writes a time of day as its text, to the microsecond, not as a count of microseconds', () => {
    expect(value('SELECT TIME \'01:00:00.5\'')).toBe('01:00:00.500000')
    expect(value('SELECT TIME \'23:59:59.999999\'')).toBe('23:59:59.999999')
  })

  it('writes an interval as an ISO 8601 duration, each part with its own sign', () => {
    // Arrow 17 reads DuckDB's months, days and nanoseconds as a year-month pair, from the wrong bytes
    expect(value('SELECT [INTERVAL 1 DAY, INTERVAL 14 MONTH, INTERVAL 3 SECOND, NULL]')).toEqual(['P1D', 'P1Y2M', 'PT3S', null])
    expect(value('SELECT INTERVAL \'1 hour 2 minutes 3.25 seconds\'')).toBe('PT1H2M3.25S')
    expect(value('SELECT -INTERVAL \'1 year 2 days 00:00:01.5\'')).toBe('P-1Y-2DT-1.5S')
    expect(value('SELECT -INTERVAL \'0.5 seconds\'')).toBe('PT-0.5S')
    expect(value('SELECT INTERVAL 0 SECOND')).toBe('PT0S')
  })

  it('writes a BIGINT as a number, and as its digits where a number would round it', () => {
    expect(value('SELECT COUNT(*) FROM range(3)')).toBe(3)
    expect(value('SELECT 9007199254740993::BIGINT')).toBe('9007199254740993')
    expect(value('SELECT 18446744073709551615::UBIGINT')).toBe('18446744073709551615')
  })

  it('writes a decimal as the number it is, not as its unscaled integer', () => {
    expect(value('SELECT 12.34::DECIMAL(5,2)')).toBe(12.34)
    expect(value('SELECT -0.05::DECIMAL(18,3)')).toBe(-0.05)
    expect(value('SELECT 1.5::DECIMAL(38,10)')).toBe(1.5)
    // a HUGEINT comes as a decimal of no fraction
    expect(value('SELECT 170141183460469231731687303715884105727::HUGEINT')).toBe('170141183460469231731687303715884105727')
    expect(value('SELECT -7::HUGEINT')).toBe(-7)
  })

  it('makes the values inside a list, a struct or a map plain as well', () => {
    expect(value('SELECT [1.5::DECIMAL(4,1), NULL]')).toEqual([1.5, null])
    expect(value('SELECT [TIME \'01:00:00\']')).toEqual(['01:00:00.000000'])
    expect(value('SELECT [[TIMESTAMP \'2500-01-01 00:00:00.000001\'], NULL, []]')).toEqual([['2500-01-01T00:00:00.000001+00:00'], null, []])
    expect(value('SELECT range(3)')).toEqual([0, 1, 2])
    expect(value('SELECT [1, 2]::INTEGER[2]')).toEqual([1, 2])
    expect(value('SELECT {\'n\': 7::BIGINT, \'t\': TIMESTAMP \'2020-01-01\', \'l\': [{\'d\': 0.5::DECIMAL(3,2)}]}')).toEqual({
      n: 7,
      t: '2020-01-01T00:00:00.000000+00:00',
      l: [{ d: 0.5 }],
    })
    expect(value('SELECT MAP {\'k\': 2::BIGINT}')).toEqual({ k: 2 })
    expect(value('SELECT MAP {DATE \'2020-01-01\': 1}')).toEqual({ '2020-01-01T00:00:00.000000+00:00': 1 })
    expect(value('SELECT MAP {[1, 2]: \'x\'}')).toEqual({ '[1,2]': 'x' })
    expect(value('SELECT [{\'a\': 1}, NULL]')).toEqual([{ a: 1 }, null])
  })

  it('reads a struct\'s fields by position, whatever they are named', () => {
    // Arrow's StructRow answers a name it has a method of with the method
    expect(value('SELECT {\'toJSON\': 1, \'constructor\': 2, \'__proto__\': 3}')).toEqual(JSON.parse('{"toJSON":1,"constructor":2,"__proto__":3}'))
  })

  it('makes a union\'s value plain by the type of the member it holds', () => {
    expect(rows('SELECT union_value(t := TIMESTAMP \'2020-01-01\')::UNION(t TIMESTAMP, d DECIMAL(3,1)) AS u UNION ALL SELECT union_value(d := 1.5)')).toEqual([
      { u: '2020-01-01T00:00:00.000000+00:00' },
      { u: 1.5 },
    ])
  })

  it('writes bytes as the list of them', () => {
    expect(value('SELECT \'hi\'::BLOB')).toEqual([104, 105])
  })

  it('leaves plain values as they are, and a missing one as null', () => {
    expect(rows('SELECT 1.5 AS f, 2::INTEGER AS i, \'01048\' AS s, true AS b, NULL::BIGINT AS n, NULL::TIMESTAMP AS t')).toEqual([
      { f: 1.5, i: 2, s: '01048', b: true, n: null, t: null },
    ])
  })

  it('gives no rows for a result of none', () => {
    expect(rows('SELECT {\'a\': 1} AS s, [1] AS l, MAP {\'k\': 1} AS m WHERE false')).toEqual([])
  })

  it('gives each row its own values across the chunks a large result comes in', () => {
    const plain = rows('SELECT range AS n, [range, NULL] AS l, {\'t\': TIMESTAMP \'2020-01-01\' + to_seconds(range)} AS s, MAP {range: range::DECIMAL(9,1)} AS m, to_seconds(range) AS i FROM range(5000)')
    expect(plain).toHaveLength(5000)
    expect(plain[4999]).toEqual({ n: 4999, l: [4999, null], s: { t: '2020-01-01T01:23:19.000000+00:00' }, m: { 4999: 4999 }, i: 'PT1H23M19S' })
  })

  it('gives every row, a name two columns share holding the last one\'s value', () => {
    expect(rows('SELECT TIMESTAMP \'2020-01-01\' AS n, range::DECIMAL(3,1) + 0.5 AS n FROM range(2)')).toEqual([{ n: 0.5 }, { n: 1.5 }])
  })
})

describe('plainRows with a NaN or an infinity', () => {
  it('writes each as null, at any depth, as the REST API answers none', () => {
    expect(rows('SELECT \'nan\'::DOUBLE AS n, 1 / 0.0 AS p, -1 / 0.0 AS m, \'inf\'::FLOAT AS f, [\'nan\'::DOUBLE, 1.5] AS l, {\'x\': \'-inf\'::DOUBLE} AS s')).toEqual([
      { n: null, p: null, m: null, f: null, l: [null, 1.5], s: { x: null } },
    ])
  })

  it('is downloaded the same as CSV and as JSON, and shown and copied as the CSV writes it', () => {
    // the CSV download wrote NaN, Infinity and -Infinity, where the JSON download wrote null
    const plain = rows('SELECT \'nan\'::DOUBLE AS n, 1 / 0.0 AS p, [-1 / 0.0, 2.5] AS l')
    expect(valuesToCsv(plain, ['n', 'p', 'l'])).toBe('n,p,l\n,,",2.5"')
    expect(JSON.parse(valuesToJson(plain, ['n', 'p', 'l']))).toEqual({ values: [{ n: null, p: null, l: [null, 2.5] }] })
    expect(fieldText(plain[0]!.n)).toBe('')
  })
})

describe('plainRows of a BIGNUM', () => {
  it('writes a BIGNUM as the integer it is, not as DuckDB\'s bytes', () => {
    // DuckDB hands one over as its own bytes: 123 as [128, 0, 1, 123]
    expect(rows('SELECT 0::VARINT AS z, 123::VARINT AS p, -123::VARINT AS n, -256::VARINT AS m, NULL::VARINT AS x')).toEqual([
      { z: 0, p: 123, n: -123, m: -256, x: null },
    ])
    expect(value('SELECT 9007199254740993::VARINT')).toBe('9007199254740993')
    expect(value(`SELECT '-${'9'.repeat(50)}'::VARINT`)).toBe(`-${'9'.repeat(50)}`)
  })

  it('writes a BIGNUM inside a list, an array, a struct or a union as the integer it is', () => {
    expect(value('SELECT [1::VARINT, NULL, -2::VARINT]')).toEqual([1, null, -2])
    expect(value('SELECT [1::VARINT]::VARINT[1]')).toEqual([1])
    expect(value('SELECT {\'v\': 300::VARINT}')).toEqual({ v: 300 })
    expect(value('SELECT union_value(v := 5::VARINT)::UNION(v VARINT, s VARCHAR)')).toBe(5)
    // inside a map's key or value, where these keep the extension type the map's own fields lose
    const inMap = 'SELECT MAP {[2::VARINT]: {\'s\': 3::VARINT}} AS a, MAP {1: [4::VARINT]::VARINT[1]} AS b, MAP {1: union_value(v := 5::VARINT)::UNION(v VARINT, s VARCHAR)} AS c'
    expect(rows(inMap)).toEqual([{ a: { '[2]': { s: 3 } }, b: { 1: [4] }, c: { 1: 5 } }])
  })

  it('leaves a BLOB of the same bytes as its bytes', () => {
    expect(value('SELECT \'\\x80\\x00\\x01\\x7B\'::BLOB')).toEqual([128, 0, 1, 123])
  })
})

describe('plainRows of a map with a NaN or an infinite key', () => {
  it('keeps each such key apart, by its own name', () => {
    // each was keyed by "null", the last one's value the only one kept
    expect(value('SELECT MAP {\'nan\'::DOUBLE: 1, \'inf\'::DOUBLE: 2, \'-inf\'::DOUBLE: 3, 1.5::DOUBLE: 4}')).toEqual({ 'NaN': 1, 'Infinity': 2, '-Infinity': 3, '1.5': 4 })
    expect(value('SELECT MAP {\'nan\'::FLOAT: 1, \'inf\'::FLOAT: 2}')).toEqual({ NaN: 1, Infinity: 2 })
  })

  it('gives each row its own keys across the chunks a large result comes in', () => {
    const plain = rows('SELECT MAP {\'nan\'::DOUBLE: range, (CASE WHEN range % 2 = 0 THEN \'inf\' ELSE \'-inf\' END)::DOUBLE: -range} AS m FROM range(5000)')
    expect(plain[0]).toEqual({ m: { NaN: 0, Infinity: 0 } })
    expect(plain[4999]).toEqual({ m: { 'NaN': 4999, '-Infinity': -4999 } })
  })

  it('reads a map with an infinite timestamp key, which Arrow\'s getter cannot', () => {
    // read only a float key from the getter, which throws on these ticks
    expect(() => rows('SELECT MAP {\'infinity\'::TIMESTAMP: 1, \'-infinity\'::TIMESTAMP: 2} AS m')).not.toThrow()
  })
})

describe('plainRows of a map with an infinite date or timestamp key', () => {
  it('keeps each such key apart, by DuckDB\'s text', () => {
    // each was keyed by "null", the last one's value the only one kept (GH-2148)
    const finite = '2020-01-01T00:00:00.000000+00:00'
    expect(value('SELECT MAP {\'infinity\'::DATE: 1, \'-infinity\'::DATE: 2, DATE \'2020-01-01\': 3}')).toEqual({ 'infinity': 1, '-infinity': 2, [finite]: 3 })
    for (const type of ['TIMESTAMP', 'TIMESTAMPTZ', 'TIMESTAMP_S', 'TIMESTAMP_MS', 'TIMESTAMP_NS'])
      expect(value(`SELECT MAP {'infinity'::${type}: 1, '-infinity'::${type}: 2, TIMESTAMP '2020-01-01'::${type}: 3}`), type).toEqual({ 'infinity': 1, '-infinity': 2, [finite]: 3 })
  })

  it('gives each row its own keys across the chunks a large result comes in', () => {
    const plain = rows('SELECT MAP {(CASE WHEN range % 2 = 0 THEN \'infinity\' ELSE \'-infinity\' END)::DATE: range} AS d, MAP {(CASE WHEN range % 2 = 0 THEN \'-infinity\' ELSE \'infinity\' END)::TIMESTAMP: range} AS t FROM range(5000)')
    expect(plain[0]).toEqual({ d: { infinity: 0 }, t: { '-infinity': 0 } })
    expect(plain[4999]).toEqual({ d: { '-infinity': 4999 }, t: { infinity: 4999 } })
  })
})

describe('plainRows of a GEOMETRY', () => {
  // DuckDB hands one over as its WKB bytes, which the query panel's note names with the cast
  it('comes as its WKB bytes, and as its text once cast to VARCHAR', () => {
    expect(value('SELECT \'POINT(1 2)\'::GEOMETRY')).toEqual([1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 240, 63, 0, 0, 0, 0, 0, 0, 0, 64])
    expect(value('SELECT CAST(\'POINT(1 2)\'::GEOMETRY AS VARCHAR)')).toBe('POINT (1 2)')
  })

  it('is named by the query panel\'s note in every language, with the cast that reads it', () => {
    const dir = fileURLToPath(new URL('../../i18n/locales', import.meta.url))
    for (const name of readdirSync(dir).filter(name => name.endsWith('.json'))) {
      const note: string = JSON.parse(readFileSync(`${dir}/${name}`, 'utf-8')).validation.misreadTypes
      expect(note, name).toMatch(/GEOMETRY.*WKB.*CAST\(\w+ AS VARCHAR\)/)
    }
  })
})
