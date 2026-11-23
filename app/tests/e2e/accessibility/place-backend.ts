import type { Station } from '../../../shared/types/api'
import type { Handlers } from './mock-backend'
import { distanceKm } from '../../../app/utils/map-tool'
import { defaultHandlers } from './mock-backend'

// What a place found by its name is answered from (GH-3791): the stations of a network ranked by their distance to a position, as the REST API ranks them
// (`GET /api/stations?latitude=&longitude=&rank=`, each with its `distance` in kilometres), over the mock's stations and, for the forecast, a few more points
// round Bad Tölz, so that the closest station has others near it with another height. The points are the mock's own: no provider is asked.

/** Forecast points round Bad Tölz (47.76 N, 11.56 E), the mock's own, with their heights: the closest is 1.4 km away, the next ones 17 and 17 km */
export const MOSMIX_BAD_TOELZ: Station[] = [
  { station_id: 'M0814', name: 'BAD TOELZ', region: null, latitude: 47.77, longitude: 11.55, elevation: 668, start_timestamp: null, end_timestamp: null },
  { station_id: 'M0816', name: 'KOCHEL AM SEE', region: null, latitude: 47.65, longitude: 11.37, elevation: 614, start_timestamp: null, end_timestamp: null },
  { station_id: 'M0818', name: 'TEGERNSEE', region: null, latitude: 47.71, longitude: 11.76, elevation: 735, start_timestamp: null, end_timestamp: null },
]

/**
 * The handlers with `stations` ranked where the request carries a position: the nearest `rank` of the network's list (the forecast's with the points
 * round Bad Tölz), the closest first, each with its `distance`. A request without a position is answered as `handlers` answer it. `asked` collects the
 * requests with a position, so that a test says what was sent.
 */
export function rankedStations(handlers: Handlers = defaultHandlers(), asked: Array<Record<string, string>> = []): Handlers {
  const list = handlers.stations!
  return {
    ...handlers,
    stations: async (url, route) => {
      if (!url.searchParams.has('latitude')) {
        // a link's station by its id: the points round Bad Tölz are stations of the forecast as well
        const wanted = url.searchParams.getAll('stations').flatMap(ids => ids.split(','))
        const own = wanted.length && url.searchParams.get('network') === 'mosmix' ? MOSMIX_BAD_TOELZ.filter(station => wanted.includes(station.station_id)) : []
        const answer = await list(url, route) as { stations: Station[] }
        return own.length ? { stations: [...answer.stations, ...own] } : answer
      }
      asked.push(Object.fromEntries(url.searchParams))
      // the list the position ranks: the request without it
      const whole = new URL(url)
      for (const key of ['latitude', 'longitude', 'rank', 'distance'])
        whole.searchParams.delete(key)
      const answer = await list(whole, route) as { stations: Station[] }
      const mosmix = url.searchParams.get('network') === 'mosmix'
      const point = { latitude: Number(url.searchParams.get('latitude')), longitude: Number(url.searchParams.get('longitude')) }
      const ranked = [...answer.stations, ...(mosmix ? MOSMIX_BAD_TOELZ : [])]
        .filter(station => station.latitude != null && station.longitude != null)
        .map(station => ({ ...station, distance: Math.round(distanceKm(point, { latitude: station.latitude!, longitude: station.longitude! }) * 10) / 10 }))
        .sort((a, b) => a.distance - b.distance)
      return { stations: ranked.slice(0, Number(url.searchParams.get('rank') ?? ranked.length)) }
    },
  }
}
