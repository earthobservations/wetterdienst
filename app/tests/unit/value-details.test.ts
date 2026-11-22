import { describe, expect, it } from 'vitest'
import { sumsUp, valueDetails, windowMinutes, windowsOverlap } from '../../app/utils/value-details'

// The value details of the Explorer (GH-4296): by station, a sum only where the parameter's own aggregation says the values
// add up and the window its name states is no longer than its rows

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
    ['occurrence', true],
    ['mean', false],
    ['instant', false],
    ['max', false],
    ['min', false],
    ['mean_of_max', false],
    ['probability', false],
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

  it('adds up the days of an event as it adds up a count: an occurrence', () => {
    const occurrence = [{ resolution: 'daily', dataset: 'climate_summary', name: 'frost_day', unit: 'one', aggregation: 'occurrence' as const }]
    const rows = [reading('01975', 'frost_day', 1), reading('01975', 'frost_day', 0), reading('01975', 'frost_day', 1)]
    const { groups } = valueDetails(rows, { split: true, stations: [hamburg], parameters: occurrence })
    expect([groups[0]!.sums, groups[0]!.overlap, groups[0]!.rows[0]!.sum]).toEqual([true, false, 2])
  })

  it('finds the facts of a parameter by the name the source gives it, where the answer is not humanized', () => {
    const { groups } = details([reading('01975', 'rsk', 4)], [hamburg])
    expect([groups[0]!.sums, groups[0]!.unit, groups[0]!.rows[0]!.sum]).toEqual([true, 'mm', 4])
  })
})

describe('the window a name states', () => {
  it.each([
    ['precipitation_amount_last_1h', 60],
    ['precipitation_amount_last_3h', 180],
    ['precipitation_amount_significant_weather_last_6h', 360],
    ['evapotranspiration_potential_last_24h', 1440],
    ['wind_speed_mean_last_10min', 10],
    ['wind_direction_mean_last_2min', 2],
    ['precipitation_amount_last_15h', 900],
    ['radiation_short_wave_net_last_3h', 180],
    ['precipitation_amount', null],
    ['temperature_air_mean_2m', null],
    ['last_night_frost', null],
  ])('reads %s as %s minutes', (name, minutes) => {
    expect(windowMinutes(name)).toBe(minutes)
  })

  it.each([
    // longer than the row: the windows of consecutive rows overlap
    ['precipitation_amount_last_3h', 'hourly', true],
    ['precipitation_amount_last_6h', 'hourly', true],
    ['precipitation_amount_last_12h', 'hourly', true],
    ['precipitation_amount_last_24h', 'hourly', true],
    ['precipitation_amount_last_1h', '10_minutes', true],
    ['precipitation_amount_last_10min', '1_minute', true],
    ['evapotranspiration_potential_last_24h', '6_hours', true],
    // the same length as the row, or shorter: no overlap
    ['precipitation_amount_last_1h', 'hourly', false],
    ['precipitation_amount_last_10min', '10_minutes', false],
    ['precipitation_amount_last_24h', 'daily', false],
    ['precipitation_amount_last_6h', '6_hours', false],
    ['precipitation_amount_last_3h', '6_hours', false],
    ['precipitation_amount_last_1h', 'daily', false],
    // a name that states no window
    ['precipitation_amount', 'hourly', false],
    ['precipitation_amount', undefined, false],
    // rows of no fixed length cannot be told not to overlap
    ['precipitation_amount_last_3h', 'subdaily', true],
    ['precipitation_amount_last_3h', undefined, true],
  ])('%s in %s rows overlaps: %s', (name, resolution, expected) => {
    expect(windowsOverlap(name, resolution)).toBe(expected)
  })

  const windowed = (name: string, resolution: string, aggregation: 'sum' | 'mean' = 'sum') => [{ resolution, dataset: 'data', name, unit: 'mm', aggregation }]
  const rowsOf = (parameter: string, resolution: string) => [{ station_id: '01975', resolution, dataset: 'data', parameter, timestamp: '2025-01-01T00:00:00Z', value: 1 }, { station_id: '01975', resolution, dataset: 'data', parameter, timestamp: '2025-01-01T01:00:00Z', value: 2 }]

  it.each(['precipitation_amount_last_3h', 'precipitation_amount_last_6h', 'precipitation_amount_last_12h', 'precipitation_amount_last_24h'])('shows no sum of %s in hourly rows, and says why', (name) => {
    const { groups } = valueDetails(rowsOf(name, 'hourly'), { split: true, stations: [hamburg], parameters: windowed(name, 'hourly') })
    expect([groups[0]!.sums, groups[0]!.overlap, groups[0]!.rows[0]!.sum]).toEqual([false, true, null])
    // the other numbers stay
    expect(groups[0]!.rows[0]).toMatchObject({ count: 2, min: 1, max: 2, mean: 1.5 })
  })

  it('still shows the sum of a window the length of its rows', () => {
    const name = 'precipitation_amount_last_1h'
    const { groups } = valueDetails(rowsOf(name, 'hourly'), { split: true, stations: [hamburg], parameters: windowed(name, 'hourly') })
    expect([groups[0]!.sums, groups[0]!.overlap, groups[0]!.rows[0]!.sum]).toEqual([true, false, 3])
  })

  it('shows the sum of a daily total whose window is the day', () => {
    const name = 'precipitation_amount_last_24h'
    const { groups } = valueDetails(rowsOf(name, 'daily'), { split: true, stations: [hamburg], parameters: windowed(name, 'daily') })
    expect([groups[0]!.sums, groups[0]!.rows[0]!.sum]).toEqual([true, 3])
  })

  it('says nothing of overlap for a parameter that does not add up, a mean over a window', () => {
    const name = 'temperature_air_mean_2m_last_24h'
    const { groups } = valueDetails(rowsOf(name, 'hourly'), { split: true, stations: [hamburg], parameters: windowed(name, 'hourly', 'mean') })
    expect([groups[0]!.sums, groups[0]!.overlap]).toEqual([false, false])
  })

  it('finds the window in the canonical name where the rows carry the source\'s', () => {
    const facts = [{ resolution: 'hourly', dataset: 'data', name: 'precipitation_amount_last_6h', name_original: 'rr6', unit: 'mm', aggregation: 'sum' as const }]
    const { groups } = valueDetails(rowsOf('rr6', 'hourly'), { split: true, stations: [hamburg], parameters: facts })
    expect([groups[0]!.sums, groups[0]!.overlap]).toEqual([false, true])
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
  })

  it('lists one station on its own too', () => {
    const result = details(rows.filter(row => row.station_id === '01975'), [hamburg])
    expect(result.split).toBe(true)
    expect(result.groups.map(group => group.rows.length)).toEqual([1, 1])
  })

  it('lists three stations', () => {
    const result = details([...rows, reading('10147', 'precipitation_amount', 1)], [hamburg, munich, { id: '10147', name: null }])
    expect(result.groups[0]!.rows.map(row => row.station.id)).toEqual(['01975', '03379', '10147'])
  })

  it('is one series for a point: no station, however the rows are named', () => {
    const result = details(rows, [], false)
    expect(result.split).toBe(false)
    expect(result.stations).toEqual([{ id: '', name: null }])
    expect(result.groups[0]!.rows).toHaveLength(1)
    expect(result.groups[0]!.rows[0]).toMatchObject({ count: 3, sum: 8 })
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
