import { describe, expect, it } from 'vitest'
import {
  clusterAt,
  clusterRadius,
  clusterStations,
  clusterText,
  DEFAULT_GROUPING,
  GROUPING_COMPULSORY_ABOVE,
  groupingFor,
  GROUPINGS,
  isGroupedAt,
  worldPixels,
  zoomForCluster,
} from '../../app/utils/map-cluster'
import { placed } from '../../app/utils/map-tool'

// The groups of stations at the outer zooms of the map tool (GH-4079).

function station(station_id: string, latitude: number, longitude: number) {
  return { station_id, name: station_id, region: null, latitude, longitude, elevation: null }
}

// two stations of Hamburg a few kilometres apart, one of Berlin and one of Munich
const FUHLSBUETTEL = station('01975', 53.6332, 9.9881)
const NEUWIEDENTHAL = station('01981', 53.4777, 9.8965)
const BERLIN = station('10384', 52.47, 13.4)
const MUNICH = station('03379', 48.1632, 11.5429)
const ALL = placed([FUHLSBUETTEL, NEUWIEDENTHAL, BERLIN, MUNICH])

describe('the grouping of a layer', () => {
  it('follows the choice on a layer of up to 10,000 stations, whether it is none or a step', () => {
    expect(groupingFor('off', 5_600)).toEqual({ choice: 'off', compulsory: false, grouping: null })
    expect(groupingFor('coarse', 5_600)).toEqual({ choice: 'coarse', compulsory: false, grouping: GROUPINGS.coarse })
    expect(groupingFor('off', GROUPING_COMPULSORY_ABOVE)).toMatchObject({ compulsory: false, grouping: null })
  })

  it('is compulsory on a layer of more than 10,000 stations, which the choice of none cannot turn off: it takes the default step', () => {
    expect(groupingFor('off', GROUPING_COMPULSORY_ABOVE + 1)).toEqual({ choice: DEFAULT_GROUPING, compulsory: true, grouping: GROUPINGS[DEFAULT_GROUPING] })
    expect(groupingFor('off', 133_041).grouping).not.toBeNull()
    // but it still sets how fine the groups are
    expect(groupingFor('fine', 133_041)).toEqual({ choice: 'fine', compulsory: true, grouping: GROUPINGS.fine })
  })

  it('has steps that group more and keep grouping to a closer zoom as they get coarser', () => {
    expect(GROUPINGS.fine.radius).toBeLessThan(GROUPINGS.medium.radius)
    expect(GROUPINGS.medium.radius).toBeLessThan(GROUPINGS.coarse.radius)
    expect(GROUPINGS.fine.separateFrom).toBeLessThan(GROUPINGS.medium.separateFrom)
    expect(GROUPINGS.medium.separateFrom).toBeLessThan(GROUPINGS.coarse.separateFrom)
  })

  it('groups at the zooms before the one every station is its own dot from, and not at it or after', () => {
    const { separateFrom } = GROUPINGS.medium
    expect(isGroupedAt(GROUPINGS.medium, separateFrom - 1)).toBe(true)
    expect(isGroupedAt(GROUPINGS.medium, separateFrom)).toBe(false)
    expect(isGroupedAt(null, 2)).toBe(false)
  })
})

describe('the groups of a list at a zoom', () => {
  it('put the stations that lie close together in one group, with their number, their middle and the box a click zooms to', () => {
    const groups = clusterStations(ALL, 5, 50)
    const hamburg = groups.find(group => group.count === 2)!
    expect(hamburg.station).toBeNull()
    expect(hamburg.latitude).toBeCloseTo((FUHLSBUETTEL.latitude + NEUWIEDENTHAL.latitude) / 2, 6)
    expect(hamburg.longitude).toBeCloseTo((FUHLSBUETTEL.longitude + NEUWIEDENTHAL.longitude) / 2, 6)
    expect(hamburg.bounds).toEqual({ south: NEUWIEDENTHAL.latitude, north: FUHLSBUETTEL.latitude, west: NEUWIEDENTHAL.longitude, east: FUHLSBUETTEL.longitude })
  })

  it('keep a station that is alone as itself: a group of one is the station, drawn as a dot', () => {
    const groups = clusterStations(ALL, 5, 50)
    expect(groups.filter(group => group.count === 1).map(group => group.station!.station_id).sort()).toEqual(['03379', '10384'])
    expect(groups.reduce((sum, group) => sum + group.count, 0)).toBe(ALL.length)
  })

  it('split up as the map zooms in, until every station is a group of its own', () => {
    expect(clusterStations(ALL, 2, 50).length).toBeLessThan(clusterStations(ALL, 5, 50).length)
    expect(clusterStations(ALL, 12, 50)).toHaveLength(ALL.length)
  })

  it('group less with a smaller radius, and more with a larger one', () => {
    expect(clusterStations(ALL, 6, 30).length).toBeGreaterThanOrEqual(clusterStations(ALL, 6, 80).length)
  })

  it('count every station once: a list of none is no groups, and stations at one place are one group', () => {
    expect(clusterStations([], 5, 50)).toEqual([])
    const same = placed([station('a', 50, 10), station('b', 50, 10), station('c', 50, 10)])
    const groups = clusterStations(same, 14, 30)
    expect(groups).toHaveLength(1)
    expect(groups[0]!.count).toBe(3)
  })

  it('are made for a list of 133,041 stations (GHCN daily) in a fraction of a second, at the zoom the map opens a world view at', () => {
    // a deterministic spread over the land of the world, denser in a few places as the real list is
    let seed = 7
    const random = () => (seed = (seed * 48271) % 2147483647) / 2147483647
    const many = placed(Array.from({ length: 133_041 }, (_, index) => station(String(index), -55 + random() * 130, -170 + random() * 340)))
    const started = performance.now()
    const groups = clusterStations(many, 3, 50)
    const took = performance.now() - started
    expect(groups.reduce((sum, group) => sum + group.count, 0)).toBe(133_041)
    // the world at zoom 3 is 2,048 px wide: a few hundred groups, not one disc for each station
    expect(groups.length).toBeLessThan(2000)
    // generous: a cold machine in CI. The work is one pass with a sum for each cell
    expect(took).toBeLessThan(1500)
  })
})

describe('the disc of a group', () => {
  it('grows with its number, from the size of a dot beside it to one that is still smaller than a tile', () => {
    expect(clusterRadius(2)).toBeGreaterThan(8)
    expect(clusterRadius(100)).toBeGreaterThan(clusterRadius(2))
    expect(clusterRadius(10_000)).toBeGreaterThan(clusterRadius(100))
    expect(clusterRadius(133_041)).toBeLessThan(40)
  })

  it('has its number written whole under a thousand, then in thousands', () => {
    expect([2, 38, 999, 1000, 1234, 12_000, 133_041].map(clusterText)).toEqual(['2', '38', '999', '1k', '1.2k', '12k', '133k'])
  })
})

describe('a click on a group', () => {
  const zoom = 5
  const groups = clusterStations(ALL, zoom, 50)
  const hamburg = groups.find(group => group.count === 2)!
  const centre = worldPixels(hamburg.latitude, hamburg.longitude, zoom)

  it('is on it within the radius of its disc and a little more, and on nothing farther off', () => {
    const radius = clusterRadius(2)
    expect(clusterAt(groups, zoom, centre)).toBe(hamburg)
    expect(clusterAt(groups, zoom, { x: centre.x + radius, y: centre.y })).toBe(hamburg)
    expect(clusterAt(groups, zoom, { x: centre.x + radius + 20, y: centre.y })).toBeNull()
  })

  it('is on no station that is alone, which is a dot and picked as one', () => {
    const berlin = worldPixels(BERLIN.latitude, BERLIN.longitude, zoom)
    expect(clusterAt(groups, zoom, berlin)).toBeNull()
  })

  it('zooms in on the box of its stations, one zoom in at least, and no farther than the zoom every station is its own dot from', () => {
    expect(zoomForCluster(7, 5, 9, 16)).toBe(7)
    // the box is already in view at this zoom: still one in
    expect(zoomForCluster(4, 5, 9, 16)).toBe(6)
    // stations at one place fit at the deepest zoom: the one they are separated from
    expect(zoomForCluster(16, 5, 9, 16)).toBe(9)
    expect(zoomForCluster(Number.POSITIVE_INFINITY, 5, 20, 16)).toBe(16)
  })
})
