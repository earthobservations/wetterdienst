import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// Every identifier the backend serves -- parameter, resolution, dataset -- has a label in each
// locale's glossary, and that label is a translation. `useParameterLabel` falls back to the
// prettified id ("Wind Direction Last 10min") for an id it cannot find, which reads as English in
// every language, so a missing or copied entry shows nowhere except on the screen of someone using
// that language.
//
// `i18n-parity.test.ts` holds the locales' keys to each other and `e2e/i18n-coverage.spec.ts` holds
// the English glossary to a running backend. Neither says that a locale has the *backend's* names:
// a locale and English can lose the same key together and stay in step. This reads the names from
// where the backend declares them, the Python source, which a test of the app can reach in the
// repository without starting anything:
//
// - parameters: `PARAMETER_TABLE` in `metadata/parameter_table.py`, every `CanonicalParameter(name, ...)`
// - resolutions: the `Resolution` enum in `metadata/resolution.py`
// - datasets: not declared in one place -- each provider's `metadata.py` nests them in a dict beside
//   the parameters, so no pattern over the source finds them. The English glossary is the reference
//   here, and the backend's datasets are compared with it by `e2e/i18n-coverage.spec.ts`, which
//   asks the running backend for them.

const repository = fileURLToPath(new URL('../../../', import.meta.url))
const localesDir = fileURLToPath(new URL('../../i18n/locales', import.meta.url))

interface Glossary { parameters: Record<string, string>, resolutions: Record<string, string>, datasets: Record<string, string> }

// eagerly, by pattern: a locale added later is held to this without being listed
const modules = import.meta.glob<Glossary>('../../i18n/glossary/*.ts', { eager: true })
const glossaries = Object.fromEntries(
  Object.entries(modules).map(([path, glossary]) => [path.slice(path.lastIndexOf('/') + 1, -'.ts'.length), glossary]),
)
const locales = Object.keys(glossaries).sort()
const others = locales.filter(locale => locale !== 'en')

const records = ['parameters', 'resolutions', 'datasets'] as const
type GlossaryRecord = (typeof records)[number]

function source(path: string): string {
  return readFileSync(`${repository}${path}`, 'utf-8')
}

/** The canonical parameter names: the first argument of each `CanonicalParameter(...)` in the table. */
function canonicalParameters(): string[] {
  return [...source('src/wetterdienst/metadata/parameter_table.py').matchAll(/^ {4}CanonicalParameter\(\s*"([a-z0-9_]+)"/gm)]
    .map(match => match[1] as string)
}

/** The values of the `Resolution` enum, which ends where `Frequency` begins. */
function resolutions(): string[] {
  const block = source('src/wetterdienst/metadata/resolution.py').split('class Resolution(Enum):')[1]?.split('class Frequency')[0] ?? ''
  return [...block.matchAll(/^ {4}[A-Z_0-9]+ = "([a-z0-9_]+)"/gm)].map(match => match[1] as string)
}

/** The ids each locale has to label, by record. */
const required: Record<GlossaryRecord, () => string[]> = {
  parameters: canonicalParameters,
  resolutions,
  datasets: () => Object.keys(glossaries.en!.datasets),
}

// Labels that are the same as the English one in a locale, and rightly so. A label equal to English
// is an untranslated copy unless it is written down here, and an entry here that is no longer equal
// in a locale it names fails too, so the list shrinks as the catalogs improve and never goes stale.
// `locales` left out means every locale but English.
const identical: Record<GlossaryRecord, Record<string, { why: string, locales?: string[] }>> = {
  parameters: {
    temperature_humidex: { why: '"Humidex" is the name of the index itself, coined by Environment Canada and written so in every language' },
  },
  resolutions: {},
  datasets: {
    small: { why: '"MOSMIX-S" is the name of the DWD product' },
    large: { why: '"MOSMIX-L" is the name of the DWD product' },
    icon: { why: '"ICON (global)" is the name of the model, whose qualifier these languages share with English', locales: ['da', 'de', 'de-hh', 'es', 'fr', 'lb'] },
    icon_eu: { why: '"ICON-EU" is the name of the model' },
    synop: { why: '"SYNOP" is the WMO name of the report type' },
    wind: { why: '"Wind" is the same word in German, Low German and Dutch', locales: ['de', 'de-hh', 'nl'] },
    data: { why: '"Observations" is the same word in French', locales: ['fr'] },
  },
}

describe('the glossary reads the backend\'s names from where they are declared', () => {
  // the patterns above stop working quietly if the source is reformatted: they would find nothing,
  // and every locale would pass for having labelled all of nothing
  it('finds the canonical parameters', () => {
    const names = canonicalParameters()
    expect(names.length).toBeGreaterThanOrEqual(600)
    expect(new Set(names).size, 'a parameter is declared twice').toBe(names.length)
  })

  it('finds the resolutions', () => {
    expect(resolutions()).toEqual(expect.arrayContaining(['1_minute', '6_minutes', 'hourly', 'daily', 'annual']))
    expect(resolutions()).toHaveLength(11)
  })

  it('ships a glossary for every ui locale', () => {
    const uiLocales = readdirSync(localesDir).filter(name => name.endsWith('.json')).map(name => name.replace(/\.json$/, '')).sort()
    expect(locales).toEqual(uiLocales)
  })
})

describe.each(records)('%s', (record) => {
  const ids = required[record]()

  it.each(record === 'datasets' ? others : locales)('are all labelled in %s', (locale) => {
    const labels = glossaries[locale]![record]
    expect(ids.filter(id => !(id in labels)), `${locale} has no ${record} label for these`).toEqual([])
    expect(ids.filter(id => !labels[id]?.trim()), `${locale} has an empty ${record} label for these`).toEqual([])
  })

  // English's datasets are the reference, so it can lose none to itself; the others are held to it
  it.each(record === 'datasets' ? others : locales)('are only those the backend serves in %s', (locale) => {
    // a label for an id nothing serves anymore is dead weight in every catalog
    expect(Object.keys(glossaries[locale]![record]).filter(id => !ids.includes(id))).toEqual([])
  })

  it.each(others)('are translated rather than copied from English in %s', (locale) => {
    const english = glossaries.en![record]
    const labels = glossaries[locale]![record]
    const copied = ids.filter((id) => {
      const allowed = identical[record][id]
      return labels[id] === english[id] && !(allowed && (allowed.locales ?? others).includes(locale))
    })
    expect(copied, `${locale} ${record} that are English: translate them, or write down why they are the same`).toEqual([])
  })

  it('writes down only the labels that really are the same', () => {
    for (const [id, { locales: named }] of Object.entries(identical[record])) {
      expect(ids, `${id} is on the allow list of ${record} but is not served`).toContain(id)
      for (const locale of named ?? others)
        expect(glossaries[locale]![record][id], `${locale} ${id} is translated: take it off the allow list`).toBe(glossaries.en![record][id])
    }
  })
})
