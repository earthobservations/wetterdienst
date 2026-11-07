import { describe, expect, it } from 'vitest'
import {
  DEFAULT_MEASURED,
  distanceKm,
  forecastLink,
  formatDistance,
  formatPosition,
  historyLink,
  measurementsLink,
  nearestStations,
  nearestWithin,
  placed,
  REACH_KM,
  searchStations,
  stateFromQuery,
  stateToQuery,
  stripesLink,
} from '../../app/utils/map-tool'

// The map tool's logic (GH-3650): what is nearest to a place, how a station is found, where a station is opened and
// what the address says of the map.

function station(station_id: string, name: string | null, latitude: number | null, longitude: number | null) {
  return { station_id, name, region: null, latitude, longitude, elevation: null }
}

const KIEL = station('02564', 'Kiel-Holtenau', 54.3776, 10.1424)
const HAMBURG = station('01975', 'Hamburg-Fuhlsbüttel', 53.6332, 9.9881)
const MUNICH = station('03379', 'München-Stadt', 48.1632, 11.5429)
const POSTCODE = station('01067', null, null, null)
const ALL = placed([KIEL, HAMBURG, MUNICH, POSTCODE])

describe('the distance of two points', () => {
  it('is the haversine distance in kilometres', () => {
    expect(distanceKm({ latitude: 52.52, longitude: 13.4 }, { latitude: 48.14, longitude: 11.58 })).toBeCloseTo(504, -1)
    expect(distanceKm(KIEL as never, KIEL as never)).toBe(0)
  })
})

describe('the stations that have a position', () => {
  it('leave out one that has none, which a map cannot show and a distance cannot be taken to', () => {
    expect(ALL.map(entry => entry.station_id)).toEqual(['02564', '01975', '03379'])
  })
})

describe('the nearest stations to a point', () => {
  const here = { latitude: 54.32, longitude: 10.14 }

  it('are the nearest first, each with its distance', () => {
    const [first, second] = nearestStations(ALL, here, 2)
    expect(first!.station.station_id).toBe('02564')
    expect(first!.distance).toBeLessThan(10)
    expect(second!.station.station_id).toBe('01975')
    expect(second!.distance).toBeGreaterThan(first!.distance)
  })

  it('are no more than asked for, and none for an empty list', () => {
    expect(nearestStations(ALL, here, 1)).toHaveLength(1)
    expect(nearestStations([], here, 3)).toEqual([])
  })

  it('does not depend on the order of the list', () => {
    expect(nearestStations([...ALL].reverse(), here, 1)[0]!.station.station_id).toBe('02564')
  })
})

describe('the nearest station within reach', () => {
  it('is the nearest, when it is within the reach of the panel', () => {
    const found = nearestWithin(ALL, { latitude: 53.5, longitude: 10 })
    expect(found!.station.station_id).toBe('01975')
    expect(found!.distance).toBeLessThanOrEqual(REACH_KM)
  })

  it('is none where the nearest is another place\'s: a point in France is not near a German station', () => {
    expect(nearestWithin(ALL, { latitude: 46.5, longitude: 2.5 })).toBeNull()
  })

  it('is none for an empty list', () => {
    expect(nearestWithin([], { latitude: 53.5, longitude: 10 })).toBeNull()
  })
})

describe('the search of the stations', () => {
  it('finds a station by the start of its name, without regard to case or accents', () => {
    expect(searchStations(ALL, 'munchen').map(entry => entry.station_id)).toEqual(['03379'])
    expect(searchStations(ALL, 'KIEL').map(entry => entry.station_id)).toEqual(['02564'])
  })

  it('finds a station by its number, and by every word of a query', () => {
    expect(searchStations(ALL, '01975').map(entry => entry.station_id)).toEqual(['01975'])
    expect(searchStations(ALL, 'hamburg buttel').map(entry => entry.station_id)).toEqual(['01975'])
    expect(searchStations(ALL, 'hamburg kiel')).toEqual([])
  })

  it('puts the names that start with the query before those that hold it', () => {
    const list = placed([station('1', 'Bad Kiel', 50, 8), station('2', 'Kiel-Holtenau', 54, 10)])
    expect(searchStations(list, 'kiel').map(entry => entry.station_id)).toEqual(['2', '1'])
  })

  it('finds nothing for an empty query, and no more than the limit', () => {
    expect(searchStations(ALL, '   ')).toEqual([])
    expect(searchStations(ALL, 'a', 1)).toHaveLength(1)
  })
})

describe('a distance as a reader says it', () => {
  it.each([
    [0.42, 'en', '420 m'],
    [3.24, 'en', '3.2 km'],
    [3.24, 'de', '3,2 km'],
    [42.4, 'en', '42 km'],
    [100, 'en', '100 km'],
  ])('%s km in %s is %s', (km, locale, text) => {
    // the unit and the number are written the way the language does; a no-break space may stand between them
    expect(formatDistance(km, locale).replace(/\u202F|\xA0/g, ' ')).toBe(text)
  })
})

describe('a position', () => {
  it('is signed degrees with a point, as it is copied into a map or a query, in every language', () => {
    expect(formatPosition({ latitude: 54.3776, longitude: -10.1424 })).toBe('54.3776, -10.1424')
  })
})

describe('where a station is opened', () => {
  it('has its forecast on the forecast page', () => {
    expect(forecastLink('10147')).toBe('/meteogram?station=10147')
  })

  it('has its stripes on the stripes page, for the temperature', () => {
    expect(stripesLink('00011')).toBe('/stripes?kind=temperature&station=00011')
  })

  it('has its measurements in the explorer, on the source and with the station chosen', () => {
    const link = new URL(measurementsLink({ resolution: 'hourly', dataset: 'temperature_air' }, '00011'), 'http://x')
    expect(link.pathname).toBe('/explorer')
    expect(Object.fromEntries(link.searchParams)).toEqual({
      provider: 'dwd',
      network: 'observation',
      resolution: 'hourly',
      dataset: 'temperature_air',
      mode: 'station',
      stations: '00011',
    })
  })

  it('has its history in the station history, on the source and with the station chosen', () => {
    const link = new URL(historyLink(DEFAULT_MEASURED, '00011'), 'http://x')
    expect(link.pathname).toBe('/history')
    expect(Object.fromEntries(link.searchParams)).toEqual({
      provider: 'dwd',
      network: 'observation',
      resolution: 'daily',
      dataset: 'climate_summary',
      stations: '00011',
    })
  })
})

describe('the address of the map', () => {
  const plain = { layer: 'forecast' as const, source: DEFAULT_MEASURED, stationId: null, place: null }

  it('is empty for the plain map, so that its link is /map', () => {
    expect(stateToQuery(plain)).toEqual({})
    expect(stateFromQuery({})).toEqual(plain)
  })

  it('names the layer, the source of the measurements, the station and the place picked when they are not the default', () => {
    const state = { layer: 'measured' as const, source: { resolution: 'hourly', dataset: 'temperature_air' }, stationId: '00011', place: { latitude: 47.91234, longitude: 8.51234 } }
    expect(stateToQuery(state)).toEqual({ layer: 'measured', resolution: 'hourly', dataset: 'temperature_air', station: '00011', lat: '47.9123', lon: '8.5123' })
    expect(stateFromQuery(stateToQuery(state))).toEqual({ ...state, place: { latitude: 47.9123, longitude: 8.5123 } })
  })

  it('takes a station of the search (`?station=`) on the forecast layer', () => {
    expect(stateFromQuery({ station: '10147' })).toEqual({ ...plain, stationId: '10147' })
  })

  it('leaves a place out where there is no station, and a place that is no position', () => {
    expect(stateToQuery({ ...plain, place: { latitude: 50, longitude: 8 } })).toEqual({})
    expect(stateFromQuery({ station: '1', lat: 'north', lon: '8' }).place).toBeNull()
    expect(stateFromQuery({ station: '1', lat: '95', lon: '8' }).place).toBeNull()
    expect(stateFromQuery({ lat: '50', lon: '8' }).place).toBeNull()
  })

  it('is the default layer where the address names one there is none of', () => {
    expect(stateFromQuery({ layer: 'satellite' }).layer).toBe('forecast')
    expect(stateFromQuery({ layer: ['measured', 'forecast'] }).layer).toBe('measured')
  })
})
