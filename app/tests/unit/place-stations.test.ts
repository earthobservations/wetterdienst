import { describe, expect, it } from 'vitest'
import { distanceKm } from '../../app/utils/map-tool'
import { NEAR_STATIONS_COUNT, PLACE_REACH_KM, stationForPlace, stationsNear, withinReach } from '../../app/utils/place-stations'

// The stations near a place found by its name (GH-3791): which are the closest, how far each is and how high it stands against the closest one, and
// whether the closest is near enough to be called the place's. A place has no height of its own, so a height is only ever compared between stations.

const BAD_TOELZ = { latitude: 47.7614, longitude: 11.5583 }
const station = (station_id: string, latitude: number | null, longitude: number | null, elevation: number | null = null) => ({ station_id, name: station_id, latitude, longitude, elevation })

const STATIONS = [
  station('MUENCHEN', 48.16, 11.54, 515),
  station('TEGERNSEE', 47.71, 11.76, 735),
  station('BAD TOELZ', 47.77, 11.55, 668),
  station('KOCHEL', 47.65, 11.37, 614),
  station('NO POSITION', null, null, 100),
  station('NO HEIGHT', 47.8, 11.4, null),
  station('HAMBURG', 53.63, 10.0, 11),
]

describe('the reach of a place', () => {
  it('is 50 km: the distance of a station is told by the great circle, and a station that far is still the place\'s', () => {
    expect(PLACE_REACH_KM).toBe(50)
    expect(withinReach(0)).toBe(true)
    expect(withinReach(50)).toBe(true)
    expect(withinReach(50.01)).toBe(false)
    expect(withinReach(681)).toBe(false)
  })
})

describe('the stations near a place', () => {
  it('are the closest first, with their distance in kilometres from the place', () => {
    const near = stationsNear(BAD_TOELZ, STATIONS)
    expect(near.map(entry => entry.station.station_id)).toEqual(['BAD TOELZ', 'NO HEIGHT', 'TEGERNSEE', 'KOCHEL', 'MUENCHEN'])
    expect(near[0]!.distanceKm).toBeCloseTo(distanceKm(BAD_TOELZ, { latitude: 47.77, longitude: 11.55 }), 6)
    expect(near[0]!.distanceKm).toBeCloseTo(1.14, 1)
    expect(near.map(entry => entry.distanceKm)).toEqual(near.map(entry => entry.distanceKm).sort((a, b) => a - b))
  })

  it('leave out a station that has no position, which has no distance, and are at most as many as were asked for', () => {
    expect(stationsNear(BAD_TOELZ, STATIONS).map(entry => entry.station.station_id)).not.toContain('NO POSITION')
    expect(stationsNear(BAD_TOELZ, STATIONS, 2)).toHaveLength(2)
    expect(stationsNear(BAD_TOELZ, STATIONS)).toHaveLength(NEAR_STATIONS_COUNT)
    expect(stationsNear(BAD_TOELZ, [])).toEqual([])
  })

  it('give the height of each against the closest station\'s, none for the closest itself and none where either has no height', () => {
    const near = stationsNear(BAD_TOELZ, STATIONS)
    expect(near[0]!.heightDifference).toBeNull()
    // NO HEIGHT has none
    expect(near[1]!.heightDifference).toBeNull()
    // Tegernsee stands 67 m above Bad Tölz's point, Kochel 54 m below, Munich 153 m below
    expect(near[2]!.heightDifference).toBe(67)
    expect(near[3]!.heightDifference).toBe(-54)
    expect(near[4]!.heightDifference).toBe(-153)
  })

  it('give no height difference at all where the closest has no height', () => {
    const near = stationsNear(BAD_TOELZ, [station('A', 47.77, 11.55, null), station('B', 47.8, 11.5, 700)])
    expect(near.map(entry => entry.heightDifference)).toEqual([null, null])
  })

  it('are rounded to whole metres, as a height is told', () => {
    const near = stationsNear(BAD_TOELZ, [station('A', 47.77, 11.55, 100.4), station('B', 47.8, 11.5, 150.2)])
    expect(near[1]!.heightDifference).toBe(50)
  })
})

describe('the station of a place', () => {
  it('is the closest one where it is within reach', () => {
    const near = stationsNear(BAD_TOELZ, STATIONS)
    expect(stationForPlace(near)!.station.station_id).toBe('BAD TOELZ')
  })

  it('is none where the closest is farther than the reach: the nearest is told and not used', () => {
    const paris = { latitude: 48.8566, longitude: 2.3522 }
    const near = stationsNear(paris, STATIONS)
    expect(near[0]!.distanceKm).toBeGreaterThan(PLACE_REACH_KM)
    expect(stationForPlace(near)).toBeNull()
  })

  it('is none where there is no station at all', () => {
    expect(stationForPlace([])).toBeNull()
  })
})
