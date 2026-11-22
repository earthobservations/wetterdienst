import type { Value } from '#shared/types/api'
import type { WindAnswer } from '../../answers'
import type { Measure, RainDayAnswer, SnowAnswer, SunAnswer, TemperatureAnswer } from '../../day'
import type { TopicId } from '../../measurement'
import type { AnswerAction, AnswerView, ChipEnv, Choices, DateChoice, NumberLine, SelectChoice } from '../chip'
import { DateTime } from 'luxon'
import { BEAUFORT, DAY_WINDOW_DAYS, dayWindow, sameDayLastYear, WIND_FORCES_OF_GUST, WIND_FORCES_OF_MEAN, WIND_GUST, WIND_MEAN, windOnDay } from '../../answers'
import {
  DAY_PARAMETERS,
  FROST_DAY_MIN_BELOW,
  HOT_DAY_MAX_FROM,
  ICE_DAY_MAX_BELOW,
  isMeasure,
  MEASURES,
  measuresWithData,
  RAIN_DRY_BELOW_MM,
  RAIN_VERY_WET_FROM_MM,
  RAIN_WET_FROM_MM,
  rainOnDay,
  SNOW_LIES_ABOVE_CM,
  snowOnDay,
  SUMMER_DAY_MAX_FROM,
  SUN_SHARE_DULL_BELOW,
  SUN_SHARE_SUNNY_FROM,
  sunOnDay,
  temperatureOnDay,
  TROPICAL_NIGHT_MIN_FROM,
} from '../../day'
import { fromCanonical } from '../../units'
import { defineChip } from '../chip'

// What was a day like? DWD's daily readings of the place's station (GH-3518): how windy, sunny, wet, hot or cold, or snowy it was
// (GH-3764, step 2b). It began as the question "How windy was it on 26 December?", which is the wind measure of it and is what the old
// link `?ask=wind&day=...` still asks.

const SCALE = {
  calm: 'ask.wind.calm',
  breezy: 'ask.wind.breezy',
  windy: 'ask.wind.windy',
  stormy: 'ask.wind.stormy',
  dull: 'ask.day.sun.dull',
  mixed: 'ask.day.sun.mixed',
  sunny: 'ask.day.sun.sunny',
  dry: 'ask.day.rain.dry',
  light: 'ask.day.rain.light',
  wet: 'ask.day.rain.wet',
  veryWet: 'ask.day.rain.veryWet',
  hot: 'ask.day.temperature.hot',
  summer: 'ask.day.temperature.summer',
  tropical: 'ask.day.temperature.tropical',
  ice: 'ask.day.temperature.ice',
  frost: 'ask.day.temperature.frost',
  ordinary: 'ask.day.temperature.ordinary',
  snowNone: 'ask.day.snow.noSnow',
  snowCover: 'ask.day.snow.cover',
} as const

/** What a day came to, for the measure that was asked about */
type DayResult
  = | { measure: 'wind', answer: WindAnswer }
    | { measure: 'sun', answer: SunAnswer }
    | { measure: 'rain', answer: RainDayAnswer }
    | { measure: 'temperature', answer: TemperatureAnswer }
    | { measure: 'snow', answer: SnowAnswer }

/** The measure a link names, the wind where it names none: the question the chip always asked */
function measureOf(choices: Choices): Measure {
  return isMeasure(choices.measure) ? choices.measure : 'wind'
}

/** The first letter as a capital, for a word at the start of a sentence (a language that writes the noun with a capital has it already) */
function upperFirst(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** The day, in the link as `&day=2025-12-26`: the same date last year where the link names none (GH-3764), and no day after yesterday */
const DAY: DateChoice = {
  kind: 'date',
  param: 'day',
  inputId: 'answer-day',
  label: 'ask.day.dayLabel',
  initial: sameDayLastYear,
  latest: (now: DateTime) => now.minus({ days: 1 }).toISODate()!,
}

/** What it fetches: the daily readings of the place's station that every measure is read from, a week either side of the day (`dayWindow`), in one request */
const FETCH = {
  provider: 'dwd',
  network: 'observation',
  resolution: 'daily',
  dataset: 'climate_summary',
  parameters: [WIND_GUST, WIND_MEAN, DAY_PARAMETERS.sun, DAY_PARAMETERS.rain, DAY_PARAMETERS.tmax, DAY_PARAMETERS.tmin, DAY_PARAMETERS.snow],
  /** The fresh snow is not in the climate summary: it is read from the daily precipitation dataset, where the station has it */
  fresh: { dataset: 'precipitation_more', parameter: DAY_PARAMETERS.newSnow },
} as const

/** The parameters (of the climate summary) each measure is read from, and the dataset-qualified fresh snow */
const PARAMETERS_OF: Record<Measure, readonly string[]> = {
  wind: [WIND_GUST, WIND_MEAN],
  sun: [DAY_PARAMETERS.sun],
  rain: [DAY_PARAMETERS.rain],
  temperature: [DAY_PARAMETERS.tmax, DAY_PARAMETERS.tmin],
  snow: [DAY_PARAMETERS.snow],
}

/** The same data in the Explorer: the parameters of the measure at the place's station, the days the answer fetches */
function explorerLink(station: string, day: string, measure: Measure, now: DateTime) {
  const { from, to } = dayWindow(day, now)
  return { path: '/explorer', query: { mode: 'station', provider: FETCH.provider, network: FETCH.network, resolution: FETCH.resolution, dataset: FETCH.dataset, parameters: PARAMETERS_OF[measure].join(','), stations: station, startDate: from, endDate: to } }
}

interface Loaded {
  readings: Value[]
  units: Record<string, string>
}

/**
 * The measure (`&measure=sun`): the wind where the link names none (the question it always was), or, where the station has no wind
 * reading for the day, the first measure that it has one of. A measure the station has no reading of for the day is greyed out, with that
 * said in its option; a link may still name it, and the answer then says why there is none.
 */
const MEASURE: SelectChoice = {
  kind: 'select',
  param: 'measure',
  inputId: 'answer-measure',
  label: 'ask.day.measureLabel',
  initial: () => 'wind',
  values: () => MEASURES,
  options({ t, dayText }, loaded, choices) {
    const have = loaded ? measuresWithData((loaded as Loaded).readings, choices.day!) : []
    return MEASURES.map((kind) => {
      const label = upperFirst(t(`ask.day.measure.${kind}`))
      // with no measure answerable the day itself is missing: nothing is singled out
      return have.length === 0 || have.includes(kind)
        ? { value: kind, label }
        : { value: kind, label: t('ask.day.measureShort', { measureCap: label, day: dayText(choices.day!, true) }), disabled: true }
    })
  },
}

/** The rules, limits, terms and parameters of each measure, for the disclosure under its answer (the page of the methods shows every one) */
const SCOPE: Record<Measure, { rules: readonly string[], limits: readonly string[], topics: readonly TopicId[] }> = {
  wind: { rules: ['beaufort', 'gust-first', 'gust-words', 'mean-words', 'stronger-count'], limits: ['gust', 'height'], topics: ['wind'] },
  sun: { rules: ['sun-share', 'day-length', 'sun-bands'], limits: ['horizon', 'recorder'], topics: ['sunshine'] },
  rain: { rules: ['rain-trace', 'rain-wet-day', 'rain-very-wet'], limits: ['gauge'], topics: ['precipitation'] },
  temperature: { rules: ['heat-days', 'cold-days', 'tropical-night', 'tropical-daily-minimum', 'class-order'], limits: ['night'], topics: ['temperature'] },
  snow: { rules: ['snow-lies', 'fresh-snow'], limits: ['snow-reading'], topics: ['snow'] },
}
const SHARED = { rules: ['daily-values', 'default-day', 'around-window', 'default-measure', 'measure-reading'], limits: ['station', 'missing', 'window', 'time'], topics: ['time'] as readonly TopicId[] }

/** A number written whole where it is whole (1 mm), with a decimal where it is not (0.1 mm) */
const plain = (number: ChipEnv['number'], value: number) => number(value, Number.isInteger(value) ? 0 : 1)

export const day = defineChip({
  id: 'day',
  // the name the chip had when it asked about the wind only: its links keep working, and mean the wind
  aliases: ['wind'],
  icon: 'i-ph-calendar-dots',
  tool: 'explorer',
  quantity: ['speed', 'precipitation', 'temperature', 'length_short'],
  choices: [MEASURE, DAY],
  // `?ask=wind&day=...` asked how windy the day was, and still does
  aliasChoices: { wind: { measure: 'wind' } },
  // the same request answers every measure: a change of the measure is no new request, and the answer is worked out again
  loadedBy: ['day'],
  resolveChoices(loaded: Loaded | null, choices: Choices, explicit: Choices, { t, dayText }: ChipEnv) {
    if (!loaded)
      return { choices, note: '' }
    const have = measuresWithData(loaded.readings, choices.day!)
    const asked = isMeasure(explicit.measure) ? explicit.measure : null
    // the measure the link or the reader names, unless the station has no reading of it for the day: then the wind, or the first it has; where it has none at all, the one named stays, and the answer says there is none
    const measure = asked && (have.length === 0 || have.includes(asked)) ? asked : have.includes('wind') || have.length === 0 ? 'wind' : have[0]!
    const notes: string[] = []
    const dayName = dayText(choices.day!, true)
    if (asked && asked !== measure)
      notes.push(t('ask.day.noteAskedMeasure', { measureCap: upperFirst(t(`ask.day.measure.${asked}`)), day: dayName, shown: t(`ask.day.measure.${measure}`) }))
    if (have.length > 0 && have.length < MEASURES.length)
      notes.push(t('ask.day.noteGreyed', { day: dayName }))
    return { choices: { ...choices, measure }, note: notes.join(' ') }
  },
  question: (env, choices) => env.t(`ask.q.day.${measureOf(choices)}`, { day: env.dayText(choices.day!) }),
  from: 'ask.from.day',
  scale: SCALE,
  credit: { provider: 'dwd', fallback: 'Deutscher Wetterdienst' },
  i18n: [
    ...MEASURES.map(measure => `ask.q.day.${measure}`),
    'ask.from.day',
    ...Object.values(SCALE),
    'ask.wind.mean',
    'ask.wind.gust',
    'ask.wind.context',
    'ask.wind.chartGust',
    'ask.wind.chartMean',
    'ask.wind.none',
    'ask.day.sun.detail',
    'ask.day.sun.chart',
    'ask.day.sun.none',
    'ask.day.rain.detail',
    'ask.day.rain.chart',
    'ask.day.rain.none',
    'ask.day.temperature.range',
    'ask.day.temperature.classes',
    'ask.day.temperature.chartMax',
    'ask.day.temperature.chartMin',
    'ask.day.temperature.none',
    'ask.day.snow.depth',
    'ask.day.snow.fresh',
    'ask.day.snow.chart',
    'ask.day.snow.none',
    'ask.day.open',
    DAY.label,
    MEASURE.label,
    'ask.day.measureShort',
    'ask.day.noteGreyed',
    'ask.day.noteAskedMeasure',
    ...MEASURES.map(measure => `ask.day.measure.${measure}`),
    ...(['hot', 'summer', 'tropical', 'ice', 'frost'] as const).map(kind => `ask.day.class.${kind}`),
  ],

  load({ place, choices, now, unitTarget }, api): Promise<Loaded> {
    const { from, to } = dayWindow(choices.day!, now())
    return api.values({
      provider: FETCH.provider,
      network: FETCH.network,
      parameters: [
        ...FETCH.parameters.map(parameter => `${FETCH.resolution}/${FETCH.dataset}/${parameter}`),
        `${FETCH.resolution}/${FETCH.fresh.dataset}/${FETCH.fresh.parameter}`,
      ].join(','),
      stations: place.id,
      timestamp: `${from}/${to}`,
      // the sunshine is asked in hours, whatever unit the settings give a duration: the share of the day is judged in them
      unit_targets: JSON.stringify({ speed: unitTarget('speed'), precipitation: unitTarget('precipitation'), temperature: unitTarget('temperature'), length_short: unitTarget('length_short'), duration: 'hour' }),
    })
  },

  answer({ readings, units }, { choices, place }): DayResult | null {
    const chosen = choices.day!
    switch (measureOf(choices)) {
      case 'wind': {
        const answer = windOnDay(readings, chosen, units[WIND_GUST] ?? units[WIND_MEAN])
        return answer && { measure: 'wind', answer }
      }
      case 'sun': {
        const answer = sunOnDay(readings, chosen, place.latitude, units[DAY_PARAMETERS.sun])
        return answer && { measure: 'sun', answer }
      }
      case 'rain': {
        const answer = rainOnDay(readings, chosen, units[DAY_PARAMETERS.rain])
        return answer && { measure: 'rain', answer }
      }
      case 'temperature': {
        const answer = temperatureOnDay(readings, chosen, units[DAY_PARAMETERS.tmax] ?? units[DAY_PARAMETERS.tmin])
        return answer && { measure: 'temperature', answer }
      }
      case 'snow': {
        const answer = snowOnDay(readings, chosen, units[DAY_PARAMETERS.snow])
        return answer && { measure: 'snow', answer }
      }
    }
  },

  present(result, _loaded, { t, number, percent, unitText, dayText }): AnswerView {
    /** The chart of the days around the one asked about: a bar each, the day marked */
    const chart = (bars: { key: string, label: string, value: number | null, highlight?: boolean }[], caption: string, unit: string, diverging = false) => ({
      bars: bars.map(bar => ({ ...bar, label: DateTime.fromISO(bar.key).toFormat('d') })),
      caption,
      unit,
      diverging,
      every: 7,
      emphasis: 'one' as const,
      rowLabel: (bar: { key: string }) => dayText(bar.key, true),
    })
    const view = { list: null, note: '' }
    switch (result.measure) {
      case 'wind': {
        const answer = result.answer
        const details: string[] = []
        if (answer.mean !== null)
          details.push(t('ask.wind.mean', { speed: number(answer.mean), unit: unitText(answer.unit), force: answer.beaufort ?? 0 }))
        if (answer.gust !== null)
          details.push(t('ask.wind.gust', { speed: number(answer.gust), unit: unitText(answer.unit), force: answer.gustBeaufort ?? 0 }))
        if (answer.around)
          details.push(t('ask.wind.context', { stronger: answer.stronger, around: answer.around }))
        return { ...view, verdict: t(SCALE[answer.verdict]), details, chart: chart(answer.bars, t(answer.barsAreGusts ? 'ask.wind.chartGust' : 'ask.wind.chartMean', { unit: unitText(answer.unit) }), unitText(answer.unit)) }
      }
      case 'sun': {
        const answer = result.answer
        return { ...view, verdict: t(SCALE[answer.verdict]), details: [t('ask.day.sun.detail', { hours: number(answer.hours), share: percent(answer.share), possible: number(answer.possible) })], chart: chart(answer.bars, t('ask.day.sun.chart', { unit: 'h' }), 'h') }
      }
      case 'rain': {
        const answer = result.answer
        const unit = unitText(answer.unit)
        return { ...view, verdict: t(SCALE[answer.verdict]), details: [t('ask.day.rain.detail', { amount: number(answer.amount), unit })], chart: chart(answer.bars, t('ask.day.rain.chart', { unit }), unit) }
      }
      case 'temperature': {
        const answer = result.answer
        const unit = unitText(answer.unit)
        const details = [t('ask.day.temperature.range', { max: number(answer.max), min: number(answer.min), unit })]
        if (answer.classes.length)
          details.push(t('ask.day.temperature.classes', { classes: answer.classes.map(kind => t(`ask.day.class.${kind}`)).join(', ') }))
        return { ...view, verdict: t(SCALE[answer.verdict]), details, chart: chart(answer.bars, t(answer.barsAre === 'min' ? 'ask.day.temperature.chartMin' : 'ask.day.temperature.chartMax', { unit }), unit, true) }
      }
      case 'snow': {
        const answer = result.answer
        const unit = unitText(answer.unit)
        const details = [t('ask.day.snow.depth', { depth: number(answer.depth), unit })]
        if (answer.fresh !== null && answer.fresh > 0)
          details.push(t('ask.day.snow.fresh', { fresh: number(answer.fresh), unit }))
        return { ...view, verdict: t(answer.verdict === 'cover' ? SCALE.snowCover : SCALE.snowNone), details, chart: chart(answer.bars, t('ask.day.snow.chart', { unit }), unit) }
      }
    }
  },

  explanation: {
    topics: ['wind', 'sunshine', 'precipitation', 'temperature', 'snow', 'time'],
    steps: ['station', 'wind', 'sun', 'rain', 'temperature', 'snow', 'around'],
    formulas: ['force', 'daylength', 'share'],
    rules: [
      // what is read, and which day
      { id: 'daily-values', kind: 'selection', cites: [{ work: 'dwd-daily-kl', at: 'FX, FM, SDK, RSK, TXK, TNK, SHK_TAG' }, { work: 'dwd-daily-more-precip', at: 'NSH_TAG' }] },
      { id: 'default-day', kind: 'selection', cites: [], own: true },
      { id: 'default-measure', kind: 'selection', cites: [], own: true },
      { id: 'measure-reading', kind: 'selection', cites: [], own: true },
      // wind: how a speed becomes a force
      { id: 'beaufort', kind: 'band', values: { edges: BEAUFORT }, cites: [{ work: 'wmo-8-i', at: '§5.1.4, Table 5.1' }] },
      // wind: how a force becomes a word
      { id: 'gust-first', kind: 'statistic', own: true, cites: [{ work: 'wmo-8-i', at: '§5.1.2, §5.1.3, §5.1.4' }] },
      { id: 'gust-words', kind: 'band', values: { gustBreezy: WIND_FORCES_OF_GUST.breezy, gustWindy: WIND_FORCES_OF_GUST.windy, gustStormy: WIND_FORCES_OF_GUST.stormy }, own: true, cites: [{ work: 'wmo-8-i', at: 'Table 5.1' }, { work: 'dwd-warnings' }] },
      { id: 'mean-words', kind: 'band', values: { meanBreezy: WIND_FORCES_OF_MEAN.breezy, meanWindy: WIND_FORCES_OF_MEAN.windy, meanStormy: WIND_FORCES_OF_MEAN.stormy }, own: true, cites: [{ work: 'wmo-8-i', at: 'Table 5.1' }] },
      // sun: the share of the possible sunshine, and the words of it
      { id: 'sun-share', kind: 'statistic', cites: [{ work: 'wmo-8-i', at: '§8.1.1, §8.1.2' }] },
      { id: 'day-length', kind: 'statistic', cites: [{ work: 'wmo-8-i', at: 'Annex 7.F, Annex 7.G' }] },
      { id: 'sun-bands', kind: 'band', values: { dullBelow: SUN_SHARE_DULL_BELOW * 100, sunnyFrom: SUN_SHARE_SUNNY_FROM * 100 }, own: true, cites: [{ work: 'wmo-8-i', at: '§8.1.3' }] },
      // rain: the bands of a day's precipitation
      { id: 'rain-trace', kind: 'band', values: { dryMm: RAIN_DRY_BELOW_MM }, cites: [{ work: 'wmo-8-i', at: '§6.1.2' }] },
      { id: 'rain-wet-day', kind: 'band', values: { wetMm: RAIN_WET_FROM_MM }, cites: [{ work: 'wmo-1203', at: 'Table 1' }] },
      { id: 'rain-very-wet', kind: 'band', values: { veryWetMm: RAIN_VERY_WET_FROM_MM }, own: true, cites: [{ work: 'wmo-1203', at: 'Table 1' }] },
      // heat and cold: the days DWD names by their temperature
      { id: 'heat-days', kind: 'band', values: { summerDay: SUMMER_DAY_MAX_FROM, hotDay: HOT_DAY_MAX_FROM }, cites: [{ work: 'dwd-kenntage' }, { work: 'wmo-1203', at: 'Table 1' }] },
      { id: 'cold-days', kind: 'band', values: { frostBelow: FROST_DAY_MIN_BELOW, iceBelow: ICE_DAY_MAX_BELOW }, cites: [{ work: 'dwd-kenntage' }, { work: 'wmo-1203', at: 'Table 1' }] },
      { id: 'tropical-night', kind: 'band', values: { tropicalFrom: TROPICAL_NIGHT_MIN_FROM }, cites: [{ work: 'dwd-tropennacht' }] },
      { id: 'tropical-daily-minimum', kind: 'statistic', own: true, cites: [{ work: 'dwd-tropennacht' }] },
      { id: 'class-order', kind: 'selection', own: true, cites: [{ work: 'dwd-kenntage' }] },
      // snow: where snow lies, and the fresh snow
      { id: 'snow-lies', kind: 'band', values: { snowAboveCm: SNOW_LIES_ABOVE_CM }, cites: [{ work: 'wmo-1203', at: 'Table 1' }] },
      { id: 'fresh-snow', kind: 'selection', cites: [{ work: 'dwd-daily-more-precip', at: 'SH_TAG, NSH_TAG' }] },
      // what the day is set beside
      { id: 'around-window', kind: 'window', values: { days: DAY_WINDOW_DAYS }, cites: [], own: true },
      { id: 'stronger-count', kind: 'statistic', cites: [], own: true },
    ],
    limits: ['station', 'missing', 'window', 'time', 'gust', 'height', 'horizon', 'recorder', 'gauge', 'night', 'snow-reading'],
    scope: (choices) => {
      const measure = measureOf(choices)
      const own = SCOPE[measure]
      return {
        rules: [...SHARED.rules, ...own.rules],
        limits: [...SHARED.limits, ...own.limits],
        topics: [...SHARED.topics, ...own.topics],
        parameters: measure === 'snow' ? [...PARAMETERS_OF.snow, `${FETCH.fresh.parameter} (${FETCH.resolution}/${FETCH.fresh.dataset})`] : PARAMETERS_OF[measure],
      }
    },
    data: {
      provider: FETCH.provider,
      network: FETCH.network,
      dataset: `${FETCH.resolution}/${FETCH.dataset}`,
      // every parameter of every measure, as the page of the methods lists them: an answer lists those of its measure (`scope`)
      parameters: [...FETCH.parameters, `${FETCH.fresh.parameter} (${FETCH.resolution}/${FETCH.fresh.dataset})`],
      open: ({ place, now }, choices) => explorerLink(place.id, choices.day!, measureOf(choices), now()),
    },
    numbers(result, _loaded, { number, percent, unitText, place, dayText }, _choices): NumberLine[] {
      const station: NumberLine[] = [{ id: 'station', params: { name: place.name, id: place.id } }, { id: 'day', params: { day: dayText(result.answer.day, true) } }]
      const around = (answer: { bars: { value: number | null }[] }): NumberLine => ({ id: 'window', params: { days: DAY_WINDOW_DAYS, given: answer.bars.filter(bar => bar.value !== null).length } })
      switch (result.measure) {
        case 'wind': {
          const answer = result.answer
          const unit = unitText(answer.unit)
          const lines: NumberLine[] = [...station]
          if (answer.mean !== null)
            lines.push({ id: 'mean', params: { speed: number(answer.mean), unit, force: answer.beaufort ?? 0 } })
          if (answer.gust !== null)
            lines.push({ id: 'gust', params: { speed: number(answer.gust), unit, force: answer.gustBeaufort ?? 0 } })
          const forces = answer.gust !== null ? WIND_FORCES_OF_GUST : WIND_FORCES_OF_MEAN
          lines.push({ id: answer.gust !== null ? 'scaleGust' : 'scaleMean', params: { breezy: forces.breezy, windy: forces.windy, stormy: forces.stormy } })
          lines.push({ id: 'around', params: { around: answer.around, stronger: answer.stronger, days: DAY_WINDOW_DAYS } })
          return lines
        }
        case 'sun': {
          const answer = result.answer
          return [
            ...station,
            { id: 'sunHours', params: { hours: number(answer.hours), possible: number(answer.possible), latitude: number(place.latitude, 2), share: percent(answer.share) } },
            { id: 'sunScale', params: { dull: percent(SUN_SHARE_DULL_BELOW), sunny: percent(SUN_SHARE_SUNNY_FROM) } },
            around(answer),
          ]
        }
        case 'rain': {
          const answer = result.answer
          const unit = unitText(answer.unit)
          // a band is a millimetre figure: written in the unit of the answer
          const edge = (millimeters: number) => plain(number, fromCanonical('precipitation', answer.unit, millimeters))
          return [
            ...station,
            { id: 'rainAmount', params: { amount: number(answer.amount), unit } },
            { id: 'rainScale', params: { dry: edge(RAIN_DRY_BELOW_MM), wet: edge(RAIN_WET_FROM_MM), veryWet: edge(RAIN_VERY_WET_FROM_MM), unit } },
            around(answer),
          ]
        }
        case 'temperature': {
          const answer = result.answer
          const unit = unitText(answer.unit)
          const degrees = (celsius: number) => number(fromCanonical('temperature', answer.unit, celsius), 0)
          return [
            ...station,
            { id: 'tempRange', params: { max: number(answer.max), min: number(answer.min), unit } },
            ...answer.classes.map(kind => ({ id: 'tempClass', params: { kind } })),
            { id: 'tempScale', params: { summer: degrees(SUMMER_DAY_MAX_FROM), hot: degrees(HOT_DAY_MAX_FROM), ice: degrees(ICE_DAY_MAX_BELOW), frost: degrees(FROST_DAY_MIN_BELOW), tropical: degrees(TROPICAL_NIGHT_MIN_FROM), unit } },
            around(answer),
          ]
        }
        case 'snow': {
          const answer = result.answer
          const unit = unitText(answer.unit)
          return [
            ...station,
            { id: 'snowDepth', params: { depth: number(answer.depth), unit } },
            answer.fresh === null ? { id: 'snowNoFresh', params: {} } : { id: 'snowFresh', params: { fresh: number(answer.fresh), unit } },
            { id: 'snowScale', params: { above: number(fromCanonical('length_short', answer.unit, SNOW_LIES_ABOVE_CM), 0), unit } },
            around(answer),
          ]
        }
      }
    },
  },

  empty: (_loaded, { t, dayText }, choices) => t(measureOf(choices) === 'wind' ? 'ask.wind.none' : `ask.day.${measureOf(choices)}.none`, { day: dayText(choices.day!, true) }),

  actions: ({ t, place, now }, choices): AnswerAction[] => [{ key: 'explorer', label: t('ask.day.open'), tool: 'explorer', to: explorerLink(place.id, choices.day!, measureOf(choices), now()) }],
})
