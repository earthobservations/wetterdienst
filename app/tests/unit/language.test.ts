import { describe, expect, it } from 'vitest'
import { parseAcceptLanguage, pickLocale } from '../../shared/utils/language'
import { DEFAULT_LOCALE, isLocaleCode, LANGUAGE_COOKIE, LOCALES } from '../../shared/utils/locales'

// The language the app opens in (GH-4106), which the server writes the head of the shell in. The rule is the one
// `@nuxtjs/i18n` applies in the browser (nuxt.config.ts `detectBrowserLanguage`): the `wd_lang` cookie if it names a
// locale, else the browser's first language that a locale matches, else German. `tests/e2e/seo-language.spec.ts`
// holds the server's answer to the page's, in a browser; this pins the rule and the header's reading.

describe('the languages of an Accept-Language header', () => {
  it('are listed by weight, then by position', () => {
    expect(parseAcceptLanguage('en-GB,en;q=0.9,de;q=0.8')).toEqual(['en-GB', 'en', 'de'])
    expect(parseAcceptLanguage('de;q=0.5, fr;q=0.9, en')).toEqual(['en', 'fr', 'de'])
    expect(parseAcceptLanguage('de;q=0.9, fr;q=0.9')).toEqual(['de', 'fr'])
  })

  it('leave out a language of weight 0, the wildcard and what is empty', () => {
    expect(parseAcceptLanguage('en;q=0, de')).toEqual(['de'])
    expect(parseAcceptLanguage('*')).toEqual([])
    expect(parseAcceptLanguage('')).toEqual([])
    expect(parseAcceptLanguage(undefined)).toEqual([])
    expect(parseAcceptLanguage(',,de,')).toEqual(['de'])
  })
})

describe('the language the app opens in', () => {
  it('is German for a visitor that sends no language, as a crawler does', () => {
    expect(pickLocale(undefined, parseAcceptLanguage(undefined))).toBe('de')
    expect(DEFAULT_LOCALE).toBe('de')
  })

  it('is the first language of the browser that the app has', () => {
    expect(pickLocale(undefined, parseAcceptLanguage('en-US,en;q=0.9'))).toBe('en')
    expect(pickLocale(undefined, parseAcceptLanguage('de-AT,de;q=0.9'))).toBe('de')
    expect(pickLocale(undefined, parseAcceptLanguage('fr-CH, de;q=0.8'))).toBe('fr')
    expect(pickLocale(undefined, parseAcceptLanguage('pt-BR,pt;q=0.9,en-US;q=0.8'))).toBe('en')
    expect(pickLocale(undefined, parseAcceptLanguage('en;q=0.9,de;q=0.5'))).toBe('en')
    expect(pickLocale(undefined, parseAcceptLanguage('de;q=0.9'))).toBe('de')
  })

  it('is German for languages the app has none of', () => {
    expect(pickLocale(undefined, parseAcceptLanguage('pt-BR,zh-Hans-CN;q=0.8'))).toBe('de')
  })

  it('is the language of the cookie over the browser\'s', () => {
    expect(pickLocale('fr', ['en-US'])).toBe('fr')
    expect(pickLocale('de-hh', ['en-US'])).toBe('de-hh')
    expect(pickLocale('en', [])).toBe('en')
  })

  it('ignores a cookie that names no locale of the app, as the module does', () => {
    expect(pickLocale('xx', ['en-US'])).toBe('en')
    expect(pickLocale('', ['fr'])).toBe('fr')
    // the module takes the code as it is written
    expect(pickLocale('EN', ['fr'])).toBe('fr')
  })

  it('never answers the dialect for a browser\'s de-DE, which the visitor picks on purpose', () => {
    expect(pickLocale(undefined, ['de-DE'])).toBe('de')
    expect(pickLocale(undefined, ['de-hh'])).toBe('de')
  })

  it('has a code of the table for every answer', () => {
    for (const { code } of LOCALES)
      expect(isLocaleCode(pickLocale(code, []))).toBe(true)
    expect(LANGUAGE_COOKIE).toBe('wd_lang')
  })
})
