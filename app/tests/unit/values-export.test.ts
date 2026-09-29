import type { Value } from '#shared/types/api'
import { describe, expect, it } from 'vitest'
import { valuesToCsv, valuesToJson } from '../../app/utils/values-export'

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
