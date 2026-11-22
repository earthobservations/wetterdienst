import type { ProviderCredit } from './provider-credit'
import type { LatLng } from './storm-cells'
import { clockSkew, creditOf } from './provider-credit'
import { formatFrameTime } from './radar'
import { outlineOf } from './storm-cells'
import { timestampDate } from './timestamp'

/**
 * DWD's official weather warnings (GH-4295) as the app shows them: what the backend's `GET /api/alerts` answers
 * (`dwd/alerts`, one entry for each CAP message of DWD's snapshot) read into the few things the map draws and the
 * banner and the question tell, and the decisions of showing them (which level a warning has, what is in force now,
 * which warnings contain a position, which of DWD's texts a reader gets).
 *
 * The warning is DWD's statement. Nothing here rates, shortens or rewords it: the level is the one the CAP profile
 * gives its `severity` (§2.2.2.6), the texts are DWD's, and a position is told to be in a warning only when a polygon
 * of it contains the position. A warning with no polygon (the community product names the sea and the coast only by
 * their warn cells) is kept and listed, but never placed.
 */

/** DWD's four levels of warning, which the CAP `severity` names: Minor, Moderate, Severe, Extreme (CAP DWD profile 2.1.12, §2.2.2.6) */
export type WarningLevel = 1 | 2 | 3 | 4

export const WARNING_LEVELS: readonly WarningLevel[] = [1, 2, 3, 4]

/** A warning (`warning`), or DWD's preliminary information on severe weather (`preliminary`, "Vorabinformation Unwetter", §3.1.2) */
export type WarningKind = 'warning' | 'preliminary'

/** How often the snapshot is asked for again while the warnings are wanted: the backend keeps the latest snapshot for 5 minutes (`CacheExpiry.FIVE_MINUTES`), so asking more often only asks for the same file */
export const WARNINGS_REFRESH_MS = 5 * 60 * 1000

/** After this long without a snapshot that arrived, what is in hand is said to be old: three refreshes */
export const WARNINGS_STALE_AFTER_MS = 3 * WARNINGS_REFRESH_MS

/**
 * Where DWD warns: the box of the network's `extent` in the backend (`dwd/alerts/api.py`: Germany and the sea round its
 * coast), as `[west, south, east, north]`. A position outside it has no warnings source, which the app says plainly;
 * inside it, a position may still be in a neighbouring country, which a box cannot tell, so what is said there is
 * that no warning of DWD has an area that contains it.
 */
export const WARNING_BOX = { west: 3, south: 47, east: 16, north: 56 } as const

/** Whether DWD warns for a position at all, by the box of its network */
export function inWarningBox(point: { latitude: number, longitude: number }): boolean {
  return point.latitude >= WARNING_BOX.south && point.latitude <= WARNING_BOX.north && point.longitude >= WARNING_BOX.west && point.longitude <= WARNING_BOX.east
}

/** One text of DWD's, in one language */
export interface WarningText {
  event: string | null
  headline: string | null
  description: string | null
  instruction: string | null
}

/** The box of an outline: its parts together */
export interface Box { south: number, west: number, north: number, east: number }

export interface Warning {
  /** DWD's identifier of the CAP message, which is the only name a warning has */
  id: string
  kind: WarningKind
  /** The level of the CAP `severity`; null for a severity the profile does not list */
  level: WarningLevel | null
  /** The texts by the language's first subtag (`de`, `en`, `pl`): the first block of the message is German whatever product was asked for, the others are its translations */
  texts: Record<string, WarningText>
  /** DWD's own event code (`II`, 59 for fog), which the profile asks readers not to take for a number */
  eventCode: string | null
  /** `effective`, `onset`, `expires` and `sent` as ISO text (UTC); `expires` is absent for the event types that have none (§2.2.2.11) */
  effective: string | null
  onset: string | null
  expires: string | null
  sent: string | null
  /** The areas the warning is issued for, which the community product names by warn cell */
  areaNames: string[]
  warncellIds: string[]
  /** Every surface of the polygon (holes as holes), `[latitude, longitude]` as Leaflet takes it; empty where DWD gave no polygon */
  outline: LatLng[][][]
  box: Box | null
}

/** The snapshot as the app holds it: the warnings and what is known of when and from whom */
export interface WarningSnapshot {
  warnings: Warning[]
  /** The newest `sent` of the whole snapshot (the answer's `data_updated_at`): when DWD last said anything */
  latestIssue: string | null
  /** When the answer was made (its `retrieved_at`) */
  retrievedAt: string | null
  credit: ProviderCredit | null
  clockSkewMs: number
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const text = (value: unknown): string | null => typeof value === 'string' && value.trim() !== '' ? value.trim() : null
/** A time of the answer as ISO text, or null for none or a text that is no time */
function time(value: unknown): string | null {
  const found = text(value)
  return found && timestampDate(found) ? found : null
}

/** The level of a CAP `severity`: Minor 1, Moderate 2, Severe 3, Extreme 4, null for anything else (CAP DWD profile 2.1.12, §2.2.2.6) */
export function levelOfSeverity(severity: unknown): WarningLevel | null {
  const found = { minor: 1, moderate: 2, severe: 3, extreme: 4 }[String(severity ?? '').toLowerCase() as 'minor']
  return (found ?? null) as WarningLevel | null
}

/** The event codes of DWD's preliminary information on severe weather (CAP DWD profile 2.1.12, §3.1.2; 99 is its test) */
export const PRELIMINARY_EVENT_CODES: readonly string[] = ['40', '55', '65', '75', '85', '89', '99']

/** The first subtag of a language as DWD writes it (`de-DE` is `de`), lower case */
export function languageOf(tag: unknown): string {
  return String(tag ?? '').split('-')[0]!.toLowerCase()
}

function textOf(record: Record<string, unknown>): WarningText {
  return {
    event: text(record.event),
    headline: text(record.headline),
    description: text(record.description),
    instruction: text(record.instruction),
  }
}

/** The box of the parts of an outline */
function boxOf(outline: LatLng[][][]): Box | null {
  const points = outline.flatMap(surface => surface[0] ?? [])
  if (!points.length)
    return null
  return {
    south: Math.min(...points.map(point => point[0])),
    north: Math.max(...points.map(point => point[0])),
    west: Math.min(...points.map(point => point[1])),
    east: Math.max(...points.map(point => point[1])),
  }
}

/**
 * One entry of the answer's `alerts` as a {@link Warning}, or null for what is no warning to show: not an object, no
 * identifier, a message of `Test` status ("technical testing only, all recipients disregard", §2.2.1.4) or a `Cancel` (it
 * cancels earlier messages, §2.2.1.5), which a snapshot of the warnings in force should not hold and which is dropped here
 * if it does.
 */
export function parseWarning(entry: unknown, index = 0): Warning | null {
  if (!isRecord(entry))
    return null
  if (text(entry.status)?.toLowerCase() === 'test' || text(entry.msg_type)?.toLowerCase() === 'cancel')
    return null
  const texts: Record<string, WarningText> = {}
  texts[languageOf(entry.language) || 'de'] = textOf(entry)
  if (Array.isArray(entry.translations)) {
    for (const translation of entry.translations) {
      if (isRecord(translation) && languageOf(translation.language))
        texts[languageOf(translation.language)] ??= textOf(translation)
    }
  }
  const outline = outlineOf(entry.geometry)
  const eventCode = text(entry.event_code)
  const strings = (value: unknown) => Array.isArray(value) ? value.filter((one): one is string => typeof one === 'string' && one.trim() !== '') : []
  return {
    id: text(entry.alert_id) ?? `alert-${index}`,
    kind: eventCode !== null && PRELIMINARY_EVENT_CODES.includes(eventCode) ? 'preliminary' : 'warning',
    level: levelOfSeverity(entry.severity),
    texts,
    eventCode,
    effective: time(entry.effective),
    onset: time(entry.onset),
    expires: time(entry.expires),
    sent: time(entry.sent),
    areaNames: strings(entry.area_names),
    warncellIds: strings(entry.warncell_ids),
    outline,
    box: boxOf(outline),
  }
}

/**
 * The answer of `GET /api/alerts` as a {@link WarningSnapshot}. An answer with no list of alerts is no snapshot (the
 * caller's error, told by the thrown message); an empty list is the usual quiet day's, and a snapshot like any other.
 * The warnings are sorted as {@link sortWarnings} does, so that a refresh that changes nothing changes no order.
 */
export function parseWarnings(answer: unknown): WarningSnapshot {
  if (!isRecord(answer) || !Array.isArray(answer.alerts))
    throw new TypeError('The answer has no list of weather warnings')
  const warnings = answer.alerts.map(parseWarning).filter((warning): warning is Warning => warning !== null)
  const metadata = isRecord(answer.metadata) ? answer.metadata : null
  return {
    warnings: sortWarnings(warnings),
    latestIssue: time(metadata?.data_updated_at),
    retrievedAt: time(metadata?.retrieved_at),
    credit: creditOf(answer.metadata),
    clockSkewMs: clockSkew(answer.metadata),
  }
}

// ----------------------------------------------------------------------------------------------- what is in force

/** Where a warning stands against the clock: in force now, announced for later, or over */
export type WarningPhase = 'active' | 'upcoming' | 'over'

/**
 * Whether a warning is in force at `now`: its onset has come and its end (where it has one) has not. A warning with
 * no onset is taken as begun; one with no end runs until DWD takes it back out of the snapshot. A snapshot lags the clock
 * by up to its refresh, so a warning that has ended since is `over`, and not told as in force.
 */
export function phaseOf(warning: Pick<Warning, 'onset' | 'expires'>, now: number): WarningPhase {
  const onset = warning.onset ? timestampDate(warning.onset)?.getTime() : undefined
  const expires = warning.expires ? timestampDate(warning.expires)?.getTime() : undefined
  if (expires !== undefined && expires <= now)
    return 'over'
  return onset !== undefined && onset > now ? 'upcoming' : 'active'
}

/** The warnings not yet over at `now` */
export function notOver(warnings: readonly Warning[], now: number): Warning[] {
  return warnings.filter(warning => phaseOf(warning, now) !== 'over')
}

/**
 * The order the lists read in: the most severe level first (a warning of a level the profile does not list last), those in
 * force before those announced, then by onset, then by identifier, so that the order is the same from one refresh to the next.
 */
export function sortWarnings<T extends Pick<Warning, 'id' | 'level' | 'onset' | 'expires'>>(warnings: readonly T[], now?: number): T[] {
  const rank = (warning: T) => (now === undefined ? 0 : phaseOf(warning, now) === 'upcoming' ? 1 : 0)
  const start = (warning: T) => (warning.onset ? timestampDate(warning.onset)?.getTime() : undefined) ?? 0
  return warnings.toSorted((a, b) =>
    (b.level ?? 0) - (a.level ?? 0)
    || rank(a) - rank(b)
    || start(a) - start(b)
    || a.id.localeCompare(b.id, 'en'))
}

// ------------------------------------------------------------------------------------------- warnings at a position

const EDGE_TOLERANCE = 1e-12

/** Where a point lies against a closed ring: strictly inside, on its edge, or outside */
export type Location = 'inside' | 'edge' | 'outside'

/**
 * Where the point lies against a ring of `[latitude, longitude]` points. Planar, as DWD's polygons are small and none crosses
 * the antimeridian: the ray to the east counts the edges it crosses, and a point on an edge is on it (the backend's
 * `place.locate`, `dwd/alerts/place.py`, which the answer's own filter by point uses, is the same test, so the two agree).
 */
export function locate(ring: readonly LatLng[], latitude: number, longitude: number): Location {
  let inside = false
  for (let index = 0; index < ring.length - 1; index++) {
    const [y1, x1] = ring[index]!
    const [y2, x2] = ring[index + 1]!
    if (
      Math.min(x1, x2) <= longitude && longitude <= Math.max(x1, x2)
      && Math.min(y1, y2) <= latitude && latitude <= Math.max(y1, y2)
      && Math.abs((x2 - x1) * (latitude - y1) - (y2 - y1) * (longitude - x1)) <= EDGE_TOLERANCE
    ) {
      return 'edge'
    }
    // the ray to the east crosses this segment: one of its ends is above the point, the other not
    if ((y1 > latitude) !== (y2 > latitude) && longitude < x1 + (latitude - y1) * (x2 - x1) / (y2 - y1))
      inside = !inside
  }
  return inside ? 'inside' : 'outside'
}

/**
 * Whether an outline (the surfaces of a MultiPolygon, each its edge and its holes) contains the point: inside the edge or on it, and not
 * inside a hole (the land inside a warning of the sea, the enclave of a district), whose own edge still counts as inside.
 */
export function outlineContains(outline: readonly LatLng[][][], latitude: number, longitude: number): boolean {
  return outline.some((surface) => {
    const [edge, ...holes] = surface
    return edge !== undefined
      && locate(edge, latitude, longitude) !== 'outside'
      && holes.every(hole => locate(hole, latitude, longitude) !== 'inside')
  })
}

/** Whether a warning's polygon contains the point; a warning with no polygon contains none */
export function containsPoint(warning: Pick<Warning, 'outline' | 'box'>, point: { latitude: number, longitude: number }): boolean {
  const box = warning.box
  if (!box || point.latitude < box.south || point.latitude > box.north || point.longitude < box.west || point.longitude > box.east)
    return false
  return outlineContains(warning.outline, point.latitude, point.longitude)
}

/** The warnings, not yet over, whose polygon contains the point, in the order of {@link sortWarnings} */
export function warningsAt(warnings: readonly Warning[], point: { latitude: number, longitude: number }, now: number): Warning[] {
  return sortWarnings(notOver(warnings, now).filter(warning => containsPoint(warning, point)), now)
}

/** The warnings, not yet over, that have no polygon: they are listed and never placed */
export function withoutOutline(warnings: readonly Warning[], now: number): Warning[] {
  return sortWarnings(notOver(warnings, now).filter(warning => warning.outline.length === 0), now)
}

/** The warnings, not yet over, that have a polygon to draw */
export function drawn(warnings: readonly Warning[], now: number): Warning[] {
  return sortWarnings(notOver(warnings, now).filter(warning => warning.outline.length > 0), now)
}

// ------------------------------------------------------------------------------------------------------ the language

/** The products of the backend (`language` of `/api/alerts`) */
export type AlertsProduct = 'de' | 'en' | 'es' | 'fr' | 'mul'

/**
 * Which product to ask for to read DWD's texts in the language of the page, and which language of it to read. DWD writes the
 * warnings in German, English, Spanish and French as products of their own, and in eight languages in the `mul` product
 * (German, English, French, Spanish, Arabic, Russian, Turkish and Polish), which is some 10 to 60 % larger: it is asked for
 * for Polish only. Every other language of the app (Czech, Danish, Italian, Dutch, Luxembourgish, Low German) is not one DWD
 * writes in: it gets the German product, DWD's own text, and the page says so.
 */
export function productFor(locale: string): { product: AlertsProduct, language: string } {
  const language = languageOf(locale)
  if (language === 'en' || language === 'es' || language === 'fr')
    return { product: language, language }
  if (language === 'pl')
    return { product: 'mul', language }
  return { product: 'de', language: 'de' }
}

/**
 * The text a reader gets: DWD's in the language of the page where it has one, else the German one (the original, which every
 * message has first). `translated` is whether the text is in the language of the page, which the page says where it is not.
 */
export function textFor(warning: Pick<Warning, 'texts'>, locale: string): { text: WarningText, language: string, inLocale: boolean } {
  const wanted = languageOf(locale)
  const found = warning.texts[wanted]
  if (found && (found.headline || found.description))
    return { text: found, language: wanted, inLocale: true }
  const german = warning.texts.de ?? Object.values(warning.texts)[0] ?? { event: null, headline: null, description: null, instruction: null }
  return { text: german, language: 'de', inLocale: wanted === 'de' }
}

// ------------------------------------------------------------------------------------------------------- the drawing

/**
 * How a level is drawn. Colour is never the only cue (WCAG 1.4.1): the edge is dotted for level 1, dashed for 2, solid for 3 and
 * solid and heavy for 4, dash-dot for the preliminary information, and the list says each level in words. The fills are DWD's
 * colours of the profile (§3.5: yellow 255 235 59, orange 251 140 0, red 229 57 53, dark pink 136 14 79, preliminary 255 128 128), and
 * the edges the darker tones of them that hold 3:1 against the map's light tiles (1.4.11).
 */
export interface LevelStyle {
  fill: string
  edge: string
  weight: number
  dashArray: string | null
  fillOpacity: number
}

export const LEVEL_STYLES: Record<WarningLevel | 'preliminary' | 'unknown', LevelStyle> = {
  1: { fill: '#ffeb3b', edge: '#7a6200', weight: 2, dashArray: '2 5', fillOpacity: 0.34 },
  2: { fill: '#fb8c00', edge: '#a14d00', weight: 2.5, dashArray: '9 5', fillOpacity: 0.36 },
  3: { fill: '#e53935', edge: '#a51c1a', weight: 3.5, dashArray: null, fillOpacity: 0.38 },
  4: { fill: '#880e4f', edge: '#880e4f', weight: 5, dashArray: null, fillOpacity: 0.42 },
  preliminary: { fill: '#ff8080', edge: '#b3261e', weight: 2.5, dashArray: '12 4 2 4', fillOpacity: 0.24 },
  unknown: { fill: '#8a93a6', edge: '#5b6577', weight: 2, dashArray: '1 6', fillOpacity: 0.2 },
}

/** The key of the style of a warning in {@link LEVEL_STYLES} */
export function styleKey(warning: Pick<Warning, 'kind' | 'level'>): WarningLevel | 'preliminary' | 'unknown' {
  return warning.kind === 'preliminary' ? 'preliminary' : warning.level ?? 'unknown'
}

/** What the map is given of a warning to draw: its outline and how it looks, and whether it is the one picked from the list */
export interface DrawnWarning {
  id: string
  style: LevelStyle
  outline: LatLng[][][]
  focused: boolean
}

export function drawnOf(warnings: readonly Warning[], focused: string | null): DrawnWarning[] {
  // the weakest first, so that the heavier edges are drawn over the lighter ones where polygons overlap
  return warnings
    .filter(warning => warning.outline.length > 0)
    .toSorted((a, b) => (a.level ?? 0) - (b.level ?? 0))
    .map(warning => ({ id: warning.id, style: LEVEL_STYLES[styleKey(warning)], outline: warning.outline, focused: warning.id === focused }))
}

/** The area a list names a warning's areas by: the first few, and how many more there are */
export const AREAS_SHOWN = 4

/** The key of a level's name in the catalog (`warnings.level.<key>`) */
export function levelKey(warning: Pick<Warning, 'kind' | 'level'>): string {
  return String(styleKey(warning))
}

// ------------------------------------------------------------------------------------------------------ the words

export type WarningsTranslate = (key: string, params?: Record<string, string | number>) => string

/** What a warning is called and told by, in the language of the page: the words of its row, of its details and of the question's answer */
export interface WarningWords {
  title: string
  /** `Level 2 of 4`, none for the preliminary information and a severity the profile does not list */
  levelNumber: string | null
  levelName: string
  /** `Level 2 of 4 · Marked weather warning` */
  level: string
  /** `In force` or `Announced` */
  phase: string
  /** `Sat 14:00 CET to Sat 22:00 CET`, and where DWD gives a part only, that; empty where it gives none */
  validity: string
  /** The time DWD issued it, as the reader's zone writes it; empty where it has none */
  issued: string
  areas: string
  /** DWD's own words, and the language they are in (`de`, the original, where DWD has none in the page's) */
  text: WarningText
  language: string
  inLocale: boolean
}

/** A moment as the Radar writes the time of a frame: the time of day in the reader's zone with the zone's name, the weekday where it is not today */
export function clockOf(iso: string | null, formatLanguage: string, now: number): string {
  const at = iso ? timestampDate(iso) : null
  return at ? formatFrameTime(at.getTime(), formatLanguage, now) : ''
}

/** The words of one warning: the same in its row, its details and the answer of the question */
export function wordsOf(warning: Warning, t: WarningsTranslate, locale: string, formatLanguage: string, now: number): WarningWords {
  const found = textFor(warning, locale)
  const levelName = t(`warnings.level.${levelKey(warning)}`)
  const levelNumber = warning.kind === 'warning' && warning.level ? t('warnings.levelOf', { level: warning.level }) : null
  const from = clockOf(warning.onset, formatLanguage, now)
  const to = clockOf(warning.expires, formatLanguage, now)
  const names = warning.areaNames
  return {
    title: found.text.event ?? found.text.headline ?? t('warnings.untitled'),
    levelNumber,
    levelName,
    level: levelNumber ? `${levelNumber} · ${levelName}` : levelName,
    phase: phaseOf(warning, now) === 'upcoming' ? t('warnings.upcoming') : t('warnings.inForce'),
    validity: from && to ? t('warnings.fromTo', { from, to }) : from ? t('warnings.fromOpen', { from }) : to ? t('warnings.until', { to }) : '',
    issued: clockOf(warning.sent, formatLanguage, now),
    areas: names.length > AREAS_SHOWN ? t('warnings.areasMore', { names: names.slice(0, AREAS_SHOWN).join(', '), count: names.length - AREAS_SHOWN }) : names.join(', '),
    text: found.text,
    language: found.language,
    inLocale: found.inLocale,
  }
}
