import type { Station } from '#shared/types/api'
import type { StripesFetch, StripesRequest } from '../../app/utils/stripes-source'
import { describe, expect, it, vi } from 'vitest'
import { StripesRefusedError } from '../../app/utils/stripes-scale'
import { DWD_STRIPES_PARAMETER, fetchDwdStripesStations, fetchStripes, fetchStripesStations, hasLongRecord } from '../../app/utils/stripes-source'
import { recordOf } from '../helpers/stripes-answer'

// What the app reads for the climate stripes, and how it makes them of it (GH-4258): the generic API for DWD, the app's own
// server for GHCN's days. The fetch is a stand-in that answers as the API does; no stripes route of the backend is asked for.

function station(id: string, start: string | null, end: string | null, name = `Station ${id}`): Station {
  return {
    station_id: id,
    name,
    region: 'Berlin',
    latitude: 52,
    longitude: 13,
    elevation: 10,
    start_timestamp: start === null ? null : `${start}-01-01T00:00:00.000000+00:00`,
    end_timestamp: end === null ? null : `${end}-12-31T00:00:00.000000+00:00`,
  }
}

interface Call { url: string, query: Record<string, string> }

/** A fetch that answers each address from `answers` (a function of the query), and notes what it was asked */
function fetchOf(answers: Record<string, (query: Record<string, string>) => unknown>): { fetch: StripesFetch, calls: Call[] } {
  const calls: Call[] = []
  const fetch = (async (url: string, options?: { query?: Record<string, string> }) => {
    const query = options?.query ?? {}
    calls.push({ url, query })
    const answer = answers[url]
    if (!answer)
      throw new Error(`unexpected request ${url}`)
    return answer(query)
  }) as StripesFetch
  return { fetch, calls }
}

/** The answer of `/api/values` for a station's annual values, in the unit symbol the metadata names */
function valuesAnswer(record: Array<{ year: number, value: number | null, flags?: string | null }>, options: { unit?: string, name?: string, warnings?: Array<{ code: string }> } = {}) {
  return {
    metadata: {
      provider: { name_local: 'Deutscher Wetterdienst', attribution: 'Source: Deutscher Wetterdienst', license: { spdx_id: 'CC-BY-4.0', name: 'Creative Commons Attribution 4.0 International', url: 'https://creativecommons.org/licenses/by/4.0/' } },
      parameters: [{ name: options.name ?? 'temperature_air_mean_2m', unit: options.unit ?? '°C' }],
      warnings: options.warnings ?? [],
    },
    values: record.filter(item => item.value !== null).map(item => ({
      station_id: '01048',
      resolution: 'annual',
      dataset: 'climate_summary',
      parameter: options.name ?? 'temperature_air_mean_2m',
      timestamp: `${item.year}-01-01T00:00:00.000000+00:00`,
      value: item.value,
      quality_flags: item.flags ?? '1',
    })),
  }
}

describe('a station of DWD with a record long enough', () => {
  it.each([
    ['1950', '2020', true],
    ['2011', '2020', true], // 10 years, first to last
    ['2012', '2020', false], // 9
    ['2020', '2020', false],
  ])('%s to %s is listed: %s', (start, end, listed) => {
    expect(hasLongRecord(station('1', start, end))).toBe(listed)
  })

  it('is kept where it has no start or no end', () => {
    expect(hasLongRecord(station('1', null, '2020'))).toBe(true)
    expect(hasLongRecord(station('1', '2019', null))).toBe(true)
    expect(hasLongRecord(station('1', null, null))).toBe(true)
  })
})

describe('the stations DWD has stripes for', () => {
  it('are those of the historical annual record that span 10 years and still report, in the order of the listing, from /api/stations alone', async () => {
    const long = station('01048', '1934', '2025')
    const answers = {
      '/api/stations': (query: Record<string, string>) => ({
        stations: query.periods === 'historical'
          ? [long, station('00061', '1976', '1977'), station('00044', '1950', '2000'), station('05000', null, null), station('07000', '1990', '2025')]
          : [station('01048', '2020', '2026'), station('05000', '2020', '2026'), station('07000', '2020', '2026')],
      }),
    }
    const { fetch, calls } = fetchOf(answers)

    const stations = await fetchDwdStripesStations(fetch, 'temperature')

    // 00061 has too short a record, 00044 has stopped reporting (no recent record)
    expect(stations.map(item => item.station_id)).toEqual(['01048', '05000', '07000'])
    expect(stations[0]).toBe(long)
    expect(calls.map(call => call.url)).toEqual(['/api/stations', '/api/stations'])
    expect(calls.map(call => call.query.periods).sort()).toEqual(['historical', 'recent'])
    for (const call of calls)
      expect(call.query).toMatchObject({ provider: 'dwd', network: 'observation', parameters: DWD_STRIPES_PARAMETER.temperature, all: 'true' })
  })

  it('are listed for the parameter of the kind: the annual precipitation amount', async () => {
    const { fetch, calls } = fetchOf({ '/api/stations': () => ({ stations: [] }) })
    await fetchStripesStations(fetch, 'dwd', 'precipitation')
    expect(calls.every(call => call.query.parameters === 'annual/precipitation_more/precipitation_amount')).toBe(true)
  })

  it('are, for GHCN daily, those the app\'s own server lists for the kind, which it makes of the backend\'s lists of the elements: no read of them in the browser', async () => {
    const { fetch, calls } = fetchOf({ '/_ghcn/stations': () => ({ stations: [station('USW00094728', '1869', null)] }) })
    expect((await fetchStripesStations(fetch, 'ghcn', 'temperature')).map(item => item.station_id)).toEqual(['USW00094728'])
    expect(calls).toEqual([{ url: '/_ghcn/stations', query: { kind: 'temperature' } }])
  })
})

function request(overrides: Partial<StripesRequest> = {}): StripesRequest {
  return {
    source: 'dwd',
    kind: 'temperature',
    station: { station_id: '01048', name: 'Dresden-Klotzsche' },
    unitTargets: { temperature: 'degree_celsius' },
    ...overrides,
  }
}

const record = recordOf(1934, 2025, year => 8 + (year - 1934) * 0.02 + (year % 2 ? 0.3 : -0.3), [1990])

describe('the stripes of a station of DWD', () => {
  it('are made of its annual values from /api/values, asked for as the backend\'s stripes read them', async () => {
    const { fetch, calls } = fetchOf({ '/api/values': () => valuesAnswer(record) })

    const stripes = await fetchStripes(fetch, request())

    expect(calls).toEqual([{
      url: '/api/values',
      query: {
        provider: 'dwd',
        network: 'observation',
        parameters: 'annual/climate_summary/temperature_air_mean_2m',
        periods: 'historical',
        stations: '01048',
        shape: 'long',
        humanize: 'true',
        skip_empty: 'false',
        with_metadata: 'true',
        unit_targets: '{"temperature":"degree_celsius"}',
      },
    }])
    expect(stripes.series).toEqual({
      station: { station_id: '01048', name: 'Dresden-Klotzsche' },
      resolution: 'annual',
      dataset: 'climate_summary',
      parameter: 'temperature_air_mean_2m',
      unit: '°C',
      method: null,
    })
    // every year from the first to the last, the gap of 1990 a row with no value, the classes of the whole record
    expect(stripes.values).toHaveLength(92)
    expect(stripes.values.find(item => item.timestamp?.startsWith('1990'))).toMatchObject({ value: null, anomaly: null, stripe_class: null })
    expect(stripes.reference.centre).toMatchObject({ first_year: 1971, last_year: 2000, fallback: false })
    // the credit and the licence of the answer, for the file of the table
    expect(stripes.metadata?.provider).toMatchObject({ attribution: 'Source: Deutscher Wetterdienst', license: { name: 'Creative Commons Attribution 4.0 International' } })
  })

  it('reads the annual precipitation for the kind, and the unit of the unit asked for where the answer names none', async () => {
    const answer = valuesAnswer(record, { name: 'precipitation_amount' })
    answer.metadata.parameters = []
    const { fetch, calls } = fetchOf({ '/api/values': () => answer })
    const stripes = await fetchStripes(fetch, request({ kind: 'precipitation', unitTargets: { precipitation: 'millimeter' } }))
    expect(calls[0]!.query.parameters).toBe('annual/precipitation_more/precipitation_amount')
    expect(calls[0]!.query.unit_targets).toBe('{"precipitation":"millimeter"}')
    expect(stripes.series).toMatchObject({ dataset: 'precipitation_more', parameter: 'precipitation_amount', unit: 'mm' })
  })

  it('leave out a value a plausibility check flagged suspect, as no year with data', async () => {
    const flagged = record.map(item => item.year === 2001 ? { ...item, flags: '1,suspect:range' } : item)
    const { fetch } = fetchOf({ '/api/values': () => valuesAnswer(flagged) })
    const { values } = await fetchStripes(fetch, request())
    expect(values.find(item => item.timestamp?.startsWith('2001'))).toMatchObject({ value: null })
  })

  it('keep the classes of the whole record where a window of years is asked for, and send no window to the API', async () => {
    const { fetch, calls } = fetchOf({ '/api/values': () => valuesAnswer(record) })
    const whole = await fetchStripes(fetch, request())
    const window = await fetchStripes(fetch, request({ startYear: 2000, endYear: 2010 }))
    expect(window.reference).toEqual(whole.reference)
    expect(window.values.map(item => item.timestamp?.slice(0, 4))).toEqual(Array.from({ length: 11 }, (_, index) => String(2000 + index)))
    expect(window.values.map(item => item.stripe_class)).toEqual(whole.values.filter(item => Number(item.timestamp?.slice(0, 4)) >= 2000 && Number(item.timestamp?.slice(0, 4)) <= 2010).map(item => item.stripe_class))
    expect(Object.keys(calls[1]!.query)).not.toContain('start_year')
  })

  it('are refused as a 404 for a station the API does not know, as the backend\'s stripes were', async () => {
    const { fetch } = fetchOf({ '/api/values': () => ({ ...valuesAnswer([]), metadata: { warnings: [{ code: 'unknown-station' }] } }) })
    await expect(fetchStripes(fetch, request({ station: { station_id: '00011', name: 'x' } }))).rejects.toMatchObject({
      statusCode: 404,
      data: { detail: 'No station with a station_id similar to \'00011\' found' },
    })
  })

  it('are a failure to try again, a 502, where the lookup went without a listing of DWD\'s and the station is not found: an outage is never no such station', async () => {
    const answer = { ...valuesAnswer([]), metadata: { warnings: [{ code: 'file-skipped' }, { code: 'unknown-station' }] } }
    const { fetch } = fetchOf({ '/api/values': () => answer })
    const failure = await fetchStripes(fetch, request({ station: { station_id: '00011', name: 'x' } })).catch((error: unknown) => error)
    expect(failure).toBeInstanceOf(StripesRefusedError)
    expect(failure).toMatchObject({ statusCode: 502, data: { status: 502, type: 'urn:wetterdienst:problem:upstream-failed' } })
    expect((failure as Error).message).toContain('No station found for 00011. The lookup of the stations went without a listing of the provider')
    expect((failure as Error).message).toContain('Try again later.')
  })

  it('are refused as a 400 for a record of fewer than 10 years, naming it', async () => {
    const { fetch } = fetchOf({ '/api/values': () => valuesAnswer(recordOf(1976, 1977, () => 8)) })
    await expect(fetchStripes(fetch, request())).rejects.toMatchObject({
      statusCode: 400,
      reason: 'record-too-short',
      data: { detail: 'At least 10 years with data are required to scale climate stripes; station 01048 has data for 2 (from 1976 to 1977)' },
    })
  })

  it('are refused as a 400 for a window of fewer than two years, which is no record too short', async () => {
    const { fetch } = fetchOf({ '/api/values': () => valuesAnswer(record) })
    await expect(fetchStripes(fetch, request({ startYear: 2030, endYear: 2040 }))).rejects.toMatchObject({ statusCode: 400, reason: 'window-too-short' })
  })

  it('are refused as a 422 for a window that ends before it starts, before anything is read', async () => {
    const asked = vi.fn()
    const fetch = (async (...args: unknown[]) => asked(...args)) as StripesFetch
    const failure = await fetchStripes(fetch, request({ startYear: 1990, endYear: 1990 })).catch((error: unknown) => error)
    expect(failure).toBeInstanceOf(StripesRefusedError)
    expect(failure).toMatchObject({ statusCode: 422 })
    expect(asked).not.toHaveBeenCalled()
  })

  it('pass on a failure of the read as it is', async () => {
    const failure = Object.assign(new Error('Bad Gateway'), { statusCode: 502, data: { detail: 'The backend could not be reached.' } })
    const { fetch } = fetchOf({ '/api/values': () => {
      throw failure
    } })
    await expect(fetchStripes(fetch, request())).rejects.toBe(failure)
  })
})

describe('the stripes of a station of GHCN daily', () => {
  const answer = {
    metadata: { provider: { attribution: 'NOAA National Centers for Environmental Information (NCEI), Global Historical Climatology Network', license: { name: 'Creative Commons Zero v1.0 Universal', url: 'https://creativecommons.org/publicdomain/zero/1.0/' } } },
    series: { station_id: 'USW00094728', parameter: 'temperature_air_mean_2m', unit: '°F', method: 'midrange' as const },
    values: record.map(item => ({ timestamp: `${item.year}-01-01T00:00:00.000000+00:00`, value: item.value })),
  }

  it('are made of the annual values the app\'s own server calculates, asked for with the kind, the station and the unit', async () => {
    const { fetch, calls } = fetchOf({ '/_ghcn/annual': () => answer })

    const stripes = await fetchStripes(fetch, request({ source: 'ghcn', station: { station_id: 'USW00094728', name: 'NY CITY CENTRAL PARK' }, unitTargets: { temperature: 'degree_fahrenheit' } }))

    expect(calls).toEqual([{ url: '/_ghcn/annual', query: { kind: 'temperature', station: 'USW00094728', unit_targets: '{"temperature":"degree_fahrenheit"}' } }])
    expect(stripes.series).toMatchObject({ resolution: 'daily', dataset: 'data', parameter: 'temperature_air_mean_2m', unit: '°F', method: 'midrange' })
    expect(stripes.metadata?.provider?.attribution).toContain('NOAA')
    expect(stripes.values).toHaveLength(92)
    expect(stripes.reference.centre.fallback).toBe(false)
  })

  it('are refused as DWD\'s are where the years are too few, and a window is the page\'s own', async () => {
    const { fetch } = fetchOf({ '/_ghcn/annual': () => ({ ...answer, values: answer.values.slice(0, 5) }) })
    await expect(fetchStripes(fetch, request({ source: 'ghcn' }))).rejects.toMatchObject({ statusCode: 400 })
    const full = fetchOf({ '/_ghcn/annual': () => answer })
    const windowed = await fetchStripes(full.fetch, request({ source: 'ghcn', startYear: 2000, endYear: 2005 }))
    expect(windowed.values).toHaveLength(6)
    expect(full.calls[0]!.query).not.toHaveProperty('start_year')
  })

  it('never ask a stripes route of the backend', async () => {
    const { fetch, calls } = fetchOf({ '/api/values': () => valuesAnswer(record), '/_ghcn/annual': () => answer, '/api/stations': () => ({ stations: [] }), '/_ghcn/stations': () => ({ stations: [] }) })
    await fetchStripes(fetch, request())
    await fetchStripes(fetch, request({ source: 'ghcn' }))
    await fetchStripesStations(fetch, 'dwd', 'temperature')
    await fetchStripesStations(fetch, 'ghcn', 'temperature')
    expect(calls.map(call => call.url).filter(url => /stripes/.test(url))).toEqual([])
  })
})
