import type { components } from '../../.generated/api-schema'
import type { Point } from './map-tool'
import type { ProviderCredit } from './provider-credit'
import { creditOf } from './provider-credit'

/**
 * DWD's design rainfall (KOSTRA-DWD-2020, GH-4500) as the Heavy-rainfall tool reads it: what `GET /api/kostra` answers for a point
 * read into the table the page draws (22 durations by 9 return periods, each with a depth, an intensity and DWD's uncertainty), the
 * cell of DWD's 5 km grid drawn on the map, and the few decisions of the page (the point in the link, the label of a duration).
 *
 * The values are DWD's estimates for the 5 km cell that holds the point, not measurements at it.
 */

type Answer = components['schemas']['_KostraWithMetadataDict']

/** The durations of a rain DWD gives, in minutes: 5 minutes to 7 days */
export const KOSTRA_DURATIONS = [5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 360, 540, 720, 1080, 1440, 2880, 4320, 5760, 7200, 8640, 10080] as const

/** The return periods DWD gives, in years: the rain of a duration that comes back every so many years on average */
export const KOSTRA_RETURN_PERIODS = [1, 2, 3, 5, 10, 20, 30, 50, 100] as const

/** What the table shows: the depth of the rain in mm, or its intensity in l/(s·ha) */
export type KostraQuantity = 'depth' | 'intensity'

export interface KostraCell {
  /** DWD's own name of the cell: the row (counted from the north) and the column, `144197` */
  indexRc: string
  /** Its centre */
  latitude: number
  longitude: number
}

/** One value of the table: null where DWD gives none */
export interface KostraEntry {
  depthMm: number | null
  intensity: number | null
  /** DWD's tolerance in plus-minus percent, for the depth and for the intensity */
  uncertaintyPercent: number | null
}

export interface KostraTable {
  edition: string
  cell: KostraCell
  /** `rows[d][r]` is the value of `KOSTRA_DURATIONS[d]` and `KOSTRA_RETURN_PERIODS[r]`, null where the answer has none */
  rows: (KostraEntry | null)[][]
  credit: ProviderCredit | null
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const number = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null

/**
 * The table of an answer, or null where it is not one (no cell, no list of values): a page that read a proxy's page for it would show
 * a table of nothing. A value the answer holds for a duration or a return period DWD does not give is left out.
 */
export function parseKostra(answer: unknown): KostraTable | null {
  if (!isRecord(answer) || !isRecord(answer.cell) || !Array.isArray(answer.values))
    return null
  const cell = answer.cell as Partial<Answer['cell']>
  const latitude = number(cell.latitude)
  const longitude = number(cell.longitude)
  if (typeof cell.index_rc !== 'string' || latitude === null || longitude === null)
    return null
  const rows: (KostraEntry | null)[][] = KOSTRA_DURATIONS.map(() => KOSTRA_RETURN_PERIODS.map(() => null))
  for (const value of answer.values as unknown[]) {
    if (!isRecord(value))
      continue
    const duration = (KOSTRA_DURATIONS as readonly number[]).indexOf(Number(value.duration_minutes))
    const period = (KOSTRA_RETURN_PERIODS as readonly number[]).indexOf(Number(value.return_period_years))
    if (duration < 0 || period < 0)
      continue
    rows[duration]![period] = { depthMm: number(value.depth_mm), intensity: number(value.intensity_l_s_ha), uncertaintyPercent: number(value.uncertainty_percent) }
  }
  return {
    edition: typeof answer.edition === 'string' ? answer.edition : 'KOSTRA-DWD-2020',
    cell: { indexRc: cell.index_rc, latitude, longitude },
    rows,
    credit: creditOf(answer.metadata),
  }
}

/** The number a table shows for an entry in the quantity chosen, null where DWD gives none */
export function quantityOf(entry: KostraEntry | null, quantity: KostraQuantity): number | null {
  if (!entry)
    return null
  return quantity === 'depth' ? entry.depthMm : entry.intensity
}

/** The unit of the quantity, as it is written in every language */
export const KOSTRA_UNITS: Record<KostraQuantity, string> = { depth: 'mm', intensity: 'l/(s·ha)' }

// ------------------------------------------------------------------------------------------------ the label of a duration

type Translate = (key: string, named?: Record<string, unknown>) => string

/**
 * A duration as it is read: minutes under an hour and where it is not a whole number of hours (`5 min`, `90 min`), hours for a whole
 * number of them under a day (`1 h`, `12 h`), days for a whole number of them (`1 d`, `7 d`). The unit is the language's own
 * abbreviation (`kostra.duration.*`); the number is a plain integer in every language.
 */
export function durationLabel(minutes: number, t: Translate): string {
  if (minutes >= 1440 && minutes % 1440 === 0)
    return t('kostra.duration.days', { n: minutes / 1440 })
  if (minutes >= 60 && minutes < 1440 && minutes % 60 === 0)
    return t('kostra.duration.hours', { n: minutes / 60 })
  return t('kostra.duration.minutes', { n: minutes })
}

// ------------------------------------------------------------------------------------------------ the point in the link

/** A decimal number as a link writes it: an optional sign, digits and an optional fraction, and nothing else (`Number` would read `0x34` as 52 and `1e1` as 10) */
const DECIMAL = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/

/** The point of a link's `lat` and `lon`, or null where either is missing, is no decimal number or is no place on the globe */
export function linkPoint(query: Record<string, unknown>): Point | null {
  const read = (value: unknown): number | null => {
    const text = Array.isArray(value) ? value[0] : value
    if (typeof text !== 'string' || !DECIMAL.test(text.trim()))
      return null
    const parsed = Number(text.trim())
    return Number.isFinite(parsed) ? parsed : null
  }
  const latitude = read(query.lat)
  const longitude = read(query.lon)
  if (latitude === null || longitude === null || Math.abs(latitude) > 90 || Math.abs(longitude) > 180)
    return null
  return { latitude, longitude }
}

/** A coordinate to the four decimals a link keeps (about 11 m: far less than the 5 km cell the answer is for) */
export function roundLinkCoordinate(value: number): number {
  return Math.round(value * 10_000) / 10_000
}

/** The `lat` and `lon` of a link for a point, rounded, as text with a point in every language */
export function queryOfPoint(point: Point): { lat: string, lon: string } {
  return { lat: String(roundLinkCoordinate(point.latitude)), lon: String(roundLinkCoordinate(point.longitude)) }
}

/** The point as the page writes it: a point in every language, as a position is copied into a map or a query */
export function pointText(point: Point): string {
  return `${roundLinkCoordinate(point.latitude).toFixed(4)}, ${roundLinkCoordinate(point.longitude).toFixed(4)}`
}

// ------------------------------------------------------------------------------------------------ the cell on the map

/** The width of a cell of DWD's grid, in metres */
export const CELL_METRES = 5000

const EARTH_RADIUS = 6_371_007
/** The centre of DWD's grid, ETRS89-LAEA (EPSG:3035): 52 N, 10 E */
const GRID_CENTRE = { latitude: 52, longitude: 10 }
const rad = (degrees: number) => degrees * Math.PI / 180
const deg = (radians: number) => radians * 180 / Math.PI

/** Lambert azimuthal equal-area, on the sphere, about the centre of the grid */
function toGrid(latitude: number, longitude: number): [number, number] {
  const phi = rad(latitude)
  const phi0 = rad(GRID_CENTRE.latitude)
  const dLambda = rad(longitude - GRID_CENTRE.longitude)
  const k = Math.sqrt(2 / (1 + Math.sin(phi0) * Math.sin(phi) + Math.cos(phi0) * Math.cos(phi) * Math.cos(dLambda)))
  return [
    EARTH_RADIUS * k * Math.cos(phi) * Math.sin(dLambda),
    EARTH_RADIUS * k * (Math.cos(phi0) * Math.sin(phi) - Math.sin(phi0) * Math.cos(phi) * Math.cos(dLambda)),
  ]
}

function fromGrid(x: number, y: number): [number, number] {
  const phi0 = rad(GRID_CENTRE.latitude)
  const rho = Math.hypot(x, y)
  if (rho === 0)
    return [GRID_CENTRE.latitude, GRID_CENTRE.longitude]
  const c = 2 * Math.asin(rho / (2 * EARTH_RADIUS))
  const phi = Math.asin(Math.cos(c) * Math.sin(phi0) + y * Math.sin(c) * Math.cos(phi0) / rho)
  const lambda = rad(GRID_CENTRE.longitude) + Math.atan2(x * Math.sin(c), rho * Math.cos(phi0) * Math.cos(c) - y * Math.sin(phi0) * Math.sin(c))
  return [deg(phi), deg(lambda)]
}

/**
 * The four corners of a cell as `[latitude, longitude]`, from its centre: the cell is a 5 km square of the grid's own projection, so
 * on a map it is a square turned a little (about 3 degrees at Dresden), not a box of latitudes and longitudes. Drawn on the sphere, which
 * differs from DWD's ellipsoid by metres at this size, as an outline for the eye and not a boundary to measure with.
 */
export function cellCorners(cell: Pick<KostraCell, 'latitude' | 'longitude'>): [number, number][] {
  const [x, y] = toGrid(cell.latitude, cell.longitude)
  const half = CELL_METRES / 2
  return [[-half, half], [half, half], [half, -half], [-half, -half]].map(([dx, dy]) => fromGrid(x + dx!, y + dy!))
}

// ------------------------------------------------------------------------------------------------ the colours of the curves

/**
 * The nine return periods are an order, from the shortest to the longest, so they are one hue from light to dark (a sequential ramp, not nine
 * hues): by day the lightest is 3.4:1 against the white of a card and the darkest 13.6:1; at night it is turned, the longest period
 * the lightest on the dark card (3.1:1 to 11.3:1). `tests/unit/kostra.test.ts` holds both to 3:1.
 */
export const KOSTRA_CURVE_COLOURS = {
  light: ['#5d8ece', '#4d81c3', '#3e74b8', '#2f67ad', '#1e5ba1', '#134e91', '#084382', '#003772', '#002c63'],
  dark: ['#3f70ad', '#4a7dbf', '#548bd0', '#5f99e2', '#6aa7f4', '#7bb6ff', '#8bc4ff', '#9cd3ff', '#ace2ff'],
} as const
