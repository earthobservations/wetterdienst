import type { Value } from '#shared/types/api'
import { describe, expect, it } from 'vitest'
import { exportColumns, valuesToCsv, valuesToJson } from '../../app/utils/values-export'

const rows: Value[] = [
  { station_id: '01048', resolution: 'daily', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m', timestamp: '2020-01-01T00:00:00Z', value: 1.5, quality: 10 },
  { station_id: '04411', resolution: 'daily', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m', timestamp: '2020-01-01T00:00:00Z', value: null, quality: null },
]

describe('valuesToCsv', () => {
  it('writes the columns given, in their order, with a header row', () => {
    expect(valuesToCsv(rows, ['station_id', 'value'])).toBe('station_id,value\n01048,1.5\n04411,')
  })

  it('quotes a field holding a comma, so it stays one column', () => {
    // several ids in one field, as an interpolation reports the stations it took
    const taken = [{ ...rows[0]!, taken_station_ids: '01048,04411' }]
    expect(valuesToCsv(taken, ['station_id', 'taken_station_ids'])).toBe('station_id,taken_station_ids\n01048,"01048,04411"')
  })

  it('doubles a quote inside a quoted field', () => {
    const quoted = [{ ...rows[0]!, station_id: 'say "hi"' }]
    expect(valuesToCsv(quoted, ['station_id'])).toBe('station_id\n"say ""hi"""')
  })

  it('writes nothing for no rows', () => {
    expect(valuesToCsv([], ['station_id'])).toBe('')
  })
})

describe('valuesToJson', () => {
  it('answers as the REST API does, each row with the columns given', () => {
    expect(JSON.parse(valuesToJson(rows, ['station_id', 'value']))).toEqual({
      values: [
        { station_id: '01048', value: 1.5 },
        { station_id: '04411', value: null },
      ],
    })
  })
})

const TABLE_COLUMNS = ['station_id', 'resolution', 'dataset', 'parameter', 'timestamp', 'value', 'quality']

describe('exportColumns', () => {
  it('keeps every column the rows carry, in the table\'s order, whatever it shows', () => {
    // resolution and dataset are hidden by default and were missing from the download
    expect(exportColumns(rows, TABLE_COLUMNS)).toEqual(TABLE_COLUMNS)
  })

  it('puts the columns the table has no place for after its own', () => {
    // a wide-shaped answer: one column per parameter, and no parameter or value column
    const wide = [{ station_id: '01048', timestamp: '2020-01-01', temperature_air_mean_2m: 1.5, precipitation_amount: 0.2 }]
    expect(exportColumns(wide, TABLE_COLUMNS)).toEqual(['station_id', 'timestamp', 'temperature_air_mean_2m', 'precipitation_amount'])
  })

  it('keeps a column the query panel added', () => {
    const grouped = [{ avg_value: 1.5, timestamp: '2020-01-01', parameter: 'temperature_air_mean_2m' }]
    expect(exportColumns(grouped, TABLE_COLUMNS)).toEqual(['parameter', 'timestamp', 'avg_value'])
  })
})

describe('valuesToCsv with a query panel\'s nested values', () => {
  it('writes a struct or a list as its JSON text, quoted, not as [object Object]', () => {
    const nested = [{ station_id: '01048', s: { a: 1, n: 2n }, l: [1, 2] }]
    expect(valuesToCsv(nested, ['station_id', 's', 'l'])).toBe('station_id,s,l\n01048,"{""a"":1,""n"":2}","[1,2]"')
  })
})

describe('valuesToCsv with a query panel\'s column names', () => {
  it('quotes a header naming an expression', () => {
    const rounded = [{ 'timestamp': '2020-01-01', 'round(avg("value"), 2)': 1.5 }]
    expect(valuesToCsv(rounded, ['timestamp', 'round(avg("value"), 2)'])).toBe('timestamp,"round(avg(""value""), 2)"\n2020-01-01,1.5')
  })
})

describe('valuesToJson over rows of different shapes', () => {
  it('writes a column a row lacks as null, as the first row holds it', () => {
    const sparse = [{ station_id: '01048', value: 1.5, taken_station_id: '01048' }, { station_id: '04411', value: 2.5 }]
    expect(JSON.parse(valuesToJson(sparse, ['station_id', 'value', 'taken_station_id'])).values[1]).toEqual({
      station_id: '04411',
      value: 2.5,
      taken_station_id: null,
    })
  })
})

describe('valuesToJson with columns the rows do not hold exactly', () => {
  it('writes the columns asked for, not the row\'s own, where as many as it holds', () => {
    // the rows were written as they are whenever they held as many keys as there were columns
    expect(JSON.parse(valuesToJson([{ a: 1, b: 2 }], ['b', 'c']))).toEqual({ values: [{ b: 2, c: null }] })
  })

  it('writes an undefined value as null, not by leaving the key out', () => {
    expect(JSON.parse(valuesToJson([{ a: 1, b: undefined }], ['a', 'b']))).toEqual({ values: [{ a: 1, b: null }] })
  })
})

describe('valuesToJson with a query panel\'s count', () => {
  it('writes a BigInt as the number it is, and as its digits past 2^53', () => {
    // DuckDB answers COUNT(*) as a BigInt, which JSON.stringify refuses
    const counted = [{ count: 42n, h: 18446744073709551615n }]
    expect(JSON.parse(valuesToJson(counted, ['count', 'h']))).toEqual({
      values: [{ count: 42, h: '18446744073709551615' }],
    })
  })
})

describe('exportColumns over rows of different shapes', () => {
  it('keeps a column only a later row carries', () => {
    const sparse = [{ station_id: '01048', value: 1.5 }, { station_id: '04411', value: 2.5, taken_station_id: '04411' }]
    expect(exportColumns(sparse, ['station_id', 'value'])).toEqual(['station_id', 'value', 'taken_station_id'])
  })
})
