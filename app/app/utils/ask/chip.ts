import type { Provider, ProviderNetworkCoverageResponse, Station, Value } from '#shared/types/api'
import type { Place } from '../../composables/usePlace'
import type { Bar } from '../answers'
import type { TOOLS } from '../sections'
import type { Quantity } from '../units'
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
 * link is read with `initial` as the value where it names none, or names one that is no value. Only a day exists
 * for now (`kind`); a choice of another kind adds its kind here, and the control of it to the panel.
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
export type Choice = DateChoice

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

/**
 * What the reader is told about how an answer was worked out and where it comes from (step 1b of GH-3764). Typed and
 * empty until that step fills it in; a definition leaves it out.
 */
export type ChipExplanation = Readonly<Record<string, never>>

/**
 * One chip. `Loaded` is what its requests bring back, `Result` what the answer function makes of it (null where the data
 * does not carry an answer). A registry holds the definitions as `Chip` (see `defineChip`).
 */
export interface ChipDefinition<Id extends string, Loaded, Result> {
  /** The name in the link (`?ask=summer`) and in the test id of the chip (`question-summer`) */
  id: Id
  /** The icon of the chip's button, an Iconify name the app bundles */
  icon: string
  /** The tool the answer leads into */
  tool: ToolKey
  /** The quantity whose unit the settings choose for the answer, and a change of which asks it again */
  quantity?: Quantity
  /** The choices of the question, with their names in the link; the question's own, so another chip's link carries none of them */
  choices?: readonly Choice[]
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
  /** Not written until step 1b of GH-3764 */
  explanation?: ChipExplanation
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
  return asked && isCalendarDay(asked) ? asked : choice.initial(now)
}

/** The values of a chip's choices, read from a link's query */
export function readChoices(chip: Chip, query: Record<string, unknown>, now: DateTime): Choices {
  return Object.fromEntries((chip.choices ?? []).map(choice => [choice.param, readChoice(choice, query[choice.param], now)]))
}

/** Whether a value the reader typed is one the choice takes: a day, not after `latest` */
export function acceptsChoice(choice: Choice, value: unknown, now: DateTime): boolean {
  const text = String(value ?? '')
  return /^\d{4}-\d{2}-\d{2}$/.test(text) && text <= choice.latest(now)
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
export function queryOfChoice(link: Record<string, unknown>, id: string, param: string, value: string): Record<string, string> {
  return queryWith(link, { ask: id, [param]: value })
}
