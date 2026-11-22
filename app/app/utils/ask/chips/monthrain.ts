import type { Value } from '#shared/types/api'
import type { MonthRainAnswer } from '../../compare-answers'
import type { AnswerAction, NumberLine } from '../chip'
import { DateTime } from 'luxon'
import { MONTH_MIN_DAYS, MONTH_RAIN_PARAMETER, MONTH_SIMILAR_MM, MONTH_SIMILAR_SHARE, monthRain } from '../../compare-answers'
import { defineChip } from '../chip'

// Was this month wetter than the same month last year? DWD's daily precipitation of the place's station, the days of the month so far
// against the same days of the month a year before (GH-4296). The Compare tool shows the same two stretches side by side.

const SCALE = {
  wetter: 'ask.monthrain.wetter',
  drier: 'ask.monthrain.drier',
  similar: 'ask.monthrain.similar',
} as const

/** What it fetches: the daily precipitation of the place's station */
const FETCH = { provider: 'dwd', network: 'observation', resolution: 'daily', dataset: 'climate_summary', parameter: MONTH_RAIN_PARAMETER } as const

interface Loaded {
  readings: Value[]
  units: Record<string, string>
}

/**
 * The span the answer reads: the first day of the month before this one, a year earlier (the month the answer is about where the running
 * one has too few days, and the one before it a year back), to yesterday, which is the newest day that is published
 */
export function monthRainWindow(now: DateTime): { from: string, to: string } {
  const today = now.toUTC().startOf('day')
  return { from: today.startOf('month').minus({ months: 1, years: 1 }).toISODate()!, to: today.minus({ days: 1 }).toISODate()! }
}

/** The answer for the data that was fetched: what the actions and the link into the Explorer need of it */
function answerOf(loaded: Loaded | null, now: DateTime): MonthRainAnswer | null {
  return loaded ? monthRain(loaded.readings, now, loaded.units[MONTH_RAIN_PARAMETER]) : null
}

/** The months the answer is about as the two periods of the Compare tool: this year's so far and the whole of the same month a year before, day against day */
function periodsOf(answer: MonthRainAnswer | null, now: DateTime) {
  const month = answer?.month ?? now.toUTC().toFormat('yyyy-MM')
  const start = DateTime.fromISO(`${month}-01`, { zone: 'utc' })
  const last = start.minus({ years: 1 })
  const yesterday = now.toUTC().startOf('day').minus({ days: 1 })
  const end = DateTime.min(start.endOf('month').startOf('day'), yesterday)
  return { periodA: `${last.toISODate()}/${last.endOf('month').toISODate()}`, periodB: `${start.toISODate()}/${end.toISODate()}`, from: last.toISODate()!, to: end.toISODate()! }
}

/** The same two stretches side by side in the Compare tool: one station, one stretch against the other */
function compareLink(station: string, answer: MonthRainAnswer | null, now: DateTime) {
  const { periodA, periodB } = periodsOf(answer, now)
  return { path: '/compare', query: { compare: 'periods', resolution: FETCH.resolution, parameter: FETCH.parameter, stations: station, periodA, periodB } }
}

/** The same data in the Explorer: the daily precipitation of the place's station over both stretches */
function explorerLink(station: string, answer: MonthRainAnswer | null, now: DateTime) {
  const { from, to } = periodsOf(answer, now)
  return { path: '/explorer', query: { mode: 'station', provider: FETCH.provider, network: FETCH.network, resolution: FETCH.resolution, dataset: FETCH.dataset, parameters: FETCH.parameter, stations: station, startDate: from, endDate: to } }
}

export const monthrain = defineChip({
  id: 'monthrain',
  icon: 'i-ph-cloud-rain',
  tool: 'compare',
  quantity: 'precipitation',
  question: env => env.t('ask.q.monthrain'),
  from: 'ask.from.monthrain',
  scale: SCALE,
  credit: { provider: 'dwd', fallback: 'Deutscher Wetterdienst' },
  i18n: [
    'ask.q.monthrain',
    'ask.from.monthrain',
    ...Object.values(SCALE),
    'ask.monthrain.detail',
    'ask.monthrain.fallback',
    'ask.monthrain.chart',
    'ask.monthrain.none',
    'ask.monthrain.open',
  ],

  load: ({ place, now, unitTarget }, api): Promise<Loaded> => {
    const { from, to } = monthRainWindow(now())
    return api.values({
      provider: FETCH.provider,
      network: FETCH.network,
      parameters: `${FETCH.resolution}/${FETCH.dataset}/${FETCH.parameter}`,
      stations: place.id,
      timestamp: `${from}/${to}`,
      unit_targets: JSON.stringify({ precipitation: unitTarget('precipitation') }),
    })
  },

  answer: (loaded, { now }) => answerOf(loaded, now()),

  present(answer, _loaded, { t, number, unitText }) {
    const unit = unitText(answer.unit)
    return {
      verdict: t(SCALE[answer.verdict], { difference: number(Math.abs(answer.difference)), unit }),
      details: [
        t('ask.monthrain.detail', { month: answer.month, lastMonth: answer.lastMonth, days: answer.days, sum: number(answer.sum), lastSum: number(answer.lastSum), unit }),
      ],
      chart: { bars: answer.bars, caption: t('ask.monthrain.chart', { unit }), unit, emphasis: 'one' },
      list: null,
      // where the running month has too few days, the answer is about the last complete one, and says why
      note: answer.fallback ? t('ask.monthrain.fallback', { count: answer.runningDays, min: MONTH_MIN_DAYS, month: answer.month }) : '',
    }
  },

  explanation: {
    topics: ['precipitation', 'time'],
    steps: ['days', 'sums', 'verdict'],
    formulas: ['sums'],
    rules: [
      // what is read
      { id: 'daily-precipitation', kind: 'selection', cites: [{ work: 'dwd-daily-kl', at: 'RSK' }] },
      // which days
      { id: 'month-so-far', kind: 'window', cites: [], own: true },
      { id: 'same-days', kind: 'selection', cites: [], own: true },
      { id: 'min-days', kind: 'fallback', values: { minDays: MONTH_MIN_DAYS }, cites: [], own: true },
      // how they are added up and judged
      { id: 'month-sum', kind: 'statistic', cites: [], own: true },
      { id: 'similar-band', kind: 'band', values: { similarMm: MONTH_SIMILAR_MM, similarShare: MONTH_SIMILAR_SHARE * 100 }, cites: [], own: true },
    ],
    limits: ['station', 'recent', 'gauge', 'band'],
    data: {
      provider: FETCH.provider,
      network: FETCH.network,
      dataset: `${FETCH.resolution}/${FETCH.dataset}`,
      parameters: [FETCH.parameter],
      open: (env, _choices, loaded) => explorerLink(env.place.id, answerOf(loaded, env.now()), env.now()),
    },
    numbers(answer, _loaded, { number, unitText, place }) {
      const unit = unitText(answer.unit)
      const lines: NumberLine[] = [
        { id: 'station', params: { name: place.name, id: place.id } },
        { id: 'month', params: { month: answer.month, lastMonth: answer.lastMonth, days: answer.days } },
        { id: 'sums', params: { month: answer.month, lastMonth: answer.lastMonth, sum: number(answer.sum), lastSum: number(answer.lastSum), unit } },
        { id: 'difference', params: { difference: number(answer.difference), unit } },
        { id: 'band', params: { similarMm: number(MONTH_SIMILAR_MM, 0), similarShare: number(MONTH_SIMILAR_SHARE * 100, 0) } },
      ]
      if (answer.fallback)
        lines.push({ id: 'fallback', params: { count: answer.runningDays, min: MONTH_MIN_DAYS } })
      return lines
    },
  },

  empty: (_loaded, { t }) => t('ask.monthrain.none', { min: MONTH_MIN_DAYS }),

  actions: (env, _choices, loaded): AnswerAction[] => [
    { key: 'compare', label: env.t('ask.monthrain.open'), tool: 'compare', to: compareLink(env.place.id, answerOf(loaded, env.now()), env.now()) },
  ],
})
