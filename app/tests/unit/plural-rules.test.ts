import { describe, expect, it } from 'vitest'
import { pluralForms, pluralRules } from '../../i18n/plural-rules'

// The plural rules the app hands to vue-i18n (GH-2968). Each language's rule is held to the CLDR plural
// categories of that language, which `Intl.PluralRules` knows, for every whole count up to a thousand.
// What the catalogs say for each form is pinned in tests/nuxt/utils/i18n-plurals.test.ts, through the
// app's own i18n, and that every plural message has the forms its language needs in i18n-quality.test.ts.

// the language whose CLDR rules a locale follows: `de-hh` is Low German, which Intl knows as `nds`
const cldr = (locale: string) => locale === 'de-hh' ? 'nds' : locale
const locales = Object.keys(pluralRules)

/** The form a CLDR category is written in: one is the first, few the second where there are three. */
function formOf(category: Intl.LDMLPluralRule, forms: number): number {
  if (category === 'one')
    return 0
  if (forms === 3 && category === 'few')
    return 1
  return forms - 1
}

describe('the plural rules', () => {
  it('has a rule and a form count for every locale of the app', () => {
    expect(Object.keys(pluralForms).sort()).toEqual(locales.sort())
    expect(locales).toEqual(expect.arrayContaining(['cs', 'de', 'de-hh', 'en', 'fr', 'lb', 'pl']))
  })

  it('gives Polish and Czech three forms and every other language two', () => {
    expect(Object.fromEntries(locales.map(locale => [locale, pluralForms[locale]]))).toEqual({
      'cs': 3,
      'da': 2,
      'de': 2,
      'de-hh': 2,
      'en': 2,
      'es': 2,
      'fr': 2,
      'it': 2,
      'lb': 2,
      'nl': 2,
      'pl': 3,
    })
  })

  it.each(locales)('picks the form of the CLDR category in %s', (locale) => {
    const forms = pluralForms[locale]!
    const wrong: string[] = []
    for (let count = 0; count <= 1000; count++) {
      const category = new Intl.PluralRules(cldr(locale)).select(count)
      const picked = pluralRules[locale]!(count, forms)
      // French has "many" for the millions, which no count here reaches
      if (picked !== formOf(category, forms))
        wrong.push(`${count}: ${category} should be form ${formOf(category, forms)}, got ${picked}`)
    }
    expect(wrong).toEqual([])
  })

  it.each([
    ['pl', [[0, 2], [1, 0], [2, 1], [4, 1], [5, 2], [12, 2], [14, 2], [22, 1], [24, 1], [25, 2], [112, 2], [122, 1]]],
    ['cs', [[0, 2], [1, 0], [2, 1], [4, 1], [5, 2], [22, 2], [100, 2]]],
    ['fr', [[0, 0], [1, 0], [2, 1], [5, 1]]],
    ['en', [[0, 1], [1, 0], [2, 1], [5, 1]]],
  ] as const)('picks, in %s, for the counts that tell the languages apart', (locale, expected) => {
    for (const [count, form] of expected)
      expect(pluralRules[locale]!(count, pluralForms[locale]!), `${locale} ${count}`).toBe(form)
  })

  it.each(locales)('never answers a form a two-form or one-form message does not have in %s', (locale) => {
    // a Polish text that falls back to the English one has two forms, and a message without any `|` one
    for (const length of [1, 2]) {
      for (const count of [0, 1, 2, 3, 5, 12, 22, 100])
        expect(pluralRules[locale]!(count, length), `${locale} ${count} of ${length}`).toBeLessThan(length)
    }
  })
})
