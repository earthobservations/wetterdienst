import { describe, expect, it } from 'vitest'
import { compareToCsv, compareToJson } from '../../app/utils/compare-export'
import {
  addressOf,
  alignPeriods,
  alignStations,
  chartPoints,
  compareFromQuery,
  compareToQuery,
  difference,
  isComplete,
  isTotal,
  momentOf,
  periodLength,
  readingsOf,
  readPeriod,
  requestWindow,
  sideKindOf,
  sidesDiffer,
  stateOfAddress,
  stepOf,
  suggestedPeriods,
  summarize,
  valueText,
} from '../../app/utils/compare-model'

// The Compare tool (GH-4296): the arithmetic and the address, without a browser. The alignment is the thing most worth holding: two
// stations by calendar date, two periods by their place in the period, and a step that a side lacks is a row with no difference.

const day = (date: string, value: number | null) => ({ date, value })

describe('the difference', () => {
  it('is B minus A, free of floating point noise', () => {
    expect(difference(1.5, 4)).toBe(2.5)
    expect(difference(0.1, 0.3)).toBe(0.2)
    expect(difference(4, 1.5)).toBe(-2.5)
  })

  it('is none where either side has none: a missing value is never zero', () => {
    expect(difference(null, 3)).toBeNull()
    expect(difference(3, null)).toBeNull()
    expect(difference(null, null)).toBeNull()
    expect(difference(Number.NaN, 3)).toBeNull()
  })

  it('has no minus zero', () => {
    expect(Object.is(difference(2, 2), 0)).toBe(true)
    expect(Object.is(difference(0.1 + 0.2, 0.3), 0)).toBe(true)
  })
})

describe('the periods', () => {
  it('are two calendar days, the end not before the start', () => {
    expect(readPeriod('2025-03-01/2025-03-31')).toEqual({ start: '2025-03-01', end: '2025-03-31' })
    expect(readPeriod('2025-03-01/2025-03-01')).toEqual({ start: '2025-03-01', end: '2025-03-01' })
    for (const bad of ['2025-03-31/2025-03-01', '2025-02-30/2025-03-01', '2025-03-01', '2025-03-01/2025-03-05/2025-03-09', '', undefined, 5])
      expect(readPeriod(bad), String(bad)).toBeNull()
  })

  it('count their days or their months, both ends included', () => {
    expect(periodLength({ start: '2025-03-01', end: '2025-03-31' }, 'daily')).toBe(31)
    expect(periodLength({ start: '2024-02-01', end: '2024-02-29' }, 'daily')).toBe(29)
    expect(periodLength({ start: '2025-01-15', end: '2025-03-02' }, 'monthly')).toBe(3)
    expect(periodLength({ start: '2025-03-01', end: '2026-02-28' }, 'monthly')).toBe(12)
  })

  it('step by days or months, past their own end too', () => {
    const march = { start: '2025-03-01', end: '2025-03-31' }
    expect(stepOf(march, 'daily', 0)).toBe('2025-03-01')
    expect(stepOf(march, 'daily', 30)).toBe('2025-03-31')
    expect(stepOf(march, 'daily', 31)).toBe('2025-04-01')
    expect(stepOf({ start: '2025-11-15', end: '2026-02-01' }, 'monthly', 2)).toBe('2026-01-01')
  })

  it('are asked for as whole months where the values are monthly, since a month is stamped at its first day', () => {
    expect(requestWindow({ start: '2025-03-15', end: '2025-05-10' }, 'monthly')).toEqual({ start: '2025-03-01', end: '2025-05-31' })
    expect(requestWindow({ start: '2025-12-02', end: '2025-12-02' }, 'monthly')).toEqual({ start: '2025-12-01', end: '2025-12-31' })
    expect(requestWindow({ start: '2025-03-15', end: '2025-05-10' }, 'daily')).toEqual({ start: '2025-03-15', end: '2025-05-10' })
  })

  it('start as the last complete month, and a year of months at monthly, with the same stretch a year before', () => {
    const now = new Date('2026-11-22T10:00:00Z')
    expect(suggestedPeriods('daily', now)).toEqual({ latest: { start: '2026-10-01', end: '2026-10-31' }, yearBefore: { start: '2025-10-01', end: '2025-10-31' } })
    expect(suggestedPeriods('monthly', now).latest).toEqual({ start: '2025-11-01', end: '2026-10-31' })
    // in January the last complete month is December of the year before
    expect(suggestedPeriods('daily', new Date('2027-01-05T00:00:00Z')).latest).toEqual({ start: '2026-12-01', end: '2026-12-31' })
    // and a leap February has its 29 days
    expect(suggestedPeriods('daily', new Date('2024-03-10T00:00:00Z')).latest).toEqual({ start: '2024-02-01', end: '2024-02-29' })
  })
})

describe('two stations, aligned by calendar date', () => {
  const period = { start: '2026-03-01', end: '2026-03-04' }

  it('have a row for every day of the period, the same date on both sides', () => {
    const a = [day('2026-03-01', 5), day('2026-03-02', 6), day('2026-03-03', 7), day('2026-03-04', 8)]
    const b = [day('2026-03-01', 6), day('2026-03-02', 6.5), day('2026-03-03', 5), day('2026-03-04', 8)]
    expect(alignStations(a, b, period, 'daily')).toEqual([
      { step: 1, dateA: '2026-03-01', dateB: '2026-03-01', a: 5, b: 6, difference: 1 },
      { step: 2, dateA: '2026-03-02', dateB: '2026-03-02', a: 6, b: 6.5, difference: 0.5 },
      { step: 3, dateA: '2026-03-03', dateB: '2026-03-03', a: 7, b: 5, difference: -2 },
      { step: 4, dateA: '2026-03-04', dateB: '2026-03-04', a: 8, b: 8, difference: 0 },
    ])
  })

  it('keep a day only one side has as a row with no difference, and a day neither has as a row with two empty cells', () => {
    const a = [day('2026-03-01', 5), day('2026-03-02', null), day('2026-03-04', 8)]
    const b = [day('2026-03-01', 6), day('2026-03-02', 4)]
    const rows = alignStations(a, b, period, 'daily')
    expect(rows.map(row => [row.a, row.b, row.difference])).toEqual([[5, 6, 1], [null, 4, null], [null, null, null], [8, null, null]])
  })

  it('are matched by month where the values are monthly, whichever day the source stamps', () => {
    const rows = alignStations([day('2026-01-01', 1), day('2026-02-01', 2)], [day('2026-01-01', 3), day('2026-02-01', 1)], { start: '2026-01-10', end: '2026-02-20' }, 'monthly')
    expect(rows.map(row => [row.dateA, row.difference])).toEqual([['2026-01-01', 2], ['2026-02-01', -1]])
  })
})

describe('two periods, aligned by their place in the period', () => {
  it('pair day 1 with day 1, whatever the dates', () => {
    const march2025 = { start: '2025-03-01', end: '2025-03-03' }
    const march2026 = { start: '2026-03-01', end: '2026-03-03' }
    const rows = alignPeriods([day('2025-03-01', 10), day('2025-03-02', 11), day('2025-03-03', 12)], march2025, [day('2026-03-01', 12), day('2026-03-02', 11), day('2026-03-03', 9)], march2026, 'daily')
    expect(rows).toEqual([
      { step: 1, dateA: '2025-03-01', dateB: '2026-03-01', a: 10, b: 12, difference: 2 },
      { step: 2, dateA: '2025-03-02', dateB: '2026-03-02', a: 11, b: 11, difference: 0 },
      { step: 3, dateA: '2025-03-03', dateB: '2026-03-03', a: 12, b: 9, difference: -3 },
    ])
  })

  it('pair across a leap day by position: the 29th of February has a partner only where the other period reaches that far', () => {
    const feb2024 = { start: '2024-02-01', end: '2024-02-29' }
    const feb2025 = { start: '2025-02-01', end: '2025-02-28' }
    const rows = alignPeriods([day('2024-02-29', 3)], feb2024, [day('2025-02-28', 1)], feb2025, 'daily')
    expect(rows).toHaveLength(29)
    expect(rows[28]).toEqual({ step: 29, dateA: '2024-02-29', dateB: null, a: 3, b: null, difference: null })
    expect(rows[27]!.dateB).toBe('2025-02-28')
  })

  it('compare periods of unequal length as far as the shorter reaches: the rest has no partner and no difference', () => {
    const long = { start: '2026-03-01', end: '2026-03-05' }
    const short = { start: '2025-03-10', end: '2025-03-12' }
    const rows = alignPeriods(
      [day('2026-03-01', 1), day('2026-03-02', 2), day('2026-03-03', 3), day('2026-03-04', 4), day('2026-03-05', 5)],
      long,
      [day('2025-03-10', 1), day('2025-03-11', 1), day('2025-03-12', 1)],
      short,
      'daily',
    )
    expect(rows.map(row => row.difference)).toEqual([0, -1, -2, null, null])
    expect(rows.map(row => row.dateB)).toEqual(['2025-03-10', '2025-03-11', '2025-03-12', null, null])
    expect(rows.map(row => row.dateA)).toEqual(['2026-03-01', '2026-03-02', '2026-03-03', '2026-03-04', '2026-03-05'])
    // the other way round, the longer one is B
    const flipped = alignPeriods([day('2025-03-10', 1)], short, [day('2026-03-04', 4)], long, 'daily')
    expect(flipped.map(row => row.dateA)).toEqual(['2025-03-10', '2025-03-11', '2025-03-12', null, null])
  })

  it('pair month 1 with month 1 at monthly', () => {
    const rows = alignPeriods([day('2025-03-01', 5), day('2025-04-01', 8)], { start: '2025-03-01', end: '2025-04-30' }, [day('2026-03-01', 6), day('2026-04-01', 7)], { start: '2026-03-01', end: '2026-04-30' }, 'monthly')
    expect(rows.map(row => [row.dateA, row.dateB, row.difference])).toEqual([['2025-03-01', '2026-03-01', 1], ['2025-04-01', '2026-04-01', -1]])
  })
})

describe('the readings of a request', () => {
  const rows = [
    { station_id: '00011', timestamp: '2026-03-01T00:00:00+00:00', value: 4.5 },
    { station_id: '00044', timestamp: '2026-03-01T00:00:00+00:00', value: 7 },
    { station_id: '00011', timestamp: '2026-03-02T00:00:00+00:00', value: null },
    { station_id: '00011', timestamp: 'not a date', value: 1 },
    { station_id: '00011', timestamp: '2026-03-03T00:00:00+00:00', value: Number.NaN },
  ]

  it('are the station\'s own, with a missing value as null and a row that is no date left out', () => {
    expect(readingsOf(rows, '00011', 'daily')).toEqual([{ date: '2026-03-01', value: 4.5 }, { date: '2026-03-02', value: null }, { date: '2026-03-03', value: null }])
    expect(readingsOf(rows, null, 'daily')).toHaveLength(4)
  })

  it('are dated by the first of the month at monthly', () => {
    expect(readingsOf([{ station_id: 'x', timestamp: '2026-03-17T12:00:00+00:00', value: 1 }], 'x', 'monthly')).toEqual([{ date: '2026-03-01', value: 1 }])
  })
})

describe('what the sides are', () => {
  const kind = { resolution: 'daily', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m', unit: '°C', aggregation: 'mean', timestampPosition: 'start' }

  it('is told from the answer\'s metadata and its rows', () => {
    expect(sideKindOf('temperature_air_mean_2m', [{ name: 'temperature_air_mean_2m', unit: '°C', aggregation: 'mean', timestamp_position: 'start', resolution: 'daily', dataset: 'climate_summary' }], [])).toEqual(kind)
    expect(sideKindOf('p', null, [{ parameter: 'p', resolution: 'monthly', dataset: 'climate_summary' }])).toMatchObject({ resolution: 'monthly', dataset: 'climate_summary', unit: null })
  })

  it.each([
    ['resolution', { resolution: 'monthly' }],
    ['dataset', { dataset: 'more_precip' }],
    ['parameter', { parameter: 'temperature_air_max_2m' }],
    ['unit', { unit: 'K' }],
    ['aggregation', { aggregation: 'max' }],
    ['position', { timestampPosition: 'end' }],
  ])('are refused with the reason where the %s differs, and not otherwise', (reason, change) => {
    expect(sidesDiffer(kind, { ...kind, ...change })).toBe(reason)
    expect(sidesDiffer(kind, kind)).toBeNull()
  })

  it('says a total or a count is a total', () => {
    expect(isTotal('sum')).toBe(true)
    expect(isTotal('count')).toBe(true)
    expect(isTotal('mean')).toBe(false)
    expect(isTotal(null)).toBe(false)
  })
})

describe('what the table comes to', () => {
  const rows = alignStations(
    [day('2026-03-01', 4), day('2026-03-02', 6), day('2026-03-03', 8), day('2026-03-04', null)],
    [day('2026-03-01', 5), day('2026-03-02', 6), day('2026-03-03', null), day('2026-03-04', 10)],
    { start: '2026-03-01', end: '2026-03-04' },
    'daily',
  )

  it('is taken over the steps both sides have, so that the means are of the same days and their difference is the mean of the differences', () => {
    const summary = summarize(rows)
    expect(summary).toMatchObject({ rows: 4, compared: 2, unpaired: 2, meanA: 5, meanB: 5.5, meanDifference: 0.5, sumA: 10, sumB: 11, sumDifference: 1 })
  })

  it('has nothing where no step has both', () => {
    expect(summarize([])).toMatchObject({ rows: 0, compared: 0, meanA: null, meanDifference: null, sumDifference: null })
    expect(summarize(alignStations([day('2026-03-01', 1)], [day('2026-03-02', 1)], { start: '2026-03-01', end: '2026-03-02' }, 'daily')).compared).toBe(0)
  })

  it('is written as the table writes a number: two decimals at most, a sign for a difference, no minus zero', () => {
    expect(valueText(12.345, 'en')).toBe('12.35')
    expect(valueText(12.3, 'en')).toBe('12.3')
    expect(valueText(0.8, 'en', true)).toBe('+0.8')
    expect(valueText(-0.8, 'en', true)).toBe('-0.8')
    expect(valueText(-0.001, 'en', true)).toBe('0')
    expect(valueText(12.5, 'de')).toBe('12,5')
  })
})

describe('the chart', () => {
  it('draws two stations on their own dates', () => {
    const rows = alignStations([day('2026-03-01', 1)], [day('2026-03-01', 2)], { start: '2026-03-01', end: '2026-03-02' }, 'daily')
    const points = chartPoints(rows, 'stations', undefined, 'daily')
    expect(points.a.x).toEqual([momentOf('2026-03-01'), momentOf('2026-03-02')])
    expect(points.b.y).toEqual([2, null])
  })

  it('draws two periods on the dates of A, the same step on the same x, and carries A\'s calendar on past its end', () => {
    const a = { start: '2025-03-30', end: '2025-03-31' }
    const b = { start: '2026-03-10', end: '2026-03-12' }
    const rows = alignPeriods([day('2025-03-30', 1), day('2025-03-31', 2)], a, [day('2026-03-10', 5), day('2026-03-11', 6), day('2026-03-12', 7)], b, 'daily')
    const points = chartPoints(rows, 'periods', a, 'daily')
    expect(points.a.x).toEqual([momentOf('2025-03-30'), momentOf('2025-03-31')])
    expect(points.b.x).toEqual([momentOf('2025-03-30'), momentOf('2025-03-31'), momentOf('2025-04-01')])
    expect(points.b.y).toEqual([5, 6, 7])
  })
})

describe('the address', () => {
  it('holds two stations over a period', () => {
    const query = { compare: 'stations', resolution: 'monthly', parameter: 'temperature_air_mean_2m', stations: '00011,00044', startDate: '2025-11-01', endDate: '2026-10-31' }
    const address = compareFromQuery(query)
    expect(address).toEqual({ by: 'stations', resolution: 'monthly', parameter: 'temperature_air_mean_2m', stations: ['00011', '00044'], period: { start: '2025-11-01', end: '2026-10-31' } })
    expect(isComplete(address)).toBe(true)
    expect(compareToQuery(address)).toEqual(query)
  })

  it('holds one station over two periods, which `periodA` alone says too', () => {
    const query = { compare: 'periods', resolution: 'daily', parameter: 'precipitation_amount', stations: '00011', periodA: '2025-03-01/2025-03-31', periodB: '2026-03-01/2026-03-31' }
    const address = compareFromQuery(query)
    expect(address.by).toBe('periods')
    expect(address.periodB).toEqual({ start: '2026-03-01', end: '2026-03-31' })
    expect(isComplete(address)).toBe(true)
    expect(compareToQuery(address)).toEqual(query)
    expect(compareFromQuery({ periodA: '2025-03-01/2025-03-31', stations: '00011' }).by).toBe('periods')
  })

  it('round-trips through the state the page holds, for either kind', () => {
    for (const query of [
      { compare: 'stations', resolution: 'daily', parameter: 'temperature_air_mean_2m', stations: 'A,B', startDate: '2026-03-01', endDate: '2026-03-31' },
      { compare: 'periods', resolution: 'daily', parameter: 'temperature_air_mean_2m', stations: 'A', periodA: '2025-03-01/2025-03-31', periodB: '2026-03-01/2026-03-31' },
    ])
      expect(compareToQuery(addressOf(stateOfAddress(compareFromQuery(query))))).toEqual(query)
  })

  it('keeps what is valid of a link and leaves out the rest, never an error', () => {
    const address = compareFromQuery({ compare: 'periods', resolution: 'hourly', parameter: 'Not A Name', stations: '00011,00044', periodA: '2025-03-31/2025-03-01', periodB: '2026-03-01/2026-03-31' })
    expect(address).toEqual({ by: 'periods', resolution: 'daily', stations: ['00011'], periodB: { start: '2026-03-01', end: '2026-03-31' } })
    expect(isComplete(address)).toBe(false)
    expect(compareFromQuery({})).toEqual({ by: 'stations', resolution: 'daily', stations: [] })
    expect(compareFromQuery({ stations: ['00011', 'x'] }).stations).toEqual(['00011'])
  })

  it('is complete only with a parameter, two different stations and a period, or one station and two periods', () => {
    const stations = { by: 'stations', resolution: 'daily', parameter: 'p', stations: ['a', 'b'], period: { start: '2026-03-01', end: '2026-03-02' } } as const
    expect(isComplete(stations)).toBe(true)
    expect(isComplete({ ...stations, parameter: undefined })).toBe(false)
    expect(isComplete({ ...stations, stations: ['a', 'a'] })).toBe(false)
    expect(isComplete({ ...stations, stations: ['a'] })).toBe(false)
    expect(isComplete({ ...stations, period: undefined })).toBe(false)
  })

  it('writes the ids of the state a station has not yet been restored for, and the periods that are valid', () => {
    const address = addressOf({ by: 'stations', resolution: 'daily', parameter: 'p', idA: 'a', idB: 'b', period: { start: '2026-03-31', end: '2026-03-01' }, periodA: {}, periodB: {} })
    expect(address).toEqual({ by: 'stations', resolution: 'daily', parameter: 'p', stations: ['a', 'b'] })
  })
})

describe('the files', () => {
  const rows = alignStations([day('2026-03-01', 1)], [day('2026-03-01', 3)], { start: '2026-03-01', end: '2026-03-02' }, 'daily')
  const description = {
    by: 'stations' as const,
    parameter: 'temperature_air_mean_2m',
    resolution: 'daily',
    unit: '°C',
    aggregation: 'mean',
    sides: { a: { name: 'Kiel (02564)', period: '2026-03-01/2026-03-02' }, b: { name: 'Hamburg (01975)', period: '2026-03-01/2026-03-02' } },
    alignment: 'calendar' as const,
    difference: 'B - A' as const,
  }

  it('hold both sides and the difference of every step, with the credit as comments before the header', () => {
    const csv = compareToCsv(rows, description, ['Source: Deutscher Wetterdienst', '', 'Side A: Kiel. Side B: Hamburg.'])
    const lines = csv.split('\n')
    expect(lines.filter(line => line.startsWith('#'))).toEqual(['# temperature_air_mean_2m (°C), daily, difference = B - A', '# Source: Deutscher Wetterdienst', '# Side A: Kiel. Side B: Hamburg.'])
    expect(lines.slice(3)).toEqual(['step,date_a,date_b,value_a,value_b,difference', '1,2026-03-01,2026-03-01,1,3,2', '2,2026-03-02,2026-03-02,,,'])
  })

  it('hold the sides, the numbers and the credit in the JSON, the rows under `values`', () => {
    const json = JSON.parse(compareToJson(rows, description, summarize(rows), { provider: { attribution: 'Source: DWD', license: null }, processing_note: 'A note.' }))
    expect(json.metadata.provider.attribution).toBe('Source: DWD')
    expect(json.metadata.processing_note).toBe('A note.')
    expect(json.metadata.compare.sides.b.name).toBe('Hamburg (01975)')
    expect(json.metadata.compare.summary.meanDifference).toBe(2)
    expect(json.values[0]).toEqual({ step: 1, date_a: '2026-03-01', date_b: '2026-03-01', value_a: 1, value_b: 3, difference: 2 })
    expect(json.values[1].difference).toBeNull()
  })
})
