import type { Station, Value } from '#shared/types/api'
import type { RainAnswer } from '../../answers'
import type { AnswerAction } from '../chip'
import tzLookup from 'tz-lookup'
import { RAIN_AMOUNT, RAIN_AMOUNTS, RAIN_CHANCE, rainTomorrow } from '../../answers'
import { defineChip } from '../chip'

// Will it rain tomorrow? DWD MOSMIX, the forecast point nearest the place (GH-3518).

const SCALE = {
  yes: 'ask.rain.yes',
  maybe: 'ask.rain.maybe',
  no: 'ask.rain.no',
} as const

/** What it fetches: the hourly amounts and the chance of rain of the MOSMIX point nearest the place */
const FETCH = { provider: 'dwd', network: 'mosmix', dataset: 'hourly/large' } as const

interface Loaded {
  point: Station
  readings: Value[]
  units: Record<string, string>
}

export const rain = defineChip({
  id: 'rain',
  icon: 'i-ph-cloud-rain',
  tool: 'forecast',
  quantity: 'precipitation',
  question: env => env.t('ask.q.rain', { place: env.place.name }),
  from: 'ask.from.rain',
  scale: SCALE,
  credit: { provider: 'dwd', fallback: 'Deutscher Wetterdienst' },
  i18n: [
    'ask.q.rain',
    'ask.from.rain',
    ...Object.values(SCALE),
    'ask.rain.total',
    'ask.rain.wettest',
    'ask.rain.chance',
    'ask.rain.point',
    'ask.rain.pointNoDistance',
    'ask.rain.chart',
    'ask.rain.none',
    'ask.rain.open',
  ],

  async load({ place, unitTarget }, api): Promise<Loaded | null> {
    const near = await api.stations({ provider: FETCH.provider, network: FETCH.network, parameters: FETCH.dataset, latitude: place.latitude, longitude: place.longitude, rank: 1 })
    const point = near[0]
    if (!point)
      return null
    // the chance is a probability, which the sentence writes as a percentage whatever the settings' unit for fractions
    // (oktas, say, are no way to write one): asked as a decimal, and read by the unit the answer gives where it is not
    const { readings, units } = await api.values({
      provider: FETCH.provider,
      network: FETCH.network,
      parameters: [...RAIN_AMOUNTS, 'r101'].map(parameter => `${FETCH.dataset}/${parameter}`).join(','),
      stations: point.station_id,
      unit_targets: JSON.stringify({ precipitation: unitTarget('precipitation'), fraction: 'decimal' }),
    })
    return { point, readings, units }
  },

  answer(loaded, { place, now }): RainAnswer | null {
    if (!loaded)
      return null
    const { readings, units } = loaded
    return rainTomorrow(readings, tzLookup(place.latitude, place.longitude), now(), { precipitation: units[RAIN_AMOUNT], fraction: units[RAIN_CHANCE] })
  },

  present(answer, loaded, env) {
    const { t, number, percent, unitText } = env
    const details = [t('ask.rain.total', { amount: number(answer.total), unit: unitText(answer.unit) })]
    if (answer.wettest) {
      const next = (answer.wettest.hour + 1) % 24
      details.push(t('ask.rain.wettest', { from: String(answer.wettest.hour).padStart(2, '0'), to: String(next).padStart(2, '0'), amount: number(answer.wettest.amount), unit: unitText(answer.unit) }))
    }
    if (answer.maxChance !== null)
      details.push(t('ask.rain.chance', { chance: percent(answer.maxChance) }))
    const point = loaded!.point
    const distance = (point as Station & { distance?: number }).distance
    return {
      verdict: t(SCALE[answer.verdict]),
      details,
      chart: { bars: answer.hours, caption: t('ask.rain.chart', { unit: unitText(answer.unit) }), unit: unitText(answer.unit), every: 3, emphasis: 'all', rowLabel: bar => `${bar.label}:00` },
      list: null,
      note: distance === undefined
        ? t('ask.rain.pointNoDistance', { name: point.name ?? point.station_id, place: env.place.name })
        : t('ask.rain.point', { name: point.name ?? point.station_id, place: env.place.name, distance: number(distance) }),
    }
  },

  empty: (loaded, env) => env.t('ask.rain.none', { name: loaded?.point.name ?? env.place.name }),

  actions: (env, _choices, loaded): AnswerAction[] => loaded
    ? [{ key: 'forecast', label: env.t('ask.rain.open'), tool: 'forecast', to: { path: '/meteogram', query: { station: loaded.point.station_id } } }]
    : [],
})
