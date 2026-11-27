/**
 * The regions of DWD's pollen forecast (GH-4501): 27 of them, which have no position and no change from one day to the next, so
 * the Forecast asks the backend's `stations` for the whole list once and keeps the answer, as it does the stations that have a
 * snow forecast (`snow-stations.ts`). Each has the state or states it covers as its `region` and the part-region's own name as its
 * `name`, which is all a state is matched to its regions by (`pollenPartsOfState`). A failed request, and an answer with no
 * region, is not kept: the next forecast asks again. A tab left open for an hour asks again, as DWD adds regions to the file.
 */
import type { Station } from '#shared/types/api'

/** How long the list is kept */
export const POLLEN_REGIONS_TTL_MS = 3_600_000

type Region = Pick<Station, 'station_id' | 'name' | 'region'>

let known: { regions: Promise<Region[]>, at: number } | null = null

/** The regions of the pollen forecast; `load` is asked once an hour, and again after a failure */
export function pollenRegions(load: () => Promise<{ stations?: Region[] | null }>, now: number = Date.now()): Promise<Region[]> {
  if (known && now - known.at < POLLEN_REGIONS_TTL_MS)
    return known.regions
  const regions = load().then((answer) => {
    const found = answer.stations ?? []
    if (!found.length && known?.regions === regions)
      known = null
    return found
  })
  const entry = { regions, at: now }
  known = entry
  regions.catch(() => {
    if (known === entry)
      known = null
  })
  return regions
}

/** Forgets the list, so that the next call asks again (a test's, and nothing else's) */
export function forgetPollenRegions(): void {
  known = null
}
