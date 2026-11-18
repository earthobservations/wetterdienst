import { timestampDate } from './timestamp'

/**
 * The thunderstorm cells of DWD's KONRAD3D (GH-4208), as the map shows them: what the backend's `GET /api/storm-cells`
 * answers (`dwd/storm_cells`, GH-4202) read into the few things the map draws and tells, and the decisions of the drawing
 * (the style of a severity, where the arrow of the motion points, what a cell is called in words).
 *
 * KONRAD3D writes a scan every 5 minutes and about 80 % of them hold no cell, so an empty scan is the usual answer and
 * says when it was true. The motion of a cell is not DWD's: the backend calculates its direction from the first two
 * positions of the cell's forecast track (`direction_degrees`), and the map says so wherever it shows it. The mesocyclone
 * group of a cell is left out (decided on GH-4090).
 */

/** The severity of a cell as DWD gives it: 0 weak, 1 moderate, 2 severe, 3 extreme */
export type Severity = 0 | 1 | 2 | 3

export const SEVERITIES: readonly Severity[] = [0, 1, 2, 3]

/** How often the scan is asked for again while the layer is shown: DWD writes one every 5 minutes */
export const REFRESH_MS = 5 * 60 * 1000

/** A point of an outline as Leaflet takes it: latitude, longitude */
export type LatLng = [latitude: number, longitude: number]

/** One cell, as far as the map reads it */
export interface StormCell {
  /** The cell's identifier of the scan (not unique over time: DWD reuses it after a cell has died), which the list names it by */
  id: string
  /** Null where the answer gives none or one that is no severity */
  severity: Severity | null
  /**
   * Every surface of its outline (a cell can be in several), each a list of rings, the first its edge and any other a hole in
   * it, as Leaflet takes a multipolygon; empty where DWD gave none
   */
  outline: LatLng[][][]
  latitude: number | null
  longitude: number | null
  /** How fast the cell moves, in km/h */
  speedKmh: number | null
  /** The bearing the cell moves towards in degrees clockwise from north: calculated by the backend from the forecast track, not DWD's */
  directionDegrees: number | null
}

/** The terms the data is published under, from the `metadata` block of the answer */
export interface StormCredit {
  /** The credit line the provider asks for ("Source: Deutscher Wetterdienst") */
  attribution: string | null
  copyright: string | null
  /** The licence: its name, its SPDX identifier where it has one, and the page of its terms */
  license: { name: string, spdx: string | null, url: string } | null
}

/** A scan as the layer holds it: the cells, which scan they are of, and what the answer warned of */
export interface StormScan {
  /** The reference time of the scan (ISO text, UTC), the start of DWD's radar cycle: an empty scan has it too */
  referenceTime: string | null
  cells: StormCell[]
  /** The newest scan is much older than it should be (the backend's `scan-stale` warning): an empty scan is then no all-clear */
  stale: boolean
  credit: StormCredit | null
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const finite = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null
const text = (value: unknown): string | null => typeof value === 'string' && value.trim() !== '' ? value : null

/** A severity of the answer: an integer of 0 to 3, else none */
function severityOf(value: unknown): Severity | null {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= 3 ? value as Severity : null
}

/** A ring of GeoJSON (`[longitude, latitude]` points) as Leaflet's (`[latitude, longitude]`), the points that are numbers only; a ring of fewer than three is no outline */
function ringOf(ring: unknown): LatLng[] {
  if (!Array.isArray(ring))
    return []
  const points: LatLng[] = []
  for (const point of ring) {
    const longitude = Array.isArray(point) ? finite(point[0]) : null
    const latitude = Array.isArray(point) ? finite(point[1]) : null
    if (latitude !== null && longitude !== null && Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180)
      points.push([latitude, longitude])
  }
  return points.length >= 3 ? points : []
}

/**
 * The surfaces of a cell's GeoJSON geometry, where it is a polygon or a multipolygon: a cell's outline can be in parts,
 * and every part is drawn. A surface is its rings, the first its edge and any other a hole in it.
 */
export function outlineOf(geometry: unknown): LatLng[][][] {
  if (!isRecord(geometry) || !Array.isArray(geometry.coordinates))
    return []
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.type === 'MultiPolygon' ? geometry.coordinates : []
  const surfaces: LatLng[][][] = []
  for (const polygon of polygons) {
    if (!Array.isArray(polygon))
      continue
    const rings = polygon.map(ringOf)
    // the first ring of a polygon is its edge: without it the holes are of nothing
    if (rings[0]?.length)
      surfaces.push(rings.filter(ring => ring.length))
  }
  return surfaces
}

/** One entry of the answer's `cells` as a {@link StormCell}, or null for what is no cell (no object) */
export function parseCell(entry: unknown, index: number): StormCell | null {
  if (!isRecord(entry))
    return null
  const id = entry.cell_id != null ? String(entry.cell_id) : entry.code != null ? String(entry.code) : String(index + 1)
  const speed = finite(entry.cell_speed_kmh)
  const direction = finite(entry.direction_degrees)
  // the geometry of a cell asked for as an outline; a centre is a point, which is no outline
  const geometry = isRecord(entry.geometry) && entry.geometry.type === 'Point' ? null : entry.geometry
  return {
    id,
    severity: severityOf(entry.severity),
    outline: outlineOf(geometry),
    latitude: finite(entry.centroid_latitude),
    longitude: finite(entry.centroid_longitude),
    speedKmh: speed !== null && speed >= 0 ? speed : null,
    directionDegrees: direction !== null && direction >= 0 && direction <= 360 ? direction % 360 : null,
  }
}

function creditOf(metadata: unknown): StormCredit | null {
  const provider = isRecord(metadata) && isRecord(metadata.provider) ? metadata.provider : null
  if (!provider)
    return null
  const license = isRecord(provider.license) && text(provider.license.name) && text(provider.license.url)
    ? { name: text(provider.license.name)!, spdx: text(provider.license.spdx_id), url: text(provider.license.url)! }
    : null
  const credit = { attribution: text(provider.attribution), copyright: text(provider.copyright), license }
  return credit.attribution || credit.copyright || credit.license ? credit : null
}

/**
 * The answer of `GET /api/storm-cells` as a {@link StormScan}. The cells are sorted for a list that reads from the
 * dangerous down: the most severe first, then by identifier, so a refresh that changes nothing changes no order.
 * An answer that has no list of cells is no scan (the caller's error), which is told by the thrown message.
 */
export function parseScan(answer: unknown): StormScan {
  if (!isRecord(answer) || !Array.isArray(answer.cells))
    throw new TypeError('The answer has no list of thunderstorm cells')
  const cells = answer.cells.map(parseCell).filter((cell): cell is StormCell => cell !== null)
  cells.sort((a, b) => (b.severity ?? -1) - (a.severity ?? -1) || a.id.localeCompare(b.id, 'en', { numeric: true }))
  const warnings = isRecord(answer.metadata) && Array.isArray(answer.metadata.warnings) ? answer.metadata.warnings : []
  const referenceTime = text(answer.reference_time)
  return {
    referenceTime: referenceTime && timestampDate(referenceTime) ? referenceTime : null,
    cells,
    stale: warnings.some(warning => isRecord(warning) && warning.code === 'scan-stale'),
    credit: creditOf(answer.metadata),
  }
}

/** How many cells the list in the panel shows before "Show all": a day of storms has some hundred, which would push the stations out of the panel */
export const LIST_LIMIT = 10

/** The cells the list shows: the first {@link LIST_LIMIT} (the most severe, the scan is sorted so), or all of them where the reader asked */
export function listed(cells: StormCell[], all: boolean): StormCell[] {
  return all || cells.length <= LIST_LIMIT ? cells : cells.slice(0, LIST_LIMIT)
}

/** The cells of the scan that have an outline or a centre to draw: a cell that has neither is only in the list */
export function drawable(cells: StormCell[]): StormCell[] {
  return cells.filter(cell => cell.outline.length > 0 || (cell.latitude !== null && cell.longitude !== null))
}

/**
 * How a severity is drawn. Colour is never the only cue (WCAG 1.4.1): the number of the severity is written on the
 * mark at the cell's centre, and the edge is the thicker the more severe the cell, dashed for the weakest. The colours
 * are DWD's (green, yellow, red, violet) in the shades that hold 3:1 against the map's light tones (1.4.11) and give
 * the white number of the mark 4.5:1 or more: the yellow of "moderate" is an amber for that reason.
 */
export interface SeverityStyle {
  /** The edge and the mark */
  color: string
  /** The edge's width in pixels */
  weight: number
  /** The edge's dashes, or null for a solid one */
  dashArray: string | null
  /** The fill's opacity: the more severe, the stronger */
  fillOpacity: number
  /** What the mark says: the number of the severity, a question mark where there is none */
  text: string
}

export const SEVERITY_STYLES: Record<Severity, SeverityStyle> = {
  0: { color: '#1b7a34', weight: 2, dashArray: '6 4', fillOpacity: 0.14, text: '0' },
  1: { color: '#b35900', weight: 2.5, dashArray: null, fillOpacity: 0.2, text: '1' },
  2: { color: '#c62828', weight: 3.5, dashArray: null, fillOpacity: 0.26, text: '2' },
  3: { color: '#6a1b9a', weight: 4.5, dashArray: null, fillOpacity: 0.32, text: '3' },
}

/** A cell with no severity: grey, dotted, and a question mark */
export const UNKNOWN_SEVERITY_STYLE: SeverityStyle = { color: '#5b6577', weight: 2, dashArray: '2 4', fillOpacity: 0.1, text: '?' }

export function styleOf(severity: Severity | null): SeverityStyle {
  return severity === null ? UNKNOWN_SEVERITY_STYLE : SEVERITY_STYLES[severity]
}

/**
 * Whether the cell has a motion to draw as an arrow and to tell: a direction, and a speed that is not nil. A cell that
 * stands (under 1 km/h) has no direction worth an arrow, and a speed with no direction is told in words only.
 */
export function hasMotion(cell: Pick<StormCell, 'speedKmh' | 'directionDegrees'>): boolean {
  return cell.directionDegrees !== null && (cell.speedKmh === null || cell.speedKmh >= 1)
}

/** The eight points of the compass, from north clockwise, which a bearing is told by */
export const COMPASS_POINTS = ['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw'] as const
export type CompassPoint = typeof COMPASS_POINTS[number]

/** The point of the compass a bearing in degrees is nearest: 0 and 360 north, 45 north-east, 337.5 and more north */
export function compassPoint(degrees: number): CompassPoint {
  return COMPASS_POINTS[Math.round((((degrees % 360) + 360) % 360) / 45) % 8]!
}

/** The side of the mark's square, in pixels */
export const MARK_SIZE = 64

/**
 * The mark at a cell's centre as an inline SVG, which Leaflet lays over the map as a div icon: a disc with the number
 * of the severity, and, where the cell has a motion, an arrow from the disc in the direction of it, dashed to say that
 * the direction is calculated. The mark is no stop of the keyboard and is hidden from assistive technology: the list
 * of the cells in the panel is its text.
 */
export function markSvg(cell: Pick<StormCell, 'severity' | 'speedKmh' | 'directionDegrees'>): string {
  const style = styleOf(cell.severity)
  const middle = MARK_SIZE / 2
  const arrow = hasMotion(cell) && cell.directionDegrees !== null
    // pointing up before it is turned by the bearing about the middle: a shaft from the disc's edge, and a head
    ? `<g transform="rotate(${Math.round(cell.directionDegrees * 10) / 10} ${middle} ${middle})" fill="none" stroke-linecap="round" stroke-linejoin="round">`
    + `<path d="M${middle} ${middle - 11} V${middle - 25}" stroke="#ffffff" stroke-width="6.5"/>`
    + `<path d="M${middle - 6} ${middle - 20} L${middle} ${middle - 27} L${middle + 6} ${middle - 20}" stroke="#ffffff" stroke-width="6.5"/>`
    + `<path d="M${middle} ${middle - 11} V${middle - 25}" stroke="${style.color}" stroke-width="2.5" stroke-dasharray="3 3"/>`
    + `<path d="M${middle - 6} ${middle - 20} L${middle} ${middle - 27} L${middle + 6} ${middle - 20}" stroke="${style.color}" stroke-width="2.5"/>`
    + `</g>`
    : ''
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${MARK_SIZE}" height="${MARK_SIZE}" viewBox="0 0 ${MARK_SIZE} ${MARK_SIZE}" aria-hidden="true" focusable="false">`
    + `${arrow}<circle cx="${middle}" cy="${middle}" r="10" fill="${style.color}" stroke="#ffffff" stroke-width="2"/>`
    + `<text x="${middle}" y="${middle + 0.5}" text-anchor="middle" dominant-baseline="central" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#ffffff">${style.text}</text>`
    + `</svg>`
}

/** The age after which a scan is out of date, as the backend's `scan-stale` warning has it (`SCAN_STALE_AFTER`): 20 minutes */
export const OUTDATED_AFTER_MS = 20 * 60 * 1000

/**
 * Whether a scan is out of date at `now`: its reference time (the start of DWD's radar cycle) is more than 20 minutes behind.
 * A scan kept while the layer was off, the tab hidden or a refresh failing ages; its cells, which were true then, are then
 * no longer drawn as the sky now. A scan with no time of its own is not told out of date, as nothing says it is.
 */
export function isOutdated(referenceTime: string | null, now: number): boolean {
  const at = referenceTime ? timestampDate(referenceTime) : null
  return at !== null && now - at.getTime() > OUTDATED_AFTER_MS
}

/** The bearing from one point to another in degrees clockwise from north (0 to 360), the initial course of the great circle */
export function bearingDegrees(from: { latitude: number, longitude: number }, to: { latitude: number, longitude: number }): number {
  const rad = Math.PI / 180
  const dLon = (to.longitude - from.longitude) * rad
  const y = Math.sin(dLon) * Math.cos(to.latitude * rad)
  const x = Math.cos(from.latitude * rad) * Math.sin(to.latitude * rad) - Math.sin(from.latitude * rad) * Math.cos(to.latitude * rad) * Math.cos(dLon)
  return (Math.atan2(y, x) / rad + 360) % 360
}

/** The box of a cell's outline: its parts together */
function outlineBox(cell: Pick<StormCell, 'outline'>): { south: number, west: number, north: number, east: number } | null {
  const points = cell.outline.flat(2)
  if (!points.length)
    return null
  const latitudes = points.map(point => point[0])
  const longitudes = points.map(point => point[1])
  return { south: Math.min(...latitudes), north: Math.max(...latitudes), west: Math.min(...longitudes), east: Math.max(...longitudes) }
}

/** Where a cell is: its centre, or the middle of its outline where DWD gave none, and the box the map fits to it; null where it has neither */
export function cellView(cell: Pick<StormCell, 'outline' | 'latitude' | 'longitude'>): { latitude: number, longitude: number, bounds: { south: number, west: number, north: number, east: number } } | null {
  const box = outlineBox(cell)
  const latitude = cell.latitude ?? (box ? (box.south + box.north) / 2 : null)
  const longitude = cell.longitude ?? (box ? (box.west + box.east) / 2 : null)
  if (latitude === null || longitude === null)
    return null
  // a cell with no outline is a point: a box of a few kilometres round it, which the map zooms to a town
  const pad = 0.03
  return { latitude, longitude, bounds: box ?? { south: latitude - pad, north: latitude + pad, west: longitude - pad, east: longitude + pad } }
}

/** A position rounded to two decimals (about a kilometre) with a point, as it is read out: `50.10, 8.70` */
export function roundedPosition(point: { latitude: number, longitude: number }): string {
  return `${point.latitude.toFixed(2)}, ${point.longitude.toFixed(2)}`
}

const escapeHtml = (value: string) => value.replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', '\'': '&#39;' })[character]!)

/**
 * The credit of the cells' data as a line of the map's attribution (Leaflet takes HTML): the provider's credit line, the
 * product, and the licence as a link to its terms. Both come from the answer, so they are escaped, and a link is made only
 * for an `http(s)` address.
 */
export function creditHtml(credit: { text: string, license: { label: string, url: string } | null }): string {
  const link = credit.license && /^https?:\/\//i.test(credit.license.url)
    ? `, <a href="${escapeHtml(credit.license.url)}" target="_blank" rel="noopener">${escapeHtml(credit.license.label)}</a>`
    : ''
  return `${escapeHtml(credit.text)}${link}`
}
