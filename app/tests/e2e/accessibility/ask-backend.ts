import type { Handlers } from './mock-backend'
import { DateTime } from 'luxon'
import { defaultHandlers, STATIONS } from './mock-backend'

// What the home page's questions are answered from (components/AnswerPanel.vue), as the mock backend gives it: the
// MOSMIX point nearest the place with tomorrow's rain, the monthly means of the summers, the daily wind of a fortnight,
// and a provider list whose networks have an hourly resolution. Small and fixed, shaped as `shared/types/api.ts` has
// them, and relative to the day the spec runs on, as the questions are.

export const KIEL_MOSMIX = { station_id: '10046', name: 'KIEL-HOLTENAU', region: null, latitude: 54.38, longitude: 10.15, elevation: 28, start_timestamp: null, end_timestamp: null, distance: 0.6 }

/** Every request the questions made, by path and its query, so that a spec can say what was asked and what was not */
export interface Asked {
  path: string
  query: Record<string, string>
}

function reading(station_id: string, resolution: string, dataset: string, parameter: string, timestamp: string, value: number) {
  return { station_id, resolution, dataset, parameter, timestamp, value, quality_flags: null }
}

/** The last June to August that is over (the answer's rule: from the first of September on) */
export function lastSummerYear(now = DateTime.now()): number {
  return now >= DateTime.utc(now.year, 9, 1) ? now.year : now.year - 1
}

export function rainValues(station: string) {
  // tomorrow in Kiel, 15:00 to 16:00 local, is a millimetre; the rest of the days is dry. Four days of hours, so that the whole of tomorrow is there
  const tomorrow = DateTime.now().setZone('Europe/Berlin').startOf('day').plus({ days: 1 })
  // the hour closing at 16:00 is the wettest, with the one before and after it
  const wet = new Map(([[15, 0.3], [16, 1.2], [17, 0.6]] as Array<[number, number]>).map(([hour, amount]) => [tomorrow.plus({ hours: hour }).toMillis(), amount]))
  const start = DateTime.now().toUTC().startOf('hour').minus({ hours: 12 })
  return Array.from({ length: 108 }, (_, hour) => start.plus({ hours: hour })).flatMap((at) => {
    const stamp = at.toISO({ suppressMilliseconds: true })!
    return [
      reading(station, 'hourly', 'large', 'precipitation_amount_significant_weather_last_1h', stamp, wet.get(at.toMillis()) ?? 0),
      reading(station, 'hourly', 'large', 'probability_precipitation_amount_gt_0_1mm_last_1h', stamp, wet.has(at.toMillis()) ? 0.85 : 0.05),
    ]
  })
}

export function summerValues(station: string) {
  const last = lastSummerYear()
  return Array.from({ length: last - 1985 }, (_, index) => 1986 + index).flatMap(year =>
    [6, 7, 8].map(month => reading(station, 'monthly', 'climate_summary', 'temperature_air_mean_2m', `${year}-0${month}-01T00:00:00+00:00`, year === last ? 18.1 : 16.2 + 0.3 * Math.sin(year))),
  )
}

export function windValues(station: string, range: string | null) {
  const [from, to] = (range ?? '2025-12-19/2026-01-02').split('/')
  const first = DateTime.fromISO(from!, { zone: 'utc' })
  const days = Math.round(DateTime.fromISO(to!, { zone: 'utc' }).diff(first, 'days').days)
  return Array.from({ length: days + 1 }, (_, index) => first.plus({ days: index })).flatMap((day) => {
    const stamp = `${day.toISODate()}T00:00:00+00:00`
    const stormy = day.month === 12 && day.day === 26
    return [
      reading(station, 'daily', 'climate_summary', 'wind_gust_max', stamp, stormy ? 21.6 : 5 + 2 * Math.sin(day.day)),
      reading(station, 'daily', 'climate_summary', 'wind_speed_mean', stamp, stormy ? 9.1 : 3.2 + Math.cos(day.day)),
    ]
  })
}

/** A backend that answers the questions; `asked` collects what they ask */
export function askHandlers(asked: Asked[] = []): Handlers {
  const base = defaultHandlers()
  const record = (path: string, url: URL) => asked.push({ path, query: Object.fromEntries(url.searchParams) })
  return {
    stations: (url, route) => {
      record('stations', url)
      // the forecast point nearest a place
      if (url.searchParams.get('network') === 'mosmix' && url.searchParams.has('latitude'))
        return { stations: [KIEL_MOSMIX] }
      return base.stations!(url, route)
    },
    values: (url) => {
      record('values', url)
      const station = url.searchParams.get('stations') ?? '02564'
      const parameters = url.searchParams.get('parameters') ?? ''
      if (url.searchParams.get('network') === 'mosmix')
        return { values: rainValues(station) }
      if (parameters.startsWith('monthly/'))
        return { values: summerValues(station) }
      return { values: windValues(station, url.searchParams.get('timestamp')) }
    },
    providers: (url, route) => {
      const list = structuredClone(base.providers!(url, route)) as { providers: Array<{ networks: Array<{ network: string, resolutions: Array<{ name: string, datasets: unknown[] }> }> }> }
      // an hourly resolution for the two measuring networks
      for (const provider of list.providers) {
        for (const network of provider.networks) {
          if (network.network === 'observation')
            network.resolutions = [{ name: 'hourly', datasets: [{ name: 'temperature_air', parameters: 2 }] }, ...network.resolutions]
        }
      }
      return list
    },
  }
}

export { STATIONS }
