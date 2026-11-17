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
  reportingSweep,
  worldPixels,
  worldPoint,
  zoomForCluster,
} from '../../app/utils/map-cluster'
import { dotRadius, placed } from '../../app/utils/map-tool'

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

// a seeded generator, so that the fixtures are the same in every run
let seed = 7
function random() {
  seed = (seed * 48271) % 2147483647
  return seed / 2147483647
}

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

  it('has two steps, fine (the default) and coarse, that group more and keep grouping to a closer zoom as they get coarser', () => {
    expect(Object.keys(GROUPINGS)).toEqual(['fine', 'coarse'])
    expect(DEFAULT_GROUPING).toBe('fine')
    expect(GROUPINGS.fine).toEqual({ radius: 30, separateFrom: 8 })
    expect(GROUPINGS.coarse).toEqual({ radius: 80, separateFrom: 10 })
  })

  it('groups at the zooms before the one every station is its own dot from, and not at it or after', () => {
    const { separateFrom } = GROUPINGS.fine
    expect(isGroupedAt(GROUPINGS.fine, separateFrom - 1)).toBe(true)
    expect(isGroupedAt(GROUPINGS.fine, separateFrom)).toBe(false)
    expect(isGroupedAt(null, 2)).toBe(false)
  })
})

describe('the groups of a list at a zoom', () => {
  it('put the stations that lie close together in one group, with their number, their middle and the box a click zooms to', () => {
    const groups = clusterStations(ALL, 5, 50)
    const hamburg = groups.find(group => group.count === 2)!
    expect(hamburg.station).toBeNull()
    expect(hamburg.latitude).toBeCloseTo((FUHLSBUETTEL.latitude + NEUWIEDENTHAL.latitude) / 2, 3)
    expect(hamburg.longitude).toBeCloseTo((FUHLSBUETTEL.longitude + NEUWIEDENTHAL.longitude) / 2, 3)
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

  it('are made for a list of 133,041 stations (GHCN daily), none lost, with a number of groups that fits the map', () => {
    const many = placed(Array.from({ length: 133_041 }, (_, index) => station(String(index), -55 + random() * 130, -170 + random() * 340)))
    // the world at zoom 3 is 2,048 px wide: a few hundred groups, not one disc for each station
    for (const zoom of [3, 5, 7]) {
      const started = performance.now()
      const groups = clusterStations(many, zoom, 30)
      const took = performance.now() - started
      expect(groups.reduce((sum, group) => sum + group.count, 0)).toBe(133_041)
      if (zoom === 3)
        expect(groups.length).toBeLessThan(2000)
      // not a measure, a guard against a pass that grows with the square of the list: about 0.1 to 0.5 s on a laptop
      expect(took).toBeLessThan(15_000)
    }
  })

  it('keep the discs apart: no two groups of a list overlap, at either step and at several zooms, and none lies over a lone station', () => {
    // towns: dense knots of stations with space between them, where a grid cuts a knot into squares whose groups lie close
    const towns = placed(Array.from({ length: 4000 }, (_, index) => {
      const town = index % 200
      const centre = { latitude: 47 + (town % 20) * 0.35, longitude: 6 + Math.floor(town / 20) * 0.6 }
      return station(String(index), centre.latitude + (random() - 0.5) * 0.12, centre.longitude + (random() - 0.5) * 0.18)
    }))
    for (const [radius, zooms] of [[30, [5, 6, 7]], [80, [5, 7, 9]]] as const) {
      for (const zoom of zooms) {
        const groups = clusterStations(towns, zoom, radius)
        expect(groups.reduce((sum, group) => sum + group.count, 0)).toBe(towns.length)
        const dot = dotRadius(zoom)
        const radiusOf = (group: { count: number }) => group.count === 1 ? dot : clusterRadius(group.count)
        let overlapping = 0
        for (let first = 0; first < groups.length; first++) {
          for (let second = first + 1; second < groups.length; second++) {
            if (Math.hypot(groups[first]!.x - groups[second]!.x, groups[first]!.y - groups[second]!.y) < radiusOf(groups[first]!) + radiusOf(groups[second]!))
              overlapping++
          }
        }
        expect(overlapping, `radius ${radius} at zoom ${zoom}`).toBe(0)
      }
    }
  })

  it('are drawn where their stations are: the position of a group is the mean of the positions of its stations', () => {
    const pair = placed([station('a', 50, 10), station('b', 50.01, 10.01)])
    const [group] = clusterStations(pair, 4, 50)
    const first = worldPixels(50, 10, 4)
    const second = worldPixels(50.01, 10.01, 4)
    expect(group!.count).toBe(2)
    expect(group!.x).toBeCloseTo((first.x + second.x) / 2, 6)
    expect(group!.y).toBeCloseTo((first.y + second.y) / 2, 6)
    // and the point it reports is that position, which the map projects back to the pixels
    const back = worldPixels(group!.latitude, group!.longitude, 4)
    expect(back.x).toBeCloseTo(group!.x, 6)
    expect(back.y).toBeCloseTo(group!.y, 6)
  })
})

describe('the pixels of the world map', () => {
  it('are Leaflet\'s: the world is 256 px at zoom 0, and the map ends at 85.0511 degrees', () => {
    expect(worldPixels(0, 0, 0)).toEqual({ x: 128, y: 128 })
    expect(worldPixels(85.0511287798, -180, 0).y).toBeCloseTo(0, 6)
    // a station at the pole is drawn at the edge of the map, where Leaflet's own projection stops, not past it
    expect(worldPixels(89.9, 0, 3).y).toBeCloseTo(worldPixels(85.0511287798, 0, 3).y, 9)
    expect(worldPixels(-89.9, 0, 3).y).toBeCloseTo(256 * 8, 6)
  })

  it('are given back to the point they came from', () => {
    for (const [latitude, longitude, zoom] of [[52.5, 13.4, 6], [-33.9, 151.2, 3], [0, 0, 10], [70.9, -8.7, 12]] as const) {
      const at = worldPixels(latitude, longitude, zoom)
      const back = worldPoint(at.x, at.y, zoom)
      expect(back.latitude).toBeCloseTo(latitude, 8)
      expect(back.longitude).toBeCloseTo(longitude, 8)
    }
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
    expect(clusterAt(groups, centre)).toBe(hamburg)
    expect(clusterAt(groups, { x: centre.x + radius, y: centre.y })).toBe(hamburg)
    expect(clusterAt(groups, { x: centre.x + radius + 20, y: centre.y })).toBeNull()
  })

  it('is on no station that is alone, which is a dot and picked as one', () => {
    const berlin = worldPixels(BERLIN.latitude, BERLIN.longitude, zoom)
    expect(clusterAt(groups, berlin)).toBeNull()
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

describe('groups of stations that report and stations that have stopped (GH-4079)', () => {
  // 500 stations that report and 600 that have stopped, spread over Germany and mixed: a place has both, as the real list's do
  const mixed = placed(Array.from({ length: 1100 }, (_, index) => station(String(index), 47.5 + random() * 7.5, 6 + random() * 9)))
  const stopped = new Set(mixed.filter((_, index) => index % 11 < 6).map(entry => entry.station_id))
  const reports = (entry: { station_id: string }) => !stopped.has(entry.station_id)

  it('are one group for a place: the stations of both kinds are grouped together, and the numbers add up', () => {
    for (const zoom of [5, 6, 7]) {
      const groups = clusterStations(mixed, zoom, 30, undefined, reports)
      expect(groups.reduce((sum, group) => sum + group.count, 0)).toBe(mixed.length)
      expect(groups.reduce((sum, group) => sum + group.reporting, 0)).toBe(mixed.length - stopped.size)
      // a group of both kinds is the place's one disc
      expect(groups.some(group => group.reporting > 0 && group.reporting < group.count)).toBe(true)
      // a group of one keeps its own kind, as its dot
      for (const group of groups.filter(entry => entry.station))
        expect(group.reporting).toBe(reports(group.station!) ? 1 : 0)
    }
  })

  it('do not overlap, across the kinds, at either step and at several zooms', () => {
    for (const [radius, zooms] of [[30, [5, 6, 7]], [80, [5, 6, 8]]] as const) {
      for (const zoom of zooms) {
        const groups = clusterStations(mixed, zoom, radius, undefined, reports)
        const dot = dotRadius(zoom)
        const radiusOf = (group: { count: number }) => group.count === 1 ? dot : clusterRadius(group.count)
        let overlapping = 0
        for (let first = 0; first < groups.length; first++) {
          for (let second = first + 1; second < groups.length; second++) {
            if (Math.hypot(groups[first]!.x - groups[second]!.x, groups[first]!.y - groups[second]!.y) < radiusOf(groups[first]!) + radiusOf(groups[second]!))
              overlapping++
          }
        }
        expect(overlapping, `radius ${radius} at zoom ${zoom}`).toBe(0)
      }
    }
  })

  it('count every station as reporting where the layer has no status', () => {
    const groups = clusterStations(mixed, 5, 50)
    expect(groups.reduce((sum, group) => sum + group.reporting, 0)).toBe(mixed.length)
    expect(groups.every(group => group.reporting === group.count)).toBe(true)
  })

  it('are clicked on as one, which zooms to the box of all its stations, those that report and those that have stopped', () => {
    const groups = clusterStations(mixed, 6, 30, undefined, reports)
    const biggest = groups.reduce((best, group) => group.count > best.count ? group : best)
    expect(clusterAt(groups, { x: biggest.x, y: biggest.y })).toBe(biggest)
    // the box holds every station of the group, the stopped ones and the reporting ones
    const inside = mixed.filter(entry => entry.latitude >= biggest.bounds.south && entry.latitude <= biggest.bounds.north && entry.longitude >= biggest.bounds.west && entry.longitude <= biggest.bounds.east)
    expect(inside.length).toBeGreaterThanOrEqual(biggest.count)
    expect(biggest.reporting).toBeGreaterThan(0)
    expect(biggest.reporting).toBeLessThan(biggest.count)
  })
})

describe('the share of a group that reports, as the angle of its ring', () => {
  it('is nothing for stopped stations and the whole circle for stations that all report, a hollow disc and a filled one', () => {
    expect(reportingSweep(0, 40)).toBe(0)
    expect(reportingSweep(40, 40)).toBe(2 * Math.PI)
  })

  it('is the share of the circle for a mix, from the top clockwise', () => {
    expect(reportingSweep(20, 40)).toBeCloseTo(Math.PI, 9)
    expect(reportingSweep(10, 40)).toBeCloseTo(Math.PI / 2, 9)
    expect(reportingSweep(30, 40)).toBeCloseTo(1.5 * Math.PI, 9)
  })

  it('never reads as all or none for a mix: a sliver of 12 degrees at least, and a gap of 12 degrees at most', () => {
    expect(reportingSweep(1, 1000)).toBeCloseTo(Math.PI / 15, 9)
    expect(reportingSweep(999, 1000)).toBeCloseTo(2 * Math.PI - Math.PI / 15, 9)
    expect(reportingSweep(1, 1000)).toBeGreaterThan(0)
    expect(reportingSweep(999, 1000)).toBeLessThan(2 * Math.PI)
  })
})
