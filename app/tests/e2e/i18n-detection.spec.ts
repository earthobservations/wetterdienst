import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

// Which language a visitor is shown, as nuxt.config.ts configures it (GH-2610): the `wd_lang` cookie
// first, then the browser's languages, then German. `tests/nuxt/utils/i18n-detection.test.ts` pins
// how a browser tag is matched to a locale; this drives a real page load, where the cookie, the
// browser's languages and the fallback are put together, with the region tags no locale spells out.
// The app is client-rendered (ssr: false), so navigator.languages takes part and the header does not.

const localesDir = fileURLToPath(new URL('../../i18n/locales', import.meta.url))

/** The home page tagline of a locale: a sentence that tells the locales apart. */
function tagline(locale: string): string {
  return JSON.parse(readFileSync(`${localesDir}/${locale}.json`, 'utf-8')).home.tagline
}

const COOKIE = 'wd_lang'

/** The browser languages, as navigator.languages carries them. */
const visits: { name: string, languages: string[], cookie?: string, shown: string }[] = [
  { name: 'de-AT opens in German', languages: ['de-AT'], shown: 'de' },
  { name: 'en-US opens in English', languages: ['en-US'], shown: 'en' },
  { name: 'fr-CH opens in French', languages: ['fr-CH'], shown: 'fr' },
  { name: 'pt-BR, which the app has no translation for, opens in German', languages: ['pt-BR'], shown: 'de' },
  { name: 'pt-BR then en-US opens in English', languages: ['pt-BR', 'en-US'], shown: 'en' },
  { name: 'the cookie wins over the browser', languages: ['en-US'], cookie: 'pl', shown: 'pl' },
  { name: 'a cookie naming no locale is ignored', languages: ['en-US'], cookie: 'xx', shown: 'en' },
]

for (const { name, languages, cookie, shown } of visits) {
  test.describe(name, () => {
    test.use({ locale: languages[0] })

    test('is shown the right language on first load', async ({ page, context, baseURL }) => {
      await context.addInitScript((list) => {
        // the client side reads navigator.languages, which `locale` sets to the first one only
        Object.defineProperty(navigator, 'languages', { get: () => list })
      }, languages)
      if (cookie)
        await context.addCookies([{ name: COOKIE, value: cookie, url: baseURL! }])
      await page.goto('/')
      await expect(page.getByText(tagline(shown), { exact: true })).toBeVisible()
    })
  })
}

test.describe('picking a language', () => {
  test.use({ locale: 'en-US' })

  test('is remembered in the wd_lang cookie for the next visit', async ({ page, context }) => {
    await page.goto('/settings')
    await expect(page.getByRole('heading', { name: 'Settings' }).first()).toBeVisible()
    // the language select on the settings page: choose Deutsch
    await page.getByRole('combobox').first().click()
    await page.getByRole('option', { name: /Deutsch/ }).click()
    await expect(page.getByText('Einstellungen').first()).toBeVisible()

    const cookies = await context.cookies()
    expect(cookies.find(c => c.name === COOKIE)?.value).toBe('de')

    await page.goto('/')
    await expect(page.getByText(tagline('de'), { exact: true })).toBeVisible()
  })
})
