import type { MeasurementTexts } from '../../../i18n/measurement/types'
import type { MethodTexts } from '../../../i18n/methods/types'
import type { Chip, Citation, NumberLine, Rule } from './chip'
import type { WorkId } from './works'
import { workAnchor, WORKS } from './works'

// The words of the explanations of "Ask the weather" (GH-3764): which language the long texts are in, how a text is filled in
// with the numbers of a definition or an answer, and the addresses of the page of the methods. The long texts are written in
// German and English (`i18n/methods/`), as the entries of "How weather is measured" are (`i18n/measurement/`): a reader of
// another language sees English, with a note, and a reader of Low German or Luxembourgish German, as the privacy policy is shown.

/** The path of the page of the methods */
export const METHODS_PATH = '/methods'

/** The address of the section of a chip on the page of the methods (`/methods#summer`) */
export function methodPath(chipId: string): string {
  return `${METHODS_PATH}#${chipId}`
}

/** The address of a work in the list of works cited (`/methods#work-wmo-1203`) */
export function workPath(work: WorkId): string {
  return `${METHODS_PATH}#${workAnchor(work)}`
}

/** The language the long texts are shown in for a language of the interface */
export function textLanguageOf(locale: string): 'de' | 'en' {
  return ['de', 'de-hh', 'lb'].includes(locale) ? 'de' : 'en'
}

/** The texts of the methods in a language; the module is loaded when it is asked for, so that the home page does not carry it until an explanation is opened */
export async function loadMethodTexts(language: 'de' | 'en'): Promise<MethodTexts> {
  return language === 'de' ? (await import('../../../i18n/methods/de')).methods : (await import('../../../i18n/methods/en')).methods
}

/** The entries of "How weather is measured" in a language, which the terms of an explanation are taken from */
export async function loadMeasurementTexts(language: 'de' | 'en'): Promise<MeasurementTexts> {
  return language === 'de' ? (await import('../../../i18n/measurement/de')).measurement : (await import('../../../i18n/measurement/en')).measurement
}

/** A number or a list of numbers of a rule as a language writes it: no grouping (a year is no thousand), up to two decimals, a list with commas */
export function valueText(value: string | number | readonly number[], tag: string): string {
  const format = new Intl.NumberFormat(tag, { useGrouping: false, maximumFractionDigits: 2 })
  if (typeof value === 'string')
    return value
  return typeof value === 'number' ? format.format(value) : value.map(each => format.format(each)).join(', ')
}

/** `{name}` in a text replaced by the value of `name`; a name that has no value is left as it is, which a test finds */
export function fill(text: string, params: Readonly<Record<string, string | number>>): string {
  return text.replace(/\{(\w+)\}/g, (whole, name: string) => name in params ? String(params[name]) : whole)
}

/** The names a text uses */
export function placeholders(text: string): string[] {
  return [...new Set([...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]!))].sort()
}

/** The values of all the rules of a chip, written in a language (a tag of the long texts, `de` or `en`, which every browser has data for): the numbers its steps, limits and rules say */
export function ruleParams(rules: readonly Rule[], tag: string): Record<string, string> {
  return Object.fromEntries(rules.flatMap(rule => Object.entries(rule.values ?? {}).map(([name, value]) => [name, valueText(value, tag)])))
}

/**
 * One line of "the numbers used" as it is written. A name of the line's parameters that the chip's texts list under `terms`
 * (the season, its months and its plural) holds an id there (`winter`), which is written as the texts' own language has it.
 */
export function numberLineText(texts: MethodTexts, chip: Chip, line: NumberLine): string {
  const method = texts.chips[chip.id]
  const params: Record<string, string | number> = { ...line.params }
  for (const [name, words] of Object.entries(method?.terms ?? {})) {
    const id = line.params[name]
    if (typeof id === 'string' && id in words)
      params[name] = words[id]!
  }
  return fill(method?.numbers[line.id] ?? '', params)
}

/** Where in a work a rule's source is, as a link names it: "WMO-No. 1203 (2017), §3" */
export function citationText(citation: Citation): string {
  return `${WORKS[citation.work].short}${citation.at ? `, ${citation.at}` : ''}`
}

/** The works a chip cites, each once, in the order of its rules */
export function worksOf(chip: Chip): WorkId[] {
  return [...new Set(chip.explanation.rules.flatMap(rule => rule.cites.map(citation => citation.work)))]
}
