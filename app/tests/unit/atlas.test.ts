import type { PlacedStation } from '../../app/utils/atlas'
import { describe, expect, it } from 'vitest'
import {
  distanceKm,
  formatDistance,
  formatPosition,
  historyLink,
  measurementsLink,
  nearestStations,
  placed,
  searchStations,
  stripesLink,
} from '../../app/utils/atlas'
import { COLOR_MAPS, stripeColour } from '../../app/utils/stripes'

function station(station_id: string, name: string | null, latitude: number, longitude: number): PlacedStation {
  return { station_id, name, region: null, latitude, longitude, elevation: null, start_timestamp: null, end_timestamp: null }
}

const BERLIN = station('10384', 'BERLIN-TEMPELHOF', 52.47, 13.4)
const HAMBURG = station('10147', 'HAMBURG-FUHLSBUETTEL', 53.63, 10.0)
const MUNICH = station('10865', 'MÜNCHEN-STADT', 48.16, 11.54)
const JAN_MAYEN = station('01001', 'JAN MAYEN', 70.93, -8.67)
const STATIONS = [BERLIN, HAMBURG, MUNICH, JAN_MAYEN]

describe('the distance of two places', () => {
  it('is the great-circle distance in kilometres', () => {
    // Berlin to Munich is about 500 km as the crow flies
    expect(distanceKm(BERLIN, MUNICH)).toBeGreaterThan(490)
    expect(distanceKm(BERLIN, MUNICH)).toBeLessThan(520)
    expect(distanceKm(BERLIN, BERLIN)).toBe(0)
  })

  it('is the same both ways', () => {
    expect(distanceKm(HAMBURG, JAN_MAYEN)).toBeCloseTo(distanceKm(JAN_MAYEN, HAMBURG), 9)
  })
})

describe('the stations nearest to a place', () => {
  it('are nearest first, with their distances, as many as asked for', () => {
    const found = nearestStations(STATIONS, { latitude: 53.5, longitude: 10.2 }, 2)
    expect(found.map(entry => entry.station.station_id)).toEqual(['10147', '10384'])
    expect(found[0]!.distance).toBeLessThan(found[1]!.distance)
  })

  it('are none in an empty list, and all of a short one', () => {
    expect(nearestStations([], BERLIN, 3)).toEqual([])
    expect(nearestStations(STATIONS, BERLIN, 10)).toHaveLength(4)
  })
})

describe('only the stations with a position', () => {
  it('are kept for the map', () => {
    expect(placed([BERLIN, { ...HAMBURG, latitude: null, longitude: null }]).map(entry => entry.station_id)).toEqual(['10384'])
  })
})

describe('the search for a station', () => {
  it('finds a name without its accents, and a name that starts with the query first', () => {
    expect(searchStations(STATIONS, 'munchen').map(entry => entry.station_id)).toEqual(['10865'])
    expect(searchStations(STATIONS, 'mayen').map(entry => entry.station_id)).toEqual(['01001'])
  })

  it('finds an id, and every word of the query', () => {
    expect(searchStations(STATIONS, '10147').map(entry => entry.station_id)).toEqual(['10147'])
    expect(searchStations(STATIONS, 'berlin tempel').map(entry => entry.station_id)).toEqual(['10384'])
    expect(searchStations(STATIONS, 'berlin hamburg')).toEqual([])
  })

  it('finds nothing for nothing', () => {
    expect(searchStations(STATIONS, '  ')).toEqual([])
  })
})

describe('a distance and a position, as a reader writes them', () => {
  it('in metres under a kilometre, with a decimal under ten and whole kilometres beyond', () => {
    expect(formatDistance(0.234, 'en')).toBe('230 m')
    expect(formatDistance(3.25, 'en')).toBe('3.3 km')
    expect(formatDistance(3.25, 'de')).toBe('3,3 km')
    expect(formatDistance(123.4, 'en')).toBe('123 km')
  })

  it('in degrees with the hemisphere', () => {
    expect(formatPosition(52.47, 13.4, 'en')).toBe('52.47° N, 13.40° E')
    expect(formatPosition(-33.9, -70.65, 'de')).toBe('33,90° S, 70,65° W')
  })
})

describe('the pages a station is opened on', () => {
  const source = { provider: 'dwd', network: 'observation', resolution: 'daily', dataset: 'climate_summary' }

  it('are the explorer with the source and the station chosen, and the stripes of the temperature', () => {
    expect(measurementsLink(source, '00011')).toBe('/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&mode=station&stations=00011')
    expect(stripesLink('00011')).toBe('/stripes?kind=temperature&station=00011')
  })

  it('include the history only for DWD\'s observations, the one network that has it', () => {
    expect(historyLink(source, '00011')).toBe('/history?resolution=daily&dataset=climate_summary&stations=00011')
    expect(historyLink({ ...source, provider: 'noaa', network: 'ghcn' }, 'X')).toBeNull()
  })
})

describe('the colour of a stripe', () => {
  it('is a stop of the scale where it is one, and between two stops a mix of them', () => {
    expect(stripeColour(COLOR_MAPS.temperature, 0)).toBe('rgb(5, 48, 97)')
    expect(stripeColour(COLOR_MAPS.temperature, 0.5)).toBe('rgb(247, 247, 247)')
    expect(stripeColour(COLOR_MAPS.temperature, 1)).toBe('rgb(178, 24, 43)')
    expect(stripeColour(COLOR_MAPS.temperature, 0.1)).toBe('rgb(19, 75, 135)')
  })

  it('is the end of the scale beyond it', () => {
    expect(stripeColour(COLOR_MAPS.temperature, -1)).toBe('rgb(5, 48, 97)')
    expect(stripeColour(COLOR_MAPS.temperature, 2)).toBe('rgb(178, 24, 43)')
  })
})
