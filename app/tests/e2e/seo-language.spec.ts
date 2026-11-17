import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The language of the shell is the language of the page (GH-4106). The server writes the head of the HTML in the
// language the app will show the visitor, by the rule the app applies at startup (`shared/utils/language.ts`, the
// `wd_lang` cookie, then the browser's languages, then German), so a crawler that runs no script and one that does
// read one language for one URL. This drives both for the same visitor: the HTML a request without a script gets, and
// the page a browser with the same `Accept-Language`, `navigator.languages` and cookie shows. They must agree on the
// `lang` of `<html>` and on the title.

const COOKIE = 'wd_lang'

/** The visitors: the languages of the browser, in its order, and the cookie it holds. */
const visits: { name: string, languages: string[], cookie?: string }[] = [
  { name: 'a browser that asks for English', languages: ['en-US', 'en'] },
  { name: 'a browser that asks for German', languages: ['de-DE', 'de', 'en'] },
  { name: 'a browser that asks for French first', languages: ['fr-CH', 'de'] },
  { name: 'a browser whose first language the app has none of, and then English', languages: ['pt-BR', 'en-US'] },
  { name: 'a browser that asks for a language the app has none of', languages: ['pt-BR'] },
  { name: 'the language cookie over the browser\'s', languages: ['en-US'], cookie: 'pl' },
  { name: 'a language cookie that names no language of the app', languages: ['en-US'], cookie: 'xx' },
  { name: 'the dialect picked by cookie', languages: ['en-US'], cookie: 'de-hh' },
]

/** The header a browser with these languages sends: the first one whole, the others weighted down. */
function acceptLanguage(languages: string[]): string {
  return languages.map((language, index) => index === 0 ? language : `${language};q=${(1 - index / 10).toFixed(1)}`).join(',')
}

for (const { name, languages, cookie } of visits) {
  test.describe(name, () => {
    test.use({ locale: languages[0] })

    test('is told the same language by the shell and by the page', async ({ page, context, baseURL }) => {
      await mockBackend(page, baseURL!)
      await context.addInitScript((list) => {
        // the page reads navigator.languages, which `locale` sets to the first one only
        Object.defineProperty(navigator, 'languages', { get: () => list })
      }, languages)
      if (cookie)
        await context.addCookies([{ name: COOKIE, value: cookie, url: baseURL! }])

      const raw = await (await context.request.get('/about', { headers: { 'Accept-Language': acceptLanguage(languages) } })).text()
      const rawLang = /<html[^>]* lang="([^"]*)"/.exec(raw)?.[1]
      const rawTitle = /<title>([^<]*)<\/title>/.exec(raw)?.[1]
      expect(rawLang, 'the shell says its language').toBeTruthy()
      expect(rawTitle, 'the shell has a title').toBeTruthy()

      await page.goto('/about')
      await expect(page.locator('html')).toHaveAttribute('lang', rawLang!)
      // the title is plain text in the shell, and escaped as HTML there
      await expect(page).toHaveTitle(rawTitle!.replaceAll('&amp;', '&'))
    })
  })
}

// Deliberate, and for crawlers: a request with no `Accept-Language` at all gets the English head, since a crawler
// sends no header and the page it renders is English (Googlebot's browser has navigator.languages of en-US). A
// browser always sends the header, so no visitor is in this case. A header that names no language of the app gets
// German, as the page does.
test.describe('a request with no language at all', () => {
  test('gets the English head, as the page a crawler renders is English', async ({ request }) => {
    const html = await (await request.get('/about', { headers: { 'Accept-Language': '' } })).text()

    expect(html).toContain('<html lang="en"')
    expect(html).toContain('<title>About - Wetterdienst</title>')
  })

  test('with a language the app has none of gets the German head, as the app falls back', async ({ request }) => {
    const html = await (await request.get('/about', { headers: { 'Accept-Language': 'pt-BR' } })).text()

    expect(html).toContain('<html lang="de"')
    expect(html).toContain('<title>Über uns - Wetterdienst</title>')
  })
})

test.describe('the widget', () => {
  test('is left out of the index in every language', async ({ request }) => {
    for (const language of ['de', 'en-US', 'fr']) {
      const response = await request.get('/widget', { headers: { 'Accept-Language': language } })
      expect(response.headers()['x-robots-tag'], language).toBe('noindex')
      expect(await response.text(), language).toContain('<meta name="robots" content="noindex">')
    }
  })
})
