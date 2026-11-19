import type { PlacedStation } from './map-tool'
import { dotRadius } from './map-tool'

/**
 * Groups of stations on the map tool (GH-4079): at the outer zooms the stations that lie close together are drawn as one
 * disc with their number, which a click zooms in on. Done here and drawn on the canvas tiles beside the dots, not with
 * `leaflet.markercluster`, whose groups are DOM markers: they would be stops of the keyboard (the map tool keeps its
 * stations out of the Tab order, see `StationMap.vue`) and a layer of 133,041 stations (GHCN daily) is too many of them.
 *
 * The groups are made by distance, in screen pixels at the zoom (GH-4241): stations are taken in a stable order, the densest
 * place first, and each takes the stations that are not yet in a group within the radius of it, so a town's stations are one
 * group at the town, wherever a grid would have cut it. One pass over the list with a grid of squares of the radius to find the
 * neighbours (a lookup, not a tree to build), no index of all the zooms, and nothing to keep but the groups of the zoom in view.
 */

/**
 * What grouping sets, the two settings behind the switch on the map: the radius of a group in screen pixels (every station
 * of a group is within it of the station the group formed round), and the zoom from which every station is its own dot.
 */
export interface Grouping {
  radius: number
  separateFrom: number
}

/** The one grouping the map has (GH-4209: the switch is on or off; the fine step of GH-4172 is gone), on by default, which the pickers take their separation zoom from */
export const GROUPING: Grouping = { radius: 40, separateFrom: 9 }

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
 * groupingFor(false, 133_041) // { on: true, compulsory: true, grouping: { radius: 40, separateFrom: 9 } }
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

/** The most squares across the grid that neighbours are found in (a grid of 4 million squares at most, a few MB), so that a list at a deep zoom has no grid of a billion */
const GRID_MAX = 2048

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
  /** The radius of its disc in pixels, as drawn: a dot for a group of one */
  radius: number
}

/** The edge of the squares the neighbours of a group are looked for in: more than the two largest discs side by side */
const NEIGHBOUR_CELL = 64

/**
 * Joins the groups whose discs would overlap, until none do: a group is drawn at the middle of its stations, which is not
 * where it formed, so the discs of two groups that formed `radius` apart can reach over each other and hide each other's
 * number. A lone station counts as the dot it is drawn as. The joined group is bigger (a larger disc) and has moved to the
 * middle of all its stations, so another may now overlap it: the pass is made again until a pass joins nothing.
 *
 * The cascade is not capped: a cap would leave discs lying on each other where the stations are denser than a disc, which is
 * what the pass is for. With groups that formed a radius (40 px) apart, and discs of 12 to 24 px, it joins few: only where a
 * group's middle has moved toward its neighbour. The neighbours are looked for in a grid of squares of `NEIGHBOUR_CELL`
 * pixels, made for each pass from the groups' places (a lookup, not a tree).
 */
function mergeOverlapping(groups: Group[], dot: number, size: number): Group[] {
  const side = Math.max(NEIGHBOUR_CELL, size / GRID_MAX)
  const across = Math.floor(size / side) + 1
  let alive = groups
  for (let pass = 0; pass < 32; pass++) {
    const count = alive.length
    const squareOf = new Int32Array(count)
    const from = new Int32Array(across * across + 1)
    for (let index = 0; index < count; index++) {
      const group = alive[index]!
      group.radius = group.count === 1 ? dot : clusterRadius(group.count)
      const square = Math.floor(group.sx / group.count / side) * across + Math.floor(group.sy / group.count / side)
      squareOf[index] = square
      from[square + 1]!++
    }
    for (let square = 0; square < across * across; square++)
      from[square + 1]! += from[square]!
    const members = new Int32Array(count)
    const filled = from.slice(0, across * across)
    for (let index = 0; index < count; index++)
      members[filled[squareOf[index]!]!++] = index
    let joined = false
    for (const group of alive) {
      if (!group.alive)
        continue
      let again = true
      while (again) {
        again = false
        const x = group.sx / group.count
        const y = group.sy / group.count
        const column = Math.floor(x / side)
        const row = Math.floor(y / side)
        for (let dc = Math.max(column - 1, 0); dc <= Math.min(column + 1, across - 1); dc++) {
          for (let dr = Math.max(row - 1, 0); dr <= Math.min(row + 1, across - 1); dr++) {
            const near = dc * across + dr
            for (let at = from[near]!; at < from[near + 1]!; at++) {
              const other = alive[members[at]!]!
              if (other === group || !other.alive)
                continue
              const reach = group.radius + other.radius
              const dx = other.sx / other.count - x
              const dy = other.sy / other.count - y
              if (dx * dx + dy * dy >= reach * reach)
                continue
              group.count += other.count
              group.reporting += other.reporting
              group.sx += other.sx
              group.sy += other.sy
              group.south = Math.min(group.south, other.south)
              group.north = Math.max(group.north, other.north)
              group.west = Math.min(group.west, other.west)
              group.east = Math.max(group.east, other.east)
              group.radius = clusterRadius(group.count)
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
 * The groups of a list at a zoom, by distance (GH-4241): the stations are taken in a stable order, and each that is not yet in
 * a group starts one with every other station not yet in a group within `radius` pixels of it, drawn at the middle of its stations. The order
 * is the densest place first (the stations of a square of `radius` pixels with the most stations in it and the squares
 * around it, then the list's own order), so that a town's stations are taken together by a station of the town, not by one
 * at its edge that a grid's corner would have cut it at. Groups whose discs would overlap are then joined
 * (`mergeOverlapping`), so that every disc is over its own stations and no number is hidden by another. A group of one is that
 * station, drawn as a dot of `dot` pixels. The stations of every kind are grouped together (`reports` says which report): one
 * group for a place, whatever its stations' status, with the number of those that report.
 *
 * The groups depend on the list and the zoom only, never on the part of the map in view or on a drag. The neighbours are found
 * in a grid of squares of `radius` pixels (the 3 x 3 squares round a station), so the pass is linear in the list, and made
 * for one zoom when it is asked for (the map keeps the groups of a zoom until the list or the grouping changes). Measured on
 * GHCN daily's 132,894 stations (2026-11-19, a laptop): 10 to 16 ms at zoom 2 to 5, 20 and 31 ms at zoom 6 and 7, 68 ms at
 * zoom 8 in Node (51 ms in Chrome), where the grid of 80 px took 7 to 17 ms; one list spread over the world, with more groups, 98 ms at
 * zoom 8.
 *
 * @example
 * clusterStations(stations, 5, 40) // [{ count: 38, latitude: 52.4, longitude: 9.9, x, y, ... }, { count: 1, station, ... }]
 */
export function clusterStations(stations: PlacedStation[], zoom: number, radius: number, dot = dotRadius(zoom), reports?: (station: PlacedStation) => boolean): Cluster[] {
  const count = stations.length
  const xs = new Float64Array(count)
  const ys = new Float64Array(count)
  // the grid the neighbours are found in: squares of the radius, or larger where that would be more than GRID_MAX of them
  // across (a square larger than the radius only has more to look through, and finds the same neighbours)
  const size = TILE * 2 ** zoom
  const side = Math.max(radius, size / GRID_MAX)
  const across = Math.floor(size / side) + 1
  const squareOf = new Int32Array(count)
  // the stations of each square, by a counting sort that keeps the list's order in a square: `from[square]` to `from[square + 1]`
  const from = new Int32Array(across * across + 1)
  // the squares that have stations, in the order of the first station of each in the list
  const used: number[] = []
  for (let index = 0; index < count; index++) {
    const station = stations[index]!
    const at = worldPixels(station.latitude, station.longitude, zoom)
    xs[index] = at.x
    ys[index] = at.y
    const square = Math.floor(at.x / side) * across + Math.floor(at.y / side)
    squareOf[index] = square
    if (from[square + 1]!++ === 0)
      used.push(square)
  }
  for (let square = 0; square < across * across; square++)
    from[square + 1]! += from[square]!
  const members = new Int32Array(count)
  const filled = from.slice(0, across * across)
  for (let index = 0; index < count; index++)
    members[filled[squareOf[index]!]!++] = index
  const sizeOf = (column: number, row: number) => column < 0 || row < 0 || column >= across || row >= across ? 0 : from[column * across + row + 1]! - from[column * across + row]!
  // the density of a square: its stations and those of the eight round it, which are all within two radii of a station of it.
  // The densest square first, the squares of one density in the order of their first station in the list: packed into one
  // number each, which sorts as a number (the density is bounded by the list, and a list has under 2^22 squares in use)
  const ranked = new Float64Array(used.length)
  for (let rank = 0; rank < used.length; rank++) {
    const column = Math.floor(used[rank]! / across)
    const row = used[rank]! % across
    let density = 0
    for (let dc = -1; dc <= 1; dc++) {
      for (let dr = -1; dr <= 1; dr++)
        density += sizeOf(column + dc, row + dr)
    }
    ranked[rank] = (count - density) * 4_194_304 + rank
  }
  ranked.sort()
  const taken = new Uint8Array(count)
  const groups: Group[] = []
  const reach = radius * radius
  for (const packed of ranked) {
    const square = used[packed % 4_194_304]!
    const column = Math.floor(square / across)
    const row = square % across
    for (let at = from[square]!; at < from[square + 1]!; at++) {
      const seed = members[at]!
      if (taken[seed])
        continue
      const group: Group = { count: 0, reporting: 0, sx: 0, sy: 0, south: 90, west: 180, north: -90, east: -180, first: stations[seed]!, alive: true, radius: 0 }
      for (let dc = Math.max(column - 1, 0); dc <= Math.min(column + 1, across - 1); dc++) {
        for (let dr = Math.max(row - 1, 0); dr <= Math.min(row + 1, across - 1); dr++) {
          const near = dc * across + dr
          for (let other = from[near]!; other < from[near + 1]!; other++) {
            const index = members[other]!
            if (taken[index])
              continue
            const dx = xs[index]! - xs[seed]!
            const dy = ys[index]! - ys[seed]!
            if (dx * dx + dy * dy > reach)
              continue
            taken[index] = 1
            const station = stations[index]!
            group.count++
            if (!reports || reports(station))
              group.reporting++
            group.sx += xs[index]!
            group.sy += ys[index]!
            group.south = Math.min(group.south, station.latitude)
            group.north = Math.max(group.north, station.latitude)
            group.west = Math.min(group.west, station.longitude)
            group.east = Math.max(group.east, station.longitude)
          }
        }
      }
      groups.push(group)
    }
  }
  return mergeOverlapping(groups, dot, size).map((group) => {
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

/** The zoom the mirroring of `boundsAround` is done at: the map is the same shape at every zoom, only larger */
const MIRROR_ZOOM = 8

/**
 * The box a click on a group fits the map to: its stations' box, grown to be as far from the disc on every side as it is on
 * the one where it is farthest, so that the disc is the middle of it. The disc is drawn at the mean of the stations' positions
 * and the stations are not spread evenly round it (a town with outliers to one side), so the middle of the stations' box
 * (`bounds.getCenter()`, which GH-4209 found a click on a group centred the map on) is somewhere else than the disc: the map
 * zoomed in with the group off to one side. A map centred on the disc with this box shows all of the stations.
 *
 * The distances are mirrored in pixels of the world map (`worldPixels`), not in degrees: north of the equator a degree of
 * latitude is taller on the map, so a box mirrored in degrees is too short on the side of the disc that the stations are
 * not farthest on, and the zoom fitted to it cuts off the stations at the far side.
 */
export function boundsAround(cluster: Pick<Cluster, 'latitude' | 'longitude' | 'bounds'>): Cluster['bounds'] {
  const { latitude, longitude, bounds } = cluster
  const size = TILE * 2 ** MIRROR_ZOOM
  const disc = worldPixels(latitude, longitude, MIRROR_ZOOM)
  const northWest = worldPixels(bounds.north, bounds.west, MIRROR_ZOOM)
  const southEast = worldPixels(bounds.south, bounds.east, MIRROR_ZOOM)
  const halfWidth = Math.max(southEast.x - disc.x, disc.x - northWest.x)
  const halfHeight = Math.max(southEast.y - disc.y, disc.y - northWest.y)
  const top = worldPoint(disc.x - halfWidth, Math.max(0, disc.y - halfHeight), MIRROR_ZOOM)
  const bottom = worldPoint(disc.x + halfWidth, Math.min(size, disc.y + halfHeight), MIRROR_ZOOM)
  return {
    south: Math.max(-MAX_LATITUDE, bottom.latitude),
    north: Math.min(MAX_LATITUDE, top.latitude),
    west: top.longitude,
    east: bottom.longitude,
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
