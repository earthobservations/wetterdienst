// The language a visitor is shown (GH-4106). `@nuxtjs/i18n` chooses it when the app starts, as nuxt.config.ts
// configures it (`detectBrowserLanguage`): the language of the `wd_lang` cookie if it names a locale of the app,
// else the first of the browser's languages (`navigator.languages`) that a locale matches, else German. The server
// cannot read `navigator.languages`, but the browser sends the same list as `Accept-Language`, so it asks the
// same question of it, with the module's own matcher (`findBrowserLocale`) over the same table of locales. A
// visitor that names no language the app has gets what the app falls back to. A request with no header at all is
// the one place the server decides differently from the app (`pickRequestLocale`).
import type { LocaleCode } from './locales'
// `#i18n-kit/browser` is `@internal` in @nuxtjs/i18n. Reusing the module's own matcher is what keeps the server and
// the app picking the same language; a minor release of the module may move it, which the build and `pnpm typecheck`
// would catch (and `tests/unit/language.test.ts` and `tests/e2e/seo-language.spec.ts` would then fail).
import { findBrowserLocale } from '#i18n-kit/browser'
import { DEFAULT_LOCALE, isLocaleCode, LOCALES } from './locales'

/**
 * The languages of an `Accept-Language` header, the preferred first: by weight (`q`), and in the order the header
 * names them where the weights are equal, as a browser lists `navigator.languages`. A language of weight 0 is one the
 * visitor does not want, and `*` is no language.
 *
 * @param header The header, if any
 * @returns The language tags
 */
export function parseAcceptLanguage(header: string | undefined): string[] {
  const entries = (header ?? '').split(',').flatMap((part, index) => {
    const [tag = '', ...params] = part.split(';').map(piece => piece.trim())
    if (tag === '' || tag === '*')
      return []
    const weight = params.map(param => /^q=(\d+(?:\.\d*)?|\.\d+)$/i.exec(param)?.[1]).find(match => match !== undefined)
    const q = weight === undefined ? 1 : Number(weight)
    return q > 0 ? [{ tag, q, index }] : []
  })
  return entries.sort((a, b) => b.q - a.q || a.index - b.index).map(entry => entry.tag)
}

/**
 * The language the app opens in for a visitor, as `@nuxtjs/i18n` chooses it in the browser.
 *
 * @param cookie The `wd_lang` cookie, if any; a value that is no locale of the app is ignored
 * @param languages The languages of the browser, the preferred first (`navigator.languages`, or `parseAcceptLanguage`
 * of the header on the server)
 * @returns The code of a locale of the app
 */
export function pickLocale(cookie: string | undefined, languages: readonly string[]): LocaleCode {
  if (isLocaleCode(cookie))
    return cookie
  const found = findBrowserLocale(LOCALES.map(({ code, language }) => ({ code, language })), languages)
  return isLocaleCode(found) ? found : DEFAULT_LOCALE
}

/** The language of a request that sends no `Accept-Language` at all, which the app's rule has no answer for. */
export const NO_HEADER_LOCALE: LocaleCode = 'en'

/**
 * The language the server writes the head of the shell in for a request: the language the app opens in
 * (`pickLocale`), except that a request with no `Accept-Language` header, and no cookie that names a locale, gets
 * English. That is deliberate and for crawlers: they send no header, and the page they render (Googlebot's browser
 * has `navigator.languages` of `en-US`) is English, so the HTML they read first agrees with it. A browser always
 * sends the header, so a visitor is never in this case. A header that names no language the app has is not
 * "no header": the app falls back to German there, and so does the server.
 *
 * @param cookie The `wd_lang` cookie, if any
 * @param acceptLanguage The `Accept-Language` header, if any
 * @returns The code of a locale of the app
 */
export function pickRequestLocale(cookie: string | undefined, acceptLanguage: string | undefined): LocaleCode {
  if (isLocaleCode(cookie))
    return cookie
  if (acceptLanguage === undefined || acceptLanguage.trim() === '')
    return NO_HEADER_LOCALE
  return pickLocale(undefined, parseAcceptLanguage(acceptLanguage))
}
