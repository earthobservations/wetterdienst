import type { Value } from '#shared/types/api'
import type { SummerAnswer } from '../../answers'
import type { AnswerAction } from '../chip'
import { lastSummer } from '../../answers'
import { defineChip } from '../chip'

// Was last summer hotter than usual? DWD's monthly means of the place's station (GH-3518).

const SCALE = {
  hotter: 'ask.summer.hotter',
  cooler: 'ask.summer.cooler',
  usual: 'ask.summer.usual',
} as const

/** What it fetches: the monthly mean air temperature of the place's station, the whole record */
const FETCH = { provider: 'dwd', network: 'observation', parameters: 'monthly/climate_summary/temperature_air_mean_2m' } as const

interface Loaded {
  readings: Value[]
  units: Record<string, string>
}

export const summer = defineChip({
  id: 'summer',
  icon: 'i-ph-thermometer-hot',
  tool: 'explorer',
  quantity: 'temperature',
  question: env => env.t('ask.q.summer'),
  from: 'ask.from.summer',
  scale: SCALE,
  credit: { provider: 'dwd', fallback: 'Deutscher Wetterdienst' },
  i18n: [
    'ask.q.summer',
    'ask.from.summer',
    ...Object.values(SCALE),
    'ask.summer.detail',
    'ask.summer.rank',
    'ask.summer.chart',
    'ask.summer.none',
    'ask.summer.open',
    'ask.summer.stripes',
  ],

  load: ({ place, unitTarget }, api): Promise<Loaded> => api.values({
    ...FETCH,
    stations: place.id,
    unit_targets: JSON.stringify({ temperature: unitTarget('temperature') }),
  }),

  answer: ({ readings, units }, { now }): SummerAnswer | null => lastSummer(readings, now(), units.temperature_air_mean_2m),

  present(answer, _loaded, { t, number, unitText }) {
    return {
      verdict: t(SCALE[answer.verdict], { anomaly: number(Math.abs(answer.anomaly)), unit: unitText(answer.unit) }),
      details: [
        t('ask.summer.detail', { year: answer.year, mean: number(answer.mean), from: answer.normalFrom, to: answer.normalTo, normal: number(answer.normal), unit: unitText(answer.unit) }),
        t('ask.summer.rank', { rank: answer.rank, count: answer.summers, first: answer.bars[0]?.label ?? '' }),
      ],
      chart: {
        bars: answer.bars,
        caption: t('ask.summer.chart', { from: answer.normalFrom, to: answer.normalTo, unit: unitText(answer.unit) }),
        unit: unitText(answer.unit),
        diverging: true,
        emphasis: 'one',
      },
      list: null,
      note: '',
    }
  },

  empty: (_loaded, { t }) => t('ask.summer.none'),

  actions: ({ t, place }): AnswerAction[] => [
    { key: 'explorer', label: t('ask.summer.open'), tool: 'explorer', to: { path: '/explorer', query: { mode: 'station', provider: FETCH.provider, network: FETCH.network, resolution: 'monthly', dataset: 'climate_summary', parameters: 'temperature_air_mean_2m', stations: place.id } } },
    { key: 'stripes', label: t('ask.summer.stripes'), tool: 'stripes', to: { path: '/stripes', query: { kind: 'temperature', station: place.id } } },
  ],
})
