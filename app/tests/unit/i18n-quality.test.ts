import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// Mechanical checks of the translations that `i18n-parity.test.ts` does not make (GH-2610). That one
// holds the *keys* of the eleven locales to each other; this one looks at what is written under them:
//
// - placeholders: `{count}`, `@:` links and tags that a translation dropped, renamed or added
// - plural syntax: none is used, and none may be used until pluralRules exist for the languages whose
//   plural has more than two forms (pl, cs, ...)
// - whitespace and empty labels, in the UI catalogs and in the glossaries
// - text copied from en or de, which shows a reader that language they did not choose
// - the project's own terms, written down in i18n/TERMS.md and used the same way throughout a locale
//
// What it cannot check is whether a translation is good. That takes a native speaker, and the
// rows that wait for one are the allow-list entries below that say so.

const i18nDir = fileURLToPath(new URL('../../i18n', import.meta.url))

type Catalog = Record<string, string>

function flatten(obj: Record<string, unknown>, prefix = ''): Catalog {
  return Object.fromEntries(Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    return value && typeof value === 'object'
      ? Object.entries(flatten(value as Record<string, unknown>, path))
      : [[path, String(value)]]
  }))
}

// eagerly, by pattern: a locale added later is held to all of this without being listed
const uiModules = import.meta.glob<Record<string, unknown>>('../../i18n/locales/*.json', { eager: true, import: 'default' })
const glossaryModules = import.meta.glob<Record<string, Record<string, string>>>('../../i18n/glossary/*.ts', { eager: true })

function codeOf(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1).replace(/\.(json|ts)$/, '')
}

const ui: Record<string, Catalog> = Object.fromEntries(
  Object.entries(uiModules).map(([path, data]) => [codeOf(path), flatten(data)]),
)
/** `parameters.temperature_humidex` -> 'Humidex': the three label records of a glossary, as one catalog. */
const glossary: Record<string, Catalog> = Object.fromEntries(
  Object.entries(glossaryModules).map(([path, mod]) => [
    codeOf(path),
    Object.fromEntries(['parameters', 'resolutions', 'datasets'].flatMap(record =>
      Object.entries(mod[record] ?? {}).map(([key, label]) => [`${record}.${key}`, label]),
    )),
  ]),
)
const locales = Object.keys(ui).sort()
const others = locales.filter(locale => locale !== 'en')
// Low German and Luxembourgish share much of their vocabulary with German, so a copy of the German
// text is not evidence of anything there; every other locale is held to it
const germanLike = ['de', 'de-hh', 'lb']

describe('the catalogs are read', () => {
  it('finds a catalog and a glossary for every locale', () => {
    expect(locales.length).toBeGreaterThan(2)
    expect(Object.keys(glossary).sort()).toEqual(locales)
    for (const locale of locales)
      expect(Object.keys(glossary[locale]!).length, `${locale} glossary labels`).toBeGreaterThan(500)
  })
})

describe('placeholders', () => {
  // `{name}` slots, `@:key` / `@.modifier:key` links to another message, tags, and the `|` that
  // separates plural forms. Compared as sorted lists, so a placeholder dropped, renamed or added
  // fails, and so does one that is written twice where en has it once.
  const TOKEN = /\{[^{}]*\}|@[.:][\w.:-]*|<\/?[a-z][^<>]*>|\|/gi
  const tokens = (text: string) => (text.match(TOKEN) ?? []).sort()

  it.each(others)('keeps the placeholders of en in %s', (locale) => {
    const wrong = Object.keys(ui.en!)
      .filter(key => JSON.stringify(tokens(ui[locale]![key] ?? '')) !== JSON.stringify(tokens(ui.en![key]!)))
      .map(key => `${key}: en has [${tokens(ui.en![key]!)}], ${locale} has [${tokens(ui[locale]![key] ?? '')}]`)
    expect(wrong).toEqual([])
  })

  it('has placeholders in en that are plain names', () => {
    // `{count}`, not `{ count }` or `{0}`, so that the comparison above is between names
    const odd = Object.entries(ui.en!).flatMap(([key, text]) =>
      (text.match(/\{[^{}]*\}/g) ?? []).filter(slot => !/^\{[a-z][A-Za-z]*\}$/.test(slot)).map(slot => `${key}: ${slot}`),
    )
    expect(odd).toEqual([])
  })

  it('has no placeholder in a glossary label', () => {
    // the labels are looked up by id and shown as they are; nothing fills a slot in them
    const slots = Object.entries(glossary).flatMap(([locale, labels]) =>
      Object.entries(labels).filter(([, label]) => /[{}@|]/.test(label)).map(([key]) => `${locale} ${key}`),
    )
    expect(slots).toEqual([])
  })
})

describe('plural syntax', () => {
  // vue-i18n splits a message at `|` into plural forms and picks one by the count, with a rule that
  // knows two forms (one / other) unless `pluralRules` says otherwise. The app has none, and shows
  // its counts as "{count} values" with no form to pick. A message that wants plural forms has to
  // bring `pluralRules` in the same change for the languages that have more than two (pl, cs: one,
  // few, other), and give those two as many forms, or Polish and Czech are shown the wrong one.
  const usedIn = (catalog: Catalog) => Object.keys(catalog).filter(key => catalog[key]!.includes('|'))
  const forms = (text: string) => text.split('|').length
  const manyForms = ['pl', 'cs']

  it('is used only with pluralRules for the languages with more than two forms', () => {
    const used = new Set(Object.values(ui).flatMap(usedIn))
    if (used.size === 0)
      return
    const config = readFileSync(`${i18nDir}/i18n.config.ts`, 'utf-8')
    expect(config, 'plural forms are used but i18n.config.ts has no pluralRules').toMatch(/pluralRules/)
    // only the text from pluralRules on: the file has a 'pl' and a 'cs' in its number and date formats
    const rules = config.slice(config.indexOf('pluralRules'))
    for (const locale of manyForms)
      expect(rules, `pluralRules has no rule for ${locale}`).toMatch(new RegExp(`['"]?${locale}['"]?\\s*:`))
  })

  it.each(others)('gives %s as many plural forms as en, or at least three where it has three', (locale) => {
    const keys = Object.keys(ui.en!).filter(key => [ui.en!, ui[locale]!].some(catalog => catalog[key]!.includes('|')))
    const wrong = keys.filter(key => manyForms.includes(locale)
      ? forms(ui[locale]![key]!) < 3
      : forms(ui[locale]![key]!) !== forms(ui.en![key]!))
    expect(wrong).toEqual([])
  })
})

describe('whitespace', () => {
  const sets: [string, Record<string, Catalog>][] = [['UI text', ui], ['glossary label', glossary]]

  it.each(sets)('has no stray whitespace in a %s', (_name, catalogs) => {
    const stray = Object.entries(catalogs).flatMap(([locale, catalog]) =>
      Object.entries(catalog)
        .filter(([, text]) => text !== text.trim() || /\s{2,}|[\t\n\r]/.test(text))
        .map(([key, text]) => `${locale} ${key}: ${JSON.stringify(text)}`),
    )
    expect(stray).toEqual([])
  })

  it('has no empty glossary label', () => {
    const empty = Object.entries(glossary).flatMap(([locale, catalog]) =>
      Object.entries(catalog).filter(([, text]) => text.trim() === '').map(([key]) => `${locale} ${key}`),
    )
    expect(empty).toEqual([])
  })
})

// Why a text may be the same as en's or de's. An entry says which locales may show the text as it is;
// one that no longer matches is stale and fails, so the list cannot outlive the text it excuses.
const NAME = 'a name, a format or a product, written the same in every language'
const UNIT = 'an international unit name, written the same'
const COGNATE = 'the ordinary word in that language is spelled the same'
const PENDING = 'still the English text: waits for a native speaker (GH-2610)'
const SUSPECT = 'the word looks borrowed rather than native: waits for a native speaker (GH-2610)'

interface Same { en?: string[], de?: string[], why: string }

const UI_SAME: Record<string, Same> = {
  'common.all': { de: ['da'], why: COGNATE },
  'common.documentation': { en: ['fr'], de: ['da'], why: COGNATE },
  'home.statParameters': { en: ['nl'], why: COGNATE },
  'home.kindRadarTitle': { en: ['cs', 'da', 'de-hh', 'de', 'es', 'fr', 'it', 'lb', 'nl', 'pl'], why: COGNATE },
  'about.linksTitle': { en: ['da', 'de-hh', 'de', 'nl'], why: COGNATE },
  'about.linkDocs': { en: ['fr'], de: ['da'], why: COGNATE },
  'nav.home': { en: ['it'], de: ['da', 'nl'], why: COGNATE },
  'nav.explorer': { en: ['de-hh', 'de', 'lb'], why: COGNATE },
  'nav.api': { en: ['cs', 'da', 'de-hh', 'de', 'es', 'fr', 'it', 'lb', 'nl', 'pl'], why: NAME },
  'nav.support': { en: ['da'], why: COGNATE },
  'header.github': { en: ['cs', 'da', 'de-hh', 'de', 'es', 'fr', 'it', 'lb', 'nl', 'pl'], why: NAME },
  'header.pypi': { en: ['cs', 'da', 'de-hh', 'de', 'es', 'fr', 'it', 'lb', 'nl', 'pl'], why: NAME },
  'header.menu': { en: ['da', 'fr', 'it', 'nl', 'pl'], why: COGNATE },
  'footer.copyright': { en: ['cs', 'da', 'de-hh', 'de', 'es', 'fr', 'it', 'lb', 'nl', 'pl'], why: NAME },
  'settings.themeSystem': { en: ['da', 'de-hh', 'de', 'lb'], why: COGNATE },
  'settings.unitTemperature': { de: ['da'], why: COGNATE },
  'settings.unitAngle': { en: ['fr'], why: COGNATE },
  'settings.unitConcentration': { en: ['fr'], why: COGNATE },
  'units.degree_kelvin': { en: ['cs', 'da', 'de-hh', 'de', 'es', 'fr', 'it', 'lb', 'nl'], why: UNIT },
  'units.beaufort': { en: ['cs', 'da', 'de-hh', 'de', 'es', 'fr', 'it', 'lb', 'nl', 'pl'], why: NAME },
  'units.pascal': { en: ['cs', 'da', 'de-hh', 'de', 'es', 'fr', 'it', 'lb', 'nl'], why: UNIT },
  'units.hectopascal': { en: ['es', 'fr', 'nl'], de: ['cs', 'da'], why: UNIT },
  'units.kilopascal': { en: ['cs', 'da', 'de-hh', 'de', 'es', 'fr', 'lb', 'nl'], why: UNIT },
  'units.millimeter': { de: ['da', 'nl'], why: UNIT },
  'units.decimal': { en: ['da', 'es'], why: UNIT },
  'units.meter': { de: ['da', 'nl'], why: UNIT },
  'units.kilometer': { de: ['da', 'nl'], why: UNIT },
  'units.radian': { en: ['fr'], why: UNIT },
  'units.minute': { en: ['fr'], de: ['nl'], why: UNIT },
  'support.title': { en: ['da'], why: COGNATE },
  'support.discussionsTitle': { en: ['fr'], why: COGNATE },
  'impressum.contactTitle': { en: ['fr', 'nl'], de: ['cs', 'da', 'pl'], why: COGNATE },
  'impressum.phoneLabel': { de: ['cs', 'da', 'pl'], why: COGNATE },
  'impressum.githubLabel': { en: ['cs', 'da', 'de-hh', 'de', 'es', 'fr', 'it', 'lb', 'nl', 'pl'], why: NAME },
  'impressum.disclaimerTitle': { en: ['nl'], why: COGNATE },
  'impressum.openSourceTitle': { en: ['da', 'fr', 'it'], why: COGNATE },
  'api.title': { en: ['cs', 'de-hh', 'de'], why: NAME },
  'api.endpointsTitle': { en: ['da', 'es', 'nl'], why: COGNATE },
  'api.paramHeader': { en: ['da', 'de-hh', 'de', 'lb', 'nl'], why: COGNATE },
  'api.descHeader': { en: ['fr'], why: COGNATE },
  'glossary.parametersTitle': { en: ['nl'], why: COGNATE },
  'meteogram.chart.panelTemperature': { de: ['da'], why: COGNATE },
  'meteogram.chart.panelWind': { en: ['de-hh', 'de', 'nl'], why: COGNATE },
  'meteogram.chart.horizonAll': { de: ['nl'], why: COGNATE },
  'meteogram.chart.viewNormal': { en: ['da', 'de-hh', 'de', 'es', 'fr', 'lb'], why: COGNATE },
  'meteogram.chart.viewCompact': { en: ['fr', 'nl'], de: ['da'], why: COGNATE },
  'meteogram.chart.seriesTemperature': { de: ['da'], why: COGNATE },
  'meteogram.chart.seriesWind': { en: ['de-hh', 'de', 'nl'], why: COGNATE },
  'meteogram.chart.seriesDirection': { en: ['fr'], why: COGNATE },
  'meteogram.chart.seriesRain': { de: ['nl'], why: COGNATE },
  'meteogram.chart.hoverTemperature': { de: ['da'], why: COGNATE },
  'meteogram.chart.hoverWind': { en: ['de-hh', 'de', 'nl'], why: COGNATE },
  'meteogram.chart.hoverRain': { de: ['nl'], why: COGNATE },
  'meteogram.chart.axisWind': { en: ['de-hh', 'de', 'nl'], why: COGNATE },
  'stripes.typeTemperature': { de: ['da'], why: COGNATE },
  'stripes.station': { en: ['da', 'de-hh', 'de', 'fr', 'nl'], why: COGNATE },
  'stripes.region': { en: ['cs', 'da', 'de-hh', 'de', 'pl'], why: COGNATE },
  'stripes.auto': { en: ['cs', 'da', 'es', 'fr', 'it', 'lb', 'nl', 'pl'], why: COGNATE },
  'stripes.hoverTrend': { en: ['cs', 'de-hh', 'de', 'lb', 'nl', 'pl'], why: COGNATE },
  'explorer.title': { en: ['de-hh', 'de', 'lb'], why: COGNATE },
  'explorer.mode': { en: ['fr'], de: ['nl'], why: COGNATE },
  'explorer.modeStation': { en: ['da', 'de-hh', 'de', 'fr', 'nl'], why: COGNATE },
  'explorer.modeInterpolation': { en: ['da', 'de-hh', 'de', 'fr'], why: COGNATE },
  'explorer.unitDefault': { de: ['da'], why: COGNATE },
  'explorer.shape': { de: ['da'], why: COGNATE },
  'explorer.shapeLong': { en: ['fr'], de: ['da', 'nl'], why: COGNATE },
  'explorer.stationsDetails': { de: ['nl'], why: COGNATE },
  'explorer.modeStationDesc': { en: ['lb'], why: PENDING },
  'explorer.modeInterpolationDesc': { en: ['lb'], why: PENDING },
  'explorer.modeSummaryDesc': { en: ['lb'], why: PENDING },
  'explorer.modeStationHow': { en: ['lb'], why: PENDING },
  'explorer.modeInterpolationHow': { en: ['lb'], why: PENDING },
  'explorer.modeSummaryHow': { en: ['lb'], why: PENDING },
  'explorer.modeHowItWorks': { en: ['lb'], why: PENDING },
  'stationTable.name': { en: ['de-hh', 'de'], why: COGNATE },
  'stationTable.region': { en: ['cs', 'da', 'de-hh', 'de', 'pl'], why: COGNATE },
  'stationTable.latitude': { en: ['fr'], why: COGNATE },
  'stationTable.longitude': { en: ['fr'], why: COGNATE },
  'parameterSelection.datasetLabel': { en: ['it', 'lb', 'nl'], why: COGNATE },
  'parameterSelection.parametersLabel': { en: ['nl'], why: COGNATE },
  'interpolation.source': { en: ['fr'], why: COGNATE },
  'interpolation.latitude': { en: ['fr'], why: COGNATE },
  'interpolation.longitude': { en: ['fr'], why: COGNATE },
  'dateRange.optional': { en: ['de-hh', 'de', 'lb'], why: COGNATE },
  'dateRange.max': { en: ['it'], de: ['cs', 'nl'], why: COGNATE },
  'dataViewer.dataTitle': { en: ['cs', 'da'], why: COGNATE },
  'dataViewer.axisDate': { en: ['fr'], de: ['cs', 'nl'], why: COGNATE },
  'dataViewer.paramLabelParameter': { en: ['da', 'de-hh', 'de', 'lb', 'nl'], why: COGNATE },
  'dataViewer.paramLabelDatasetParameter': { en: ['lb', 'nl'], why: COGNATE },
  'dataViewer.statDataset': { en: ['it', 'lb', 'nl'], why: COGNATE },
  'dataViewer.statParameter': { en: ['da', 'de-hh', 'de', 'lb', 'nl'], why: COGNATE },
  'dataViewer.statMin': { en: ['de-hh', 'de', 'fr', 'it'], why: COGNATE },
  'dataViewer.statMax': { en: ['de-hh', 'de', 'fr', 'it'], why: COGNATE },
  'dataViewer.statSum': { en: ['da'], why: COGNATE },
  'query.enable': { en: ['lb'], why: PENDING },
  'query.title': { en: ['lb'], why: PENDING },
  'query.run': { en: ['lb'], why: PENDING },
  'query.cancel': { en: ['lb'], why: PENDING },
  'query.placeholder': { en: ['lb'], why: PENDING },
  'query.syntaxError': { en: ['lb'], why: PENDING },
  'query.hint': { en: ['lb'], why: PENDING },
  'query.availableColumns': { en: ['lb'], why: PENDING },
  'query.examples': { en: ['lb'], why: PENDING },
  'query.success': { en: ['lb'], why: PENDING },
  'query.exampleAll': { en: ['lb'], why: PENDING },
  'query.exampleParameter': { en: ['lb'], why: PENDING },
  'query.exampleTimestamp': { en: ['lb'], why: PENDING },
  'query.exampleRange': { en: ['lb'], why: PENDING },
  'query.exampleRecent': { en: ['lb'], why: PENDING },
  'query.exampleStations': { en: ['lb'], why: PENDING },
  'query.exampleStation': { en: ['lb'], why: PENDING },
  'query.noData': { en: ['lb'], why: PENDING },
  'query.initFailed': { en: ['lb'], why: PENDING },
  'query.loadFailed': { en: ['lb'], why: PENDING },
  'query.unknownError': { en: ['lb'], why: PENDING },
  'query.queryFailed': { en: ['lb'], why: PENDING },
  'history.datasetLabel': { en: ['it', 'lb', 'nl'], why: COGNATE },
  'history.error': { en: ['es'], why: COGNATE },
  'history.colName': { en: ['de-hh', 'de'], why: COGNATE },
  'history.colLatitude': { en: ['fr'], why: COGNATE },
  'history.colLongitude': { en: ['fr'], why: COGNATE },
  'history.colRegion': { en: ['cs', 'da', 'de-hh', 'de', 'pl'], why: COGNATE },
  'history.stationNames': { de: ['nl'], why: COGNATE },
  'history.colParameter': { en: ['da', 'de-hh', 'de', 'lb', 'nl'], why: COGNATE },
  'history.colDescription': { en: ['fr'], why: COGNATE },
  'history.colMethod': { en: ['lb'], de: ['nl'], why: SUSPECT },
}

const GLOSSARY_SAME: Record<string, Same> = {
  'parameters.temperature_humidex': { en: ['cs', 'da', 'de', 'de-hh', 'es', 'fr', 'it', 'lb', 'nl', 'pl'], why: NAME },
  'datasets.small': { en: ['cs', 'da', 'de', 'de-hh', 'es', 'fr', 'it', 'lb', 'nl', 'pl'], why: NAME },
  'datasets.large': { en: ['cs', 'da', 'de', 'de-hh', 'es', 'fr', 'it', 'lb', 'nl', 'pl'], why: NAME },
  'datasets.icon': { en: ['da', 'de', 'de-hh', 'es', 'fr', 'lb'], why: NAME },
  'datasets.icon_eu': { en: ['cs', 'da', 'de', 'de-hh', 'es', 'fr', 'it', 'lb', 'nl', 'pl'], why: NAME },
  'datasets.synop': { en: ['cs', 'da', 'de', 'de-hh', 'es', 'fr', 'it', 'lb', 'nl', 'pl'], why: NAME },
  'datasets.data': { en: ['fr'], why: COGNATE },
  'datasets.wind': { en: ['de', 'de-hh', 'nl'], why: COGNATE },
  'datasets.hydrology': { de: ['cs', 'fr', 'nl'], why: COGNATE },
  'datasets.climate': { de: ['cs', 'da'], why: COGNATE },
  'datasets.rain': { de: ['nl'], why: COGNATE },
  'datasets.temperature': { de: ['da'], why: COGNATE },
  'datasets.temperature_air': { de: ['da'], why: COGNATE },
  'datasets.wind_synoptic': { de: ['nl'], why: COGNATE },
  'parameters.temperature_air_2m': { de: ['da'], why: COGNATE },
  'parameters.temperature_air_0_05m': { de: ['da'], why: COGNATE },
  'parameters.temperature_air_mean_0_05m': { de: ['da'], why: COGNATE },
  'parameters.temperature_air_mean_0_1m': { de: ['da'], why: COGNATE },
}

/**
 * The texts that equal en's (or de's, outside the German-like locales) and are not in `allowed`, and the
 * `allowed` entries that no longer describe a copy.
 */
function copies(catalogs: Record<string, Catalog>, allowed: Record<string, Same>) {
  const unexplained: string[] = []
  const stale: string[] = []
  const seen = new Set<string>()
  for (const locale of others) {
    for (const [key, english] of Object.entries(catalogs.en!)) {
      const text = catalogs[locale]![key]
      const german = catalogs.de![key]
      const ofEn = text === english
      const ofDe = !ofEn && !germanLike.includes(locale) && text === german
      const entry = allowed[key]
      if (ofEn || ofDe) {
        seen.add(`${key} ${ofEn ? 'en' : 'de'} ${locale}`)
        if (!entry?.[ofEn ? 'en' : 'de']?.includes(locale))
          unexplained.push(`${locale} ${key}: ${JSON.stringify(text)} is the ${ofEn ? 'English' : 'German'} text`)
      }
    }
  }
  for (const [key, entry] of Object.entries(allowed)) {
    for (const source of ['en', 'de'] as const) {
      for (const locale of entry[source] ?? []) {
        if (!seen.has(`${key} ${source} ${locale}`))
          stale.push(`${key}: ${locale} is no longer a copy of ${source}`)
      }
    }
  }
  return { unexplained, stale }
}

describe('text copied from en or de', () => {
  // A catalog that matches en wholesale is a copied stub, which `i18n-parity.test.ts` catches for the
  // glossaries; this is the same question one string at a time. Cognates are real (German "Wind",
  // French "Station"), so the strings that are legitimately the same are written down with the reason.
  it('has no UI text left in the language it was copied from', () => {
    const { unexplained } = copies(ui, UI_SAME)
    expect(unexplained).toEqual([])
  })

  it('has no stale entry in the list of UI texts that may be copies', () => {
    expect(copies(ui, UI_SAME).stale).toEqual([])
  })

  it('has no glossary label left in the language it was copied from', () => {
    expect(copies(glossary, GLOSSARY_SAME).unexplained).toEqual([])
  })

  it('has no stale entry in the list of glossary labels that may be copies', () => {
    expect(copies(glossary, GLOSSARY_SAME).stale).toEqual([])
  })

  it('names a reason for every entry', () => {
    for (const entry of [...Object.values(UI_SAME), ...Object.values(GLOSSARY_SAME)])
      expect(entry.why.length).toBeGreaterThan(10)
  })

  it.each([
    ['de-hh', 'UI text', 0.9],
    ['de-hh', 'glossary label', 0.25],
    ['lb', 'UI text', 0.25],
    ['lb', 'glossary label', 0.25],
  ] as const)('keeps %s from turning into a copy of de: at most %d of its %s', (locale, kind, ceiling) => {
    // Hamburgisch is a deliberate dialect locale, not German with another name. Most of its UI text
    // is still German today (GH-2610), so the ceiling sits just above where it is: a ratchet, to be
    // lowered as the text is written in the dialect, that fails when it goes back up. Luxembourgish
    // is held to a ceiling a good way above where it is, so that it cannot drift into German.
    const catalogs = kind === 'UI text' ? ui : glossary
    const keys = Object.keys(catalogs.de!)
    const same = keys.filter(key => catalogs[locale]![key] === catalogs.de![key]).length
    expect(same / keys.length, `${locale} ${kind}s equal to de`).toBeLessThan(ceiling)
  })
})

describe('terminology', () => {
  // The project's own terms, as i18n/TERMS.md writes them down. The table there is read back here, so
  // it cannot say anything the catalogs do not, and the stems below are what a locale's text is
  // checked for wherever en uses the term: a second word for the same thing (Provider as Anbieter in
  // one place and Provider in another) is the drift this is for.
  const terms = readFileSync(`${i18nDir}/TERMS.md`, 'utf-8')

  function table(): { keys: string[], heads: string[], rows: Record<string, string[]> } {
    // the first table of the file: the rows from the one headed "Locale | Station" to the next line
    // that is not a row (the address table further down is headed "Locale | Address")
    const all = terms.split('\n')
    const start = all.findIndex(line => line.startsWith('| Locale | Station'))
    expect(start, 'TERMS.md has no table of terms').toBeGreaterThanOrEqual(0)
    const lines = all.slice(start).filter((_, index, rest) => rest.slice(0, index + 1).every(line => line.startsWith('|'))).map(line => line.slice(1, line.lastIndexOf('|')).split('|').map(cell => cell.trim()))
    const head = lines[0]!
    const keys = lines.find(cells => cells[0] === 'Source key')!.slice(1).map(cell => cell.replace(/`/g, ''))
    const rows = Object.fromEntries(lines
      .filter(cells => /^`[a-z-]+`$/.test(cells[0]!))
      .map(cells => [cells[0]!.replace(/`/g, ''), cells.slice(1)]))
    return { keys, heads: head.slice(1), rows }
  }

  it('lists a row for every locale', () => {
    expect(Object.keys(table().rows).sort()).toEqual(locales)
  })

  it.each(locales)('matches the catalogs in %s', (locale) => {
    const { keys, heads, rows } = table()
    const written = rows[locale]!
    const wrong = keys.flatMap((key, index) => {
      const actual = key.startsWith('glossary:') ? glossary[locale]![key.slice('glossary:'.length)] : ui[locale]![key]
      return written[index] === actual ? [] : [`${heads[index]} (${key}): TERMS.md says "${written[index]}", the catalog "${actual}"`]
    })
    expect(wrong).toEqual([])
  })

  // The word each locale uses for a term, as a pattern that also matches its plurals, cases and the
  // compounds it forms (Stationsdetails, Wetterstationen). Written down rather than derived, for the
  // reason the flag words in i18n-parity.test.ts are.
  interface Term {
    en: RegExp
    label: string
    stems: Record<string, string>
    /** Texts a locale words without the term on purpose, with the reason: key -> locales. */
    rephrased?: Record<string, { locales: string[], why: string }>
  }
  const TERMS: Record<string, Term> = {
    station: { en: /\bstations?\b/i, label: 'stripes.station', stems: {
      'cs': 'stani[cč]',
      'da': 'station',
      'de': 'station',
      'de-hh': 'station',
      'en': 'station',
      'es': 'estaci',
      'fr': 'station',
      'it': 'stazion',
      'lb': 'statioun',
      'nl': 'station',
      'pl': 'stac(j|yj)',
    } },
    parameter: { en: /\bparameters?\b/i, label: 'dataViewer.statParameter', stems: {
      'cs': 'parametr',
      'da': 'parametr|parameter',
      'de': 'parameter',
      'de-hh': 'parameter',
      'en': 'parameter',
      'es': 'par[aá]metro',
      'fr': 'param[eè]tre',
      'it': 'parametr',
      'lb': 'parameter',
      'nl': 'parameter',
      'pl': 'parametr',
    } },
    dataset: { en: /\bdatasets?\b/i, label: 'parameterSelection.datasetLabel', stems: {
      'cs': 'datov\\S* sa?d',
      'da': 'datasæt',
      'de': 'datens[aä]tz',
      'de-hh': 'datens[aä]tz',
      'en': 'dataset',
      'es': 'conjuntos? de datos',
      'fr': 'jeux? de données',
      'it': 'dataset',
      'lb': 'dataset|datesätz',
      'nl': 'dataset',
      'pl': 'zbi\\S* danych',
    } },
    resolution: { en: /\bresolutions?\b/i, label: 'parameterSelection.resolutionLabel', stems: {
      'cs': 'rozlišení',
      'da': 'opløsning',
      'de': 'aufl[oö]s|aufgel[oö]s',
      'de-hh': 'aufl[oö]s|aufgel[oö]s',
      'en': 'resolution',
      'es': 'resoluci',
      'fr': 'résolution',
      'it': 'risoluzion',
      'lb': 'opléisung',
      'nl': 'resoluti',
      'pl': 'rozdzielczo',
    } },
    provider: { en: /\bproviders?\b/i, label: 'parameterSelection.providerLabel', stems: {
      'cs': 'poskytovatel',
      'da': 'udbyder',
      'de': 'anbieter',
      'de-hh': 'anbieter',
      'en': 'provider',
      'es': 'proveedor',
      'fr': 'fournisseur',
      'it': 'fornitor',
      'lb': 'ubidder',
      'nl': 'aanbieder',
      'pl': 'dostawc',
    } },
    network: { en: /\bnetworks?\b/i, label: 'parameterSelection.networkLabel', stems: {
      'cs': 'sí[ťt]',
      'da': 'netværk',
      'de': 'netz',
      'de-hh': 'netz',
      'en': 'network',
      'es': '\\bred(es)?\\b',
      'fr': 'réseau',
      'it': '\\bret[ei]\\b',
      'lb': 'netzwierk',
      'nl': 'netwerk',
      'pl': 'sie[ćc]i?',
    }, rephrased: {
      'stripes.aboutText2': { locales: ['de', 'de-hh'], why: 'says "Daten des Deutschen Wetterdienstes" where en says "DWD observation network"' },
    } },
    period: { en: /\bperiods?\b/i, label: 'history.periods', stems: {
      'cs': 'období',
      'da': 'periode',
      'de': 'zeitr',
      'de-hh': 'zeitr',
      'en': 'period',
      'es': 'periodo',
      'fr': 'période',
      'it': 'period',
      'lb': 'period',
      'nl': 'perio',
      'pl': 'okres',
    } },
  }

  /** What en says with the placeholders taken out: `{parameter}` is a slot, not the word. */
  const worded = (text: string) => text.replace(/\{[^{}]*\}/g, '')

  it.each(Object.keys(TERMS))('writes the %s label with the locale\'s word for it', (name) => {
    const term = TERMS[name]!
    const off = locales.filter(locale => !new RegExp(term.stems[locale]!, 'i').test(ui[locale]![term.label]!))
    expect(off, `these locales' ${term.label} does not contain their word for ${name}`).toEqual([])
  })

  it.each(Object.keys(TERMS))('says %s the same way wherever en says it', (name) => {
    const term = TERMS[name]!
    expect(Object.keys(term.stems).sort(), 'a stem for every locale').toEqual(locales)
    const off = others.flatMap(locale =>
      Object.entries(ui.en!)
        .filter(([key, english]) => term.en.test(worded(english)) && ui[locale]![key] !== english)
        .filter(([key]) => !term.rephrased?.[key]?.locales.includes(locale))
        .filter(([key]) => !new RegExp(term.stems[locale]!, 'i').test(ui[locale]![key]!))
        .map(([key]) => `${locale} ${key}: ${JSON.stringify(ui[locale]![key])}`),
    )
    expect(off, `where en says "${name}" and the locale's word for it is missing`).toEqual([])
  })
})
