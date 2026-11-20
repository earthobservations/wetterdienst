import { useApiBase } from '../../utils/apiBase'
import { readGhcnStations } from '../../utils/ghcnStations'

// The stations of NOAA GHCN daily for the map (GH-4267): all 133k of them, as columns (`shared/types/ghcn-stations.ts`), made
// from the backend's list once and kept for a day (the list changes when NOAA adds or retires a station, a few a week).
// `/api/map/...` is the app's own and is not the backend's, so it is no part of the proxy of `/api/[...]`, which a route of this
// name is more specific than; it counts against the rate limit like any other route under `/api` that is not the catalogue's
// (`server/middleware/rate-limit.ts`): the first request after a restart or a day costs the backend a 3 s answer of 44 MB.
//
// The cache is the one Nitro has: stale-while-revalidate, so that the first request after the day is answered with the list in hand
// while the next one is made, and a backend that is down then costs nothing. A problem is no cache entry (Nitro keeps no answer of a
// status of 400 or more), so an outage at the first request, or at a restart, is a 502 for the page to retry and never a list of none.
const MAX_AGE_SECONDS = 24 * 60 * 60

const cached = defineCachedEventHandler(async (event) => {
  const requestId = globalThis.crypto.randomUUID().replaceAll('-', '')
  const read = await readGhcnStations(useApiBase(), requestId)
  if ('body' in read) {
    setResponseStatus(event, read.status)
    for (const [name, value] of Object.entries(read.headers))
      setResponseHeader(event, name, value)
    return JSON.stringify(read.body)
  }
  setResponseHeader(event, 'content-type', 'application/json')
  // text, not an object, so that Nitro keeps and sends it as it is and does not read and write 8 MB at every request
  return JSON.stringify(read)
}, {
  maxAge: MAX_AGE_SECONDS,
  swr: true,
  name: 'ghcn-stations',
  getKey: () => 'all',
})

// Nitro puts the day's `s-maxage` on every answer of its cache, a problem too: one that a CDN in front of the app took for a day of a list
export default defineEventHandler(async (event) => {
  const body = await cached(event)
  if (getResponseStatus(event) >= 400)
    setResponseHeader(event, 'cache-control', 'no-store')
  return body
})
