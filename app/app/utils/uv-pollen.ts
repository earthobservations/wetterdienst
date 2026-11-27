/**
 * The "UV & pollen" panel of the Forecast (GH-4501): DWD's UV index forecast (`dwd/uvi`, GH-4089) and pollen load forecast
 * (`dwd/pollen`, GH-4088) for the three days a file of theirs holds (today, tomorrow and the day after), shown below the
 * meteogram of a station in Germany, the extent of both products.
 *
 * This file is what can be said without a request or a component: the queries, which place and which regions a station is
 * given, the classes of a number and the days of the rows. `composables/useUvPollen.ts` asks, `components/UvPollenPanel.vue`
 * shows, and `tests/unit/uv-pollen.test.ts` holds this.
 */
import type { Station, Value } from '#shared/types/api'
import type { NearStation } from './place-stations'
import { DateTime } from 'luxon'
import { stationsNear } from './place-stations'
import { zoneOfPosition } from './station-zone'

// ---- where the panel is shown ---------------------------------------------------------------------------------------------

/**
 * How far the nearest place of the UV index may be, in kilometres: beyond it there is no UV part. DWD's file has 38 places (a
 * city, a mountain top, an island), one for every 100 km or so, and gives no position of its own (`uvi/places.py`).
 */
export const UV_REACH_KM = 100

/** The time zones of Germany: `Europe/Busingen` is Büsingen am Hochrhein, a German exclave in Switzerland, which the zone database gives a zone of its own */
const GERMAN_ZONES: readonly string[] = ['Europe/Berlin', 'Europe/Busingen']

/**
 * Whether a position is in Germany, the extent of both products (DWD's UV index and pollen load). By the time zone of the
 * position, which `tz-lookup` finds by the zone's boundary (the same lookup that sets the forecast's Today, `zoneOfPosition`), and
 * which follows the border of the country: Strasbourg is `Europe/Paris`, Salzburg `Europe/Vienna`, Basel `Europe/Zurich`, Venlo
 * `Europe/Amsterdam`. A box does not: the box of DWD's warnings (`inWarningBox`, the Forecast's banner) holds Strasbourg, Basel,
 * Salzburg and Venlo, and the nearest German station or place of such a station is a few kilometres away. The border is the
 * lookup's own, simplified: a station within a kilometre or two of it may be counted to either side.
 */
export function inGermany(point: { latitude: number | null | undefined, longitude: number | null | undefined }): boolean {
  return GERMAN_ZONES.includes(zoneOfPosition(point.latitude, point.longitude))
}

// ---- the requests ---------------------------------------------------------------------------------------------------------

const DWD = { provider: 'dwd', resolution: 'daily', dataset: 'data' } as const

/** The UV index forecast: one parameter, the highest index of the day, for each of the 38 places */
export const UVI_REQUEST = { ...DWD, network: 'uvi', parameter: 'uv_index_max' } as const

/**
 * DWD's eight pollen types in the order of its file and of the grid (`dwd/pollen`'s `POLLEN_TYPES`): hazel, alder, ash, birch,
 * grass, rye, mugwort and ragweed. The canonical parameter of each is `pollen_load_<type>`.
 */
export const POLLEN_TYPES = ['hazel', 'alder', 'ash', 'birch', 'grass', 'rye', 'mugwort', 'ragweed'] as const
export type PollenType = typeof POLLEN_TYPES[number]

/** The pollen load forecast: a level of each type for each of the 27 regions, which have no position */
export const POLLEN_REQUEST = { ...DWD, network: 'pollen' } as const

/** The dataset that lists a state for any position: every station of `dwd/observation` has a `region`, and this dataset lists them all */
const OBSERVATION_STATE_PARAMETERS = 'daily/climate_summary'

/** The canonical parameter of a pollen type: `pollen_load_birch` */
export function pollenParameter(type: PollenType): string {
  return `pollen_load_${type}`
}

/** The nearest place of the UV index to a position: its name and its position, which the file does not give */
export function uvPlaceQuery(point: { latitude: number, longitude: number }): Record<string, string> {
  return {
    provider: UVI_REQUEST.provider,
    network: UVI_REQUEST.network,
    parameters: `${UVI_REQUEST.resolution}/${UVI_REQUEST.dataset}`,
    latitude: String(point.latitude),
    longitude: String(point.longitude),
    rank: '1',
  }
}

/** The nearest station of the observation network to a position, whose `region` is its state */
export function stateQuery(point: { latitude: number, longitude: number }): Record<string, string> {
  return {
    provider: 'dwd',
    network: 'observation',
    parameters: OBSERVATION_STATE_PARAMETERS,
    latitude: String(point.latitude),
    longitude: String(point.longitude),
    rank: '1',
  }
}

/** The 27 regions of the pollen forecast, asked for once for the whole list (`utils/pollen-regions.ts`) */
export function pollenRegionsQuery(): Record<string, string> {
  return { provider: POLLEN_REQUEST.provider, network: POLLEN_REQUEST.network, parameters: `${POLLEN_REQUEST.resolution}/${POLLEN_REQUEST.dataset}`, all: 'true' }
}

/**
 * What the answer is asked to look like, whatever the server's own `WD_TS_*` settings are: long rows, a row for each day with
 * its `null` where DWD has no value (a missing value is a fact the grid shows as "–"). The unit of both products is a plain
 * number, so none is asked for or converted.
 */
const VALUES_SETTINGS = { shape: 'long', humanize: 'true', skip_empty: 'false', drop_nulls: 'false' } as const

/** The query of `/api/values` for the UV index of a place */
export function uvValuesQuery(placeId: string): Record<string, string> {
  return {
    provider: UVI_REQUEST.provider,
    network: UVI_REQUEST.network,
    parameters: `${UVI_REQUEST.resolution}/${UVI_REQUEST.dataset}/${UVI_REQUEST.parameter}`,
    stations: placeId,
    ...VALUES_SETTINGS,
  }
}

/** The query of `/api/values` for the eight pollen types of the given regions (the parts of a state, asked for in one request) */
export function pollenValuesQuery(regionIds: readonly string[]): Record<string, string> {
  return {
    provider: POLLEN_REQUEST.provider,
    network: POLLEN_REQUEST.network,
    parameters: POLLEN_TYPES.map(type => `${POLLEN_REQUEST.resolution}/${POLLEN_REQUEST.dataset}/${pollenParameter(type)}`).join(','),
    stations: regionIds.join(','),
    ...VALUES_SETTINGS,
  }
}

// ---- the UV index ---------------------------------------------------------------------------------------------------------

/** The WHO's five classes of the UV index, from the lowest */
export const UV_CLASSES = ['low', 'moderate', 'high', 'veryHigh', 'extreme'] as const
export type UvClass = typeof UV_CLASSES[number]

/**
 * The WHO's class of a UV index: 0 to 2 low, 3 to 5 moderate, 6 to 7 high, 8 to 10 very high and 11 and above extreme. The index
 * is a whole number (the WHO rounds it to one, and DWD gives it as one), so a number between two is rounded first. Null for a
 * value that is not a number (a day with none).
 */
export function uvClass(value: number | null | undefined): UvClass | null {
  if (value == null || !Number.isFinite(value))
    return null
  const index = Math.round(value)
  if (index <= 2)
    return 'low'
  if (index <= 5)
    return 'moderate'
  if (index <= 7)
    return 'high'
  if (index <= 10)
    return 'veryHigh'
  return 'extreme'
}

/**
 * The colours of the WHO's UV index (green, yellow, orange, red, violet) with the colour of the number written on each: the class
 * is told in words as well, never by colour alone (WCAG 1.4.1), and the number is held to 4.5:1 against its fill (WCAG 1.4.3) by
 * `tests/unit/uv-pollen.test.ts`. The same in the light and the dark scheme: the badge is a fill of its own on either.
 */
export const UV_COLORS: Record<UvClass, { fill: string, text: string }> = {
  low: { fill: '#289500', text: '#000000' },
  moderate: { fill: '#f7e400', text: '#000000' },
  high: { fill: '#f85900', text: '#000000' },
  veryHigh: { fill: '#d8001d', text: '#ffffff' },
  extreme: { fill: '#6b49c8', text: '#ffffff' },
}

/** A place of the UV index and how far it is from the forecast station */
export type UvPlace = NearStation<Station>

/**
 * The nearest place of the UV index within `UV_REACH_KM` of a position, or null where there is none. The places are what the
 * backend answers for `rank=1`, which is one; a longer list is searched all the same, and a place with no position is no
 * candidate (it has no distance).
 */
export function nearestUvPlace(point: { latitude: number, longitude: number }, places: readonly Station[]): UvPlace | null {
  const nearest = stationsNear(point, places, 1)[0]
  return nearest && nearest.distanceKm <= UV_REACH_KM ? nearest : null
}

// ---- the state, and the pollen regions it has -----------------------------------------------------------------------------

/**
 * The state of the nearest station of the observation network: its `region` column as DWD writes it (`Sachsen`,
 * `Baden-Württemberg`). The forecast station is in Germany (`inGermany`), where every station of the network is. Null where the
 * list has no station with a region.
 */
export function stateOfStation(point: { latitude: number, longitude: number }, stations: readonly Station[]): string | null {
  const nearest = stationsNear(point, stations.filter(station => !!station.region?.trim()), 1)[0]
  if (!nearest)
    return null
  return nearest.station.region!.trim()
}

/**
 * The states a pollen region's `region` column names: DWD's regions are one or two states (`Niedersachsen und Bremen`,
 * `Rheinland-Pfalz und Saarland`, `Schleswig-Holstein und Hamburg`, `Brandenburg und Berlin`), joined by "und". The column is
 * split and the pieces are compared whole, never searched: `Sachsen` is inside `Sachsen-Anhalt` and `Niedersachsen` as text and
 * is neither of them.
 */
export function statesOfRegion(region: string): string[] {
  return region.split(/\s+und\s+/).map(state => state.trim()).filter(Boolean)
}

/** A part-region of the pollen forecast: its id (DWD's number), and the words of its chip */
export interface PollenPart {
  id: string
  /** The part's name without the region's (`Tiefland Sachsen`), or the region's where DWD gives it none (`Mecklenburg-Vorpommern`) */
  label: string
  /** The name as the backend gives it: `Sachsen: Tiefland Sachsen` */
  name: string
}

/** The words of a part-region: the name of a station is `<region>: <part-region>`, and the region alone where there is no part */
function partOf(station: Pick<Station, 'station_id' | 'name' | 'region'>): PollenPart {
  const name = station.name ?? station.region ?? station.station_id
  const prefix = station.region ? `${station.region}: ` : ''
  const label = prefix && name.startsWith(prefix) ? name.slice(prefix.length) : name
  return { id: station.station_id, label, name }
}

/**
 * The words a part-region's name is made of: DWD joins them with a comma, a slash or "und" (`Geest,Schleswig-Holstein und Hamburg`,
 * `Westl. Niedersachsen/Bremen`, `Rhein, Pfalz, Nahe und Mosel`).
 */
function wordsOfPart(label: string): string[] {
  return label.split(/\s*(?:,|\/)\s*|\s+und\s+/).map(word => word.trim().toLocaleLowerCase('de')).filter(Boolean)
}

/**
 * The part-regions of a state: those of the regions whose `region` names the state, in DWD's order (the order of the numbers), the
 * parts whose own name names the state first (`Saarland`, a part of `Rheinland-Pfalz und Saarland`; `Geest,Schleswig-Holstein und
 * Hamburg`, which names Hamburg; `Westl. Niedersachsen/Bremen`, which names Bremen), so that the first chip, which is the one
 * preselected, is the one a station in that state is in. Empty where no region names the state: there is then no pollen part. A
 * state of one region of one part has one chip.
 *
 * The regions are the stations of `dwd/pollen`, which have no position: the state is all there is to find one by. It is
 * compared whole and without regard to case.
 */
export function pollenPartsOfState(state: string, regions: readonly Pick<Station, 'station_id' | 'name' | 'region'>[]): PollenPart[] {
  const wanted = state.trim().toLocaleLowerCase('de')
  if (!wanted)
    return []
  const parts = regions
    .filter(region => !!region.region && statesOfRegion(region.region).some(named => named.toLocaleLowerCase('de') === wanted))
    .map(partOf)
  const named = parts.filter(part => wordsOfPart(part.label).includes(wanted))
  return [...named, ...parts.filter(part => !named.includes(part))]
}

// ---- the pollen load ------------------------------------------------------------------------------------------------------

/**
 * DWD's seven classes of the pollen load, by their level (0 to 3 in steps of a half): none, none to low, low, low to medium,
 * medium, medium to high, high (`dwd/pollen/metadata.py`)
 */
export const POLLEN_CLASSES = ['none', 'noneToLow', 'low', 'lowToMedium', 'medium', 'mediumToHigh', 'high'] as const
export type PollenClass = typeof POLLEN_CLASSES[number]

/** The class of a level (0, 0.5, 1 ... 3), or null for a value that is none of the seven steps (no value, or a number DWD does not use) */
export function pollenClass(level: number | null | undefined): PollenClass | null {
  if (level == null || !Number.isFinite(level))
    return null
  const step = level * 2
  return Number.isInteger(step) && step >= 0 && step <= 6 ? POLLEN_CLASSES[step]! : null
}

/** How much of the scale a level fills, 0 to 1, for the bar beside its name; 0 where it is no level */
export function pollenFill(level: number | null | undefined): number {
  return pollenClass(level) === null ? 0 : level! / 3
}

/** A row of the pollen answer, as the panel reads it */
export type PollenRow = Pick<Value, 'station_id' | 'parameter' | 'timestamp' | 'value'>

/**
 * Whether no load is expected: there are rows and every level is 0, which is what DWD writes out of season, so the grid is replaced
 * by a line saying so. A level that has no value (DWD's -1, a missing one) is no 0, and no rows say nothing of the load: neither
 * is "no load expected" (see `hasNoForecast`).
 */
export function isOutOfSeason(rows: readonly Pick<PollenRow, 'value'>[]): boolean {
  return rows.length > 0 && rows.every(row => row.value === 0)
}

/** Whether DWD gives nothing for the part: no row, or every level without a value. A line says so; a grid of dashes would say it 24 times */
export function hasNoForecast(rows: readonly Pick<PollenRow, 'value'>[]): boolean {
  return rows.every(row => row.value == null)
}

// ---- the days -------------------------------------------------------------------------------------------------------------

/**
 * The German calendar date of a row: DWD's days are dates, and the library stamps each at 00:00 UTC of its date, so the date of
 * the timestamp is the day (`2026-11-27T00:00:00+00:00` is the 27th, in whatever zone it is read). Null for a timestamp that is none.
 */
export function dayOfRow(row: Pick<Value, 'timestamp'>): string | null {
  const day = /^\d{4}-\d{2}-\d{2}/.exec(row.timestamp ?? '')?.[0]
  return day && DateTime.fromISO(day).isValid ? day : null
}

/**
 * The days of a product to show: the dates of its rows from today (in the zone of the station, as the forecast's Today is) on,
 * the earliest first, at most three. A file that was written yesterday and has not been replaced yet still holds yesterday, which
 * is not shown; the first day it has left is then today, and what it says of tomorrow is its second.
 */
export function forecastDays(rows: readonly Pick<Value, 'timestamp'>[], today: string): string[] {
  return [...new Set(rows.map(dayOfRow).filter((day): day is string => day !== null && day >= today))].sort().slice(0, 3)
}

/** How many calendar days a day is from today: 0 is today, 1 tomorrow. Dates are compared as dates, never as moments, so a change of the clock between them is none. */
export function daysFromToday(day: string, today: string): number {
  return Math.round(DateTime.fromISO(day, { zone: 'utc' }).diff(DateTime.fromISO(today, { zone: 'utc' }), 'days').days)
}

// ---- what the reader chose ------------------------------------------------------------------------------------------------

/** The key of the storage: one entry for the choices of every state, as `{ "Sachsen": "82" }` */
export const POLLEN_PART_STORAGE_KEY = 'wd-pollen-part'

function readChoices(): Record<string, string> {
  try {
    const raw = localStorage.getItem(POLLEN_PART_STORAGE_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : null
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))
      return {}
    return Object.fromEntries(Object.entries(parsed).filter((entry): entry is [string, string] => typeof entry[1] === 'string'))
  }
  catch {
    // a storage that is blocked, or holds what is no JSON: no choice is remembered
    return {}
  }
}

/**
 * What the reader chose in this visit, by state: a storage that refuses (blocked, a private window) would otherwise lose the choice
 * at the next station, when the panel asks for it again. It is the page's own memory, and the newest choice.
 */
const chosenInThisVisit = new Map<string, string>()

/** Forgets what this visit chose (a test's, and nothing else's) */
export function forgetChoicesOfThisVisit(): void {
  chosenInThisVisit.clear()
}

/** The part-region the reader chose last for a state, as its id: in this visit, else on this device; null where none was */
export function rememberedPart(state: string): string | null {
  return chosenInThisVisit.get(state) ?? readChoices()[state] ?? null
}

/** Remembers the reader's choice for a state for this visit, and on this device where the storage takes it (blocked or full is no failure) */
export function rememberPart(state: string, partId: string): void {
  chosenInThisVisit.set(state, partId)
  try {
    localStorage.setItem(POLLEN_PART_STORAGE_KEY, JSON.stringify({ ...readChoices(), [state]: partId }))
  }
  catch {
    // the choice is kept by the page for as long as it is open
  }
}

/** The part to show: the one remembered for the state where it is still one of its parts, else the first */
export function selectedPart(parts: readonly PollenPart[], remembered: string | null): PollenPart | null {
  return parts.find(part => part.id === remembered) ?? parts[0] ?? null
}
