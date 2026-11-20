import { describe, expect, it, vi } from 'vitest'
import {
  clickReach,
  closerStoppedStation,
  DEFAULT_MEASURED,
  distanceKm,
  DOT_SLOP_PX,
  dotRadius,
  findSameStation,
  forecastLink,
  formatDistance,
  formatPosition,
  GHCN_SOURCE,
  ghcnReportingRule,
  historyLink,
  LIST_RUNNING_WITHIN_DAYS,
  matchByWmo,
  measurementsLink,
  nearestStations,
  nearestWithin,
  placed,
  prepareSearch,
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
  wmoNumber,
  yearOf,
} from '../../app/utils/map-tool'
import { chromeWithoutLuxembourgish } from '../helpers/chrome-without-luxembourgish'

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

  describe('of a list that is prepared (GH-4267: 133k names are folded once, not at every keystroke)', () => {
    const NAMES = [station('1', 'Bad Kiel', 50, 8), station('2', 'Kiel-Holtenau', 54, 10), station('3', 'München-Stadt', 48, 11.5), station('4', 'KIELER STRASSE', 50, 9), station('5', null, 51, 9), station('GM000010147', 'HAMBURG FUHLSBUETTEL', 53.6, 10), station('7', 'Hamburg-Fuhlsbüttel', 53.6, 10)]
    const LIST = placed(NAMES)
    const QUERIES = ['kiel', 'KIEL', 'munchen', 'müncHEN', 'hamburg buttel', 'hamburg fuhlsbuttel', 'gm000010147', '5', 'a', 'zzz', '   ', 'kiel hamburg', 'strasse']

    it('finds what the search of the list as it comes does, in the same order, for every query', () => {
      const prepared = [...LIST]
      prepareSearch(prepared)
      for (const query of QUERIES) {
        expect(searchStations(prepared, query).map(entry => entry.station_id), query).toEqual(searchStations(LIST, query).map(entry => entry.station_id))
        expect(searchStations(prepared, query, 2).map(entry => entry.station_id), query).toEqual(searchStations(LIST, query, 2).map(entry => entry.station_id))
      }
    })

    it('folds the query at a keystroke and no name, however long the list: the names were folded when the list was prepared', () => {
      const prepared = [...LIST]
      prepareSearch(prepared)
      const normalize = vi.spyOn(String.prototype, 'normalize')
      try {
        searchStations(prepared, 'münchen stadt')
        expect(normalize).toHaveBeenCalledTimes(1)
        normalize.mockClear()
        // the list that is not prepared folds its names at every call
        searchStations(LIST, 'münchen stadt')
        expect(normalize.mock.calls.length).toBeGreaterThan(LIST.length)
      }
      finally {
        normalize.mockRestore()
      }
    })

    it('is a list\'s own: another array of the same stations is searched as it comes', () => {
      prepareSearch([...LIST])
      const normalize = vi.spyOn(String.prototype, 'normalize')
      try {
        expect(searchStations([...LIST], 'kiel').map(entry => entry.station_id)).toEqual(['2', '4', '1'])
        expect(normalize.mock.calls.length).toBeGreaterThan(LIST.length)
      }
      finally {
        normalize.mockRestore()
      }
    })
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

  it('writes Luxembourgish as German, where the browser has no data for it', () => {
    // Chrome has none and would write the system's language: here English, "3.2 km"
    const chrome = chromeWithoutLuxembourgish()
    try {
      expect(formatDistance(3.24, 'lb').replace(/\u202F|\xA0/g, ' ')).toBe('3,2 km')
      expect(chrome.passed.filter(language => language.startsWith('lb'))).toEqual([])
    }
    finally {
      chrome.restore()
    }
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

  it('has the stripes of a station of GHCN daily on the stripes page with its provider and network', () => {
    expect(stripesLink('GM000010147', true)).toBe('/stripes?kind=temperature&provider=noaa&network=ghcn&station=GM000010147')
  })

  it('has the measurements of a station of GHCN daily in the explorer, on the network of the layer', () => {
    const link = new URL(measurementsLink(GHCN_SOURCE, 'GM000010147', { provider: 'noaa', network: 'ghcn' }), 'http://x')
    expect(Object.fromEntries(link.searchParams)).toEqual({
      provider: 'noaa',
      network: 'ghcn',
      resolution: 'daily',
      dataset: 'data',
      mode: 'station',
      stations: 'GM000010147',
    })
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

describe('why a farther station was picked (GH-3875)', () => {
  const now = Date.parse('2026-11-07T12:00:00Z')
  const ended = (end: string | null) => ({ end_timestamp: end })
  // the place of the issue: central Hamburg, two stations that stopped long ago nearer than the one that reports
  const PLACE = { latitude: 53.551, longitude: 9.994 }
  const SEEWARTE = { ...station('15526', 'Hamburg (Deutsche Seewarte)', 53.547, 9.976), ...ended('1935-12-31T00:00:00+00:00') }
  const SANKT_PAULI = { ...station('01987', 'Hamburg-Sankt Pauli', 53.5543, 9.9672), ...ended('2000-02-29T00:00:00+00:00') }
  const FUHLSBUETTEL = { ...station('01975', 'Hamburg-Fuhlsbüttel', 53.6332, 9.9881), ...ended('2026-11-06T00:00:00+00:00') }
  const NEUWIEDENTHAL = { ...station('01981', 'Hamburg-Neuwiedenthal', 53.4777, 9.8977), ...ended('2026-11-06T00:00:00+00:00') }
  const LIST = placed([SEEWARTE, SANKT_PAULI, FUHLSBUETTEL, NEUWIEDENTHAL] as never[])
  const reporting = reportingRule(LIST, now)
  const [seewarte, sanktPauli, fuhlsbuettel] = LIST

  it('names the nearest station that has stopped, with its distance and the year its record ends in, when the picked one reports', () => {
    const closer = closerStoppedStation(LIST, PLACE, fuhlsbuettel!, reporting)
    // the nearest of all is the Seewarte (1.3 km from the place), which stopped in 1935
    expect(closer?.station.station_id).toBe('15526')
    expect(closer?.endYear).toBe(1935)
    expect(closer?.distance).toBeCloseTo(distanceKm(PLACE, seewarte!), 6)
    expect(closer?.distance).toBeLessThan(distanceKm(PLACE, fuhlsbuettel!))
  })

  it('is the second station when that is the nearest: the one picked is not the nearest, and the nearest is what is named', () => {
    const closer = closerStoppedStation(LIST.filter(entry => entry.station_id !== '15526'), PLACE, fuhlsbuettel!, reporting)
    expect(closer).toMatchObject({ station: { name: 'Hamburg-Sankt Pauli' }, endYear: 2000 })
    expect(closer!.distance).toBeCloseTo(1.8, 0)
  })

  it('is null where the station picked is the nearest', () => {
    const near = { latitude: 53.6332, longitude: 9.9881 }
    expect(closerStoppedStation(LIST, near, fuhlsbuettel!, reporting)).toBeNull()
  })

  it('is null where the station picked has itself stopped: no rule put it before a nearer one', () => {
    expect(closerStoppedStation(LIST, PLACE, sanktPauli!, reporting)).toBeNull()
  })

  it('is null where the nearer station reports too: it is not the rule that passed it over', () => {
    const both = placed([{ ...SANKT_PAULI, ...ended('2026-11-05T00:00:00+00:00') }, FUHLSBUETTEL] as never[])
    expect(closerStoppedStation(both, PLACE, both[1]!, reportingRule(both, now))).toBeNull()
  })

  it('is null where the station picked is not the one the rule picks for the place: a station chosen from the list or by the address (?station=01981&lat=53.551&lon=9.994)', () => {
    // the rule picks Hamburg-Fuhlsbüttel (9.1 km) for the place, and Neuwiedenthal (10.4 km) is the reader's own choice
    expect(stationFor(LIST, PLACE, reporting)?.station.station_id).toBe('01975')
    const neuwiedenthal = LIST.find(entry => entry.station_id === '01981')!
    expect(reporting(neuwiedenthal)).toBe(true)
    expect(closerStoppedStation(LIST, PLACE, neuwiedenthal, reporting)).toBeNull()
  })

  it('has no year for a station whose list gives it no end', () => {
    const list = placed([{ ...SANKT_PAULI, ...ended(null) }, FUHLSBUETTEL] as never[])
    const closer = closerStoppedStation(list, PLACE, list[1]!, reportingRule(list, now))
    expect(closer).toMatchObject({ station: { station_id: '01987' }, endYear: null })
  })

  it('agrees with the rule that picks the station: where it picks a farther one over a nearer one, the nearer one is named', () => {
    const picked = stationFor(LIST, PLACE, reporting)!
    expect(picked.station.station_id).toBe('01975')
    expect(closerStoppedStation(LIST, PLACE, picked.station, reporting)).not.toBeNull()
  })

  it('reads the year of a timestamp in UTC, and no year of what is no date', () => {
    expect(yearOf('2000-02-29T00:00:00+00:00')).toBe(2000)
    expect(yearOf('2018-12-31T23:59:59+00:00')).toBe(2018)
    expect(yearOf(null)).toBeNull()
    expect(yearOf(undefined)).toBeNull()
    expect(yearOf('not a date')).toBeNull()
  })
})

describe('the WMO number of a station (GH-4077)', () => {
  it('is the five digits of the number, and none where the station has none', () => {
    expect(wmoNumber({ wmo_id: '10147' })).toBe('10147')
    expect(wmoNumber({ wmo_id: ' 10147 ' })).toBe('10147')
    // the REST API reads '1001' as '01001': the number is compared as it is written with its padding
    expect(wmoNumber({ wmo_id: '1001' })).toBe('01001')
    expect(wmoNumber({ wmo_id: null })).toBeNull()
    expect(wmoNumber({ wmo_id: '' })).toBeNull()
    expect(wmoNumber({ wmo_id: '   ' })).toBeNull()
    expect(wmoNumber({})).toBeNull()
  })

  it('leaves a number that is not digits as it is: no padding is made up for a text', () => {
    expect(wmoNumber({ wmo_id: 'X379' })).toBe('X379')
  })
})

describe('the station of a list that has a WMO number', () => {
  const withWmo = (id: string, wmo: string | null, latitude = 50, longitude = 10) => ({ ...station(id, id, latitude, longitude), wmo_id: wmo })
  const LIST = placed([withWmo('01975', '10147'), withWmo('02564', '10025', 54.4, 10.1), withWmo('03379', null, 48.2, 11.5), withWmo('09999', '10147', 53.6, 10.0)])

  it('is the one station that has it, found by the number whatever the ids are', () => {
    const match = matchByWmo(LIST, '10025')
    expect(match).toEqual({ kind: 'one', station: LIST[1] })
  })

  it('finds nothing where the list has no station with the number, or the station has none', () => {
    expect(matchByWmo(LIST, '99999')).toEqual({ kind: 'none' })
    expect(matchByWmo(LIST, null)).toEqual({ kind: 'none' })
    expect(matchByWmo(LIST, undefined)).toEqual({ kind: 'none' })
    expect(matchByWmo(LIST, '')).toEqual({ kind: 'none' })
    // a station with no number of its own is never found by "no number"
    expect(matchByWmo(LIST, '  ')).toEqual({ kind: 'none' })
  })

  it('finds none of the stations where the number is on several: it is not one place, and no station is guessed', () => {
    const match = matchByWmo(LIST, '10147')
    expect(match.kind).toBe('several')
    expect(match.kind === 'several' && match.stations.map(entry => entry.station_id)).toEqual(['01975', '09999'])
  })

  it('reads the number as the stations do: padded, trimmed', () => {
    expect(matchByWmo(placed([withWmo('01001', '1001')]), '01001').kind).toBe('one')
    expect(matchByWmo(placed([withWmo('01001', '01001')]), ' 1001').kind).toBe('one')
  })
})

describe('the same station in the list of another layer (GH-4077)', () => {
  const NOW = Date.now()
  const day = (days: number) => new Date(NOW - days * 86_400_000).toISOString()
  const withWmo = (id: string, wmo: string | null, end: string | null = day(1)) => ({ ...station(id, id, 50, 10), wmo_id: wmo, start_timestamp: null, end_timestamp: end })
  const picked = (overrides = {}) => ({ station_id: '02483', wmo: '10427', observation: false, reports: true, ...overrides })

  it('is the station that has the number of the one picked', () => {
    const list = placed([withWmo('X1', '10427'), withWmo('X2', '10999')])
    expect(findSameStation(list, picked(), true)).toEqual({ station: list[0], by: 'wmo' })
  })

  it('is the station of the same id where both lists are the observations, before any number', () => {
    const list = placed([withWmo('02483', null), withWmo('X1', '10427')])
    expect(findSameStation(list, picked({ observation: true }), true)).toEqual({ station: list[0], by: 'id' })
    // an id of another network is no station of this one
    expect(findSameStation(list, picked({ observation: false }), true)).toEqual({ station: list[1], by: 'wmo' })
    expect(findSameStation(list, picked({ observation: true }), false)).toEqual({ station: list[1], by: 'wmo' })
  })

  it('is not a station that has stopped where the station picked reports: a closed predecessor keeps the number', () => {
    // 10427 was Altastenberg (00098) until 1954 and is Kahler Asten (02483) after
    const closed = placed([withWmo('00098', '10427', '1954-12-31T00:00:00+00:00'), withWmo('X1', null)])
    const reporting = reportingRule(closed, NOW)
    expect(findSameStation(closed, picked(), true, reporting)).toBeNull()
    // where the station picked has stopped too, or the list has no status, it is taken
    expect(findSameStation(closed, picked({ reports: false }), true, reporting)).toEqual({ station: closed[0], by: 'wmo' })
    expect(findSameStation(closed, picked(), false)).toEqual({ station: closed[0], by: 'wmo' })
  })

  it('is none where the number is on several stations or on none, or the station has none', () => {
    const list = placed([withWmo('A', '10427'), withWmo('B', '10427')])
    expect(findSameStation(list, picked(), true)).toBeNull()
    expect(findSameStation(list, picked({ wmo: '99999' }), true)).toBeNull()
    expect(findSameStation(list, picked({ wmo: null }), true)).toBeNull()
  })
})

describe('whether a station of GHCN daily still reports (GH-4078)', () => {
  const NOW = Date.UTC(2026, 10, 19)
  const rule = ghcnReportingRule(NOW)

  it('reports with no end (its last year is this one) and with an end in last year', () => {
    expect(rule({ end_timestamp: null })).toBe(true)
    expect(rule({ end_timestamp: '2025-12-31T00:00:00.000000+00:00' })).toBe(true)
  })

  it('has stopped where its record ends before last year, or the end is no date', () => {
    expect(rule({ end_timestamp: '2024-12-31T00:00:00.000000+00:00' })).toBe(false)
    expect(rule({ end_timestamp: 'never' })).toBe(false)
  })
})

describe('the address of the GHCN layer (GH-4078)', () => {
  it('names the layer and the station, and is read back', () => {
    const state = { layer: 'ghcn' as const, source: DEFAULT_MEASURED, stationId: 'GM000010147', place: null }
    expect(stateToQuery(state)).toEqual({ layer: 'ghcn', station: 'GM000010147' })
    expect(stateFromQuery({ layer: 'ghcn', station: 'GM000010147' })).toEqual(state)
  })
})
