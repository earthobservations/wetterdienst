import type { PlacedStation } from './map-tool'

/**
 * Groups of stations on the map tool (GH-4079): at the outer zooms the stations that lie close together are drawn as one
 * disc with their number, which a click zooms in on. Done here and drawn on the canvas tiles beside the dots, not with
 * `leaflet.markercluster`, whose groups are DOM markers: they would be stops of the keyboard (the map tool keeps its
 * stations out of the Tab order, see `StationMap.vue`) and a layer of 133,041 stations (GHCN daily) is too many of them.
 *
 * The groups are made on a grid in screen pixels at the zoom: one pass over the list, a sum for each cell, no tree to
 * build and nothing to keep but the groups of the zoom in view.
 */

/** How much is grouped, as the control on the map offers it: no groups, or one of three steps */
export type GroupingChoice = 'off' | 'fine' | 'medium' | 'coarse'

export const GROUPING_CHOICES: GroupingChoice[] = ['off', 'fine', 'medium', 'coarse']

/**
 * What a step of the control sets, the two settings behind it: the radius of a group in screen pixels (every station of
 * a group is within it of the group's cell centre), and the zoom from which every station is its own dot. A coarser step
 * groups more, and keeps grouping to a closer zoom.
 */
export interface Grouping {
  radius: number
  separateFrom: number
}

export const GROUPINGS: Record<Exclude<GroupingChoice, 'off'>, Grouping> = {
  fine: { radius: 30, separateFrom: 8 },
  medium: { radius: 50, separateFrom: 9 },
  coarse: { radius: 80, separateFrom: 10 },
}

/** The step the map opens with, and the one the pickers take their separation zoom from */
export const DEFAULT_GROUPING: Exclude<GroupingChoice, 'off'> = 'medium'

/**
 * A layer whose list has more stations than this is always grouped, whatever the control says (maintainer, 2026-11-14):
 * the rule goes by the layer's count, not by a hand-picked list. The control then only sets how fine the groups are.
 * GHCN daily has 133,041 stations, MOSMIX about 5,600 and DWD's observations about 1,400, which follow the control.
 */
export const GROUPING_COMPULSORY_ABOVE = 10_000

/** What the map groups by for a choice and a layer of `count` stations: the step in force, whether it is forced, and its settings (null for none) */
export interface GroupingInForce {
  choice: GroupingChoice
  compulsory: boolean
  grouping: Grouping | null
}

/**
 * The grouping of a layer: the choice, except that a layer of more than `GROUPING_COMPULSORY_ABOVE` stations cannot be left
 * ungrouped and takes the default step where the choice is none.
 *
 * @example
 * groupingFor('off', 5_600) // { choice: 'off', compulsory: false, grouping: null }
 * groupingFor('off', 133_041) // { choice: 'medium', compulsory: true, grouping: { radius: 50, separateFrom: 9 } }
 */
export function groupingFor(choice: GroupingChoice, count: number): GroupingInForce {
  const compulsory = count > GROUPING_COMPULSORY_ABOVE
  const inForce = choice === 'off' && compulsory ? DEFAULT_GROUPING : choice
  return { choice: inForce, compulsory, grouping: inForce === 'off' ? null : GROUPINGS[inForce] }
}

/** Whether the stations are grouped at a zoom: a grouping is set and the zoom is outside the one every station is its own dot from */
export function isGroupedAt(grouping: Grouping | null, zoom: number): boolean {
  return grouping !== null && zoom < grouping.separateFrom
}

/** A group of stations at a zoom, or a lone station (`count` 1, which is drawn as a dot) */
export interface Cluster {
  latitude: number
  longitude: number
  count: number
  /** The box of its stations, which a click zooms to */
  bounds: { south: number, west: number, north: number, east: number }
  /** The station, for a group of one */
  station: PlacedStation | null
}

const TILE = 256

/** The position of a point at a zoom in pixels of the world map (Web Mercator, tiles of 256 px, as Leaflet draws them) */
export function worldPixels(latitude: number, longitude: number, zoom: number): { x: number, y: number } {
  const size = TILE * 2 ** zoom
  const sin = Math.sin(Math.max(-0.9999, Math.min(0.9999, latitude * Math.PI / 180)))
  return {
    x: (longitude + 180) / 360 * size,
    y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * size,
  }
}

/**
 * The groups of a list at a zoom: the stations in one square of 2 x `radius` pixels (so each is within `radius` of the
 * middle of it) are one group. A square with one station is that station.
 *
 * The list is gone through once and nothing is kept for a group but sums, so a list of 133,041 stations is a few
 * milliseconds, and the same at every zoom.
 *
 * @example
 * clusterStations(stations, 5, 50) // [{ count: 38, latitude: 52.4, longitude: 9.9, ... }, { count: 1, station, ... }]
 */
export function clusterStations(stations: PlacedStation[], zoom: number, radius: number): Cluster[] {
  const cell = radius * 2
  const cells = new Map<number, { count: number, lat: number, lon: number, south: number, west: number, north: number, east: number, first: PlacedStation }>()
  for (const station of stations) {
    const at = worldPixels(station.latitude, station.longitude, zoom)
    // a number for the cell: the columns of the widest world (zoom 16) fit under a million
    const key = Math.floor(at.x / cell) * 1_000_003 + Math.floor(at.y / cell)
    const group = cells.get(key)
    if (group) {
      group.count++
      group.lat += station.latitude
      group.lon += station.longitude
      group.south = Math.min(group.south, station.latitude)
      group.north = Math.max(group.north, station.latitude)
      group.west = Math.min(group.west, station.longitude)
      group.east = Math.max(group.east, station.longitude)
    }
    else {
      cells.set(key, { count: 1, lat: station.latitude, lon: station.longitude, south: station.latitude, west: station.longitude, north: station.latitude, east: station.longitude, first: station })
    }
  }
  const clusters: Cluster[] = []
  for (const group of cells.values()) {
    clusters.push({
      latitude: group.lat / group.count,
      longitude: group.lon / group.count,
      count: group.count,
      bounds: { south: group.south, west: group.west, north: group.north, east: group.east },
      station: group.count === 1 ? group.first : null,
    })
  }
  return clusters
}

/** The radius of the disc of a group in pixels: it grows with the logarithm of its number, from 11 px for two stations to 23 px for ten thousand */
export function clusterRadius(count: number): number {
  return Math.round(10 + 3.2 * Math.log10(Math.max(count, 1)))
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
 * The group of a list that a click at a pixel of the map is on, the one drawn on top where two overlap (the last of the list
 * is); a lone station is no group. `at` is the pixel clicked from the world's origin at the zoom, `slop` how far outside the
 * disc a click still is on it, in pixels.
 */
export function clusterAt(clusters: Cluster[], zoom: number, at: { x: number, y: number }, slop = 2): Cluster | null {
  let hit: Cluster | null = null
  let nearest = Number.POSITIVE_INFINITY
  for (const cluster of clusters) {
    if (cluster.count < 2)
      continue
    const centre = worldPixels(cluster.latitude, cluster.longitude, zoom)
    const distance = Math.hypot(centre.x - at.x, centre.y - at.y)
    if (distance <= clusterRadius(cluster.count) + slop && distance < nearest) {
      nearest = distance
      hit = cluster
    }
  }
  return hit
}

/**
 * The zoom a click on a group goes to: the one that fits the box of its stations, at least one in, and no farther than
 * the zoom from which every station is its own dot (the group is gone by then, if the box was a point).
 */
export function zoomForCluster(fitting: number, current: number, separateFrom: number, maxZoom: number): number {
  return Math.min(Math.max(fitting, current + 1), separateFrom, maxZoom)
}
