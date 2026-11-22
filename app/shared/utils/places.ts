// The places the search of the header finds by name (GH-3790, GH-3791): what the app's server asks of Photon (photon.komoot.io, a
// search of OpenStreetMap's data) and what it hands to the palette. The pure part lives here, for the server that reads Photon's
// answer and the palette that shows it, and so that a test can hold it without either.

/** The kinds of place the search shows, each a word of the interface (`shell.placeKinds.<kind>`) */
export const PLACE_KINDS = ['city', 'town', 'village', 'hamlet', 'district', 'county', 'region', 'country', 'island', 'mountain', 'water', 'airport'] as const
export type PlaceKind = typeof PLACE_KINDS[number]

/** One place of the answer: its name, what it is, where it lies in the words of its country, and the point the map opens on */
export interface PlaceMatch {
  /** OpenStreetMap's own id of it (`N240109189`: node, way or relation, and number), which is stable */
  id: string
  name: string
  kind: PlaceKind
  /** Where it lies, from the smallest to the largest: `Upper Bavaria, Germany` (a part is left out where Photon gives none) */
  region: string | null
  latitude: number
  longitude: number
}

/** What `GET /_search/places?q=&lang=` answers: the places, or that the search is switched off (`state: 'off'`, no places) */
export interface PlacesAnswer {
  query: string
  state: 'ok' | 'off'
  places: PlaceMatch[]
  /** The credit OpenStreetMap's licence (ODbL) asks for with its data */
  attribution: string
}

/** The credit and the licence of the data of the places: OpenStreetMap's */
export const PLACES_ATTRIBUTION = '© OpenStreetMap contributors'
export const OSM_COPYRIGHT_URL = 'https://www.openstreetmap.org/copyright'
export const ODBL_URL = 'https://opendatacommons.org/licenses/odbl/1-0/'
export const PHOTON_URL = 'https://photon.komoot.io'

/** The fewest characters that are searched, and the most places the answer has */
export const MIN_PLACE_QUERY = 3
export const MAX_PLACE_QUERY = 100
export const MAX_PLACES = 5

/** The languages Photon's public server answers in (`de`, `en`, `fr`; any other is a 400 there) */
const PHOTON_LANGUAGES = ['de', 'en', 'fr'] as const
export type PhotonLang = typeof PHOTON_LANGUAGES[number]

/**
 * The language to ask Photon for the names of the places in, from the reader's locale (`de-hh`, `fr`, `cs`): the language itself where Photon has it (Luxembourgish as German), else
 * English, which names a place of any country in letters the reader can read (the local name of Tokyo is not).
 */
export function photonLang(locale: string | undefined | null): PhotonLang {
  const primary = (locale ?? '').toLowerCase().split(/[-_]/)[0]
  // Luxembourgish is read by people who read German (and French) first
  if (primary === 'lb')
    return 'de'
  return (PHOTON_LANGUAGES as readonly string[]).includes(primary!) ? primary as PhotonLang : 'en'
}

/** A text as the search holds it: one line of single spaces, composed, with no end spaces; its case is kept (the cache key lowers it) */
export function normalisePlaceQuery(text: string): string {
  return text.normalize('NFC').replace(/\s+/g, ' ').trim()
}

/**
 * Whether a text looks like a position, which is no name and is never sent: it has a decimal number (`47.76`, `47,7`), a degree or minute sign (`47°45′`, or
 * a quote after a number), two numbers (`47 N 11 E`, `lat 47 lon 11`), a letter next to a number that is a hemisphere's or a part of one's name
 * (`N 47`, `47 N`, `A12`), or a number with a word for latitude or longitude. A partial position is as much a position as a whole one.
 */
export function looksLikePosition(text: string): boolean {
  const query = normalisePlaceQuery(text)
  if (!/\d/.test(query))
    return false
  return /[°º˚′″]/.test(query)
    || /\d\s*['"’”]/.test(query)
    || /\d\s*[.,]\s*\d/.test(query)
    || (query.match(/\d+/g) ?? []).length >= 2
    || /(?:^|\P{L})\p{L}\s*[-+]?\d/u.test(query)
    || /\d\s*\p{L}(?!\p{L})/u.test(query)
    || /(?:^|[^\p{L}])(?:lat|lon|lng|long|latitude|longitude|deg(?:rees?)?|latitud|longitud|latitudine|longitudine|breite|l[aä]nge|szer|dł)(?!\p{L})/iu.test(query)
}

/**
 * Whether a text can be a place by name, which is what is sent to Photon: at least three letters (a number or a code of two letters is no name), and not
 * a position, whole or partial (`looksLikePosition`).
 */
export function isPlaceQuery(text: string): boolean {
  const query = normalisePlaceQuery(text)
  return (query.match(/\p{L}/gu) ?? []).length >= MIN_PLACE_QUERY && !looksLikePosition(query)
}

interface PhotonProperties {
  osm_id?: unknown
  osm_type?: unknown
  osm_key?: unknown
  osm_value?: unknown
  type?: unknown
  name?: unknown
  country?: unknown
  state?: unknown
  county?: unknown
  city?: unknown
  district?: unknown
}

const SETTLEMENT_KINDS: Record<string, PlaceKind> = {
  city: 'city',
  town: 'town',
  municipality: 'town',
  village: 'village',
  hamlet: 'hamlet',
  isolated_dwelling: 'hamlet',
  suburb: 'district',
  quarter: 'district',
  neighbourhood: 'district',
  borough: 'district',
  island: 'island',
  islet: 'island',
  archipelago: 'island',
  sea: 'water',
  ocean: 'water',
  county: 'county',
  district: 'county',
  region: 'region',
  state: 'region',
  province: 'region',
  country: 'country',
}
/** `boundary=administrative` has no kind in its value: Photon's own `type` says the level */
const ADMINISTRATIVE_KINDS: Record<string, PlaceKind> = { city: 'city', district: 'district', county: 'county', state: 'region', country: 'country' }
const NATURAL_KINDS: Record<string, PlaceKind> = { peak: 'mountain', volcano: 'mountain', mountain_range: 'mountain', hill: 'mountain', ridge: 'mountain', saddle: 'mountain', water: 'water', bay: 'water', strait: 'water' }
/** A river, a stream or a canal is found by its name (`Isar`) */
const WATERWAY_KINDS: Record<string, PlaceKind> = { river: 'water', stream: 'water', canal: 'water' }

/** What an OpenStreetMap object is, among the kinds the search shows, or null for one it does not (a street, a shop, a house, a bus stop) */
export function placeKindOf(key: unknown, value: unknown, type: unknown): PlaceKind | null {
  const v = typeof value === 'string' ? value : ''
  if (key === 'place')
    return SETTLEMENT_KINDS[v] ?? null
  if (key === 'boundary' && v === 'administrative')
    return typeof type === 'string' ? ADMINISTRATIVE_KINDS[type] ?? null : null
  if (key === 'natural')
    return NATURAL_KINDS[v] ?? null
  if (key === 'waterway')
    return WATERWAY_KINDS[v] ?? null
  if (key === 'aeroway' && v === 'aerodrome')
    return 'airport'
  return null
}

/**
 * What a kind is a level of, for telling a place from itself: a city, a town, a village, a hamlet and a district are the places people live in and
 * OpenStreetMap draws one of them as a node, a relation or both, with a kind that differs by who drew it; a county and a state are its administrative
 * levels; every other kind is a level of its own.
 */
function levelOf(kind: PlaceKind): string {
  return kind === 'city' || kind === 'town' || kind === 'village' || kind === 'hamlet' || kind === 'district' ? 'settlement' : kind === 'county' || kind === 'region' ? 'administration' : kind
}

/** A name as it is compared: without accents and case, and without the word an administrative unit is named with (`Landkreis Bad Tölz-Wolfratshausen`, `Stadt Hamm`) */
function bareName(name: string): string {
  return name.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().replace(/^(?:landkreis|kreis|stadtkreis|stadt|gemeinde|markt|ville de|city of|county of|comune di)\s+/, '').trim()
}

/** Whether two hits are one place: a level of the same sort, one region, lying within 0.05 degrees (about 5 km), and the same name or one that holds the other */
function sameAs(a: PlaceMatch, b: PlaceMatch): boolean {
  if (levelOf(a.kind) !== levelOf(b.kind) || a.region !== b.region || Math.abs(a.latitude - b.latitude) >= 0.05 || Math.abs(a.longitude - b.longitude) >= 0.05)
    return false
  const [x, y] = [bareName(a.name), bareName(b.name)]
  const settlement = levelOf(a.kind) === 'settlement' || levelOf(a.kind) === 'administration'
  return x === y || (settlement && (x.includes(y) || y.includes(x)))
}

const text = (value: unknown): string | null => typeof value === 'string' && value.trim() ? value.trim() : null

/** Where a place lies, in the words of Photon: the next larger unit where the kind is a small one, then the state and the country; none where it is the country itself */
function regionOf(kind: PlaceKind, properties: PhotonProperties, name: string): string | null {
  const small = kind === 'village' || kind === 'hamlet' || kind === 'district'
  const parts = [small ? text(properties.city) ?? text(properties.county) : null, kind === 'country' || kind === 'region' ? null : text(properties.state), kind === 'country' ? null : text(properties.country)]
  const seen = new Set([name])
  const kept = parts.filter((part): part is string => part !== null && !seen.has(part) && !!seen.add(part))
  return kept.length ? kept.join(', ') : null
}

/**
 * The places of Photon's answer (GeoJSON: a feature for each hit, its position as `[longitude, latitude]` and its properties from OpenStreetMap): the ones the
 * search shows, which are settlements, regions, countries, mountains, waters and airports and not streets or shops; the same place twice (the node and the
 * relation of one town, a county and its administrative boundary) once, as what `place=` says it is; at most `limit`. Null where the answer is not Photon's.
 */
export function placesOfPhoton(body: unknown, limit = MAX_PLACES): PlaceMatch[] | null {
  const features = (body as { features?: unknown } | null)?.features
  if (!Array.isArray(features))
    return null
  const places: PlaceMatch[] = []
  /** The OpenStreetMap key each place was found as: where one place is found twice, the hit of `place=` names its kind (a boundary relation has none of its own) */
  const keys: unknown[] = []
  for (const feature of features) {
    const properties = (feature?.properties ?? {}) as PhotonProperties
    const coordinates = feature?.geometry?.coordinates
    const name = text(properties.name)
    const kind = placeKindOf(properties.osm_key, properties.osm_value, properties.type)
    if (!name || !kind || !Array.isArray(coordinates))
      continue
    const [longitude, latitude] = coordinates as unknown[]
    if (typeof longitude !== 'number' || typeof latitude !== 'number' || !Number.isFinite(longitude) || !Number.isFinite(latitude) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180)
      continue
    const osmType = text(properties.osm_type)
    const place: PlaceMatch = {
      id: osmType && typeof properties.osm_id === 'number' ? `${osmType}${properties.osm_id}` : `${latitude.toFixed(4)},${longitude.toFixed(4)}`,
      name,
      kind,
      region: regionOf(kind, properties, name),
      latitude,
      longitude,
    }
    const twin = places.findIndex(other => sameAs(other, place))
    if (twin === -1) {
      places.push(place)
      keys.push(properties.osm_key)
    }
    else if (properties.osm_key === 'place' && keys[twin] !== 'place') {
      places[twin] = place
      keys[twin] = 'place'
    }
  }
  return places.slice(0, limit)
}
