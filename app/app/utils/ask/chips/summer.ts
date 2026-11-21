import type { Value } from '#shared/types/api'
import type { SummerAnswer } from '../../answers'
import type { AnswerAction, NumberLine } from '../chip'
import { FALLBACK_MIN_SUMMERS, lastSummer, NORMAL_FROM, NORMAL_MIN_SUMMERS, NORMAL_TO, USUAL_BAND } from '../../answers'
import { differenceIn } from '../../units'
import { defineChip } from '../chip'

// Was last summer hotter than usual? DWD's monthly means of the place's station (GH-3518).

const SCALE = {
  hotter: 'ask.summer.hotter',
  cooler: 'ask.summer.cooler',
  usual: 'ask.summer.usual',
} as const

/** What it fetches: the monthly mean air temperature of the place's station, the whole record */
const FETCH = { provider: 'dwd', network: 'observation', parameters: 'monthly/climate_summary/temperature_air_mean_2m' } as const

/** The same data in the Explorer: the monthly mean temperature of the place's station */
function explorerLink(station: string) {
  return { path: '/explorer', query: { mode: 'station', provider: FETCH.provider, network: FETCH.network, resolution: 'monthly', dataset: 'climate_summary', parameters: 'temperature_air_mean_2m', stations: station } }
}

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

  explanation: {
    topics: ['temperature', 'normals'],
    steps: ['summers', 'reference', 'compare', 'verdict'],
    formulas: ['summer', 'anomaly'],
    rules: [
      // which months make a summer, and which summers count
      { id: 'season', kind: 'period', values: { months: 'June, July, August' }, cites: [{ work: 'dwd-seasons' }, { work: 'dwd-summer' }] },
      { id: 'complete-months', kind: 'selection', cites: [{ work: 'wmo-1203', at: '§4.3.3' }, { work: 'dwd-monthly-kl', at: 'Data origin' }] },
      { id: 'only-over', kind: 'selection', cites: [], own: true },
      { id: 'summer-mean', kind: 'statistic', cites: [{ work: 'wmo-1203', at: '§4.3.3 (a), note 1' }] },
      // what it is compared with
      { id: 'reference-period', kind: 'period', values: { from: NORMAL_FROM, to: NORMAL_TO }, cites: [{ work: 'wmo-1203', at: '§2, §3' }] },
      { id: 'normal-mean', kind: 'statistic', own: true, cites: [{ work: 'wmo-1203', at: '§4.3.3 (a)' }] },
      { id: 'min-summers', kind: 'fallback', values: { minSummers: NORMAL_MIN_SUMMERS, ofSummers: NORMAL_TO - NORMAL_FROM + 1 }, own: true, cites: [{ work: 'wmo-1203', at: '§4.4.2' }] },
      // where the station has too few of them
      { id: 'fallback-period', kind: 'fallback', own: true, cites: [{ work: 'wmo-1203', at: '§3' }] },
      { id: 'fallback-minimum', kind: 'fallback', values: { fallbackMin: FALLBACK_MIN_SUMMERS }, own: true, cites: [{ work: 'wmo-1203', at: '§5.2.3' }] },
      // the verdict
      { id: 'anomaly', kind: 'statistic', cites: [{ work: 'wmo-1203', at: '§2' }] },
      { id: 'usual-band', kind: 'band', values: { band: USUAL_BAND }, cites: [], own: true },
      { id: 'rank', kind: 'statistic', cites: [], own: true },
    ],
    limits: ['station', 'moved', 'gaps', 'reference', 'band'],
    data: {
      provider: FETCH.provider,
      network: FETCH.network,
      dataset: 'monthly/climate_summary',
      parameters: ['temperature_air_mean_2m'],
      open: ({ place }) => explorerLink(place.id),
    },
    numbers(answer, _loaded, { number, unitText, place }) {
      const lines: NumberLine[] = [
        { id: 'station', params: { name: place.name, id: place.id } },
        { id: 'summer', params: { year: answer.year, mean: number(answer.mean), unit: unitText(answer.unit) } },
        { id: answer.fallback ? 'referenceFallback' : 'reference', params: { from: answer.normalFrom, to: answer.normalTo, count: answer.referenceCount, normal: number(answer.normal), unit: unitText(answer.unit), normalFrom: NORMAL_FROM, normalTo: NORMAL_TO } },
        { id: 'anomaly', params: { anomaly: number(answer.anomaly), unit: unitText(answer.unit) } },
        // half a degree is half a kelvin: in the unit the reader chose, the band is as many degrees of it
        { id: 'band', params: { band: number(differenceIn('temperature', answer.unit, USUAL_BAND)), unit: unitText(answer.unit) } },
        { id: 'rank', params: { rank: answer.rank, count: answer.summers, first: answer.bars[0]?.label ?? '' } },
      ]
      return lines
    },
  },

  empty: (_loaded, { t }) => t('ask.summer.none'),

  actions: ({ t, place }): AnswerAction[] => [
    { key: 'explorer', label: t('ask.summer.open'), tool: 'explorer', to: explorerLink(place.id) },
    { key: 'stripes', label: t('ask.summer.stripes'), tool: 'stripes', to: { path: '/stripes', query: { kind: 'temperature', station: place.id } } },
  ],
})
