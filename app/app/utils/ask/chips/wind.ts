import type { Value } from '#shared/types/api'
import type { WindAnswer } from '../../answers'
import type { AnswerAction, DateChoice, NumberLine } from '../chip'
import { DateTime } from 'luxon'
import { BEAUFORT, lastBoxingDay, WIND_FORCES_OF_GUST, WIND_FORCES_OF_MEAN, WIND_GUST, WIND_MEAN, WIND_WINDOW_DAYS, windOnDay, windWindow } from '../../answers'
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

/** The same data in the Explorer: the gust and the mean of the place's station, the days the answer fetches */
function explorerLink(station: string, day: string, now: DateTime) {
  const { from, to } = windWindow(day, now)
  return { path: '/explorer', query: { mode: 'station', provider: FETCH.provider, network: FETCH.network, resolution: FETCH.resolution, dataset: FETCH.dataset, parameters: 'wind_gust_max,wind_speed_mean', stations: station, startDate: from, endDate: to } }
}

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

  explanation: {
    topics: ['wind', 'time'],
    steps: ['station', 'forces', 'verdict', 'around'],
    formulas: ['force'],
    rules: [
      // what is read
      { id: 'daily-values', kind: 'selection', cites: [{ work: 'dwd-daily-kl', at: 'FX, FM' }, { work: 'wmo-8-i', at: '§5.1.2' }] },
      { id: 'default-day', kind: 'selection', cites: [], own: true },
      // how a speed becomes a force
      { id: 'beaufort', kind: 'band', values: { edges: BEAUFORT }, cites: [{ work: 'wmo-8-i', at: '§5.1.4, Table 5.1' }] },
      // how a force becomes a word
      { id: 'gust-first', kind: 'statistic', own: true, cites: [{ work: 'wmo-8-i', at: '§5.1.3, §5.1.4' }] },
      { id: 'gust-words', kind: 'band', values: { gustBreezy: WIND_FORCES_OF_GUST.breezy, gustWindy: WIND_FORCES_OF_GUST.windy, gustStormy: WIND_FORCES_OF_GUST.stormy }, own: true, cites: [{ work: 'wmo-8-i', at: 'Table 5.1' }, { work: 'dwd-warnings' }] },
      { id: 'mean-words', kind: 'band', values: { meanBreezy: WIND_FORCES_OF_MEAN.breezy, meanWindy: WIND_FORCES_OF_MEAN.windy, meanStormy: WIND_FORCES_OF_MEAN.stormy }, own: true, cites: [{ work: 'wmo-8-i', at: 'Table 5.1' }] },
      // what the day is set beside
      { id: 'around-window', kind: 'window', values: { days: WIND_WINDOW_DAYS }, cites: [], own: true },
      { id: 'stronger-count', kind: 'statistic', cites: [], own: true },
    ],
    limits: ['station', 'gust', 'missing', 'height', 'window'],
    data: {
      provider: FETCH.provider,
      network: FETCH.network,
      dataset: `${FETCH.resolution}/${FETCH.dataset}`,
      parameters: FETCH.parameters,
      open: ({ place, now }, choices) => explorerLink(place.id, choices.day!, now()),
    },
    numbers(answer, _loaded, { number, unitText, place, dayText }) {
      const unit = unitText(answer.unit)
      const lines: NumberLine[] = [
        { id: 'station', params: { name: place.name, id: place.id } },
        { id: 'day', params: { day: dayText(answer.day, true) } },
      ]
      if (answer.mean !== null)
        lines.push({ id: 'mean', params: { speed: number(answer.mean), unit, force: answer.beaufort ?? 0 } })
      if (answer.gust !== null)
        lines.push({ id: 'gust', params: { speed: number(answer.gust), unit, force: answer.gustBeaufort ?? 0 } })
      const forces = answer.gust !== null ? WIND_FORCES_OF_GUST : WIND_FORCES_OF_MEAN
      lines.push({ id: answer.gust !== null ? 'scaleGust' : 'scaleMean', params: { breezy: forces.breezy, windy: forces.windy, stormy: forces.stormy } })
      lines.push({ id: 'around', params: { around: answer.around, stronger: answer.stronger, days: WIND_WINDOW_DAYS } })
      return lines
    },
  },

  empty: (_loaded, { t, dayText }, choices) => t('ask.wind.none', { day: dayText(choices.day!, true) }),

  actions: ({ t, place, now }, choices): AnswerAction[] => [{ key: 'explorer', label: t('ask.wind.open'), tool: 'explorer', to: explorerLink(place.id, choices.day!, now()) }],
})
