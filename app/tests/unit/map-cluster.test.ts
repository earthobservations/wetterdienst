import { describe, expect, it } from 'vitest'
import {
  boundsAround,
  clusterAt,
  clusterRadius,
  clusterStations,
  clusterText,
  GROUPING,
  GROUPING_COMPULSORY_ABOVE,
  groupingFor,
  isGroupedAt,
  reportingSweep,
  viewForCluster,
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
  it('follows the switch on a layer of up to 10,000 stations, whether it is off or on', () => {
    expect(groupingFor(false, 5_600)).toEqual({ on: false, compulsory: false, grouping: null })
    expect(groupingFor(true, 5_600)).toEqual({ on: true, compulsory: false, grouping: GROUPING })
    expect(groupingFor(false, GROUPING_COMPULSORY_ABOVE)).toMatchObject({ compulsory: false, grouping: null })
  })

  it('is compulsory on a layer of more than 10,000 stations, which the switch off cannot turn off: it is on', () => {
    expect(groupingFor(false, GROUPING_COMPULSORY_ABOVE + 1)).toEqual({ on: true, compulsory: true, grouping: GROUPING })
    expect(groupingFor(false, 133_041).grouping).not.toBeNull()
    expect(groupingFor(true, 133_041)).toEqual({ on: true, compulsory: true, grouping: GROUPING })
  })

  it('has one grouping, the one that was the coarse step: a radius of 80 pixels, and groups to zoom 9 (GH-4209)', () => {
    expect(GROUPING).toEqual({ radius: 80, separateFrom: 10 })
  })

  it('groups at the zooms before the one every station is its own dot from, and not at it or after', () => {
    const { separateFrom } = GROUPING
    expect(isGroupedAt(GROUPING, separateFrom - 1)).toBe(true)
    expect(isGroupedAt(GROUPING, separateFrom)).toBe(false)
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

  it('keep the discs apart: no two groups of a list overlap, at several zooms, and none lies over a lone station', () => {
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

  it('do not overlap, across the kinds, at several zooms', () => {
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

// A click on a group centres the map on it (GH-4209). The disc is drawn at the mean of its stations, and the map used to
// be centred on the middle of their box, which is another place where the stations are not spread evenly round the disc.
describe('the view a click on a group sets', () => {
  // nine stations in a town and one far to the north east: the disc is drawn near the town, the box reaches out to the one
  const lopsided = placed([
    ...Array.from({ length: 9 }, (_, index) => station(`T${index}`, 53 + index * 0.01, 10 + index * 0.01)),
    station('FAR', 53.8, 11),
  ])
  const group = clusterStations(lopsided, 5, 80).find(cluster => cluster.count === 10)!

  it('has the disc, as it is drawn, away from the middle of the box of its stations', () => {
    const middle = { latitude: (group.bounds.south + group.bounds.north) / 2, longitude: (group.bounds.west + group.bounds.east) / 2 }
    // what `bounds.getCenter()` gave: more than a tenth of a degree from the disc
    expect(Math.abs(middle.latitude - group.latitude)).toBeGreaterThan(0.1)
    expect(Math.abs(middle.longitude - group.longitude)).toBeGreaterThan(0.1)
  })

  it('is centred on the disc, not on the middle of the box', () => {
    const view = viewForCluster(group, () => 8, 5, 10, 16)
    expect(view.latitude).toBe(group.latitude)
    expect(view.longitude).toBe(group.longitude)
  })

  it('fits the map to a box that has the disc in the middle of it and holds every station, so that the zoom shows them all', () => {
    const asked: ReturnType<typeof boundsAround>[] = []
    viewForCluster(group, (box) => {
      asked.push(box)
      return 8
    }, 5, 10, 16)
    const [box] = asked
    // the middle on the map, not in degrees
    const disc = worldPixels(group.latitude, group.longitude, 8)
    expect((worldPixels(box!.south, 0, 8).y + worldPixels(box!.north, 0, 8).y) / 2).toBeCloseTo(disc.y, 6)
    expect((box!.west + box!.east) / 2).toBeCloseTo(group.longitude, 9)
    expect(box!.south).toBeLessThanOrEqual(group.bounds.south)
    expect(box!.north).toBeGreaterThanOrEqual(group.bounds.north)
    expect(box!.west).toBeLessThanOrEqual(group.bounds.west)
    expect(box!.east).toBeGreaterThanOrEqual(group.bounds.east)
  })

  it('takes the zoom as before: the one that fits, one in at least, no farther than the zoom every station is its own dot from', () => {
    expect(viewForCluster(group, () => 7, 5, 10, 16).zoom).toBe(7)
    expect(viewForCluster(group, () => 3, 5, 10, 16).zoom).toBe(6)
    expect(viewForCluster(group, () => 16, 5, 10, 16).zoom).toBe(10)
  })

  it('keeps the box of a group of stations at one place a point', () => {
    const point = { latitude: 52, longitude: 10, bounds: { south: 52, north: 52, west: 10, east: 10 } }
    const box = boundsAround(point)
    expect(box.south).toBeCloseTo(52, 9)
    expect(box.north).toBeCloseTo(52, 9)
    expect(box.west).toBeCloseTo(10, 9)
    expect(box.east).toBeCloseTo(10, 9)
  })

  it('mirrors the distances on the map, not in degrees: at a high latitude every station is in view at the zoom fitted to the box (a map of 540 px)', () => {
    // a group of the world's stations at zoom 2, drawn at 60 degrees north, its stations from 41 to 79 degrees
    const group = { latitude: 60, longitude: 10, bounds: { south: 41, north: 79, west: -30, east: 50 } }
    const SIZE = 540
    // the zoom at which the map of SIZE px holds a box, as Leaflet's `getBoundsZoom` finds it
    const fitting = (box: ReturnType<typeof boundsAround>) => {
      let fitted = 0
      for (let zoom = 1; zoom <= 16; zoom++) {
        const northWest = worldPixels(box.north, box.west, zoom)
        const southEast = worldPixels(box.south, box.east, zoom)
        if (southEast.x - northWest.x <= SIZE && southEast.y - northWest.y <= SIZE)
          fitted = zoom
      }
      return fitted
    }
    const view = viewForCluster(group, fitting, 0, 10, 16)
    const middle = worldPixels(view.latitude, view.longitude, view.zoom)
    // the corners of the box of the stations, the northernmost and the southernmost of them among them
    for (const [latitude, longitude] of [[79, -30], [79, 50], [41, -30], [41, 50]] as const) {
      const at = worldPixels(latitude, longitude, view.zoom)
      expect(Math.abs(at.x - middle.x), `x of ${latitude}, ${longitude}`).toBeLessThanOrEqual(SIZE / 2 + 0.5)
      expect(Math.abs(at.y - middle.y), `y of ${latitude}, ${longitude}`).toBeLessThanOrEqual(SIZE / 2 + 0.5)
    }
    // and the box mirrored in degrees would have been cut off: the zoom it fits is deeper than this one
    const inDegrees = { south: 41, north: 79, west: -30, east: 50 }
    expect(fitting({ south: 60 - 19, north: 60 + 19, west: inDegrees.west, east: inDegrees.east })).toBeGreaterThan(view.zoom)
  })

  it('does not reach beyond the latitudes the map ends at', () => {
    const box = boundsAround({ latitude: 84, longitude: 0, bounds: { south: 80, north: 85, west: -1, east: 1 } })
    expect(box.north).toBeCloseTo(85.0511287798, 9)
    expect(box.south).toBeCloseTo(80, 6)
  })
})
