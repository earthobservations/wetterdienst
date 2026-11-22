import type { Provider, ProviderNetworkCoverageResponse, Station, Value } from '#shared/types/api'
import type { Place } from '../../composables/usePlace'
import type { Bar } from '../answers'
import type { TopicId } from '../measurement'
import type { TOOLS } from '../sections'
import type { Quantity } from '../units'
import type { WorkId } from './works'
import { DateTime } from 'luxon'

// What a chip of "Ask the weather" is (GH-3518, GH-3764): ONE definition object. The home page (components/AskTheWeather.vue)
// and the answer under it (components/AnswerPanel.vue) read nothing but this: they hold no code of their own for any
// chip. A chip is a file in `chips/` that calls `defineChip`, plus its translations, plus a line in `registry.ts`;
// `README.md` next to this file says how.
//
// Nothing here knows Nuxt. What a definition needs of the page (the place, the language, the requests) it is handed, so
// that the functions of a definition can be tried by a unit test with plain values.

/** A tool of the app (`utils/sections.ts`): the one a chip's answer leads into */
export type ToolKey = typeof TOOLS[number]['key']

/** Translates a key of the catalogs (`ask.…`), with its parameters */
export type Say = (key: string, params?: Record<string, string | number>) => string

/** The place the chips are about: a DWD station */
export type ChipPlace = Pick<Place, 'id' | 'name' | 'latitude' | 'longitude'>

/** What the pure parts of a definition (the question, the words of an answer) may use of the page */
export interface ChipEnv {
  t: Say
  /** The place, as it is now */
  readonly place: ChipPlace
  /** A number in the language of the page, with `digits` decimals (1 where none are given) */
  number: (value: number, digits?: number) => string
  /** A share from 0 to 1 as a percentage */
  percent: (value: number) => string
  /** A unit as it is written (`degree_celsius` as `°C`) */
  unitText: (unit: string) => string
  /** A day as the language writes it ("26 December"), with the year where it is asked for */
  dayText: (day: string, withYear?: boolean) => string
  now: () => DateTime
}

/** The values of a chip's choices, by the name each has in the link */
export type Choices = Readonly<Record<string, string>>

/**
 * A choice the reader makes about the question, kept in the link (`&day=2025-12-26`): `param` is its name there. The
 * link is read with `initial` as the value where it names none, or names one that is no value. A day and one of a few
 * values exist (`kind`); a choice of another kind adds its kind here, and the control of it to the panel.
 */
export interface DateChoice {
  kind: 'date'
  /** The name in the link */
  param: string
  /** The id of the control, and so the target of its label */
  inputId: string
  /** The i18n key of the control's label */
  label: string
  /** The value where the link has none */
  initial: (now: DateTime) => string
  /** The last value the control takes (`YYYY-MM-DD`) */
  latest: (now: DateTime) => string
}

/** One value of a choice of a few: what the control writes for it, and the text of its option (which says why, where it cannot be chosen) */
export interface SelectOption {
  value: string
  /** The option as it is read: the reason it cannot be chosen is in it, since a native option has no other place for one */
  label: string
  /** Shown and not to be chosen: what the data of the place does not carry */
  disabled?: boolean
}

/**
 * A choice of a few values (`&season=winter`, `&ref=1961-1990`), drawn as a labelled select. The values that are valid are
 * the ones `values` names at the time (a list that grows by itself: the normals of a year), and a link that names another
 * gets `initial`. An option may be offered disabled, with its reason, for what the data of the place does not carry (`options`
 * is handed what the chip fetched, null before it came); a link may still name it, and the answer then says why it has none.
 */
export interface SelectChoice {
  kind: 'select'
  param: string
  inputId: string
  label: string
  initial: (now: DateTime) => string
  /** The values a link may name, at `now` */
  values: (now: DateTime) => readonly string[]
  /** The options of the control, from what was fetched (null before it came) and the choices as they are */
  options: (env: ChipEnv, loaded: unknown, choices: Choices) => SelectOption[]
}
export type Choice = DateChoice | SelectChoice

/** What the page gives `load` and `answer`, besides the requests */
export interface ChipContext {
  place: ChipPlace
  choices: Choices
  now: () => DateTime
  /** The language to sort and write in, as `Intl` takes it (`useFormatLanguage()`'s answer) */
  formatLanguage: string
  /** The unit the settings choose for a quantity, as the backend's `unit_targets` take it */
  unitTarget: (quantity: Quantity) => string
}

/** The requests a chip makes: the page's own, with its settings (units, shape) and its error handling */
export interface ChipApi {
  /** `/api/values` in the long shape: the readings, and the unit of each parameter */
  values: (query: Record<string, string>) => Promise<{ readings: Value[], units: Record<string, string> }>
  stations: (query: Record<string, string | number>) => Promise<Station[]>
  providers: () => Promise<Provider[]>
  coverage: (query: Record<string, string>) => Promise<ProviderNetworkCoverageResponse>
  /**
   * What a chip looks up once for the visit and keeps (the promise is kept, under `key`): a lookup that does not depend
   * on the place. One that fails is forgotten, so that the next question asks again.
   */
  kept: <T>(key: string, load: () => Promise<T>) => Promise<T>
}

/** The chart that backs an answer (components/AnswerBars.vue) */
export interface AnswerChart {
  bars: Bar[]
  caption: string
  unit: string
  diverging?: boolean
  every?: number
  emphasis: 'all' | 'one'
  rowLabel?: (bar: Bar) => string
}

/** One entry of a list of links an answer holds (the services of the download question) */
export interface AnswerListItem {
  key: string
  to: string | { path: string, query: Record<string, string> }
  /** A mark before the title, such as a flag; decoration */
  mark: string
  title: string
  detail: string
  /** Set in a medium weight after the detail */
  place?: string
}

/** What the panel writes of an answer */
export interface AnswerView {
  /** The first line, large: the verdict, or what the answer is */
  verdict: string
  /** The lines under it */
  details: string[]
  chart: AnswerChart | null
  list: { testId: string, items: AnswerListItem[] } | null
  /** A line in small print under the rest, for what the answer is about (the forecast point); empty for none */
  note: string
}

/** A link into a tool, which carries the tool's tile (`tool`); a reference page has none */
export interface AnswerAction {
  key: string
  label: string
  to: string | { path: string, query: Record<string, string> }
  tool?: ToolKey
}

// ------------------------------------------------------------------------------------------- the explanation

/** Where a choice of a method is taken from: a work of `works.ts`, and the place in it (`Table 5.1`, `§3`), as the work itself numbers it */
export interface Citation {
  work: WorkId
  at?: string
}

/** What a rule of a method is: a period, a band (a threshold or a scale), a statistic, a fallback where the data is short, a window of days, or a selection */
export type RuleKind = 'period' | 'band' | 'statistic' | 'fallback' | 'window' | 'selection'

/**
 * One choice that shapes an answer (GH-3764, step 1c): a period, a band, a statistic, a fallback rule. It cites a published
 * source (`cites`) or is marked as wetterdienst's own (`own`), with the reasoning in its text: a rule with neither is no rule
 * the page can show, and `tests/unit/ask-methods.test.ts` fails it. A rule that is its own may also cite works that are not
 * its source but bear on it (the comparison the reasoning makes). Its words are in `i18n/methods/` under `rules.<id>`.
 */
export interface Rule {
  /** The name in the texts and in the anchor of the rule on the page of the methods; plain lower case words */
  id: string
  kind: RuleKind
  /**
   * The numbers the rule's text says, as the code has them: `{from}` in the text is `values.from`, written in the language
   * of the page (a list of numbers is written with commas). The texts of the steps and the limits of the chip may use the values
   * of any of its rules, so a name is used by one rule of a chip only.
   */
  values?: Readonly<Record<string, string | number | readonly number[]>>
  cites: readonly Citation[]
  /** True for a choice that is wetterdienst's own: no published source says it */
  own?: boolean
}

/** One line of "the numbers used" of an answer: the id of its text in `i18n/methods/` (`numbers.<id>`), with its numbers and names filled in as the page writes them */
export interface NumberLine {
  id: string
  params: Record<string, string | number>
}

/** What a chip fetches, as the reader is told it, and where the same data is opened in the Explorer */
export interface ExplanationData<Loaded> {
  /** The provider, as a request names it, whose licence and credit are said; null where the answer is no provider's data */
  provider: string | null
  /** The network as a request names it; null where the answer is not from one network (the list of services) */
  network: string | null
  /** The dataset as a request names it (`monthly/climate_summary`); null for the list of services, which is wetterdienst's own */
  dataset: string | null
  /** The parameters of the dataset the answer uses, as the glossary names them */
  parameters: readonly string[]
  /** The link that opens the same data in the Explorer, or null where the answer is not one dataset (the list of services) */
  open: (env: ChipEnv, choices: Choices, loaded: Loaded | null) => AnswerAction['to'] | null
}

/**
 * How an answer was worked out and where it comes from (GH-3764, steps 1b and 1c): the structure, and the numbers in it;
 * the words are in `i18n/methods/` (German and English) under the id of the chip. It is what the disclosure under the answer
 * (`components/AnswerExplanation.vue`) and the page of the methods (`pages/methods.vue`) both write, so that a chip is on
 * the page with no edit of it.
 */
export interface ChipExplanation<Loaded, Result> {
  /** The entries of "How weather is measured" (`utils/measurement.ts`) whose terms the explanation uses and links to, so that a term is not explained twice */
  topics: readonly TopicId[]
  /** The method step by step: the ids of its steps in the texts (`steps.<id>`), in order */
  steps: readonly string[]
  /** The ids of the formulas of the method in the texts (`formulas.<id>`), none where there is no formula */
  formulas: readonly string[]
  /** Every period, band, statistic and fallback of the answer, with its source or its mark as wetterdienst's own */
  rules: readonly Rule[]
  /** The limits of the answer: the ids of their texts (`limits.<id>`) */
  limits: readonly string[]
  data: ExplanationData<Loaded>
  /** The numbers of this answer: the station, the period and how many years or days it covers, the thresholds */
  numbers: (result: Result, loaded: Loaded, env: ChipEnv, choices: Choices) => NumberLine[]
}

/**
 * One chip. `Loaded` is what its requests bring back, `Result` what the answer function makes of it (null where the data
 * does not carry an answer). A registry holds the definitions as `Chip` (see `defineChip`).
 */
export interface ChipDefinition<Id extends string, Loaded, Result> {
  /** The name in the link (`?ask=season`) and in the test id of the chip (`question-season`) */
  id: Id
  /** Other names a link may carry for the chip (`?ask=summer`, the name of the chip it grew out of): a link keeps meaning what it meant, and the chip is the same */
  aliases?: readonly string[]
  /** Rules the old section had under other names, by the old id (`summer-mean`) to the new one (`season-mean`): `/methods#summer-summer-mean` goes to `#season-season-mean`. A rule of the same id needs no entry */
  renamedRules?: Readonly<Record<string, string>>
  /** What an old name of the chip names of its choices, by the old name: `?ask=summer` asks about the summer, not about the season the chip opens on now. Counts as the link's own choice */
  aliasChoices?: Readonly<Record<string, Choices>>
  /** The icon of the chip's button, an Iconify name the app bundles */
  icon: string
  /** The tool the answer leads into */
  tool: ToolKey
  /** The quantity whose unit the settings choose for the answer, and a change of which asks it again */
  quantity?: Quantity
  /** The choices of the question, with their names in the link; the question's own, so another chip's link carries none of them */
  choices?: readonly Choice[]
  /**
   * The names in the link of the choices `load` reads, where it reads some of them only (the season and the normal are
   * judged from the same monthly means, so the panel asks again for neither): a change of any other choice is no new
   * request, and the answer is worked out again from what was fetched. Absent: every choice is read by `load`.
   */
  loadedBy?: readonly string[]
  /**
   * The choices as they are for the data that came, where the link does not say or names what the data cannot answer: the defaults that
   * depend on the place (the season completed most recently that has enough data), and the fall back off a choice with too little data.
   * `choices` are the link's with the data-less defaults, `explicit` only what the link names. The note says why a choice was not the one
   * named, and why an option is greyed out, in the language of the page; empty where there is nothing to say. Absent: the link's choices are used.
   */
  resolveChoices?: (loaded: Loaded | null, choices: Choices, explicit: Choices, env: ChipEnv) => { choices: Choices, note: string }
  /** The question, as the button and the heading of the answer say it; `choices` are the ones the link has */
  question: (env: ChipEnv, choices: Choices) => string
  /** The i18n key of the line above the question's heading: where the answer comes from */
  from: string
  /** The verdicts the answer says, each with the i18n key of its sentence: the scale of the answer. Empty where the answer is a sentence of its own */
  scale: Readonly<Record<string, string>>
  /** The first line is a word (large, the default) or a sentence (smaller) */
  verdictStyle?: 'word' | 'sentence'
  /** The provider whose credit line closes the answer, and the line where the provider list has none; null where the answer is no provider's data */
  credit: { provider: string, fallback: string } | null
  /** Every key of the catalogs the definition uses, which `tests/unit/ask-chips.test.ts` holds to all eleven locales */
  i18n: readonly string[]
  /** How the answer was worked out and what it rests on (GH-3764): the disclosure under the answer and the page of the methods */
  explanation: ChipExplanation<Loaded, Result>
  /** What it fetches: provider, network, parameters and window. It does not judge the data. */
  load: (context: ChipContext, api: ChipApi) => Promise<Loaded>
  /** The answer, worked out from what was fetched. Pure; null rather than a number made up. */
  answer: (loaded: Loaded, context: ChipContext) => Result | null
  /** How the answer is written */
  present: (result: Result, loaded: Loaded, env: ChipEnv, choices: Choices) => AnswerView
  /** What is said where there is no answer; `loaded` is null where nothing came back */
  empty: (loaded: Loaded | null, env: ChipEnv, choices: Choices) => string
  /** The ways into the tools, shown wherever the panel is not loading; `loaded` is null where nothing came back */
  actions: (env: ChipEnv, choices: Choices, loaded: Loaded | null) => AnswerAction[]
}

/** A definition as a registry holds it: what it fetches and answers is its own business */
export type Chip<Id extends string = string> = ChipDefinition<Id, unknown, unknown>

/**
 * Makes a definition a `Chip`. The definition is checked against its own `Loaded` and `Result` types, which are then let
 * go: that is the one cast, since the page hands what a chip's `load` returned to the same chip's `answer`.
 */
export function defineChip<const Id extends string, Loaded, Result>(definition: ChipDefinition<Id, Loaded, Result>): Chip<Id> {
  return definition as unknown as Chip<Id>
}

// ------------------------------------------------------------------------------------------------- the link

/** A day the calendar has: `2025-13-45` and `2025-02-30` are what a link can carry, and are no day */
export function isCalendarDay(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && DateTime.fromISO(value, { zone: 'utc' }).isValid
}

/** The value of a choice as the link carries it, or the choice's own where the link has none, or none that is one */
export function readChoice(choice: Choice, raw: unknown, now: DateTime): string {
  const asked = (raw as { toString: () => string } | null | undefined)?.toString()
  return asked && isValue(choice, asked, now) ? asked : choice.initial(now)
}

/** Whether a text is a value the choice takes: a day the calendar has, or one of the values of the choice */
function isValue(choice: Choice, text: string, now: DateTime): boolean {
  return choice.kind === 'date' ? isCalendarDay(text) : choice.values(now).includes(text)
}

/** The choices a link names, and only those that are values of theirs (an old name of the chip names its own, `aliasChoices`): where a default depends on the data, it is the data's to give */
export function readExplicit(chip: Chip, query: Record<string, unknown>, now: DateTime): Choices {
  const preset = chip.aliasChoices?.[String(query.ask)] ?? {}
  const found: Record<string, string> = {}
  for (const choice of chip.choices ?? []) {
    const raw = (query[choice.param] as { toString: () => string } | null | undefined)?.toString()
    const value = raw && isValue(choice, raw, now) ? raw : preset[choice.param]
    if (value && isValue(choice, value, now))
      found[choice.param] = value
  }
  return found
}

/** The values of a chip's choices, read from a link's query */
export function readChoices(chip: Chip, query: Record<string, unknown>, now: DateTime): Choices {
  const preset = chip.aliasChoices?.[String(query.ask)] ?? {}
  return Object.fromEntries((chip.choices ?? []).map(choice => [choice.param, readChoice(choice, query[choice.param] ?? preset[choice.param], now)]))
}

/** Whether a value the reader chose is one the choice takes: a day, not after `latest`, or one of its values */
export function acceptsChoice(choice: Choice, value: unknown, now: DateTime): boolean {
  const text = String(value ?? '')
  return choice.kind === 'date' ? /^\d{4}-\d{2}-\d{2}$/.test(text) && text <= choice.latest(now) : choice.values(now).includes(text)
}

/** The link's query with `changes` put over it; a value of null leaves its key out, and so does a value that is no text */
export function queryWith(link: Record<string, unknown>, changes: Record<string, string | null>): Record<string, string> {
  const query: Record<string, string> = {}
  for (const [key, value] of Object.entries({ ...link, ...changes })) {
    if (typeof value === 'string')
      query[key] = value
  }
  return query
}

/**
 * The query a press on a chip makes (`link` is the current one): the chip is set, or taken out where it is the open one,
 * and the choices of the other chips are taken out. The chip's own are kept, closing it included.
 */
export function queryOfPress(link: Record<string, unknown>, chips: readonly Chip[], id: string, open: string | null): Record<string, string> {
  const own = new Set((chips.find(chip => chip.id === id)?.choices ?? []).map(choice => choice.param))
  const changes: Record<string, string | null> = { ask: open === id ? null : id }
  for (const choice of chips.flatMap(chip => chip.choices ?? []))
    changes[choice.param] = own.has(choice.param) ? ((link[choice.param] as { toString: () => string } | null | undefined)?.toString() ?? null) : null
  return queryWith(link, changes)
}

/** The query a change of a choice makes: the chip is the open one, with the value */
export function queryOfChoice(link: Record<string, unknown>, id: string, param: string, value: string, own: Choices = {}): Record<string, string> {
  // what an old name of the chip named (`?ask=summer` named the summer) is written out, since the new name does not say it
  const named = Object.fromEntries(Object.entries(own).filter(([name]) => name !== param && typeof link[name] !== 'string'))
  return queryWith(link, { ...named, ask: id, [param]: value })
}
