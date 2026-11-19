import type { PlacedStation } from './map-tool'
import { dotRadius } from './map-tool'

/**
 * Groups of stations on the map tool (GH-4079): at the outer zooms the stations that lie close together are drawn as one
 * disc with their number, which a click zooms in on. Done here and drawn on the canvas tiles beside the dots, not with
 * `leaflet.markercluster`, whose groups are DOM markers: they would be stops of the keyboard (the map tool keeps its
 * stations out of the Tab order, see `StationMap.vue`) and a layer of 133,041 stations (GHCN daily) is too many of them.
 *
 * The groups are made by distance, in screen pixels at the zoom (GH-4241): stations are taken as seeds in a stable order, the
 * densest place first, and each seed's group forms round the middle of the stations about it, so a town's stations are one
 * group at the town, wherever a grid would have cut it. The neighbours are found in a grid of squares (a lookup, not a tree to
 * build), a few scans of it for each group, no index of all the zooms, and nothing to keep but the groups of each zoom the map
 * has been at.
 */

/**
 * What grouping sets, the two settings behind the switch on the map: the radius of a group in screen pixels (the stations
 * within it of the middle a group forms round are in it, unless a group has taken them first; groups that would overlap are
 * joined, so a group can be wider), and the zoom from which every station is its own dot.
 */
export interface Grouping {
  radius: number
  separateFrom: number
}

/** The one grouping the map has (GH-4209: the switch is on or off; the fine step of GH-4172 is gone), on by default, which the pickers take their separation zoom from */
export const GROUPING: Grouping = { radius: 60, separateFrom: 9 }

/**
 * How far the box of a layer that is asked for by the view reaches beyond it, in pixels of the map (GH-4078): the radius of a group,
 * so that a group at the edge of the view is made of all its stations, and 40 more for the groups that are joined and for the pan
 * that comes while the stations are on their way.
 */
export const BOX_PAD_PX = GROUPING.radius + 40

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
 * groupingFor(false, 133_041) // { on: true, compulsory: true, grouping: { radius: 60, separateFrom: 9 } }
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

/** The most squares across the grid that neighbours are found in (about a million squares at most, a few MB), so that a list that spans a deep zoom has no grid of a billion */
const GRID_MAX = 1024

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

/**
 * A grid of squares over the places of a list of points, to find the points near one without a tree: sized to the box of the
 * points, not to the world (a list of fifty stations at zoom 8 has a few squares, not a million), and its squares numbered
 * `column * rows + row` from the box's top left. A point with no position (NaN or infinite) is in no square (`squareOf` -1).
 * `side` is at least the one asked for, and larger where the box would have more than `GRID_MAX` squares across. The grid is of the
 * places with x clamped to the width of three worlds round the map (`gridX`): a longitude far beyond the world (1,000,000 degrees)
 * would stretch the box so that every real station fell in a few squares and the lookups were all of the list. Only the grid is
 * of the clamped places; the distances are of the true ones.
 */
interface Grid {
  side: number
  columns: number
  rows: number
  /** The top left of the box, which the squares are counted from */
  minX: number
  minY: number
  /** The squares' first entry in `members`: the entries of square `s` are `members[from[s]]` to `members[from[s + 1]]`, in the order of the points */
  from: Int32Array
  members: Int32Array
  squareOf: Int32Array
}

/** x as the grids have it: within one world's width of the map on each side (the world is `size` pixels wide) */
function gridX(x: number, size: number): number {
  return Math.min(2 * size, Math.max(-size, x))
}

function gridOf(xs: Float64Array, ys: Float64Array, wanted: number, size: number): Grid {
  const count = xs.length
  let minX = Number.POSITIVE_INFINITY
  let minY = Number.POSITIVE_INFINITY
  let maxX = Number.NEGATIVE_INFINITY
  let maxY = Number.NEGATIVE_INFINITY
  for (let index = 0; index < count; index++) {
    const x = gridX(xs[index]!, size)
    const y = ys[index]!
    if (!Number.isFinite(x) || !Number.isFinite(y))
      continue
    minX = Math.min(minX, x)
    maxX = Math.max(maxX, x)
    minY = Math.min(minY, y)
    maxY = Math.max(maxY, y)
  }
  const placed = minX <= maxX
  const side = Math.max(wanted, placed ? Math.max(maxX - minX, maxY - minY) / GRID_MAX : 0)
  const columns = placed ? Math.floor((maxX - minX) / side) + 1 : 0
  const rows = placed ? Math.floor((maxY - minY) / side) + 1 : 0
  const squareOf = new Int32Array(count)
  const from = new Int32Array(columns * rows + 1)
  for (let index = 0; index < count; index++) {
    const x = gridX(xs[index]!, size)
    const y = ys[index]!
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      squareOf[index] = -1
      continue
    }
    // the clamp is for a rounding at the far edge of the box: the box holds every point
    const square = Math.min(columns - 1, Math.floor((x - minX) / side)) * rows + Math.min(rows - 1, Math.floor((y - minY) / side))
    squareOf[index] = square
    from[square + 1]!++
  }
  for (let square = 0; square < columns * rows; square++)
    from[square + 1]! += from[square]!
  const members = new Int32Array(from[columns * rows]!)
  const filled = from.slice(0, columns * rows)
  for (let index = 0; index < count; index++) {
    if (squareOf[index]! >= 0)
      members[filled[squareOf[index]!]!++] = index
  }
  return { side, columns, rows, minX, minY, from, members, squareOf }
}

/** How many times the middle of a group is moved to the middle of the stations round it before the group is taken (see `clusterStations`) */
const MEAN_SHIFTS = 8

/** The number of stations round a middle from which it is not moved again: it is the mean of that many (see `clusterStations`) */
const STEADY = 100

/** The edge of the squares the neighbours of a group are looked for in: more than the two largest discs side by side */
const NEIGHBOUR_CELL = 64

/**
 * Joins the groups whose discs would overlap, until none do: a group is drawn at the middle of its stations, which is not
 * where it formed, so the discs of two groups that formed `radius` apart can reach over each other and hide each other's
 * number. A lone station counts as the dot it is drawn as. The joined group is bigger (a larger disc) and has moved to the
 * middle of all its stations, so another may now overlap it: the pass is made again until a pass joins nothing.
 *
 * The cascade is not capped: a cap would leave discs lying on each other where the stations are denser than a disc, which is
 * what the pass is for. With groups that formed a radius (60 px) apart, and discs of 12 to 27 px, it joins few: only where a
 * group's middle has moved toward its neighbour. The neighbours are looked for in a grid of squares of `NEIGHBOUR_CELL`
 * pixels over the groups' box, made for each pass from the groups' places (a lookup, not a tree).
 */
function mergeOverlapping(groups: Group[], dot: number, size: number): Group[] {
  let alive = groups
  for (let pass = 0; pass < 32; pass++) {
    const count = alive.length
    const xs = new Float64Array(count)
    const ys = new Float64Array(count)
    for (let index = 0; index < count; index++) {
      const group = alive[index]!
      group.radius = group.count === 1 ? dot : clusterRadius(group.count)
      xs[index] = group.sx / group.count
      ys[index] = group.sy / group.count
    }
    const { side, columns, rows, minX, minY, from, members } = gridOf(xs, ys, NEIGHBOUR_CELL, size)
    let joined = false
    for (const group of alive) {
      if (!group.alive)
        continue
      let again = true
      while (again) {
        again = false
        const x = group.sx / group.count
        const y = group.sy / group.count
        // a group that has grown has moved, but stays in the box of the groups: it is in the squares of the pass's own
        const column = Math.min(columns - 1, Math.max(0, Math.floor((gridX(x, size) - minX) / side)))
        const row = Math.min(rows - 1, Math.max(0, Math.floor((y - minY) / side)))
        const top = Math.max(row - 1, 0)
        const bottom = Math.min(row + 1, rows - 1)
        for (let dc = Math.max(column - 1, 0); dc <= Math.min(column + 1, columns - 1); dc++) {
          for (let at = from[dc * rows + top]!; at < from[dc * rows + bottom + 1]!; at++) {
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
    if (!joined)
      break
    alive = alive.filter(group => group.alive)
  }
  return alive.filter(group => group.alive)
}

/**
 * The groups of a list at a zoom, by distance (GH-4241): the stations are taken as seeds in a stable order, and each that is not
 * yet in a group starts one: the middle of the stations not yet in a group within `radius` pixels of the seed is found, and moved
 * to the middle of those within `radius` of it (up to `MEAN_SHIFTS` times), and the stations within `radius` of the middle it
 * comes to are the group, drawn at their mean. A seed that the middle has moved off, beyond a radius, is the group of the stations
 * round it (which are in none yet). The order is the densest place first: each station is ranked by how many stations lie within about a radius of it in
 * each direction (a window round the station itself), then by its place in the list. A town's stations are then
 * taken together by a station of the town's middle, not by one at its edge that a grid's corner would have cut it at.
 * Groups whose discs would overlap are then joined (`mergeOverlapping`), so that every disc is over its own stations and no
 * number is hidden by another: a station of a group that has been joined may be farther than `radius` from the one the group
 * formed round. A group of one is that station, drawn as a dot of `dot` pixels. The stations of every kind are grouped together
 * (`reports` says which report): one group for a place, whatever its stations' status, with the number of those that report.
 * A station with no position (NaN) is in no group.
 *
 * The groups depend on the list (in its order: the first of equally dense stations seeds) and the zoom only, never on the part
 * of the map in view or on a drag. The neighbours are found in a grid over the list's box (x clamped to three worlds round the
 * map, so that one far-off longitude does not stretch it), so the work is linear in the list (a few scans of the grid for each
 * group, `MEAN_SHIFTS` + 2 at most) and costs nothing for a world that is not in it, and it is made for one zoom when it is asked for (the map keeps the groups of
 * each zoom it has been at until the list or the grouping changes). The cost on GHCN daily's 132,894 stations is in the pull
 * request of GH-4241; the grid of 80 px this replaced took 8 to 17 ms at zoom 2 to 8.
 *
 * @example
 * clusterStations(stations, 5, 60) // [{ count: 38, latitude: 52.4, longitude: 9.9, x, y, ... }, { count: 1, station, ... }]
 */
export function clusterStations(stations: PlacedStation[], zoom: number, radius: number, dot = dotRadius(zoom), reports?: (station: PlacedStation) => boolean): Cluster[] {
  const count = stations.length
  const size = TILE * 2 ** zoom
  const xs = new Float64Array(count)
  const ys = new Float64Array(count)
  for (let index = 0; index < count; index++) {
    const station = stations[index]!
    const at = worldPixels(station.latitude, station.longitude, zoom)
    xs[index] = at.x
    ys[index] = at.y
  }
  // squares of half the radius (larger where the box is wide: `gridOf` then raises the side, and the neighbours are looked for as
  // many squares away as a radius reaches)
  const { side, columns, rows, minX, minY, from, members, squareOf } = gridOf(xs, ys, radius / 2, size)
  const reachSquares = Math.ceil(radius / side)
  // the stations in the squares from the top left to each corner (a sum over a rectangle of squares is then four lookups)
  const across = rows + 1
  const sums = new Int32Array((columns + 1) * across)
  for (let column = 0; column < columns; column++) {
    for (let row = 0; row < rows; row++) {
      const square = column * rows + row
      sums[(column + 1) * across + row + 1] = from[square + 1]! - from[square]! + sums[column * across + row + 1]! + sums[(column + 1) * across + row]! - sums[column * across + row]!
    }
  }
  const taken = new Uint8Array(count)
  const reach = radius * radius
  // Each station is ranked by the density round it: how many stations lie in the box of a radius round it (four lookups in the
  // sums above), the densest first, and those of one density in the order of the list: a counting sort, which keeps the list's
  // order within a density.
  const density = new Int32Array(count)
  let densest = 0
  for (let index = 0; index < count; index++) {
    if (squareOf[index]! < 0)
      continue
    const left = Math.max(0, Math.floor((gridX(xs[index]!, size) - radius - minX) / side))
    const right = Math.min(columns - 1, Math.floor((gridX(xs[index]!, size) + radius - minX) / side))
    const top = Math.max(0, Math.floor((ys[index]! - radius - minY) / side))
    const bottom = Math.min(rows - 1, Math.floor((ys[index]! + radius - minY) / side))
    density[index] = sums[(right + 1) * across + bottom + 1]! - sums[left * across + bottom + 1]! - sums[(right + 1) * across + top]! + sums[left * across + top]!
    densest = Math.max(densest, density[index]!)
  }
  const firstOf = new Int32Array(densest + 2)
  for (let index = 0; index < count; index++) {
    if (squareOf[index]! >= 0)
      firstOf[densest - density[index]! + 1]!++
  }
  for (let level = 0; level <= densest; level++)
    firstOf[level + 1]! += firstOf[level]!
  const order = new Int32Array(members.length)
  for (let index = 0; index < count; index++) {
    if (squareOf[index]! >= 0)
      order[firstOf[densest - density[index]!]!++] = index
  }
  /** A station into a group: it is taken */
  function take(group: Group, index: number) {
    taken[index] = 1
    const station = stations[index]!
    if (group.count++ === 0)
      group.first = station
    if (!reports || reports(station))
      group.reporting++
    group.sx += xs[index]!
    group.sy += ys[index]!
    group.south = Math.min(group.south, station.latitude)
    group.north = Math.max(group.north, station.latitude)
    group.west = Math.min(group.west, station.longitude)
    group.east = Math.max(group.east, station.longitude)
  }
  // The stations not yet in a group within `radius` of a point: how many (`found`), the sums of their places, and, where a group
  // is given, they are taken into it.
  let found = 0
  let foundX = 0
  let foundY = 0
  function scan(x: number, y: number, group: Group | null) {
    found = 0
    foundX = 0
    foundY = 0
    const column = Math.min(columns - 1, Math.max(0, Math.floor((gridX(x, size) - minX) / side)))
    const row = Math.min(rows - 1, Math.max(0, Math.floor((y - minY) / side)))
    const top = Math.max(row - reachSquares, 0)
    const bottom = Math.min(row + reachSquares, rows - 1)
    // the squares of a column from `top` to `bottom` are in one run of `members`
    for (let dc = Math.max(column - reachSquares, 0); dc <= Math.min(column + reachSquares, columns - 1); dc++) {
      for (let other = from[dc * rows + top]!; other < from[dc * rows + bottom + 1]!; other++) {
        const index = members[other]!
        if (taken[index])
          continue
        const dx = xs[index]! - x
        const dy = ys[index]! - y
        if (dx * dx + dy * dy > reach)
          continue
        found++
        foundX += xs[index]!
        foundY += ys[index]!
        if (!group)
          continue
        take(group, index)
      }
    }
  }
  const groups: Group[] = []
  for (const seed of order) {
    if (taken[seed])
      continue
    // The group forms round the middle of the stations that the seed reaches, and then round the middle of those that that reaches
    // (up to MEAN_SHIFTS times, until the middle moves less than 2 pixels): a seed at the edge of a town, however the stations are
    // ranked, thus draws the town's stations round their middle, where a station at the other edge would be left to a group of its own.
    let x = xs[seed]!
    let y = ys[seed]!
    let alone = false
    for (let step = 0; step < MEAN_SHIFTS; step++) {
      scan(x, y, null)
      if (found === 0)
        break
      // the seed alone: a station with none within a radius, which is most of the stations where they are far apart
      if (found === 1 && step === 0) {
        alone = true
        break
      }
      const moved = Math.hypot(foundX / found - x, foundY / found - y)
      x = foundX / found
      y = foundY / found
      // a middle of many stations is steady: it has moved to their mean, and a scan over so many again would only cost
      if (moved < 2 || found > STEADY)
        break
    }
    const group: Group = { count: 0, reporting: 0, sx: 0, sy: 0, south: 90, west: 180, north: -90, east: -180, first: stations[seed]!, alive: true, radius: 0 }
    if (alone)
      take(group, seed)
    else
      scan(x, y, group)
    if (group.count > 0)
      groups.push(group)
    // the seed is left where the middle has moved off it (a station at the edge of the town, beyond a radius of the middle): it
    // is the group of the stations round it, which are not in another
    if (!taken[seed]) {
      const rest: Group = { count: 0, reporting: 0, sx: 0, sy: 0, south: 90, west: 180, north: -90, east: -180, first: stations[seed]!, alive: true, radius: 0 }
      scan(xs[seed]!, ys[seed]!, rest)
      groups.push(rest)
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
