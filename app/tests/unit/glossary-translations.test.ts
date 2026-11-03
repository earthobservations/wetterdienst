import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// Every identifier the backend serves -- parameter, resolution, dataset -- has a label in each
// locale's glossary, and that label is a translation. `useParameterLabel` falls back to the
// prettified id ("Wind Direction Mean Last 10min") for an id it cannot find, which reads as English in
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

/**
 * The datasets of `dwd/phenology`: one per plant and reporter group, `annual_apple`, `immediate_black_elder`.
 * They are made from the `_PLANTS` table of `provider/dwd/phenology/metadata.py` -- a reporter directory,
 * a group directory, the file stem, then the plant's name -- so no dataset name is written out in it.
 */
function phenologyDatasets(): string[] {
  const prefix = { annual_reporters: 'annual', immediate_reporters: 'immediate' } as const
  return [...source('src/wetterdienst/provider/dwd/phenology/metadata.py')
    .matchAll(/^ {4}\(\s*"(annual_reporters|immediate_reporters)",\s*"[a-z]+",\s*"[^"]+",\s*"([a-z_]+)",/gm)]
    .map(match => `${prefix[match[1] as keyof typeof prefix]}_${match[2]}`)
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

  it('finds the phenology datasets', () => {
    const names = phenologyDatasets()
    expect(names).toHaveLength(110)
    expect(new Set(names).size, 'a dataset is declared twice').toBe(names.length)
    expect(names).toEqual(expect.arrayContaining(['annual_apple', 'annual_winter_rye', 'immediate_black_elder']))
  })

  it('ships a glossary for every ui locale', () => {
    const uiLocales = readdirSync(localesDir).filter(name => name.endsWith('.json')).map(name => name.replace(/\.json$/, '')).sort()
    expect(locales).toEqual(uiLocales)
  })
})

describe.each(records)('%s', (record) => {
  const ids = required[record]()

  it.each(locales)('are all labelled in %s', (locale) => {
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

  // `useParameterLabel` showed "Annual Winter Rye" in every language for these (GH-2866)
  if (record === 'datasets') {
    it.each(locales)('has every phenology dataset in %s', (locale) => {
      const labels = glossaries[locale]!.datasets
      expect(phenologyDatasets().filter(id => !labels[id]?.trim()), `${locale} has no label for these`).toEqual([])
    })
  }

  it('writes down only the labels that really are the same', () => {
    for (const [id, { locales: named }] of Object.entries(identical[record])) {
      expect(ids, `${id} is on the allow list of ${record} but is not served`).toContain(id)
      for (const locale of named ?? others)
        expect(glossaries[locale]![record][id], `${locale} ${id} is translated: take it off the allow list`).toBe(glossaries.en![record][id])
    }
  })
})

// What the labels say, beyond that they exist and are not copied (GH-2610). Each of these found a defect
// in a glossary that had passed every check above: the statistic that was dropped ("Windstoot" for the
// maximum gust), a variant that lost the words of its base ("Température maximale sous sol nu" among
// "Température maximale du sol sous gazon"), a unit that was spelt out, a plain space before a colon.
describe('what a label says', () => {
  // The word each locale uses for the statistic an English label names: "Maximum ...", "Mean ...",
  // "Minimum ...", "Highest ...", "Greatest ...", "Strongest ...", wherever in the label ("Direction of the
  // maximum gust", "Night minimum temperature"). A label that does not contain one has dropped it, and a
  // maximum then reads as an instantaneous value. Stems, so that the inflections of a language (pl, cs,
  // lb) and the noun next to the adjective (`Maximum`, `maximal`) are met; a locale that needs another
  // stem adds it here. The pl mean is anchored: "bezpośrednie" (direct) has `średnie` in it.
  const STATISTIC: Record<string, Record<'max' | 'min' | 'mean', RegExp>> = {
    'de': { max: /höchst|maxim|größt|spitzen|stärkst/i, min: /tiefst|niedrigst|minim|kleinst/i, mean: /mittler|mittel|durchschnitt|arithmetisch/i },
    'de-hh': { max: /hööchst|maxim|gröttst|spitzen|starkst/i, min: /sietst|minim|kleinst/i, mean: /midd[el]|mittel|arithmet/i },
    'fr': { max: /maxim|plus fort|plus élev/i, min: /minim|plus faible/i, mean: /moyen/i },
    'es': { max: /máxim|mayor|más fuerte/i, min: /mínim|menor/i, mean: /medi[ao]/i },
    'it': { max: /massim|più forte/i, min: /minim/i, mean: /medi[ao]/i },
    'pl': { max: /maksym|maksim|najwyższ|największ|najsilniejsz/i, min: /minim|najniższ|najmniejsz/i, mean: /(^|\s)średni|arytmetyczn/i },
    'nl': { max: /maxim|hoogste|grootste|sterkste/i, min: /minim|laagste|kleinste/i, mean: /gemiddeld|rekenkundig/i },
    'cs': { max: /maxim|nejvyšší|největší|nejsilnější/i, min: /minim|nejnižší|nejmenší/i, mean: /průměr/i },
    'da': { max: /maks|højeste|største|kraftigste/i, min: /minim|laveste|mindste/i, mean: /gennemsnit|middel/i },
    'lb': { max: /maxim|héchst|gréisst|stäerkst/i, min: /minim|niddregst|klengst/i, mean: /mëttel|mëttler|arithmet/i },
  }
  const NAMES: Array<['max' | 'min' | 'mean', RegExp]> = [
    ['max', /\b(maximum|highest|greatest|strongest)\b/i],
    ['min', /\b(minimum|lowest)\b/i],
    ['mean', /\b(mean|average)\b/i],
  ]

  it('has a statistic word for every locale', () => {
    expect(Object.keys(STATISTIC).sort()).toEqual(others)
  })

  it.each(Object.keys(STATISTIC))('keeps the maximum, the minimum and the mean of the English label in %s', (locale) => {
    const lost: string[] = []
    for (const [id, english] of Object.entries(glossaries.en!.parameters)) {
      for (const [statistic, name] of NAMES) {
        const label = glossaries[locale]!.parameters[id] ?? ''
        if (name.test(english) && !STATISTIC[locale]![statistic].test(label))
          lost.push(`${id}: ${english} -> ${label}`)
      }
    }
    expect(lost, `${locale} labels that dropped the statistic`).toEqual([])
  })

  it.each(others)('translates one English label one way in %s', (locale) => {
    // "Soil temperature (2 m)" is two ids; a reader of the language sees one measurement
    const split: string[] = []
    for (const record of records) {
      const byEnglish = new Map<string, Set<string>>()
      for (const [id, english] of Object.entries(glossaries.en![record]))
        byEnglish.set(english, (byEnglish.get(english) ?? new Set()).add(glossaries[locale]![record][id] ?? ''))
      for (const [english, labels] of byEnglish) {
        if (labels.size > 1)
          split.push(`${record} "${english}" -> ${[...labels].join(' / ')}`)
      }
    }
    expect(split).toEqual([])
  })

  it.each(others)('writes an hour as the locale\'s symbol after the English number in %s', (locale) => {
    // "(3 h)" is "(3 u)" in Dutch and "(3 t)" in Danish, as the labels around it have it, and never
    // "(3 uur)" or "(3 timer)" in one label and "(12 u)" in the next; and it is the same number
    const symbol = ({ nl: 'u', da: 't' } as Record<string, string>)[locale] ?? 'h'
    const wrong: string[] = []
    for (const [id, english] of Object.entries(glossaries.en!.parameters)) {
      const label = glossaries[locale]!.parameters[id] ?? ''
      for (const [, hours] of english.matchAll(/(\d+) h\)/g)) {
        if (!new RegExp(`(^|[ (])${hours} ${symbol}\\)`).test(label))
          wrong.push(`${id}: ${english} -> ${label}`)
      }
    }
    expect(wrong).toEqual([])
  })

  // A soil temperature of a cover or a texture ("Maximum soil temperature under grass (5 cm)") is the
  // plain soil temperature with more words. Every locale has its word for the soil in it; in the
  // Romance languages, where the variant is the words of the plain one followed by the cover
  // ("Température maximale du sol sous gazon"), the label also opens with them. A language that puts an
  // adjective before the noun (cs "Maximální teplota holé půdy", pl "...temperatura odkrytej gleby") is
  // held to the soil word only, as a correct label of it has no fixed opening.
  const SOIL: Record<string, RegExp> = {
    'cs': /půd/i,
    'da': /jord/i,
    'de': /boden/i,
    'de-hh': /boden/i,
    'es': /suelo/i,
    'fr': /\bsol\b/i,
    'it': /suolo/i,
    'lb': /buedem/i,
    'nl': /bodem/i,
    'pl': /grunt|gleb/i,
  }
  const OPENS_WITH_THE_BASE = ['es', 'fr', 'it']

  it('has a soil word for every locale', () => {
    expect(Object.keys(SOIL).sort()).toEqual(others)
  })

  it.each(others)('keeps the soil in a soil temperature of a cover or a texture in %s', (locale) => {
    const parameters = glossaries[locale]!.parameters
    const stem = (id: string) => (parameters[id] ?? '').replace(/ \(.*$/, '')
    const bases: Array<[RegExp, string]> = [
      [/^temperature_soil_max_[a-z_]+_\d/, 'temperature_soil_max_0_1m'],
      [/^temperature_soil_min_[a-z_]+_\d/, 'temperature_soil_min_0_1m'],
      [/^temperature_soil_mean_(loamy_sand|loamy_silt)_/, 'temperature_soil_mean_0_05m'],
    ]
    const drifted: string[] = []
    for (const id of Object.keys(parameters)) {
      for (const [pattern, base] of bases) {
        if (!pattern.test(id))
          continue
        const label = parameters[id] ?? ''
        if (!SOIL[locale]!.test(label))
          drifted.push(`${id}: ${label} (no word for the soil)`)
        else if (OPENS_WITH_THE_BASE.includes(locale) && !label.startsWith(stem(base)))
          drifted.push(`${id}: ${label} (does not open with "${stem(base)}")`)
      }
    }
    expect(drifted).toEqual([])
  })

  it('sets a French colon with a no-break space', () => {
    // the French rule of TERMS.md ("a no-break space before : ; ? !"), which the UI catalog is held to
    // and the glossary's labels ("Déclarants annuels : Maïs") had not followed
    const loose = records.flatMap(record =>
      Object.entries(glossaries.fr![record]).filter(([, label]) => / [:;?!]/.test(label)).map(([id, label]) => `${record} ${id}: ${label}`))
    expect(loose).toEqual([])
  })
})
