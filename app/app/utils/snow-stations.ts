/**
 * The stations that have a snow forecast (GH-4091): the few (15 in the Bavarian Alps, read by the backend from the newest run of
 * DWD's MOSMIX-SNOW, and, where there is none, the 15 it knows) the forecast page asks for the snow of.
 *
 * The page asks the backend's `stations` for the dataset once and keeps the answer, rather than ask for the snow values of
 * every station it shows: of the thousands of MOSMIX stations only these have any, so the request for the values would fail for
 * nearly every forecast the page makes (a request that the visitor's network, the backend's log and DWD's server are all asked
 * to carry for nothing), and a failure that is the rule says nothing about one that is a fault. The list is the same out of
 * season, which is a fact about the snow request (a 404 of its own) and not about the station. A failed request, and an
 * answer with no station (the backend has none to give only if it could not read its own list), is not kept: the next
 * forecast asks again. A tab left open for an hour asks again, as DWD adds stations to the product.
 */
import type { Station } from '#shared/types/api'

/** How long the list is kept */
export const SNOW_STATIONS_TTL_MS = 3_600_000

let known: { ids: Promise<Set<string>>, at: number } | null = null

/** The ids of the stations with a snow forecast; `load` is asked once an hour, and again after a failure */
export function snowStationIds(load: () => Promise<{ stations?: Pick<Station, 'station_id'>[] | null }>, now: number = Date.now()): Promise<Set<string>> {
  if (known && now - known.at < SNOW_STATIONS_TTL_MS)
    return known.ids
  const ids = load().then((answer) => {
    const found = new Set((answer.stations ?? []).map(station => station.station_id))
    if (!found.size && known?.ids === ids)
      known = null
    return found
  })
  const entry = { ids, at: now }
  known = entry
  ids.catch(() => {
    if (known === entry)
      known = null
  })
  return ids
}

/** Forgets the list, so that the next call asks again (a test's, and nothing else's) */
export function forgetSnowStations(): void {
  known = null
}
