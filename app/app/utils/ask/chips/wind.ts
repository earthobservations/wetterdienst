import type { Value } from '#shared/types/api'
import type { WindAnswer } from '../../answers'
import type { AnswerAction, DateChoice } from '../chip'
import { DateTime } from 'luxon'
import { lastBoxingDay, WIND_GUST, WIND_MEAN, windOnDay, windWindow } from '../../answers'
import { defineChip } from '../chip'

// How windy was it on a day? DWD's daily climate summary of the place's station (GH-3518).

const SCALE = {
  calm: 'ask.wind.calm',
  breezy: 'ask.wind.breezy',
  windy: 'ask.wind.windy',
  stormy: 'ask.wind.stormy',
} as const

/** The day, in the link as `&day=2025-12-26`: the last 26 December where the link names none, and no day after yesterday */
const DAY: DateChoice = {
  kind: 'date',
  param: 'day',
  inputId: 'answer-day',
  label: 'ask.wind.dayLabel',
  initial: lastBoxingDay,
  latest: (now: DateTime) => now.minus({ days: 1 }).toISODate()!,
}

/** What it fetches: the daily gust and mean of the place's station, a week either side of the day (`windWindow`) */
const FETCH = { provider: 'dwd', network: 'observation', resolution: 'daily', dataset: 'climate_summary', parameters: ['wind_gust_max', 'wind_speed_mean'] } as const

interface Loaded {
  readings: Value[]
  units: Record<string, string>
}

export const wind = defineChip({
  id: 'wind',
  icon: 'i-ph-wind',
  tool: 'explorer',
  quantity: 'speed',
  choices: [DAY],
  question: (env, choices) => env.t('ask.q.wind', { day: env.dayText(choices.day!) }),
  from: 'ask.from.wind',
  scale: SCALE,
  credit: { provider: 'dwd', fallback: 'Deutscher Wetterdienst' },
  i18n: [
    'ask.q.wind',
    'ask.from.wind',
    ...Object.values(SCALE),
    'ask.wind.mean',
    'ask.wind.gust',
    'ask.wind.context',
    'ask.wind.chartGust',
    'ask.wind.chartMean',
    'ask.wind.none',
    DAY.label,
    'ask.wind.open',
  ],

  load({ place, choices, now, unitTarget }, api): Promise<Loaded> {
    const { from, to } = windWindow(choices.day!, now())
    return api.values({
      provider: FETCH.provider,
      network: FETCH.network,
      parameters: FETCH.parameters.map(parameter => `${FETCH.resolution}/${FETCH.dataset}/${parameter}`).join(','),
      stations: place.id,
      timestamp: `${from}/${to}`,
      unit_targets: JSON.stringify({ speed: unitTarget('speed') }),
    })
  },

  answer: ({ readings, units }, { choices }): WindAnswer | null => windOnDay(readings, choices.day!, units[WIND_GUST] ?? units[WIND_MEAN]),

  present(answer, _loaded, { t, number, unitText, dayText }) {
    const details: string[] = []
    if (answer.mean !== null)
      details.push(t('ask.wind.mean', { speed: number(answer.mean), unit: unitText(answer.unit), force: answer.beaufort ?? 0 }))
    if (answer.gust !== null)
      details.push(t('ask.wind.gust', { speed: number(answer.gust), unit: unitText(answer.unit), force: answer.gustBeaufort ?? 0 }))
    if (answer.around)
      details.push(t('ask.wind.context', { stronger: answer.stronger, around: answer.around }))
    return {
      verdict: t(SCALE[answer.verdict]),
      details,
      chart: {
        bars: answer.bars.map(bar => ({ ...bar, label: DateTime.fromISO(bar.key).toFormat('d') })),
        caption: t(answer.barsAreGusts ? 'ask.wind.chartGust' : 'ask.wind.chartMean', { unit: unitText(answer.unit) }),
        unit: unitText(answer.unit),
        every: 7,
        emphasis: 'one',
        rowLabel: bar => dayText(bar.key, true),
      },
      list: null,
      note: '',
    }
  },

  empty: (_loaded, { t, dayText }, choices) => t('ask.wind.none', { day: dayText(choices.day!, true) }),

  actions({ t, place, now }, choices): AnswerAction[] {
    const { from, to } = windWindow(choices.day!, now())
    return [{ key: 'explorer', label: t('ask.wind.open'), tool: 'explorer', to: { path: '/explorer', query: { mode: 'station', provider: FETCH.provider, network: FETCH.network, resolution: FETCH.resolution, dataset: FETCH.dataset, parameters: 'wind_gust_max,wind_speed_mean', stations: place.id, startDate: from, endDate: to } } }]
  },
})
