import type { PlacedStation } from './map-tool'
import { dotRadius } from './map-tool'

/**
 * Groups of stations on the map tool (GH-4079): at the outer zooms the stations that lie close together are drawn as one
 * disc with their number, which a click zooms in on. Done here and drawn on the canvas tiles beside the dots, not with
 * `leaflet.markercluster`, whose groups are DOM markers: they would be stops of the keyboard (the map tool keeps its
 * stations out of the Tab order, see `StationMap.vue`) and a layer of 133,041 stations (GHCN daily) is too many of them.
 *
 * The groups are made on a grid in screen pixels at the zoom: one pass over the list, a sum for each cell, no tree to
 * build and nothing to keep but the groups of the zoom in view.
 */

/**
 * What grouping sets, the two settings behind the switch on the map: the radius of a group in screen pixels (every station
 * of a group is within it of the group's cell centre), and the zoom from which every station is its own dot.
 */
export interface Grouping {
  radius: number
  separateFrom: number
}

/** The one grouping the map has (GH-4209: the switch is on or off; the fine step of GH-4172 is gone), on by default, which the pickers take their separation zoom from */
export const GROUPING: Grouping = { radius: 80, separateFrom: 10 }

/**
 * A layer whose list has more stations than this is always grouped, whatever the switch says (maintainer, 2026-11-14):
 * the rule goes by the layer's count, not by a hand-picked list. The switch is then on, and cannot be turned off.
 * GHCN daily has 133,041 stations, MOSMIX about 5,600 and DWD's observations about 1,400, which follow the switch.
 */
export const GROUPING_COMPULSORY_ABOVE = 10_000

/** What the map groups by for the switch and a layer of `count` stations: whether it is on, whether that is forced, and the settings (null for none) */
export interface GroupingInForce {
  on: boolean
  compulsory: boolean
  grouping: Grouping | null
}

/**
 * The grouping of a layer: the switch, except that a layer of more than `GROUPING_COMPULSORY_ABOVE` stations cannot be left
 * ungrouped and is grouped where the switch is off.
 *
 * @example
 * groupingFor(false, 5_600) // { on: false, compulsory: false, grouping: null }
 * groupingFor(false, 133_041) // { on: true, compulsory: true, grouping: { radius: 80, separateFrom: 10 } }
 */
export function groupingFor(wanted: boolean, count: number): GroupingInForce {
  const compulsory = count > GROUPING_COMPULSORY_ABOVE
  const on = wanted || compulsory
  return { on, compulsory, grouping: on ? GROUPING : null }
}

/** Whether the stations are grouped at a zoom: a grouping is set and the zoom is outside the one every station is its own dot from */
export function isGroupedAt(grouping: Grouping | null, zoom: number): boolean {
  return grouping !== null && zoom < grouping.separateFrom
}

/** A group of stations at a zoom, or a lone station (`count` 1, which is drawn as a dot) */
export interface Cluster {
  latitude: number
  longitude: number
  /** Where it is drawn at the zoom, in pixels of the world map: the middle of its stations, which a click is tested against */
  x: number
  y: number
  count: number
  /** How many of its stations report: all of them where the layer has no status (the forecast's points), none for a group of stopped ones */
  reporting: number
  /** The box of its stations, which a click zooms to */
  bounds: { south: number, west: number, north: number, east: number }
  /** The station, for a group of one */
  station: PlacedStation | null
}

const TILE = 256

/** The latitude Leaflet's Web Mercator map ends at: a point beyond it is drawn at it */
const MAX_LATITUDE = 85.0511287798

/** The position of a point at a zoom in pixels of the world map (Web Mercator, tiles of 256 px, as Leaflet draws them) */
export function worldPixels(latitude: number, longitude: number, zoom: number): { x: number, y: number } {
  const size = TILE * 2 ** zoom
  const sin = Math.sin(Math.max(-MAX_LATITUDE, Math.min(MAX_LATITUDE, latitude)) * Math.PI / 180)
  return {
    x: (longitude + 180) / 360 * size,
    y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * size,
  }
}

/** The point at a position in pixels of the world map at a zoom: the inverse of `worldPixels` */
export function worldPoint(x: number, y: number, zoom: number): { latitude: number, longitude: number } {
  const size = TILE * 2 ** zoom
  return {
    latitude: 90 - 360 * Math.atan(Math.exp((y / size - 0.5) * 2 * Math.PI)) / Math.PI,
    longitude: x / size * 360 - 180,
  }
}

interface Group {
  count: number
  /** How many of the stations report */
  reporting: number
  /** The sums of the positions in pixels, whose mean is where the group is drawn */
  sx: number
  sy: number
  south: number
  west: number
  north: number
  east: number
  first: PlacedStation
  alive: boolean
}

/** The edge of the squares the neighbours of a group are looked for in: more than the two largest discs side by side */
const NEIGHBOUR_CELL = 64

/**
 * Joins the groups whose discs would overlap, until none do: a group is drawn at the middle of its stations, which is not
 * the middle of the square of the grid it was cut in, so the discs of two neighbouring squares can reach over each other
 * and hide each other's number. A lone station counts as the dot it is drawn as. The joined group is bigger (a larger
 * disc) and has moved to the middle of all its stations, so another may now overlap it: the pass is made again until a pass
 * joins nothing.
 *
 * The cascade is not capped (no limit on how far a joined group may reach beyond its square): a cap would leave discs lying on
 * each other where the stations are denser than a disc, which is what the pass is for, and the cost is small (the squares are
 * joined, not the stations: 14 to 17 ms at zoom 7 of a list in towns, 407 ms at most). At the outer zooms a group is large
 * because a place is, not because the pass ran on: 153 groups at zoom 2 for 133,041 stations spread over the world.
 */
function mergeOverlapping(groups: Group[], dot: number): Group[] {
  const radiusOf = (group: Group) => group.count === 1 ? dot : clusterRadius(group.count)
  const keyOf = (column: number, row: number) => column * 1_000_003 + row
  let alive = groups
  for (let pass = 0; pass < 32; pass++) {
    const index = new Map<number, Group[]>()
    for (const group of alive) {
      const key = keyOf(Math.floor(group.sx / group.count / NEIGHBOUR_CELL), Math.floor(group.sy / group.count / NEIGHBOUR_CELL))
      const cell = index.get(key)
      if (cell)
        cell.push(group)
      else
        index.set(key, [group])
    }
    let joined = false
    for (const group of alive) {
      if (!group.alive)
        continue
      let again = true
      while (again) {
        again = false
        const x = group.sx / group.count
        const y = group.sy / group.count
        const column = Math.floor(x / NEIGHBOUR_CELL)
        const row = Math.floor(y / NEIGHBOUR_CELL)
        for (let dc = -1; dc <= 1; dc++) {
          for (let dr = -1; dr <= 1; dr++) {
            for (const other of index.get(keyOf(column + dc, row + dr)) ?? []) {
              if (other === group || !other.alive)
                continue
              if (Math.hypot(other.sx / other.count - x, other.sy / other.count - y) >= radiusOf(group) + radiusOf(other))
                continue
              group.count += other.count
              group.reporting += other.reporting
              group.sx += other.sx
              group.sy += other.sy
              group.south = Math.min(group.south, other.south)
              group.north = Math.max(group.north, other.north)
              group.west = Math.min(group.west, other.west)
              group.east = Math.max(group.east, other.east)
              other.alive = false
              again = joined = true
            }
          }
        }
      }
    }
    if (!joined)
      break
    alive = alive.filter(group => group.alive)
  }
  return alive.filter(group => group.alive)
}

/**
 * The groups of a list at a zoom: the stations in one square of 2 x `radius` pixels of a grid (so each is within `radius`
 * of the middle of it) are one group, and groups whose discs would overlap are joined (`mergeOverlapping`), so that every
 * disc is over its own stations and no number is hidden by another. A group of one is that station, drawn as a dot of
 * `dot` pixels. The stations of every kind are grouped together (`reports` says which report): one group for a place, whatever
 * its stations' status, with the number of those that report.
 *
 * The list is gone through once for the grid, with a sum for each square, and the squares (not the stations) are then
 * joined. Measured on 133,041 stations (a laptop, 2026-11-17): 6 to 40 ms at the outer zooms (2 to 5) of a list that is in
 * towns, 10 to 17 ms at zoom 7; of one spread evenly over the world, where the groups are most, 14 ms at zoom 2 to 5
 * for the coarse step and 121 ms at zoom 6 and 407 ms at zoom 7 for the fine one (84,000 groups, which no map shows).
 * A group is made once for a zoom and kept until the list or the step changes.
 *
 * @example
 * clusterStations(stations, 5, 50) // [{ count: 38, latitude: 52.4, longitude: 9.9, x, y, ... }, { count: 1, station, ... }]
 */
export function clusterStations(stations: PlacedStation[], zoom: number, radius: number, dot = dotRadius(zoom), reports?: (station: PlacedStation) => boolean): Cluster[] {
  const cell = radius * 2
  const cells = new Map<number, Group>()
  for (const station of stations) {
    const at = worldPixels(station.latitude, station.longitude, zoom)
    // a number for the cell: the columns of the widest world (zoom 16) fit under a million
    const key = Math.floor(at.x / cell) * 1_000_003 + Math.floor(at.y / cell)
    const reporting = !reports || reports(station) ? 1 : 0
    const group = cells.get(key)
    if (group) {
      group.count++
      group.reporting += reporting
      group.sx += at.x
      group.sy += at.y
      group.south = Math.min(group.south, station.latitude)
      group.north = Math.max(group.north, station.latitude)
      group.west = Math.min(group.west, station.longitude)
      group.east = Math.max(group.east, station.longitude)
    }
    else {
      cells.set(key, { count: 1, reporting, sx: at.x, sy: at.y, south: station.latitude, west: station.longitude, north: station.latitude, east: station.longitude, first: station, alive: true })
    }
  }
  return mergeOverlapping([...cells.values()], dot).map((group) => {
    const x = group.sx / group.count
    const y = group.sy / group.count
    return {
      ...worldPoint(x, y, zoom),
      x,
      y,
      count: group.count,
      reporting: group.reporting,
      bounds: { south: group.south, west: group.west, north: group.north, east: group.east },
      station: group.count === 1 ? group.first : null,
    }
  })
}

/** The radius of the disc of a group in pixels: it grows with the logarithm of its number, from 12 px for two stations to 24 px for ten thousand */
export function clusterRadius(count: number): number {
  return Math.round(11 + 3.2 * Math.log10(Math.max(count, 1)))
}

/** The least a part of a group's ring is drawn at, in radians (12 degrees): a share of 1 in 100 is still seen */
const MIN_SWEEP = Math.PI / 15

/**
 * How much of the ring of a group is filled for the stations that report, in radians from the top clockwise: nothing for
 * a group of stopped stations, the whole circle for one that all report (a filled disc, no ring), and for a mix the share,
 * at least `MIN_SWEEP` and at most a full circle less that, so that a mix never reads as all or none.
 *
 * @example
 * reportingSweep(20, 40) // Math.PI: half the ring
 */
export function reportingSweep(reporting: number, count: number): number {
  if (reporting <= 0)
    return 0
  if (reporting >= count)
    return 2 * Math.PI
  return Math.min(2 * Math.PI - MIN_SWEEP, Math.max(MIN_SWEEP, reporting / count * 2 * Math.PI))
}

/**
 * The number written in a group: whole under a thousand, then thousands with a decimal (`1.2k`). It is drawn on a canvas,
 * which knows no language; the number is the group's size, which the map's count says in the language's own format.
 */
export function clusterText(count: number): string {
  if (count < 1000)
    return String(count)
  const thousands = Math.round(count / 100) / 10
  return `${Number.isInteger(thousands) ? thousands : thousands.toFixed(1)}k`
}

/**
 * The group of a list that a click at a pixel of the map is on: the one whose disc, as drawn, holds the pixel. Discs of a list
 * do not overlap (`clusterStations` joins them), so there is one; a lone station is no group. `at` is the pixel clicked from
 * the world's origin at the zoom of the list, `slop` how far outside the disc a click still is on it, in pixels.
 */
export function clusterAt(clusters: Cluster[], at: { x: number, y: number }, slop = 2): Cluster | null {
  let hit: Cluster | null = null
  let nearest = Number.POSITIVE_INFINITY
  for (const cluster of clusters) {
    if (cluster.count < 2)
      continue
    const distance = Math.hypot(cluster.x - at.x, cluster.y - at.y)
    if (distance <= clusterRadius(cluster.count) + slop && distance < nearest) {
      nearest = distance
      hit = cluster
    }
  }
  return hit
}

/**
 * The box a click on a group fits the map to: its stations' box, grown to be as far from the disc on every side as it is on
 * the one where it is farthest, so that the disc is the middle of it. The disc is drawn at the mean of the stations' positions
 * and the stations are not spread evenly round it (a town with outliers to one side), so the middle of the stations' box
 * (`bounds.getCenter()`, which GH-4209 found a click on a group centred the map on) is somewhere else than the disc: the map
 * zoomed in with the group off to one side. A map centred on the disc with this box shows all of the stations.
 */
export function boundsAround(cluster: Pick<Cluster, 'latitude' | 'longitude' | 'bounds'>): Cluster['bounds'] {
  const { latitude, longitude, bounds } = cluster
  const north = Math.max(bounds.north - latitude, latitude - bounds.south)
  const east = Math.max(bounds.east - longitude, longitude - bounds.west)
  return {
    south: Math.max(-MAX_LATITUDE, latitude - north),
    north: Math.min(MAX_LATITUDE, latitude + north),
    west: longitude - east,
    east: longitude + east,
  }
}

/**
 * The zoom a click on a group goes to: the one that fits the box of its stations, at least one in, and no farther than
 * the zoom from which every station is its own dot (the group is gone by then, if the box was a point).
 */
export function zoomForCluster(fitting: number, current: number, separateFrom: number, maxZoom: number): number {
  return Math.min(Math.max(fitting, current + 1), separateFrom, maxZoom)
}

/**
 * The view a click on a group sets: the map centred on the disc, as it was drawn, at the zoom that fits the stations round it.
 * `fitting` is the zoom at which the map holds a box, which only the map knows (`getBoundsZoom`).
 */
export function viewForCluster(
  cluster: Pick<Cluster, 'latitude' | 'longitude' | 'bounds'>,
  fitting: (box: Cluster['bounds']) => number,
  current: number,
  separateFrom: number,
  maxZoom: number,
): { latitude: number, longitude: number, zoom: number } {
  return {
    latitude: cluster.latitude,
    longitude: cluster.longitude,
    zoom: zoomForCluster(fitting(boundsAround(cluster)), current, separateFrom, maxZoom),
  }
}
