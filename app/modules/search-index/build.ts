import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { buildDocs, longTextLanguage } from '../../app/utils/search-docs'
import { buildIndex } from '../../app/utils/search-index'
import * as glossaryCs from '../../i18n/glossary/cs'
import * as glossaryDa from '../../i18n/glossary/da'
import * as glossaryDe from '../../i18n/glossary/de'
import * as glossaryDeHh from '../../i18n/glossary/de-hh'
import * as glossaryEn from '../../i18n/glossary/en'
import * as glossaryEs from '../../i18n/glossary/es'
import * as glossaryFr from '../../i18n/glossary/fr'
import * as glossaryIt from '../../i18n/glossary/it'
import * as glossaryLb from '../../i18n/glossary/lb'
import * as glossaryNl from '../../i18n/glossary/nl'
import * as glossaryPl from '../../i18n/glossary/pl'
import { measurement as measurementDe } from '../../i18n/measurement/de'
import { measurement as measurementEn } from '../../i18n/measurement/en'
import { methods as methodsDe } from '../../i18n/methods/de'
import { methods as methodsEn } from '../../i18n/methods/en'
import { LOCALES } from '../../shared/utils/locales'

// The index of the app's own pages for each language (GH-3790), built from the sources when the app is built (or the
// development server asks for it) and never kept in the repository: the catalogs of the interface, the long texts of
// "How weather is measured" and of the methods, and the manifest of the cards of the other pages (`utils/search-sources.ts`).
// The documents are `utils/search-docs.ts`'s, the index `utils/search-index.ts`'s; this file is only what reads the files.

const APP = join(dirname(fileURLToPath(import.meta.url)), '..', '..')

/** The locales of the app: one index for each */
export const SEARCH_LOCALES: string[] = LOCALES.map(locale => locale.code)

/** The curated labels of the parameters of each language: the glossary's names, which the glossary page shows (`i18n/glossary/<locale>.ts`) */
const GLOSSARIES: Record<string, { parameters: Record<string, string> }> = {
  'cs': glossaryCs,
  'da': glossaryDa,
  'de': glossaryDe,
  'de-hh': glossaryDeHh,
  'en': glossaryEn,
  'es': glossaryEs,
  'fr': glossaryFr,
  'it': glossaryIt,
  'lb': glossaryLb,
  'nl': glossaryNl,
  'pl': glossaryPl,
}

/** The files an index is built from, which the development server watches */
export function searchSources(locale: string): string[] {
  const language = longTextLanguage(locale)
  return [
    join(APP, 'i18n', 'locales', `${locale}.json`),
    join(APP, 'i18n', 'locales', 'en.json'),
    join(APP, 'i18n', 'measurement', `${language}.ts`),
    join(APP, 'i18n', 'methods', `${language}.ts`),
    join(APP, 'i18n', 'glossary', `${locale}.ts`),
  ]
}

function catalog(locale: string) {
  return JSON.parse(readFileSync(join(APP, 'i18n', 'locales', `${locale}.json`), 'utf-8'))
}

/** The index of one locale: what `utils/search-index.ts` searches */
export function searchIndexFor(locale: string) {
  const german = longTextLanguage(locale) === 'de'
  return buildIndex(buildDocs({
    locale,
    messages: catalog(locale),
    english: catalog('en'),
    measurement: german ? measurementDe : measurementEn,
    methods: german ? methodsDe : methodsEn,
  }))
}

/**
 * The labels of the parameters in a language, which the search shows the glossary's results by: with the index, in the one file the
 * search loads when it is opened. They are not imported by the app's own code for this (`useParameterLabel` has them all, and a
 * second way to them would split that chunk into eleven): the file of the language is read here, once, and kept in the index's.
 */
export function searchLabelsFor(locale: string): Record<string, string> {
  return GLOSSARIES[locale]!.parameters
}
