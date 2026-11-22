import type { ProviderCredit } from './provider-credit'
import { formatNumber, withData } from './format'
import { clockSkew, creditOf } from './provider-credit'
import { timestampDate } from './timestamp'

/**
 * DWD's precipitation radar as the Radar tool reads it (GH-3788): what the backend's `GET /api/radar/frames` answers read into the
 * few things the page draws and tells (the frames of the loop, where the image lies, the legend, the credit), and the decisions of
 * the player (which frame shows first, how the loop goes on, what a time is called in words).
 *
 * The frames are the analysis of the last two hours (`observation`, one for every run of DWD's RV composite, every 5 minutes) and
 * the 24 frames of DWD's forecast of the newest run (`forecast`, 5 to 120 minutes after it), which is an extrapolation of the
 * recent movement of the rain and no weather model. The times are UTC with a `Z`; the page writes them in the reader's zone.
 */

/** The product the page asks for: DWD's RV composite, which is both the loop and its forecast */
export const RADAR_PRODUCT = 'rv'
/** How many minutes of analysis the loop holds */
export const PAST_MINUTES = 120

/**
 * The view the map opens on (`[[south, west], [north, east]]`): Germany's extent, which the radar is for. DWD's composite reaches a
 * little beyond it, and the images are laid over the bounds of the answer itself; the reader can move the map to see the rest.
 */
export const RADAR_VIEW: [[number, number], [number, number]] = [[47.2, 5.8], [55.1, 15.1]]

/** How often the list of the frames is asked for again: a run comes every 5 minutes, and is 3 to 8 minutes old when it appears */
export const RADAR_REFRESH_MS = 5 * 60 * 1000

/**
 * How many frames are loaded at once. The server answers a 33rd request at once with a 503 (it serves 32), and a page that
 * asked for all 49 frames together would crowd out its own list, the cells and the tab beside it: 5 at a time.
 */
export const PRELOAD_CONCURRENCY = 5

/** How long a frame is shown while the loop plays (49 frames take about 20 seconds), and how long the last one is held before it starts again */
export const FRAME_MS = 400
export const DWELL_MS = 1500

/** The newest run older than this (the backend's `radar-stale` warning) says DWD's feed has stopped: 20 minutes */
export const STALE_AFTER_MS = 20 * 60 * 1000

export type FrameKind = 'observation' | 'forecast'

export interface RadarFrame {
  /** The UTC time the 5 minutes of the frame end at (ISO text, with its `Z`) */
  time: string
  /** The run of DWD it is read from: with it the image never changes while DWD keeps the run, which makes it cacheable for an hour */
  run: string
  /** Minutes after the run (0 for the analysis, 5 to 120 for the forecast) */
  leadMinutes: number
  kind: FrameKind
  /** `time` as a number of milliseconds */
  at: number
}

/** One class of the legend: the rates (mm/h) a colour stands for, the upper one null for the last, open class */
export interface LegendClass {
  lower: number
  upper: number | null
  color: string
}

export interface RadarLegend {
  unit: string
  /** Rates under this are as transparent as no rain */
  transparentBelow: number
  classes: LegendClass[]
}

/** Where the images lie, in WGS84 degrees: the outer edges, which a Leaflet `ImageOverlay` stretches the image over */
export interface RadarBounds {
  west: number
  south: number
  east: number
  north: number
}

export interface RadarLoop {
  /** In time order: the loop, then its forecast */
  frames: RadarFrame[]
  /** The newest run, which the forecast is of */
  run: string
  bounds: RadarBounds
  legend: RadarLegend
  /** The newest run is much older than it should be (the backend's `radar-stale` warning) */
  stale: boolean
  credit: ProviderCredit | null
  /** The server's clock minus the device's when the answer was read, from its `retrieved_at` (ms): the age of the newest run is judged by the server's time */
  clockSkewMs: number
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const finite = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null

function frameOf(entry: unknown): RadarFrame | null {
  if (!isRecord(entry) || typeof entry.time !== 'string' || typeof entry.run !== 'string')
    return null
  const at = timestampDate(entry.time)
  const lead = finite(entry.lead_minutes)
  if (!at || !timestampDate(entry.run) || lead === null || (entry.kind !== 'observation' && entry.kind !== 'forecast'))
    return null
  return { time: entry.time, run: entry.run, leadMinutes: lead, kind: entry.kind, at: at.getTime() }
}

function boundsOf(image: unknown): RadarBounds | null {
  const bounds = isRecord(image) && isRecord(image.bounds) ? image.bounds : null
  if (!bounds)
    return null
  const [west, south, east, north] = [finite(bounds.west), finite(bounds.south), finite(bounds.east), finite(bounds.north)]
  if (west === null || south === null || east === null || north === null || !(west < east) || !(south < north))
    return null
  if (Math.abs(south) > 90 || Math.abs(north) > 90 || Math.abs(west) > 180 || Math.abs(east) > 180)
    return null
  return { west, south, east, north }
}

function legendOf(legend: unknown): RadarLegend | null {
  if (!isRecord(legend) || !Array.isArray(legend.classes))
    return null
  const classes: LegendClass[] = []
  for (const entry of legend.classes) {
    const lower = isRecord(entry) ? finite(entry.lower) : null
    if (!isRecord(entry) || lower === null || typeof entry.color !== 'string' || !/^#[\da-f]{6}$/i.test(entry.color))
      return null
    classes.push({ lower, upper: finite(entry.upper), color: entry.color })
  }
  if (!classes.length)
    return null
  return { unit: typeof legend.unit === 'string' && legend.unit ? legend.unit : 'mm/h', transparentBelow: finite(legend.transparent_below) ?? classes[0]!.lower, classes }
}

/**
 * The answer of `GET /api/radar/frames` as a {@link RadarLoop}. The frames are put in time order, the ones that are no frame
 * are left out. An answer that lacks the list, the bounds or the legend is no loop (the caller's error, told by the message).
 */
export function parseLoop(answer: unknown): RadarLoop {
  if (!isRecord(answer) || !Array.isArray(answer.frames))
    throw new TypeError('The answer has no list of radar frames')
  const bounds = boundsOf(answer.image)
  const legend = legendOf(answer.legend)
  if (!bounds || !legend)
    throw new TypeError('The answer has no bounds or no legend of the radar')
  const frames = answer.frames.map(frameOf).filter((frame): frame is RadarFrame => frame !== null).sort((a, b) => a.at - b.at)
  const warnings = isRecord(answer.metadata) && Array.isArray(answer.metadata.warnings) ? answer.metadata.warnings : []
  return {
    frames,
    run: typeof answer.run === 'string' ? answer.run : (frames.filter(frame => frame.kind === 'observation').at(-1)?.run ?? ''),
    bounds,
    legend,
    stale: warnings.some(warning => isRecord(warning) && warning.code === 'radar-stale'),
    credit: creditOf(answer.metadata),
    clockSkewMs: clockSkew(answer.metadata),
  }
}

/** The address of a frame's image: with its `run`, so that it is the same for an hour in the browser's cache */
export function frameUrl(frame: Pick<RadarFrame, 'time' | 'run'>, product: string = RADAR_PRODUCT): string {
  return `/api/radar/frame?product=${encodeURIComponent(product)}&time=${encodeURIComponent(frame.time)}&run=${encodeURIComponent(frame.run)}`
}

/** The key of a frame, which the loop keeps what it knows of it by (loaded, failed): a frame of another run is another image */
export const frameKey = (frame: Pick<RadarFrame, 'time' | 'run'>): string => `${frame.run}|${frame.time}`

/**
 * Whether a place lies within the box of the radar's images (WGS84 degrees), the edges included: a position outside it is told, and the
 * map is not moved to it (the picture is the only data, and there is none there). The box is the outer box of DWD's polar-stereographic
 * grid, so its corners hold no data: inside the box is inside the picture, not a claim that the radar sees every point of it.
 */
export function isWithinBounds(point: { latitude: number, longitude: number }, bounds: RadarBounds): boolean {
  return point.latitude >= bounds.south && point.latitude <= bounds.north && point.longitude >= bounds.west && point.longitude <= bounds.east
}

/** The corners of the images as a Leaflet's bounds: `[[south, west], [north, east]]` (in Leaflet's default CRS, which is EPSG:3857) */
export function leafletBounds(bounds: RadarBounds): [[number, number], [number, number]] {
  return [[bounds.south, bounds.west], [bounds.north, bounds.east]]
}

/** The frame the loop opens on: the newest of the analysis, which is the sky as it was seen last; else the first there is */
export function openingIndex(frames: readonly Pick<RadarFrame, 'kind'>[]): number {
  const last = frames.map(frame => frame.kind).lastIndexOf('observation')
  return last === -1 ? 0 : last
}

/**
 * The order the frames are asked for in: the one the loop opens on first, so that there is a picture at once, then the others
 * in time order. A frame that failed, or is in hand, is not asked for again.
 */
export function preloadOrder<T extends Pick<RadarFrame, 'kind' | 'time' | 'run'>>(frames: readonly T[], settled: ReadonlySet<string>): T[] {
  const opening = frames[openingIndex(frames)]
  const rest = frames.filter(frame => frame !== opening)
  return [...(opening ? [opening] : []), ...rest].filter(frame => !settled.has(frameKey(frame)))
}

/**
 * The index the loop goes on at after `index` while it plays: the next frame that is `ready`, wrapping round at the end. null where
 * no other frame is ready (the loop has one frame, or waits for the next to load).
 */
export function nextReady(index: number, count: number, ready: (index: number) => boolean): number | null {
  for (let step = 1; step < count; step++) {
    const candidate = (index + step) % count
    if (ready(candidate))
      return candidate
  }
  return null
}

/**
 * How close a frame must be to the scan of the thunderstorm cells for the cells to be shown on it: 15 minutes (the maintainer's decision,
 * GH-3788). The cells are the latest scan's, so on an older frame they are of a sky that was not that one, and on a frame of the forecast
 * they are of the past; there they fade out, and the panel says so.
 */
export const CELLS_WINDOW_MS = 15 * 60 * 1000

/** Whether the cells of the scan at `scanTime` (ISO text) are shown on `frame`: an observed frame within 15 minutes of it; never on a forecast frame */
export function cellsShownOn(frame: Pick<RadarFrame, 'kind' | 'at'> | null, scanTime: string | null): boolean {
  const scan = scanTime ? timestampDate(scanTime) : null
  return Boolean(frame && scan && frame.kind === 'observation' && Math.abs(frame.at - scan.getTime()) <= CELLS_WINDOW_MS)
}

/** Whether a failure of the list is the backend saying it has no radar (a 404 or a 501, a server without the `radar` extra): no Retry would help */
export function isUnavailable(error: unknown): boolean {
  const status = isRecord(error) ? (finite(error.statusCode) ?? finite(error.status)) : null
  return status === 404 || status === 501
}

/** The age of the newest run at `now`, in milliseconds, or null where the loop has no analysis frame */
export function newestAge(frames: readonly Pick<RadarFrame, 'kind' | 'at'>[], now: number): number | null {
  const newest = frames.filter(frame => frame.kind === 'observation').at(-1)
  return newest ? now - newest.at : null
}

/** Whether the newest analysis frame is older than 20 minutes at `now`: DWD's feed has stopped, or the list is old (a refresh that failed) */
export function isStale(frames: readonly Pick<RadarFrame, 'kind' | 'at'>[], now: number): boolean {
  const age = newestAge(frames, now)
  return age !== null && age > STALE_AFTER_MS
}

/**
 * Where the loop stands after a new list of the frames came in while the reader was at `previous` (a frame's key): the same frame
 * where it is still in the loop, else the one nearest to it in time, else the opening one. Without this a refresh every 5
 * minutes would throw the reader back to the start of the loop.
 */
export function indexAfterRefresh(frames: readonly RadarFrame[], previous: Pick<RadarFrame, 'time' | 'run'> & { at: number } | null): number {
  if (!previous || !frames.length)
    return openingIndex(frames)
  const same = frames.findIndex(frame => frame.time === previous.time)
  if (same !== -1)
    return same
  let nearest = 0
  frames.forEach((frame, index) => {
    if (Math.abs(frame.at - previous.at) < Math.abs(frames[nearest]!.at - previous.at))
      nearest = index
  })
  return nearest
}

/** A rate as the page writes it: no more digits than it needs, in the language's own decimal sign (`0.5`, `2.5`, `10`) */
function rate(value: number, language: string): string {
  return formatNumber(value, language, Number.isInteger(value) ? 0 : 1)
}

/** What a class stands for, short enough for a swatch: "0.1–0.5", and "25+" for the last, open class (the unit is the legend's heading) */
export function classRange(entry: LegendClass, language: string): string {
  return entry.upper === null ? `${rate(entry.lower, language)}+` : `${rate(entry.lower, language)}–${rate(entry.upper, language)}`
}

/** The numbers of a class for a text: its limits, for the page to put into its sentence (`lower`, and `upper` where it has one) */
export function classLimits(entry: LegendClass, language: string): { lower: string, upper: string | null } {
  return { lower: rate(entry.lower, language), upper: entry.upper === null ? null : rate(entry.upper, language) }
}

/** The reader's time zone, as the browser has it (`Europe/Berlin`), or UTC where it does not say */
export function readerZone(): string {
  try {
    return new Intl.DateTimeFormat('en').resolvedOptions().timeZone || 'UTC'
  }
  catch {
    return 'UTC'
  }
}

/**
 * A frame's time as the reader writes a time of day, in the reader's own zone with the zone's short name ("14:35 CEST"), and with
 * the weekday where it is not the day of `now` (the loop spans four hours, and midnight can be in it: "Sat 00:05 CET"). The
 * language is the region-bearing tag of the locale, as `formatHour` takes it; never built from its parts.
 */
export function formatFrameTime(ms: number, language: string, now: number, timeZone: string = readerZone()): string {
  const tag = withData(language, Intl.DateTimeFormat.supportedLocalesOf)
  const day = (at: number) => new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(at)
  return new Intl.DateTimeFormat(tag, {
    ...(day(ms) === day(now) ? {} : { weekday: 'short' as const }),
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone,
    timeZoneName: 'short',
  }).format(ms)
}

type Translate = (key: string, params?: Record<string, unknown>) => string

/** What a frame is called, in the words of the page: its time, whether it is observed or forecast (with how far ahead), and the one sentence a screen reader gets for it */
export interface FrameWords {
  time: string
  /** "Observed" or "Forecast": a word, so that the two are never told apart by colour */
  kind: string
  /** "Forecast, 35 min ahead" for a forecast frame, null for an observed one */
  ahead: string | null
  /** "14:35 CEST, observed" or "15:10 CEST, forecast, 35 minutes ahead" */
  value: string
}

export function describeFrame(t: Translate, frame: Pick<RadarFrame, 'at' | 'kind' | 'leadMinutes'>, language: string, now: number): FrameWords {
  const time = formatFrameTime(frame.at, language, now)
  if (frame.kind === 'forecast')
    return { time, kind: t('radar.forecast'), ahead: t('radar.forecastAhead', { minutes: frame.leadMinutes }), value: t('radar.valueForecast', { time, minutes: frame.leadMinutes }) }
  return { time, kind: t('radar.observed'), ahead: null, value: t('radar.valueObserved', { time }) }
}
