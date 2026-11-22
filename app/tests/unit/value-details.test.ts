import { describe, expect, it } from 'vitest'
import { formatSignedPercent } from '../../app/utils/format'
import { sumsUp, valueDetails } from '../../app/utils/value-details'

// The value details of the Explorer (GH-4296): by station, the difference of two, a sum only where the parameter's own
// aggregation says the values add up

const hamburg = { id: '01975', name: 'Hamburg-Fuhlsbüttel' }
const munich = { id: '03379', name: 'München-Stadt' }

const facts = [
  { dataset: 'climate_summary', name: 'precipitation_amount', name_original: 'rsk', unit: 'mm', aggregation: 'sum' as const },
  { dataset: 'climate_summary', name: 'sunshine_duration', name_original: 'sdk', unit: 'h', aggregation: 'sum' as const },
  { dataset: 'climate_summary', name: 'temperature_air_mean_2m', name_original: 'tmk', unit: '°C', aggregation: 'mean' as const },
]

function reading(station_id: string, parameter: string, value: number | null) {
  return { station_id, resolution: 'daily', dataset: 'climate_summary', parameter, timestamp: '2025-01-01T00:00:00Z', value }
}

function details(rows: object[], stations = [hamburg, munich], split = true) {
  return valueDetails(rows, { split, stations, parameters: facts })
}

describe('the sum rule', () => {
  it.each([
    ['sum', true],
    ['count', true],
    ['mean', false],
    ['instant', false],
    ['max', false],
    ['min', false],
    ['mean_of_max', false],
    ['probability', false],
    ['occurrence', false],
    ['date', false],
    ['change', false],
    ['uncertainty', false],
    ['code', false],
    ['at_max', false],
    [null, false],
    [undefined, false],
  ])('adds up a value that is %s: %s', (aggregation, expected) => {
    expect(sumsUp(aggregation)).toBe(expected)
  })

  it('shows the sum of a sum parameter and none of a mean, whatever the name says', () => {
    const rows = [reading('01975', 'precipitation_amount', 1), reading('01975', 'precipitation_amount', 2), reading('01975', 'temperature_air_mean_2m', 3), reading('01975', 'temperature_air_mean_2m', 5)]
    const [rain, temperature] = details(rows, [hamburg]).groups
    expect([rain!.parameter, rain!.sums, rain!.rows[0]!.sum]).toEqual(['precipitation_amount', true, 3])
    expect([temperature!.parameter, temperature!.sums, temperature!.rows[0]!.sum]).toEqual(['temperature_air_mean_2m', false, null])
    // its mean and the rest are there all the same
    expect(temperature!.rows[0]).toMatchObject({ count: 2, min: 3, max: 5, mean: 4 })
  })

  it('shows no sum of a parameter the answer says nothing of', () => {
    const { groups } = valueDetails([reading('01975', 'rainfall_by_another_name', 1)], { split: true, stations: [hamburg], parameters: [] })
    expect(groups[0]!.sums).toBe(false)
    expect(groups[0]!.rows[0]!.sum).toBeNull()
  })

  it('finds the facts of a parameter by the name the source gives it, where the answer is not humanized', () => {
    const { groups } = details([reading('01975', 'rsk', 4)], [hamburg])
    expect([groups[0]!.sums, groups[0]!.unit, groups[0]!.rows[0]!.sum]).toEqual([true, 'mm', 4])
  })
})

describe('the split by station', () => {
  const rows = [
    reading('03379', 'precipitation_amount', 4),
    reading('01975', 'precipitation_amount', 1),
    reading('01975', 'precipitation_amount', 3),
    reading('03379', 'temperature_air_mean_2m', 12),
    reading('01975', 'temperature_air_mean_2m', 10),
  ]

  it('has a row for each station of each parameter, the stations in the order they are listed and not the rows\'', () => {
    const result = details(rows)
    expect(result.split).toBe(true)
    expect(result.stations).toEqual([hamburg, munich])
    expect(result.groups.map(group => [group.parameter, group.rows.map(row => row.station.id)])).toEqual([
      ['precipitation_amount', ['01975', '03379']],
      ['temperature_air_mean_2m', ['01975', '03379']],
    ])
  })

  it('takes the numbers of a station of its own values alone', () => {
    const [rain] = details(rows).groups
    expect(rain!.rows[0]).toMatchObject({ count: 2, min: 1, max: 3, mean: 2, sum: 4 })
    expect(rain!.rows[1]).toMatchObject({ count: 1, min: 4, max: 4, mean: 4, sum: 4 })
  })

  it('puts a station of the rows that the request does not name after those it does', () => {
    const result = details([reading('00044', 'precipitation_amount', 1), ...rows], [munich, hamburg])
    expect(result.stations.map(station => station.id)).toEqual(['03379', '01975', '00044'])
    expect(result.stations[2]!.name).toBeNull()
    expect(result.groups[0]!.difference).toBeNull()
  })

  it('lists one station on its own too, with no difference', () => {
    const result = details(rows.filter(row => row.station_id === '01975'), [hamburg])
    expect(result.split).toBe(true)
    expect(result.groups.map(group => group.rows.length)).toEqual([1, 1])
    expect(result.groups.every(group => group.difference === null)).toBe(true)
  })

  it('lists three stations, and a difference of none', () => {
    const result = details([...rows, reading('10147', 'precipitation_amount', 1)], [hamburg, munich, { id: '10147', name: null }])
    expect(result.groups[0]!.rows.map(row => row.station.id)).toEqual(['01975', '03379', '10147'])
    expect(result.groups[0]!.difference).toBeNull()
  })

  it('is one series for a point: no station, however the rows are named', () => {
    const result = details(rows, [], false)
    expect(result.split).toBe(false)
    expect(result.stations).toEqual([{ id: '', name: null }])
    expect(result.groups[0]!.rows).toHaveLength(1)
    expect(result.groups[0]!.rows[0]).toMatchObject({ count: 3, sum: 8 })
    expect(result.groups[0]!.difference).toBeNull()
  })

  it('is one series for rows that carry no station, as a query may leave it out', () => {
    const result = details([{ parameter: 'precipitation_amount', dataset: 'climate_summary', value: 2 }, { parameter: 'precipitation_amount', dataset: 'climate_summary', value: 3 }])
    expect(result.split).toBe(false)
    expect(result.groups[0]!.rows[0]).toMatchObject({ count: 2, sum: 5 })
  })

  it('takes rows without a parameter or a numeric value as no values at all', () => {
    expect(details([{ station_id: '01975', temperature_air_mean_2m: 1 }, { station_id: '01975', parameter: 'rsk', value: '3' }]).groups).toEqual([])
  })
})

describe('the difference of two stations', () => {
  it('is the second less the first, of min, max, mean and, where there is one, the sum', () => {
    const rows = [
      reading('01975', 'precipitation_amount', 1),
      reading('01975', 'precipitation_amount', 3),
      reading('03379', 'precipitation_amount', 5),
      reading('03379', 'precipitation_amount', 9),
    ]
    expect(details(rows).groups[0]!.difference).toEqual({ min: 4, max: 6, mean: 5, sum: 10, sumShare: 2.5 })
  })

  it('is negative where the second is the lesser', () => {
    const rows = [reading('01975', 'precipitation_amount', 10), reading('03379', 'precipitation_amount', 4)]
    expect(details(rows).groups[0]!.difference).toEqual({ min: -6, max: -6, mean: -6, sum: -6, sumShare: -0.6 })
  })

  it('has no sum, and no share, of a parameter that does not add up', () => {
    const rows = [reading('01975', 'temperature_air_mean_2m', 10), reading('03379', 'temperature_air_mean_2m', 12)]
    expect(details(rows).groups[0]!.difference).toEqual({ min: 2, max: 2, mean: 2, sum: null, sumShare: null })
  })

  it('has no share where the first sum is 0, which a share of cannot be told, but has the sum', () => {
    const rows = [reading('01975', 'precipitation_amount', 0), reading('03379', 'precipitation_amount', 3)]
    expect(details(rows).groups[0]!.difference).toMatchObject({ sum: 3, sumShare: null })
  })

  it('is the share of the magnitude of a first sum that is below 0', () => {
    const rows = [reading('01975', 'precipitation_amount', -2), reading('03379', 'precipitation_amount', 1)]
    expect(details(rows).groups[0]!.difference).toMatchObject({ sum: 3, sumShare: 1.5 })
  })

  it('is nothing where either station has no value, and the station is there with a count of 0', () => {
    const rows = [reading('01975', 'precipitation_amount', 1), reading('03379', 'precipitation_amount', null)]
    const [rain] = details(rows).groups
    expect(rain!.rows.map(row => [row.count, row.min, row.sum])).toEqual([[1, 1, 1], [0, null, null]])
    expect(rain!.difference).toEqual({ min: null, max: null, mean: null, sum: null, sumShare: null })
  })

  it('is nothing for a parameter only one station has, the other being listed with none', () => {
    const rows = [reading('01975', 'precipitation_amount', 1), reading('01975', 'temperature_air_mean_2m', 3), reading('03379', 'temperature_air_mean_2m', 4)]
    const [rain, temperature] = details(rows).groups
    expect(rain!.rows.map(row => row.count)).toEqual([1, 0])
    expect(rain!.difference!.mean).toBeNull()
    expect(temperature!.difference!.mean).toBe(1)
  })

  it('reads the order from the stations as listed: swapped, the difference changes its sign', () => {
    const rows = [reading('01975', 'temperature_air_mean_2m', 10), reading('03379', 'temperature_air_mean_2m', 12)]
    expect(details(rows, [hamburg, munich]).groups[0]!.difference!.mean).toBe(2)
    expect(details(rows, [munich, hamburg]).groups[0]!.difference!.mean).toBe(-2)
  })
})

describe('the share as the language writes it', () => {
  it.each([
    ['en', 0.081, '+8.1%'],
    ['en', -0.25, '-25.0%'],
    ['en', 0.00004, '0.0%'],
    ['de', 0.081, '+8,1 %'],
  ])('writes %s %d as %s', (locale, fraction, expected) => {
    expect(formatSignedPercent(fraction, locale, 1).replace(/−/g, '-')).toBe(expected)
  })
})
