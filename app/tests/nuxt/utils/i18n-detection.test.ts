import { describe, expect, it } from 'vitest'
import { findBrowserLocale } from '#i18n-kit/browser'

// Which language the app opens in (GH-2610). nuxt.config.ts says: detect the browser's language, remember
// the pick in the `wd_lang` cookie, and fall back to German. `@nuxtjs/i18n` does the matching with
// `findBrowserLocale` against each locale's `language` tag; these pin what that gives for the tags a
// browser really sends, including the region ones (`de-AT`, `pt-BR`) that no locale spells out.

describe('browser language detection', () => {
  // the locales as the app registers them, `language` tags included
  const detect = (...browser: string[]) => {
    const { $i18n } = useNuxtApp()
    const locales = $i18n.locales.value.map(({ code, language }) => ({ code, language }))
    return findBrowserLocale(locales, browser)
  }

  it('is configured as the app documents it', () => {
    const { $i18n } = useNuxtApp()
    const detection = useRuntimeConfig().public.i18n.detectBrowserLanguage
    expect(detection).toMatchObject({
      useCookie: true,
      cookieKey: 'wd_lang',
      fallbackLocale: 'de',
      redirectOn: 'root',
    })
    expect($i18n.defaultLocale).toBe('de')
  })

  it('writes the language picked in the settings to the wd_lang cookie', async () => {
    const { $i18n } = useNuxtApp()
    const before = $i18n.locale.value
    try {
      await $i18n.setLocale('fr')
      expect(useCookie('wd_lang').value).toBe('fr')
    }
    finally {
      await $i18n.setLocale(before)
    }
  })

  it.each([
    ['en', 'en'],
    ['en-US', 'en'],
    ['en-GB', 'en'],
    ['de', 'de'],
    ['de-DE', 'de'],
    ['fr-CH', 'fr'],
    ['es-MX', 'es'],
    ['pl-PL', 'pl'],
    ['cs', 'cs'],
    ['da-DK', 'da'],
    ['nl-BE', 'nl'],
    ['lb', 'lb'],
    ['it-CH', 'it'],
  ])('opens %s in %s', (tag, expected) => {
    expect(detect(tag)).toBe(expected)
  })

  it('opens a region of German in German, not in the dialect that shares its language tag', () => {
    // Hamburgisch is `de-DE` as far as the browser's tags go, and has to be picked on purpose
    expect(detect('de-AT')).toBe('de')
    expect(detect('de-CH')).toBe('de')
    expect(detect('de-DE')).toBe('de')
    expect(detect('de-hh')).toBe('de')
  })

  it('is case-blind about the tag', () => {
    expect(detect('DE-at')).toBe('de')
    expect(detect('EN-gb')).toBe('en')
  })

  it('finds nothing for a language the app does not have, so the fallback applies', () => {
    expect(detect('pt-BR')).toBe('')
    expect(detect('zh-Hans-CN')).toBe('')
    expect(detect()).toBe('')
  })

  it('takes the first language of the browser\'s list that the app has', () => {
    expect(detect('pt-BR', 'fr-CA', 'en')).toBe('fr')
    expect(detect('pt-BR', 'pt', 'en-US')).toBe('en')
  })

  it('keeps the browser\'s order between a region match and an exact one', () => {
    // en-GB is the `language` of the en locale and matches whole, de-AT only by its language, and the
    // module scores the earlier of the browser's tags higher either way: the user's first choice wins
    expect(detect('de-AT', 'en-GB')).toBe('de')
    expect(detect('en-GB', 'de-AT')).toBe('en')
  })
})
