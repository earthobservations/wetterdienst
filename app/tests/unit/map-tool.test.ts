import { describe, expect, it } from 'vitest'
import {
  clickReach,
  DEFAULT_MEASURED,
  distanceKm,
  DOT_SLOP_PX,
  dotRadius,
  forecastLink,
  formatDistance,
  formatPosition,
  historyLink,
  LIST_RUNNING_WITHIN_DAYS,
  measurementsLink,
  nearestStations,
  nearestWithin,
  placed,
  REACH_KM,
  REPORTING_WITHIN_DAYS,
  reportingRule,
  searchStations,
  SELECTED_EDGE_PX,
  SELECTED_RADIUS_PX,
  stateFromQuery,
  stateToQuery,
  stationAt,
  stationFor,
  stripesLink,
  TAP_RADIUS_PX,
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

describe('whether a station is still reporting', () => {
  // the REST API gives a running station an end too: the day of its last value, some way behind today, by dataset
  const now = Date.parse('2026-11-07T12:00:00+00:00')
  const DAY = 86_400_000
  /** A station that ended `days` before `now` (null for none) */
  const endedAgo = (days: number | null) => ({ end_timestamp: days === null ? null : new Date(now - days * DAY).toISOString() })
  /** The stations of a list whose newest end is `newest` days ago, and the others `behind` days before that */
  const listOf = (newest: number, ...behind: number[]) => [endedAgo(newest), ...behind.map(days => endedAgo(newest + days))]

  it('compares a station with the newest end of its own list, so that each dataset sets its own clock: solar radiation is 38 days behind and still running', () => {
    const solar = listOf(38, 0, 0, 5, 400, 2000)
    const reporting = reportingRule(solar, now)
    expect(solar.map(reporting)).toEqual([true, true, true, true, false, false])
  })

  it('reads a list that is only a day or two behind the same way', () => {
    const daily = listOf(2, 0, 3, 30, 800)
    expect(daily.map(reportingRule(daily, now))).toEqual([true, true, true, true, false])
  })

  it('has a tolerance of 90 days behind the newest end: 90 reads as reporting, 91 as stopped', () => {
    const list = listOf(2, 89, 90, 91, 92)
    expect(list.map(reportingRule(list, now))).toEqual([true, true, true, false, false])
    expect(REPORTING_WITHIN_DAYS).toBe(90)
  })

  it('does not make a running station a closed one for being a publication behind: the stations of a list are up to a month apart', () => {
    // hourly wind: 276 stations at the newest end, 17 up to 30 days before it, and all running
    const wind = listOf(2, 0, 0, 12, 20, 30, 45)
    expect(wind.every(reportingRule(wind, now))).toBe(true)
  })

  it('keeps a list that is long behind running, where it is behind as a whole: snow water equivalent 215 days after the winter, an annual list 311', () => {
    const snow = listOf(215, 0, 20, 60, 400)
    expect(snow.map(reportingRule(snow, now))).toEqual([true, true, true, true, false])
    const annual = listOf(311, 0, 0, 365, 730)
    expect(annual.map(reportingRule(annual, now))).toEqual([true, true, true, false, false])
  })

  it('reads a list that has stopped as a whole as all closed: its newest end is more than 450 days ago', () => {
    const running = listOf(450, 0, 10)
    expect(running.every(reportingRule(running, now))).toBe(true)
    const stopped = listOf(451, 0, 10)
    expect(stopped.some(reportingRule(stopped, now))).toBe(false)
    // the weather phenomena that end in 2011, and the annual ones that end in 2024
    const phenomena = [{ end_timestamp: '2011-12-31T00:00:00+00:00' }, { end_timestamp: '2011-12-31T00:00:00+00:00' }]
    expect(phenomena.some(reportingRule(phenomena, now))).toBe(false)
    expect(REPORTING_WITHIN_DAYS).toBeLessThan(LIST_RUNNING_WITHIN_DAYS)
    expect(LIST_RUNNING_WITHIN_DAYS).toBe(450)
  })

  it('takes the newest end as no later than today: an end that is ahead of the clock does not make the running ones closed', () => {
    const ahead = [endedAgo(-200), endedAgo(3), endedAgo(10)]
    expect(ahead.map(reportingRule(ahead, now))).toEqual([true, true, true])
  })

  it('takes the clock from the ends that are not later than today: one end ahead does not make a list that is a publication behind read as closed', () => {
    // a list 38 days behind, as the solar radiation is, with one station whose end is 30 days in the future
    const solar = [...listOf(38, 0, 0, 5), endedAgo(-30)]
    const reporting = reportingRule(solar, now)
    expect(solar.map(reporting)).toEqual([true, true, true, true, true])
    // and the list that is ahead as a whole is not a clock of the future: it has only the ends of the future, so none
    const ahead = [endedAgo(-5), endedAgo(-30)]
    expect(ahead.some(reportingRule(ahead, now))).toBe(false)
  })

  it('says a station with no end is not reporting, and nor is a list of none: its status is not known', () => {
    const list = [endedAgo(1), endedAgo(null), { end_timestamp: 'soon' }]
    expect(list.map(reportingRule(list, now))).toEqual([true, false, false])
    const none = [endedAgo(null), endedAgo(null)]
    expect(none.some(reportingRule(none, now))).toBe(false)
    expect(reportingRule([], now)({ end_timestamp: '2026-11-01T00:00:00+00:00' })).toBe(false)
  })

  it('reads today from the clock it is given', () => {
    const list = listOf(2, 0)
    const later = now + 449 * DAY
    // the same list 449 days on: its newest end is 451 days old, and the list has stopped
    expect(list.some(reportingRule(list, later))).toBe(false)
    expect(list.every(reportingRule(list, now))).toBe(true)
  })
})

describe('what a click reaches', () => {
  it('is the dot as drawn and a little more, not a circle of twelve pixels: at the opening zoom a dot is 2.75 px, and the click reaches 4.75', () => {
    expect(dotRadius(6)).toBe(2.75)
    expect(DOT_SLOP_PX).toBe(2)
    expect(clickReach(6, false).dot).toBe(4.75)
    expect(clickReach(6, false).dot).toBeLessThan(12)
    expect(clickReach(10, false).dot).toBe(7)
  })

  it('follows the radius the dots are drawn with at each zoom', () => {
    expect([2, 4, 5, 6, 7, 8, 9, 14].map(zoom => dotRadius(zoom))).toEqual([1.75, 1.75, 2.75, 2.75, 3.75, 3.75, 5, 5])
    expect([2, 6, 8, 12].map(zoom => clickReach(zoom, false).dot)).toEqual([3.75, 4.75, 5.75, 7])
  })

  it('has the disc of the station picked, which is drawn larger than a dot: its radius, half its edge and a little more', () => {
    expect(SELECTED_RADIUS_PX).toBe(9)
    expect(SELECTED_EDGE_PX).toBe(3)
    expect(clickReach(6, false).disc).toBe(12.5)
    expect(clickReach(6, true).disc).toBe(12.5)
    // larger than the dot at every zoom, which is why a click on the disc is a click on the station and not on the map
    for (const zoom of [2, 6, 12])
      expect(clickReach(zoom, false).disc).toBeGreaterThan(clickReach(zoom, false).dot)
  })

  it('has a ring for a tap of a finger, and none for a mouse', () => {
    expect(clickReach(6, false).tap).toBe(0)
    expect(clickReach(6, true).tap).toBe(12)
    expect(clickReach(6, true).tap).toBe(TAP_RADIUS_PX)
    // the ring is never narrower than the dot's own reach
    expect(clickReach(14, true).tap).toBeGreaterThanOrEqual(clickReach(14, true).dot)
  })
})

describe('the station picked for a place', () => {
  const running = (id: string, latitude: number, longitude: number) => ({ ...station(id, id, latitude, longitude), end_timestamp: '2026-11-06T00:00:00+00:00' })
  const closed = (id: string, latitude: number, longitude: number) => ({ ...station(id, id, latitude, longitude), end_timestamp: '2001-12-31T00:00:00+00:00' })
  const live = (entry: { end_timestamp?: string }) => entry.end_timestamp !== '2001-12-31T00:00:00+00:00'
  const here = { latitude: 53.5, longitude: 10 }
  const list = placed([closed('near-closed', 53.51, 10), running('far-running', 53.9, 10), running('too-far', 50, 10)])

  it('is the nearest that is still reporting within reach, though a closed one is nearer', () => {
    expect(stationFor(list, here, live)!.station.station_id).toBe('far-running')
  })

  it('is the nearest closed one where none that reports is within reach', () => {
    const found = stationFor(placed([closed('near-closed', 53.51, 10), running('too-far', 50, 10)]), here, live)
    expect(found!.station.station_id).toBe('near-closed')
  })

  it('is the nearest of all where no rule says which are running', () => {
    expect(stationFor(list, here)!.station.station_id).toBe('near-closed')
  })

  it('is none beyond reach, whatever the rule', () => {
    expect(stationFor(placed([running('too-far', 50, 10)]), here, live)).toBeNull()
    expect(stationFor(placed([running('too-far', 50, 10)]), here)).toBeNull()
  })

  it('is the station a point is on, within the tolerance, whatever its status, and none farther', () => {
    expect(stationAt(list, { latitude: 53.5105, longitude: 10 }, 0.5)!.station_id).toBe('near-closed')
    expect(stationAt(list, here, 0.5)).toBeNull()
  })
})
