// The documents the search is built from (GH-3790), for one language of the interface: the entries of "How weather is
// measured", the sections and the works of the methods, and the cards of About, Support and Settings. Pure: what it reads
// is handed to it (`modules/search-index.ts` reads the files, a test reads the same ones), so that a test can hold it.
//
// Only what the reader sees goes in: a language that has no long texts of its own sees German or English, as the pages
// show them, and so the index has those, with the names of the entries in the language of the interface as keywords.

import type { MeasurementTexts } from '../../i18n/measurement/types'
import type { MethodTexts } from '../../i18n/methods/types'
import type { SearchDoc } from './search-index'
import { WORKS } from './ask/works'
import { TOPICS } from './measurement'
import { excerpt } from './search-index'
import { MESSAGE_PAGE_KEY, MESSAGE_SOURCES } from './search-sources'

/** The catalog of a language as it is in `i18n/locales/*.json` */
export interface Messages { [key: string]: string | Messages }

/** The text of a key (`settings.bar.title`) in a catalog, or undefined for a key it has not */
export function messageOf(messages: Messages, key: string): string | undefined {
  let found: string | Messages | undefined = messages
  for (const part of key.split('.')) {
    if (typeof found !== 'object')
      return undefined
    found = found[part]
  }
  return typeof found === 'string' ? found : undefined
}

export interface DocsInput {
  /** The language of the interface */
  locale: string
  /** Its catalog, and the English one, which a key that the first has not falls back to and which the words of a translated name are found in as well */
  messages: Messages
  english: Messages
  /** The long texts the reader of this language sees: German for German, Low German and Luxembourgish, English for the others */
  measurement: MeasurementTexts
  methods: MethodTexts
}

/** The language of the long texts for a language of the interface (as `textLanguageOf` of `utils/ask/method-text.ts`, which has imports this file keeps out) */
export function longTextLanguage(locale: string): 'de' | 'en' {
  return ['de', 'de-hh', 'lb'].includes(locale) ? 'de' : 'en'
}

/** A text of the catalog of the language, else the English one, else the key (which a test finds) */
function say(input: DocsInput, key: string): string {
  return messageOf(input.messages, key) ?? messageOf(input.english, key) ?? key
}

/** The first of the texts that names no number of the code's (`{from}`), else the first with them left out: a line shown under a title */
function firstSaid(texts: readonly string[]): string {
  return excerpt(texts.find(text => !/\{\w+\}/.test(text)) ?? (texts[0] ?? '').replace(/\{\w+\}/g, '…'))
}

function measurementDocs(input: DocsInput): SearchDoc[] {
  const docs: SearchDoc[] = []
  for (const topic of TOPICS) {
    const entry = input.measurement[topic]
    const to = `/measurement#${topic}`
    // the name of the entry in the language of the interface, which a reader of French looks for it by (the entry's text is English)
    const keywords = `${messageOf(input.messages, `measurement.topics.${topic.replace(/-(\w)/g, (_, letter: string) => letter.toUpperCase())}`) ?? ''}`
    docs.push({ kind: 'measurement', title: entry.title, summary: entry.summary, keywords, to })
    for (const part of entry.parts)
      docs.push({ kind: 'measurement', title: entry.title, context: part.title, summary: excerpt(part.paragraphs[0] ?? ''), text: part.paragraphs.slice(1).join(' '), keywords, to })
    docs.push({
      kind: 'measurement',
      title: entry.title,
      context: say(input, 'measurement.sourcesTitle'),
      text: entry.sources.map(source => `${source.plain} ${source.citation}`).join(' '),
      keywords,
      to,
    })
  }
  return docs
}

function methodDocs(input: DocsInput): SearchDoc[] {
  const docs: SearchDoc[] = []
  for (const [id, method] of Object.entries(input.methods.chips)) {
    const to = `/methods#${id}`
    docs.push({ kind: 'method', title: method.title, summary: method.summary, text: method.data, to })
    const steps = Object.values(method.steps)
    const formulas = Object.values(method.formulas)
    if (steps.length || formulas.length)
      docs.push({ kind: 'method', title: method.title, context: say(input, 'methods.stepsTitle'), summary: firstSaid([...steps, ...formulas]), text: [...steps, ...formulas].join(' '), to })
    const rules = Object.values(method.rules)
    if (rules.length)
      docs.push({ kind: 'method', title: method.title, context: say(input, 'methods.rulesTitle'), summary: firstSaid(rules.map(rule => rule.text)), text: rules.flatMap(rule => [rule.text, rule.says ?? '', rule.reason ?? '']).join(' '), to })
    const limits = Object.values(method.limits)
    if (limits.length)
      docs.push({ kind: 'method', title: method.title, context: say(input, 'methods.limitsTitle'), summary: firstSaid(limits), text: limits.join(' '), to })
  }
  for (const [id, work] of Object.entries(WORKS)) {
    const text = input.methods.works[id as keyof typeof WORKS]
    docs.push({ kind: 'method', title: work.short, context: say(input, 'methods.worksTitle'), summary: excerpt(text?.plain ?? ''), text: work.citation, to: `/methods#work-${id}` })
  }
  return docs
}

function messageDocs(input: DocsInput): SearchDoc[] {
  return MESSAGE_SOURCES.map((source) => {
    const [first = '', ...rest] = source.text
    const title = say(input, source.title)
    const summary = first ? say(input, first) : ''
    const context = source.context ? say(input, source.context) : say(input, MESSAGE_PAGE_KEY[source.kind])
    // the words of the English page as well, so that a reader of German finds "units" as well as "Einheiten"
    const english = input.locale === 'en'
      ? ''
      : [source.title, ...source.text.slice(0, 1)].map(key => messageOf(input.english, key) ?? '').join(' ')
    return {
      kind: source.kind,
      title,
      context,
      summary: excerpt(summary),
      text: rest.map(key => say(input, key)).concat(summary.length > 120 ? [summary] : []).join(' '),
      keywords: english,
      to: source.to,
    }
  })
}

/** Every document of the app's own pages for a language: what `buildIndex` is given when the app is built */
export function buildDocs(input: DocsInput): SearchDoc[] {
  return [...measurementDocs(input), ...methodDocs(input), ...messageDocs(input)]
}

/** What of an entry of the glossary (`GET /api/glossary`) the search reads */
export interface GlossaryRow {
  name: string
  description: string
  unit_symbol?: string | null
}

/**
 * The documents of the glossary, in the language of the page: the name the reader sees, the name the backend gives it (English
 * words), the unit's symbol, and what it says. Made in the browser from what the glossary page loads, not at build time,
 * since the descriptions are the backend's.
 */
export function glossaryDocs(entries: readonly GlossaryRow[], label: (name: string) => string): SearchDoc[] {
  return entries.map(entry => ({
    kind: 'glossary',
    title: label(entry.name),
    summary: excerpt(entry.description),
    text: entry.description,
    // the name is English words (`temperature_dew_point_2m`), which is how an English word finds it in any language
    keywords: `${entry.name} ${entry.unit_symbol ?? ''}`,
    to: `/glossary#${entry.name}`,
  }))
}
