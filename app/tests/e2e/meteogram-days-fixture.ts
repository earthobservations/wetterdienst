import type { Handler } from './accessibility/mock-backend'
import { defaultHandlers } from './accessibility/mock-backend'

// A forecast of eight days in which the rain comes every other day of the station (Europe/Berlin), for the specs of the
// compact view: the mock backend's three days all have rain, and a card with no rain line (a dry day) is the case that
// differs in height from the others (GH-4138).

const PRECIPITATION = 'precipitation_amount_significant_weather_last_1h'
const DAY_MS = 86_400_000
const FORECAST_DAYS = 8

/** The station's calendar day of an instant, as a number that is odd on every other day */
function dayNumber(timestamp: string): number {
  const date = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Berlin' }).format(new Date(timestamp))
  return Math.round(Date.parse(`${date}T00:00:00Z`) / DAY_MS)
}

/** The mock's `values` handler, with its three days repeated to eight and the rain on every other day of the station only */
export function alternatingRainValues(now: Date = new Date()): Handler {
  const original = defaultHandlers(now).values!
  return async (url, route) => {
    const answer = await original(url, route) as { values: Record<string, unknown>[] }
    if (url.searchParams.get('network') !== 'mosmix' || !Array.isArray(answer?.values) || url.searchParams.get('parameters') === 'hourly/snow')
      return answer
    const copies = Math.ceil((FORECAST_DAYS * 24) / 72)
    const values = Array.from({ length: copies }, (_, copy) => answer.values.map(value => ({
      ...value,
      timestamp: new Date(Date.parse(value.timestamp as string) + copy * 72 * 3_600_000).toISOString().replace('.000Z', '+00:00'),
    }))).flat()
    return {
      values: values.map(value => value.parameter === PRECIPITATION && dayNumber(value.timestamp as string) % 2 === 0 ? { ...value, value: 0 } : value),
    }
  }
}
