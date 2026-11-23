// A place found by its name, in a link (GH-3791): its position as `lat` and `lon` (the keys the map and the Explorer already have) and its name
// and where it lies as `placeName` and `placeRegion`, so that a shared link shows the place without asking OpenStreetMap's search again. The key
// `place` is not used for it: on the home page it names a station (`?place=02564`).

/** What of a place a link keeps: where it is, and how it is called and where it lies (the words of Photon, in the language of the one who made the link) */
export interface PlaceInLink {
  name: string
  /** Where it lies, from the smallest to the largest part (`Bayern, Germany`), or null where it is a country itself */
  region: string | null
  latitude: number
  longitude: number
}

/** The longest name or region a link is taken to carry: what is longer is no place's name */
export const PLACE_LINK_TEXT_MAX = 120

type QueryValue = string | null | (string | null)[] | undefined

const first = (value: QueryValue): string | undefined => (Array.isArray(value) ? value[0] : value) ?? undefined

function coordinate(value: QueryValue, limit: number): number | null {
  const text = first(value)?.trim()
  if (!text || !/^[-+]?\d{1,3}(?:\.\d{1,8})?$/.test(text))
    return null
  const number = Number(text)
  return Number.isFinite(number) && Math.abs(number) <= limit ? number : null
}

function words(value: QueryValue): string | null {
  const text = first(value)?.replace(/\s+/g, ' ').trim()
  return text && text.length <= PLACE_LINK_TEXT_MAX ? text : null
}

/**
 * The place a link names, or null: it needs a position and a name. A link with a position alone (what the map writes) is no place of this sort: the name
 * is what shows it. The name is text of the link, shown as text and never as markup.
 */
export function placeOfQuery(query: Record<string, QueryValue>): PlaceInLink | null {
  const latitude = coordinate(query.lat, 90)
  const longitude = coordinate(query.lon, 180)
  const name = words(query.placeName)
  if (latitude === null || longitude === null || !name)
    return null
  return { name, region: words(query.placeRegion), latitude, longitude }
}

/** A place as the keys of a link, the position to four decimals (about 10 m) as the map writes it */
export function queryOfPlace(place: PlaceInLink): Record<string, string> {
  return {
    lat: place.latitude.toFixed(4),
    lon: place.longitude.toFixed(4),
    placeName: place.name,
    ...(place.region ? { placeRegion: place.region } : {}),
  }
}

/** The keys of a link that belong to a place, which a page takes out when its place is no longer the one asked about */
export const PLACE_QUERY_KEYS = ['lat', 'lon', 'placeName', 'placeRegion'] as const
