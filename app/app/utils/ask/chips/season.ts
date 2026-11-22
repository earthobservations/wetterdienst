import type { Value } from '#shared/types/api'
import type { Season, SeasonAnswer } from '../../answers'
import type { AnswerAction, ChipEnv, Choices, NumberLine, SelectChoice } from '../chip'
import {
  defaultNormalFor,
  defaultSeason,
  defaultSeasonFor,
  FALLBACK_MIN_SEASONS,
  isAnswerable,
  isSeason,
  lastSeason,
  newestNormal,
  NORMAL_FIRST_TO,
  NORMAL_MIN_SEASONS,
  NORMAL_YEARS,
  normalAvailability,
  normalOf,
  normalsAt,
  normalSpan,
  seasonMeans,
  SEASONS,
  USUAL_BAND,
} from '../../answers'
import { differenceIn } from '../../units'
import { defineChip } from '../chip'

// Was last summer, winter ... warmer than usual? DWD's monthly means of the place's station (GH-3518), for any season and
// against any complete WMO normal from 1961-1990 onward (GH-3764, step 2a).

/** The verdicts. The question asks "warmer" (spring, summer, autumn) or, for the winter, "colder": the sentence follows what was asked */
const SCALE = {
  warmer: 'ask.season.warmer',
  cooler: 'ask.season.cooler',
  usual: 'ask.season.usual',
  coldYes: 'ask.season.coldYes',
  coldNo: 'ask.season.coldNo',
  coldUsual: 'ask.season.coldUsual',
} as const

/** What it fetches: the monthly mean air temperature of the place's station, the whole record: every season and every normal is judged from it */
const FETCH = { provider: 'dwd', network: 'observation', parameters: 'monthly/climate_summary/temperature_air_mean_2m' } as const

/** The same data in the Explorer: the monthly mean temperature of the place's station */
function explorerLink(station: string) {
  return { path: '/explorer', query: { mode: 'station', provider: FETCH.provider, network: FETCH.network, resolution: 'monthly', dataset: 'climate_summary', parameters: 'temperature_air_mean_2m', stations: station } }
}

interface Loaded {
  readings: Value[]
  units: Record<string, string>
}

/** The first letter as a capital, for a word at the start of a sentence (a language that writes the noun with a capital has it already) */
function upperFirst(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** The season a link names, summer where it names none: the question the chip always asked */
function seasonOf(choices: Choices): Season {
  return isSeason(choices.season) ? choices.season : 'summer'
}

/** Whether the question asks for the cold: the winter's (colder than usual); the other seasons are asked for the warm */
const asksCold = (season: Season) => season === 'winter'

/**
 * The season (`&season=winter`): the one completed most recently where the link names none (and, once the data is there, the most
 * recent that has enough of it). A season the station has no normal to compare it with, nor seasons enough to stand in for one, is
 * greyed out, with how many complete seasons of it there are.
 */
const SEASON: SelectChoice = {
  kind: 'select',
  param: 'season',
  inputId: 'answer-season',
  label: 'ask.season.seasonLabel',
  initial: now => defaultSeason(now),
  values: () => SEASONS,
  options({ t, now }, loaded) {
    return SEASONS.map((kind) => {
      const label = upperFirst(t(`ask.season.name.${kind}`))
      if (!loaded)
        return { value: kind, label }
      const readings = (loaded as Loaded).readings
      return isAnswerable(normalAvailability(readings, kind, now()))
        ? { value: kind, label }
        : { value: kind, label: t('ask.season.seasonShort', { seasonCap: label, count: seasonMeans(readings, kind, now()).length }), disabled: true }
    })
  },
}

/** The text of a normal as it is read: `1961–1990` */
const normalText = (from: number, to: number) => `${from}–${to}`

/** The years of a normal's seasons as a kind of season writes them: `1960/61–1989/90` for a winter */
function spanText(kind: Season, from: number, to: number): string {
  const span = normalSpan(kind, from, to)
  return `${span.from}–${span.to}`
}

/**
 * The normal the season is compared with (`&ref=1961-1990`): every complete WMO normal from 1961-1990 onward, the newest
 * where the link names none. A normal that the station has too few seasons of is offered disabled with the count in its
 * option, but the newest, where the seasons before stand in for it (an own rule, `fallback-period`): that one says so
 * in its option and can be chosen.
 */
const REFERENCE: SelectChoice = {
  kind: 'select',
  param: 'ref',
  inputId: 'answer-ref',
  label: 'ask.season.refLabel',
  initial: now => newestNormal(now).key,
  values: now => normalsAt(now).map(normal => normal.key),
  options({ t, now }, loaded, choices) {
    const kind = seasonOf(choices)
    const seasons = t(`ask.season.plural.${kind}`)
    const availability = loaded ? normalAvailability((loaded as Loaded).readings, kind, now()) : []
    return normalsAt(now()).map((normal) => {
      const text = normalText(normal.from, normal.to)
      const have = availability.find(each => each.normal.key === normal.key)
      if (!have || have.enough)
        return { value: normal.key, label: text }
      // a winter normal says its winters too (1961–1990 is 1960/61 to 1989/90), as the bars are labelled
      const named = normalSaid(kind, normal.from, normal.to)
      const params = { normal: named, count: have.count, of: NORMAL_YEARS, min: NORMAL_MIN_SEASONS, seasons }
      // the newest normal can be chosen where the seasons before stand in for it; where too few of those exist, it is short like the older ones
      return have.fallback
        ? { value: normal.key, label: t('ask.season.refFallback', params) }
        : { value: normal.key, label: t('ask.season.refShort', params), disabled: true }
    })
  },
}

/** A normal as it is said in a sentence: `1961–1990`, and for a winter the winters too (`1961–1990 = 1960/61–1989/90`) */
function normalSaid(kind: Season, from: number, to: number): string {
  const text = normalText(from, to)
  return kind === 'winter' ? `${text} = ${spanText(kind, from, to)}` : text
}

export const season = defineChip({
  id: 'season',
  // the name the chip had when it asked about the summer only: its links keep working
  aliases: ['summer'],
  // the rules the old section had under other names: `/methods#summer-summer-mean` is now `#season-season-mean`
  renamedRules: { 'summer-mean': 'season-mean', 'reference-period': 'reference-choices', 'min-summers': 'min-seasons' },
  icon: 'i-ph-thermometer-hot',
  tool: 'explorer',
  quantity: 'temperature',
  choices: [SEASON, REFERENCE],
  // `?ask=summer` asked about the summer, and still does
  aliasChoices: { summer: { season: 'summer' } },
  // the whole record is fetched whatever the season and the normal: a change of either is no new request
  loadedBy: [],
  resolveChoices(loaded: Loaded | null, choices: Choices, explicit: Choices, { t, now }: ChipEnv) {
    if (!loaded)
      return { choices, note: '' }
    const readings = loaded.readings
    const notes: string[] = []
    // the season the link or the reader names, unless it has too little data here: then the one the question opens on
    const askedKind = isSeason(explicit.season) ? explicit.season : null
    // where no season can be compared at all, the one named stays: the answer says there is too little data, and nothing better is to be shown
    const anyAnswerable = SEASONS.some(each => isAnswerable(normalAvailability(readings, each, now())))
    const kind = askedKind && (!anyAnswerable || isAnswerable(normalAvailability(readings, askedKind, now()))) ? askedKind : defaultSeasonFor(readings, now())
    if (askedKind && askedKind !== kind)
      notes.push(t('ask.season.noteAskedSeason', { seasonCap: upperFirst(t(`ask.season.name.${askedKind}`)), shown: t(`ask.season.name.${kind}`) }))
    const availability = normalAvailability(readings, kind, now())
    const askedNormal = normalOf(explicit.ref, now())
    const asked = askedNormal ? availability.find(each => each.normal.key === askedNormal.key) : undefined
    const normal = asked && (asked.enough || asked.fallback) ? asked.normal : defaultNormalFor(readings, kind, now())
    if (askedNormal && asked && normal.key !== askedNormal.key)
      notes.push(t('ask.season.noteAskedNormal', { asked: normalSaid(kind, askedNormal.from, askedNormal.to), count: asked.count, of: NORMAL_YEARS, min: NORMAL_MIN_SEASONS, shown: normalSaid(kind, normal.from, normal.to) }))
    // something is greyed out in the choices: the line under them says why
    if (SEASONS.some(each => !isAnswerable(normalAvailability(readings, each, now()))) || availability.some(each => !each.enough && !each.fallback))
      notes.push(t('ask.season.noteGreyed', { min: NORMAL_MIN_SEASONS, of: NORMAL_YEARS }))
    return { choices: { season: kind, ref: normal.key }, note: notes.join(' ') }
  },
  question(env, choices) {
    const kind = seasonOf(choices)
    return env.t('ask.q.season', { last: env.t(`ask.season.last.${kind}`), warmth: env.t(`ask.season.warmth.${kind}`) })
  },
  from: 'ask.from.season',
  scale: SCALE,
  credit: { provider: 'dwd', fallback: 'Deutscher Wetterdienst' },
  i18n: [
    'ask.q.season',
    'ask.from.season',
    ...Object.values(SCALE),
    'ask.season.detail',
    'ask.season.rank',
    'ask.season.chart',
    'ask.season.none',
    'ask.season.noneNormal',
    'ask.season.open',
    'ask.season.stripes',
    SEASON.label,
    REFERENCE.label,
    'ask.season.refShort',
    'ask.season.refFallback',
    'ask.season.seasonShort',
    'ask.season.noteGreyed',
    'ask.season.noteAskedSeason',
    'ask.season.noteAskedNormal',
    ...SEASONS.flatMap(kind => [
      `ask.season.last.${kind}`,
      `ask.season.warmth.${kind}`,
      `ask.season.name.${kind}`,
      `ask.season.plural.${kind}`,
      `ask.season.months.${kind}`,
    ]),
  ],

  load: ({ place, unitTarget }, api): Promise<Loaded> => api.values({
    ...FETCH,
    stations: place.id,
    unit_targets: JSON.stringify({ temperature: unitTarget('temperature') }),
  }),

  answer: ({ readings, units }, { now, choices }): SeasonAnswer | null => lastSeason(
    readings,
    now(),
    { season: seasonOf(choices), normal: choices.ref ?? '' },
    units.temperature_air_mean_2m,
  ),

  present(answer, _loaded, { t, number, unitText }) {
    const kind = answer.season
    const cold = asksCold(kind)
    const key = answer.verdict === 'usual'
      ? (cold ? SCALE.coldUsual : SCALE.usual)
      : answer.verdict === 'warmer' ? (cold ? SCALE.coldNo : SCALE.warmer) : (cold ? SCALE.coldYes : SCALE.cooler)
    const name = t(`ask.season.name.${kind}`)
    const plural = t(`ask.season.plural.${kind}`)
    // a winter normal is written by the years of its winters (1960/61 to 1989/90 for 1961-1990), as the bars are labelled
    const span = normalSpan(kind, answer.normalFrom, answer.normalTo)
    return {
      verdict: t(key, { anomaly: number(Math.abs(answer.anomaly)), unit: unitText(answer.unit) }),
      details: [
        t('ask.season.detail', {
          seasonCap: upperFirst(name),
          year: answer.bars.find(bar => bar.highlight)?.label ?? answer.year,
          months: t(`ask.season.months.${kind}`),
          mean: number(answer.mean),
          unit: unitText(answer.unit),
          seasons: plural,
          from: span.from,
          to: span.to,
          normal: number(answer.normal),
        }),
        t('ask.season.rank', { rank: answer.rank, count: answer.seasons, seasons: plural, first: answer.bars[0]?.label ?? '' }),
      ],
      chart: {
        bars: answer.bars,
        caption: t('ask.season.chart', { season: name, from: span.from, to: span.to, unit: unitText(answer.unit) }),
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
    steps: ['seasons', 'reference', 'compare', 'verdict'],
    formulas: ['season', 'anomaly'],
    rules: [
      // which months make a season, and which seasons count
      { id: 'season', kind: 'period', cites: [{ work: 'dwd-seasons' }, { work: 'dwd-summer' }] },
      { id: 'winter-year', kind: 'period', own: true, cites: [{ work: 'wmo-1203', at: '§4.3.3' }] },
      { id: 'complete-months', kind: 'selection', cites: [{ work: 'wmo-1203', at: '§4.3.3' }, { work: 'dwd-monthly-kl', at: 'Data origin' }] },
      { id: 'only-over', kind: 'selection', cites: [], own: true },
      { id: 'season-mean', kind: 'statistic', cites: [{ work: 'wmo-1203', at: '§4.3.3 (a), note 1' }] },
      { id: 'default-season', kind: 'selection', cites: [], own: true },
      // what it is compared with, and which normals are offered
      { id: 'reference-choices', kind: 'period', values: { firstFrom: NORMAL_FIRST_TO - NORMAL_YEARS + 1, firstTo: NORMAL_FIRST_TO, years: NORMAL_YEARS }, cites: [{ work: 'wmo-1203', at: '§2, §3' }] },
      { id: 'reference-default', kind: 'period', cites: [{ work: 'wmo-1203', at: '§2, §3, §5.1' }] },
      { id: 'default-normal', kind: 'selection', cites: [], own: true },
      { id: 'normal-mean', kind: 'statistic', own: true, cites: [{ work: 'wmo-1203', at: '§4.3.3 (a)' }] },
      { id: 'min-seasons', kind: 'fallback', values: { minSeasons: NORMAL_MIN_SEASONS, ofSeasons: NORMAL_YEARS }, own: true, cites: [{ work: 'wmo-1203', at: '§4.4.2' }] },
      // where the station has too few of the newest normal
      { id: 'fallback-period', kind: 'fallback', own: true, cites: [{ work: 'wmo-1203', at: '§3' }] },
      { id: 'fallback-minimum', kind: 'fallback', values: { fallbackMin: FALLBACK_MIN_SEASONS }, own: true, cites: [{ work: 'wmo-1203', at: '§5.2.3' }] },
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
      const unit = unitText(answer.unit)
      // the season, its months and its plural are named by the id of the season: the page writes them in the language of its texts
      const kind = { season: answer.season, months: answer.season, seasons: answer.season }
      // the years of the normal as the seasons are written: a winter's by both years
      const span = normalSpan(answer.season, answer.normalFrom, answer.normalTo)
      const asked = normalSpan(answer.season, answer.asked.from, answer.asked.to)
      const lines: NumberLine[] = [
        { id: 'station', params: { name: place.name, id: place.id } },
        { id: 'season', params: { ...kind, year: answer.bars.find(bar => bar.highlight)?.label ?? answer.year, mean: number(answer.mean), unit } },
        {
          id: answer.fallback ? 'referenceFallback' : 'reference',
          params: { seasons: answer.season, from: span.from, to: span.to, count: answer.referenceCount, normal: number(answer.normal), unit, askedFrom: asked.from, askedTo: asked.to },
        },
        { id: 'anomaly', params: { ...kind, anomaly: number(answer.anomaly), unit } },
        // half a degree is half a kelvin: in the unit the reader chose, the band is as many degrees of it
        { id: 'band', params: { band: number(differenceIn('temperature', answer.unit, USUAL_BAND)), unit } },
        { id: 'rank', params: { seasons: answer.season, rank: answer.rank, count: answer.seasons, first: answer.bars[0]?.label ?? '' } },
      ]
      return lines
    },
  },

  empty(loaded, { t, now }, choices) {
    const kind = seasonOf(choices)
    const seasons = t(`ask.season.plural.${kind}`)
    // a normal the station has too few seasons of, with nothing to stand in for it, says so with the count; a station with no complete season says that
    const asked = normalOf(choices.ref, now())
    const have = loaded && asked ? normalAvailability((loaded as Loaded).readings, kind, now()).find(each => each.normal.key === asked.key) : null
    if (have && !have.enough && !have.fallback && seasonMeans((loaded as Loaded).readings, kind, now()).length > 0) {
      return t('ask.season.noneNormal', { normal: normalSaid(kind, asked!.from, asked!.to), count: have.count, of: NORMAL_YEARS, min: NORMAL_MIN_SEASONS, seasons })
    }
    return t('ask.season.none', { seasons })
  },

  actions: ({ t, place }): AnswerAction[] => [
    { key: 'explorer', label: t('ask.season.open'), tool: 'explorer', to: explorerLink(place.id) },
    { key: 'stripes', label: t('ask.season.stripes'), tool: 'stripes', to: { path: '/stripes', query: { kind: 'temperature', station: place.id } } },
  ],
})
