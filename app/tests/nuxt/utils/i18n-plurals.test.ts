import { readdirSync, readFileSync } from 'node:fs'
import { afterEach, describe, expect, it } from 'vitest'

// The counts the app writes, in the plural form of each language (GH-2968): "1 value", "2 values", and
// in Polish and Czech "1 wartość", "2 wartości", "5 wartości" with a third form for 5. Rendered through
// the app's own i18n, so the rules in i18n/plural-rules.ts, the `|` forms in the catalogs and the way the
// components pass the count are all in it. The rules themselves are held to CLDR in
// tests/unit/plural-rules.test.ts.
//
// The Polish, Czech, Luxembourgish and Low German forms are not natively reviewed (see i18n/TERMS.md).

const KEYS = ['dataViewer.valuesCount', 'dataViewer.valuesTransformed', 'dataViewer.copiedRows', 'glossary.count'] as const
const COUNTS = [0, 1, 2, 5, 22] as const

/** The form (0 = first) each language takes for 0, 1, 2, 5 and 22. */
const FORM: Record<string, readonly number[]> = {
  'cs': [2, 0, 1, 2, 2],
  'da': [1, 0, 1, 1, 1],
  'de': [1, 0, 1, 1, 1],
  'en': [1, 0, 1, 1, 1],
  'es': [1, 0, 1, 1, 1],
  'fr': [0, 0, 1, 1, 1],
  'it': [1, 0, 1, 1, 1],
  'lb': [1, 0, 1, 1, 1],
  'nl': [1, 0, 1, 1, 1],
  'pl': [2, 0, 1, 2, 1],
  'de-hh': [1, 0, 1, 1, 1],
}

/** `dataViewer.valuesCount` written out for each count, as a reader sees it. */
const VALUES: Record<string, readonly string[]> = {
  'cs': ['0 hodnot', '1 hodnota', '2 hodnoty', '5 hodnot', '22 hodnot'],
  'da': ['0 værdier', '1 værdi', '2 værdier', '5 værdier', '22 værdier'],
  'de': ['0 Werte', '1 Wert', '2 Werte', '5 Werte', '22 Werte'],
  'en': ['0 values', '1 value', '2 values', '5 values', '22 values'],
  'es': ['0 valores', '1 valor', '2 valores', '5 valores', '22 valores'],
  'fr': ['0 valeur', '1 valeur', '2 valeurs', '5 valeurs', '22 valeurs'],
  'it': ['0 valori', '1 valore', '2 valori', '5 valori', '22 valori'],
  'lb': ['0 Wäerter', '1 Wäert', '2 Wäerter', '5 Wäerter', '22 Wäerter'],
  'nl': ['0 waarden', '1 waarde', '2 waarden', '5 waarden', '22 waarden'],
  'pl': ['0 wartości', '1 wartość', '2 wartości', '5 wartości', '22 wartości'],
  'de-hh': ['0 Weerten', '1 Weert', '2 Weerten', '5 Weerten', '22 Weerten'],
}

// the catalogs as written, which the app's bundler turns into compiled messages
// (vitest runs from app/, which `import.meta.url` is not a file URL to in this environment)
const localesDir = `${process.cwd()}/i18n/locales`
const catalogs: Record<string, Record<string, unknown>> = Object.fromEntries(
  readdirSync(localesDir).filter(file => file.endsWith('.json')).map(file => [file.replace('.json', ''), JSON.parse(readFileSync(`${localesDir}/${file}`, 'utf-8'))]),
)
function message(locale: string, key: string) {
  return key.split('.').reduce<unknown>((node, part) => (node as Record<string, unknown>)[part], catalogs[locale]) as string
}

/** What a message reads when the form with this index is taken and the slots are filled. */
function filled(text: string, index: number, named: Record<string, number>) {
  return text.split('|')[index]!.trim().replace(/\{(\w+)\}/g, (_slot, name: string) => String(named[name]))
}

type Locale = Parameters<ReturnType<typeof useNuxtApp>['$i18n']['setLocale']>[0]

describe('plural forms of the counts', () => {
  // the app types its locale codes; the tables above are held to them by the first test
  const locales = Object.keys(FORM) as Locale[]
  const before = () => useNuxtApp().$i18n.locale.value

  afterEach(async () => {
    await useNuxtApp().$i18n.setLocale('en')
  })

  it('pins a form for every locale the app has', () => {
    expect(Object.keys(catalogs).sort()).toEqual([...locales].sort())
    expect(Object.keys(VALUES).sort()).toEqual([...locales].sort())
  })

  it.each(locales)('writes the values count in the form of %s for 0, 1, 2, 5 and 22', async (locale) => {
    const { $i18n } = useNuxtApp()
    await $i18n.setLocale(locale)
    expect(before()).toBe(locale)
    const written = COUNTS.map(count => $i18n.t('dataViewer.valuesCount', { count }, count))
    expect(written).toEqual(VALUES[locale])
  })

  it.each(locales)('takes the form its rule names for every count message in %s', async (locale) => {
    const { $i18n } = useNuxtApp()
    await $i18n.setLocale(locale)
    for (const key of KEYS) {
      COUNTS.forEach((count, at) => {
        // `glossary.count` takes the form of its total, the number the noun follows; the others of their count
        const named = { count, total: key === 'glossary.count' ? count : 7 }
        const plural = key === 'glossary.count' ? named.total : count
        expect($i18n.t(key, named, plural), `${locale} ${key} for ${count}`).toBe(filled(message(locale, key), FORM[locale]![at]!, named))
      })
    }
  })

  it.each(locales)('has as many forms as the language in every count message of %s', (locale) => {
    const forms = ['pl', 'cs'].includes(locale) ? 3 : 2
    for (const key of KEYS)
      expect(message(locale, key).split('|').length, `${locale} ${key}`).toBe(forms)
  })
})
