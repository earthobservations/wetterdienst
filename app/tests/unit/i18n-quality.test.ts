import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { pluralForms } from '../../i18n/plural-rules'

// Mechanical checks of the translations that `i18n-parity.test.ts` does not make (GH-2610). That one
// holds the *keys* of the eleven locales to each other; this one looks at what is written under them:
//
// - placeholders: `{count}`, `@:` links and tags that a translation dropped, renamed or added
// - plural forms: a message that is written in forms has as many as its language has (two, and three
//   in pl and cs), in every locale, as i18n/plural-rules.ts picks among them
// - whitespace and empty labels, in the UI catalogs and in the glossaries
// - text copied from en or de, which shows a reader that language they did not choose
// - the project's own terms, written down in i18n/TERMS.md and used the same way throughout a locale
//
// What it cannot check is whether a translation is good. That takes a native speaker, and pl, cs, lb
// and de-hh have not had one (i18n/TERMS.md says so under "Review status").

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
  // `{name}` slots, `@:key` / `@.modifier:key` links to another message and tags. Compared as sorted
  // lists, so a placeholder dropped, renamed or added fails, and so does one that is written twice where
  // en has it once. A message in plural forms (`one | other`, and `one | few | other` in pl and cs) is
  // compared one form at a time: each form of a locale carries what each form of en carries, so a
  // count that one form leaves out is caught, and the number of forms is the next describe's business.
  const TOKEN = /\{[^{}]*\}|@[.:][\w.:-]*|<\/?[a-z][^<>]*>/gi
  const tokens = (text: string) => (text.match(TOKEN) ?? []).sort()
  const formsOf = (text: string) => text.split('|')

  it.each(others)('keeps the placeholders of en in %s', (locale) => {
    const wrong = Object.keys(ui.en!).flatMap((key) => {
      const wanted = JSON.stringify(tokens(formsOf(ui.en![key]!)[0]!))
      return formsOf(ui[locale]![key] ?? '')
        .filter(form => JSON.stringify(tokens(form)) !== wanted)
        .map(form => `${key}: en has [${tokens(formsOf(ui.en![key]!)[0]!)}], ${locale} has [${tokens(form)}] in "${form.trim()}"`)
    })
    expect(wrong).toEqual([])
  })

  it('has the same placeholders in every form of en', () => {
    const wrong = Object.keys(ui.en!).filter(key =>
      new Set(formsOf(ui.en![key]!).map(form => JSON.stringify(tokens(form)))).size > 1,
    )
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

describe('plural forms', () => {
  // vue-i18n splits a message at `|` into plural forms and asks the rule of the active language which
  // one a count wants (i18n/plural-rules.ts, held to CLDR in plural-rules.test.ts). English writes
  // two ("1 value | 2 values"), and so does every locale but Polish and Czech, which write three (one,
  // few, other: "1 wartość | 2 wartości | 5 wartości"). A message in forms in one locale is in forms in
  // all of them, with as many forms as its language has, or a count would read "1 values" in one
  // language and be cut at the `|` in another (GH-2968).
  const usedIn = (catalog: Catalog) => Object.keys(catalog).filter(key => catalog[key]!.includes('|'))
  const forms = (text: string) => text.split('|').length

  it('has a plural rule for every locale', () => {
    expect(Object.keys(pluralForms).sort()).toEqual(locales)
  })

  it('writes the counts of the four messages that have one in plural forms', () => {
    // not a list of everything with a count: `dateRange.estimatedValues` and `errExceedsLimit` carry one
    // where one is no case, and `query.success` words it ("Returned rows: 1") so that it needs no form
    expect(usedIn(ui.en!).sort()).toEqual(['dataViewer.copiedRows', 'dataViewer.valuesCount', 'dataViewer.valuesTransformed', 'glossary.count'])
  })

  it.each(others)('has plural forms in %s for the messages that en has them in', (locale) => {
    expect(usedIn(ui[locale]!).sort()).toEqual(usedIn(ui.en!).sort())
  })

  it.each(locales)('gives %s as many plural forms as its language has', (locale) => {
    const wrong = usedIn(ui[locale]!).filter(key => forms(ui[locale]![key]!) !== pluralForms[locale])
    expect(wrong).toEqual([])
  })

  it('has a form that says the count in every form of a message', () => {
    // `{count}` is the number the reader sees; a form that dropped it would show the noun alone
    const wrong = Object.entries(ui).flatMap(([locale, catalog]) =>
      usedIn(catalog).filter(key => catalog[key]!.split('|').some(form => !form.includes('{count}'))).map(key => `${locale} ${key}`),
    )
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

describe('typography', () => {
  // How each language sets its quotation marks, so that one locale does not carry two styles (a
  // straight " next to its own „…“) and a text does not look pasted together. The straight " is
  // nobody's: every language has its own pair, and en is British (GH-2610). The apostrophe is the
  // straight ' everywhere, as the catalogs have it, not the typographic one.
  const QUOTES: Record<string, string> = {
    'cs': '„“',
    'da': '“”',
    'de': '„“',
    'de-hh': '„“',
    'en': '“”',
    'es': '«»',
    'fr': '«»',
    'it': '«»',
    'lb': '„“',
    'nl': '“”',
    'pl': '„”',
  }
  const sets: [string, Record<string, Catalog>][] = [['UI text', ui], ['glossary label', glossary]]

  it('has a quotation style written down for every locale', () => {
    expect(Object.keys(QUOTES).sort()).toEqual(locales)
  })

  it.each(sets)('sets the quotation marks of a %s the way its language does', (_name, catalogs) => {
    const off = Object.entries(catalogs).flatMap(([locale, catalog]) =>
      Object.entries(catalog)
        // «…» is the marker the operator note of the legal page names, in every language
        .filter(([, text]) => (text.replace(/«…»/g, '').match(/["“”„«»]/g) ?? []).some(mark => !QUOTES[locale]!.includes(mark)))
        .map(([key, text]) => `${locale} ${key}: ${JSON.stringify(text)}`),
    )
    expect(off).toEqual([])
  })

  it.each(sets)('writes the apostrophe of a %s straight', (_name, catalogs) => {
    const curly = Object.entries(catalogs).flatMap(([locale, catalog]) =>
      Object.entries(catalog)
        .filter(([, text]) => text.includes('’'))
        .map(([key, text]) => `${locale} ${key}: ${JSON.stringify(text)}`),
    )
    expect(curly).toEqual([])
  })

  it('sets French punctuation with a no-break space before : ; ? ! and inside « »', () => {
    // a plain space lets the colon fall to the start of the next line
    const loose = Object.entries(ui.fr!)
      .filter(([, text]) => / [:;?!»]|« /.test(text))
      .map(([key, text]) => `${key}: ${JSON.stringify(text)}`)
    expect(loose).toEqual([])
  })
})

describe('address', () => {
  // Every locale speaks to the reader in the informal singular (GH-3157): du, tu, tú, je, ty, "du" in lb,
  // the singular imperative in pl, and "you" in en, which has no other. It is written down in
  // i18n/TERMS.md ("Address and spelling"). A formal pronoun or possessive, or the formal imperative that
  // goes with one, is a text that was translated by itself. This sees the forms that have a word or an
  // ending to find: a verb form that has neither (Spanish "obtiene" for "obtienes") it does not, so the
  // read-through of a new text has to catch it. Low German is left out: it has no formal address to slip
  // into.
  // whole words, letters being any letter (JavaScript's \b sees only ASCII ones: it finds "tě" in "návštěvami")
  const word = (alternatives: string, flags = 'iu') =>
    new RegExp(`(?<![\\p{L}\\p{N}/])(${alternatives})(?![\\p{L}\\p{N}])`, flags)
  const FORMAL: Record<string, RegExp> = {
    // "Sie" is also "she" and "they", and "ihr" "her" and "their": only the capitalised forms are
    // looked at, which is where the polite address is written. One at the start of a sentence is flagged
    // as well, though it may mean "they" or "their": such a text is listed in FORMAL_OK with its reason
    de: word('Sie|Ihr|Ihre|Ihrem|Ihren|Ihrer|Ihres|Ihnen', 'u'),
    // the imperative of the second person plural ends in -ez ("Choisissez"); the singular of a verb
    // of the first group has -e, the others -s
    fr: word('vous|votre|vos|\\p{L}+-vous|(?!chez|assez|nez)\\p{L}{3,}ez|veuillez'),
    // "vy", "vás", "vám", "váš…" and the imperative plural, which ends in -te ("Vyberte", "Zkuste";
    // the singular has no -te). Any word of three letters or more that ends in -te is taken for one, so
    // a foreign word that does (date, byte, SQLite, update) would need an entry in FORMAL_OK
    cs: word('vy|vás|vámi|vám|váš\\p{L}*|vaš\\p{L}*|byste|jste|\\p{L}{2,}te'),
    // "Dir" and "Är…" are the second person plural, which lb used for a polite "you"; the singular is
    // "du", "dir", "deng", "däin…". The imperative of the plural ends in -t where the singular has none
    // ("Wielt", "Kuckt", "Gitt"), but that -t is also the third person singular ("wielt", "kuckt"). So
    // only the verbs that are no other form of the verb are listed, a capitalised one only for the start
    // of a sentence, and a verb whose singular imperative is the same word ("Luet": lueden) not at all
    lb: word('Dir|Är|Äre|Ären|Ärem|Ärer|Äert|Iech|Wielt|Kuckt|Rufft|Maacht|Setzt|Probéiert|Schränkt|Follegt|Entdeckt|Fannt|[Gg]itt|Klickt|Wiesselt|Generéiert|Interpoléiert|Visualiséiert|Konvertéiert|Iwwerschreift|Frot|Benotzt|Kritt|Sicht|Rechent', 'u'),
    da: /(?<=\s)(Dem|Deres)(?!\p{L})/u,
    es: word('usted|ustedes'),
    it: /(?<!\p{L})(Lei|Suo|Sua|Suoi|Sue)(?!\p{L})/u,
    nl: /(^|\s)(uw|u)(?=\s)/i,
    pl: /(?<!\p{L})(Pan|Pani|Państwo|Państwa)(?!\p{L})/u,
  }

  // The few places where a word of the list is right: a plural "you" that addresses several people, or a
  // word that only looks like one. An entry that no longer matches is stale and fails.
  const FORMAL_OK: Record<string, Record<string, string>> = {
    cs: { 'language.inclusiveHint': 'a welcome to everyone, which is a plural by meaning ("Vítejte všichni")' },
  }

  const prose = (text: string) => text.replace(/\{[^{}]*\}/g, '')

  it.each(Object.keys(FORMAL))('speaks to the reader of %s in the informal singular', (locale) => {
    const allowed = FORMAL_OK[locale] ?? {}
    const off = Object.entries(ui[locale]!)
      .filter(([key, text]) => !(key in allowed) && FORMAL[locale]!.test(prose(text)))
      .map(([key, text]) => `${key}: ${JSON.stringify(text)}`)
    expect(off).toEqual([])
  })

  // The patterns are held to a line that is formal on purpose (and to one that is not), so a pattern that
  // is loosened or broken until it finds nothing fails here rather than letting a formal text through
  const FORMAL_SAMPLES: Record<string, string[]> = {
    de: ['Wählen Sie eine Station.', 'In Ihrem Browser gespeichert.', 'Wenn Ihnen das hilft.'],
    fr: ['Notez le résultat.', 'Tapez une requête.', 'Choisissez une station.', 'Que souhaitez-vous faire ?', 'Allez voir.', 'Lisez la page.'],
    cs: ['Vyberte stanici.', 'Zkuste to znovu.', 'Co chcete vidět, jste si vybrali.', 'Pro vás.'],
    lb: ['Äert Browser huet et gespäichert.', 'Är Géigend.', 'Wann Dir wëllt.', 'Wielt eng Statioun.', 'Kuckt d\'Dokumentatioun.', 'Gitt hei an.'],
  }
  const INFORMAL_SAMPLES: Record<string, string[]> = {
    de: ['Wähle eine Station.', 'In deinem Browser gespeichert.'],
    fr: ['Chez nous, c\'est assez simple.', 'Notre nez le sait.', 'Choisis une station.'],
    cs: ['Vyber stanici.', 'Zkus to znovu.'],
    lb: ['Wiel eng Statioun.', 'Luet d\'Säit nei.', 'Deng Géigend.', 'Wann du wëlls.'],
  }

  it.each(Object.keys(FORMAL_SAMPLES))('finds the formal sample lines of %s, and none of the informal ones', (locale) => {
    expect(FORMAL_SAMPLES[locale]!.filter(text => !FORMAL[locale]!.test(text))).toEqual([])
    expect(INFORMAL_SAMPLES[locale]!.filter(text => FORMAL[locale]!.test(text))).toEqual([])
  })

  it('has no stale entry in the list of allowed formal forms', () => {
    const stale = Object.entries(FORMAL_OK).flatMap(([locale, keys]) =>
      Object.keys(keys)
        .filter(key => !(key in ui[locale]!) || !FORMAL[locale]!.test(prose(ui[locale]![key]!)))
        .map(key => `${locale}: ${key}`),
    )
    expect(stale).toEqual([])
  })
})

// Why a text may be the same as en's or de's. An entry says which locales may show the text as it is;
// one that no longer matches is stale and fails, so the list cannot outlive the text it excuses.
const NAME = 'a name, a format or a product, written the same in every language'
const UNIT = 'an international unit name, written the same'
const COGNATE = 'the ordinary word in that language is spelled the same'

interface Same { en?: string[], de?: string[], why: string }

const UI_SAME: Record<string, Same> = {
  'common.all': { en: ['de-hh'], de: ['da'], why: COGNATE },
  'stripes.table.class': { de: ['da', 'nl'], why: COGNATE },
  'stripes.table.classes.temperature.high': { en: ['nl'], why: COGNATE },
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
  'api.paramHeader': { en: ['da', 'de-hh', 'de', 'lb', 'nl'], why: COGNATE },
  'api.descHeader': { en: ['fr'], why: COGNATE },
  'glossary.parametersTitle': { en: ['nl'], why: COGNATE },
  'providers.licence': { en: ['cs', 'fr'], why: COGNATE },
  'providers.parametersCount': { en: ['nl'], why: COGNATE },
  'providers.source': { en: ['fr'], why: COGNATE },
  'meteogram.chart.panelTemperature': { de: ['da'], why: COGNATE },
  'meteogram.chart.panelWind': { en: ['de-hh', 'de', 'nl'], why: COGNATE },
  'meteogram.chart.horizonAll': { de: ['nl'], why: COGNATE },
  'meteogram.chart.viewNormal': { en: ['da', 'de-hh', 'de', 'es', 'fr', 'lb'], why: COGNATE },
  'meteogram.chart.viewCompact': { en: ['fr', 'nl'], de: ['da'], why: COGNATE },
  'meteogram.chart.seriesTemperature': { de: ['da'], why: COGNATE },
  'meteogram.chart.seriesWind': { en: ['de-hh', 'de', 'nl'], why: COGNATE },
  'meteogram.chart.seriesDirection': { en: ['fr'], why: COGNATE },
  'meteogram.chart.seriesRain': { de: ['nl'], why: COGNATE },
  'meteogram.chart.weather.rain': { de: ['nl'], why: COGNATE },
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
  'explorer.modeInterpolation': { en: ['da', 'de', 'fr'], why: COGNATE },
  'explorer.unitDefault': { de: ['da'], why: COGNATE },
  'explorer.shape': { de: ['da'], why: COGNATE },
  'explorer.shapeLong': { en: ['fr'], de: ['da', 'nl'], why: COGNATE },
  'explorer.stationsDetails': { de: ['nl'], why: COGNATE },
  'stationTable.name': { en: ['de'], why: COGNATE },
  'stationTable.region': { en: ['cs', 'da', 'de-hh', 'de', 'pl'], why: COGNATE },
  'stationTable.latitude': { en: ['fr'], why: COGNATE },
  'stationTable.longitude': { en: ['fr'], why: COGNATE },
  'parameterSelection.datasetLabel': { en: ['it', 'nl'], why: COGNATE },
  'parameterSelection.parametersLabel': { en: ['nl'], why: COGNATE },
  'interpolation.source': { en: ['fr'], why: COGNATE },
  'interpolation.latitude': { en: ['fr'], why: COGNATE },
  'interpolation.longitude': { en: ['fr'], why: COGNATE },
  'dateRange.optional': { en: ['de', 'lb'], why: COGNATE },
  'dateRange.max': { en: ['it'], de: ['cs', 'nl'], why: COGNATE },
  'dataViewer.dataTitle': { en: ['cs', 'da'], why: COGNATE },
  'dataViewer.axisDate': { en: ['fr'], de: ['cs', 'nl'], why: COGNATE },
  'dataViewer.paramLabelParameter': { en: ['da', 'de-hh', 'de', 'lb', 'nl'], why: COGNATE },
  'dataViewer.paramLabelDatasetParameter': { en: ['nl'], why: COGNATE },
  'dataViewer.statDataset': { en: ['it', 'nl'], why: COGNATE },
  'dataViewer.statParameter': { en: ['da', 'de-hh', 'de', 'lb', 'nl'], why: COGNATE },
  'dataViewer.statMin': { en: ['de', 'fr', 'it'], why: COGNATE },
  'dataViewer.statMax': { en: ['de', 'fr', 'it'], why: COGNATE },
  'dataViewer.statSum': { en: ['da'], why: COGNATE },
  'history.datasetLabel': { en: ['it', 'nl'], why: COGNATE },
  'history.error': { en: ['es'], why: COGNATE },
  'history.colName': { en: ['de'], why: COGNATE },
  'history.colLatitude': { en: ['fr'], why: COGNATE },
  'history.colLongitude': { en: ['fr'], why: COGNATE },
  'history.colRegion': { en: ['cs', 'da', 'de-hh', 'de', 'pl'], why: COGNATE },
  'history.stationNames': { de: ['nl'], why: COGNATE },
  'history.colParameter': { en: ['da', 'de-hh', 'de', 'lb', 'nl'], why: COGNATE },
  'history.colDescription': { en: ['fr'], why: COGNATE },
  'history.colMethod': { de: ['nl'], why: COGNATE },
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
  'parameters.temperature_air': { de: ['da'], why: COGNATE },
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
    ['de-hh', 'UI text', 0.22],
    ['de-hh', 'glossary label', 0.25],
    ['lb', 'UI text', 0.17],
    ['lb', 'glossary label', 0.25],
  ] as const)('keeps %s from turning into a copy of de: at most %d of its %s', (locale, kind, ceiling) => {
    // Hamburgisch is a deliberate dialect locale, written in Low German throughout, the UI text as well
    // as the glossary (GH-2969), not German with another name; Luxembourgish is not German either
    // (GH-2970). What the two still share with German is units, names and international words, 19 % of
    // the de-hh UI text and 14 % of the lb text today: the ceilings sit just above, so that a catalog
    // that slides back into the German text fails, and are to be lowered, never raised, to follow it.
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
      'lb': 'dates[aä]',
      'nl': 'dataset',
      'pl': 'zbi\\S* danych',
    } },
    resolution: { en: /\bresolutions?\b/i, label: 'parameterSelection.resolutionLabel', stems: {
      'cs': 'rozlišení',
      'da': 'opløsning',
      'de': 'aufl[oö]s|aufgel[oö]s',
      'de-hh': 'oplös',
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
      'de-hh': 'anbeder',
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
      'de-hh': 'nettwark',
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
    // not in the table of TERMS.md, which is the words the app's pages label things with: it is the
    // API page's own word, and fr, es, nl and da used to have two for it (GH-2610)
    endpoint: { en: /\bendpoints?\b/i, label: 'api.endpointsTitle', stems: {
      'cs': 'koncov\\S* bod',
      'da': 'endepunkt',
      'de': 'endpunkt',
      'de-hh': 'endpunkt',
      'en': 'endpoint',
      'es': 'puntos? de acceso',
      'fr': 'points? d\'accès',
      'it': 'endpoint',
      'lb': 'endpunkt',
      'nl': 'eindpunt',
      'pl': 'punkt\\S* końcow',
    } },
    period: { en: /\bperiods?\b/i, label: 'history.periods', stems: {
      'cs': 'období',
      'da': 'periode',
      'de': 'zeitr',
      'de-hh': 'tietr',
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
