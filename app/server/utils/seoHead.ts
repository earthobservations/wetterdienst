import de from '../../i18n/locales/de.json'
import en from '../../i18n/locales/en.json'
// The head and a text for a crawler that runs no script (GH-3497). The app is a single-page app (`ssr: false`), so
// the page it serves is the same shell for every path, and what a page is called and what it is about is set by
// script, which a link preview (Slack, Mastodon, a messenger) and some search engines do not run. The server writes
// the tags of the path into the shell as it sends it (`server/plugins/seo-head.ts`), and a `<noscript>` block with
// the page's name, what it is about and links to the other pages. The script then replaces them in the language
// the visitor chose (`app/app.vue`).
//
// Only German and English are written here: the default locale, and the language a crawler or a preview asks for if
// it asks for any. The other languages of the app are the visitor's own choice and need the script anyway.
import { canonicalUrl, findSeoRoute, HOME_TITLE_KEY, isNotIndexed, normalizePath, SEO_ROUTES, siteOrigin } from '../../shared/utils/seo'

export type SeoLocale = 'de' | 'en'

const MESSAGES: Record<SeoLocale, unknown> = { de, en }
// `og:locale` takes a language and a territory with an underscore (the app's `de-DE`, `en-GB` of nuxt.config.ts)
const OG_LOCALE: Record<SeoLocale, string> = { de: 'de_DE', en: 'en_GB' }
const SITE_NAME = 'Wetterdienst'

/** The text under a dotted key (`seo.pages.api`) of a catalog, or the key if there is none: a hole shows. */
export function message(locale: SeoLocale, key: string): string {
  let node: unknown = MESSAGES[locale]
  for (const part of key.split('.')) {
    if (node === null || typeof node !== 'object')
      return key
    node = (node as Record<string, unknown>)[part]
  }
  return typeof node === 'string' ? node : key
}

/**
 * The language of the page a request gets: the one the visitor chose (the cookie of the app's language
 * setting), else the one the browser prefers if that is English, else German, the app's default. A crawler sends
 * neither and gets German.
 *
 * @param cookie The `wd_lang` cookie, if any
 * @param acceptLanguage The `Accept-Language` header, if any
 * @returns `de` or `en`
 */
export function pickLocale(cookie: string | undefined, acceptLanguage: string | undefined): SeoLocale {
  if (cookie)
    return cookie.toLowerCase() === 'en' ? 'en' : 'de'
  const first = (acceptLanguage ?? '').split(',', 1)[0]?.trim().toLowerCase() ?? ''
  return first === 'en' || first.startsWith('en-') ? 'en' : 'de'
}

/** Text as it may stand in HTML, in an attribute as well. */
export function escapeHtml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

/**
 * The title of a page: its name and the app's, as `app/app.vue` writes it; the home page's is the sentence that says
 * what the site is.
 *
 * @param locale The language
 * @param path The path of the page
 * @returns The text of `<title>`
 */
export function pageTitle(locale: SeoLocale, path: string): string {
  const route = findSeoRoute(path)
  if (!route || route.title === HOME_TITLE_KEY)
    return message(locale, HOME_TITLE_KEY)
  return `${message(locale, route.title)} - ${SITE_NAME}`
}

export interface SeoHead {
  /** The `lang` of `<html>` */
  lang: SeoLocale
  /** The `<title>` text, not escaped */
  title: string
  /** The tags to put in `<head>` (not the title) */
  tags: string
  /** The `<noscript>` block to put in `<body>` */
  noscript: string
  /** Whether the page asks to be left out of the index */
  noindex: boolean
}

/**
 * What the shell of a path says about the page.
 *
 * @param path The request path
 * @param locale The language
 * @param siteUrl The `siteUrl` of the runtime configuration
 * @returns The title, the tags and the text. A path that is no page of the index (a provider's page, a path the
 * router does not know) is told as the site: its own page tells more once the script has run, and a canonical link
 * that named the home page for a path that is not would be wrong.
 */
export function seoHead(path: string, locale: SeoLocale, siteUrl: unknown): SeoHead {
  const route = findSeoRoute(path)
  const noindex = isNotIndexed(path)
  const description = message(locale, route?.description ?? 'seo.description')
  const title = pageTitle(locale, path)
  const origin = siteOrigin(siteUrl)
  const image = `${origin}/apple-touch-icon.png`
  const meta = (attribute: 'name' | 'property', name: string, content: string) =>
    `<meta ${attribute}="${name}" content="${escapeHtml(content)}">`

  const tags = [
    meta('name', 'description', description),
    ...(noindex ? [meta('name', 'robots', 'noindex')] : []),
    ...(route ? [`<link rel="canonical" href="${escapeHtml(canonicalUrl(siteUrl, route.path))}">`] : []),
    meta('property', 'og:type', 'website'),
    meta('property', 'og:site_name', SITE_NAME),
    meta('property', 'og:title', title),
    meta('property', 'og:description', description),
    ...(route ? [meta('property', 'og:url', canonicalUrl(siteUrl, route.path))] : []),
    meta('property', 'og:locale', OG_LOCALE[locale]),
    meta('property', 'og:image', image),
    meta('name', 'twitter:card', 'summary'),
    meta('name', 'twitter:title', title),
    meta('name', 'twitter:description', description),
    meta('name', 'twitter:image', image),
  ].join('')

  const links = SEO_ROUTES.map(page =>
    `<li><a href="${escapeHtml(page.path)}">${escapeHtml(message(locale, page.title === HOME_TITLE_KEY ? 'nav.home' : page.title))}</a></li>`,
  ).join('')
  const noscript = `<noscript><h1>${escapeHtml(title)}</h1><p>${escapeHtml(description)}</p>`
    + `<p>${escapeHtml(message(locale, 'seo.noscript'))}</p><nav><ul>${links}`
    + `<li><a href="https://wetterdienst.readthedocs.io/">${escapeHtml(message(locale, 'common.documentation'))}</a></li>`
    + `</ul></nav></noscript>`

  return { lang: locale, title, tags, noscript, noindex }
}

/**
 * The HTML sections of the shell with the head of a path put into them.
 *
 * @param sections The `head`, `bodyPrepend` and `htmlAttrs` sections of Nitro's `render:html`, which the call changes
 * @param sections.head The strings of `<head>`: the app's own `<title>` is replaced and the tags are added
 * @param sections.bodyPrepend The strings put at the start of `<body>`: the `<noscript>` is added
 * @param sections.htmlAttrs The attributes of `<html>`: `lang` is added where there is none
 * @param head The result of `seoHead`
 */
export function applySeoHead(
  sections: { head: string[], bodyPrepend: string[], htmlAttrs: string[] },
  head: SeoHead,
): void {
  const title = `<title>${escapeHtml(head.title)}</title>`
  const replaced = sections.head.map(part => part.replace(/<title>[\s\S]*?<\/title>/, () => title))
  sections.head.splice(0, sections.head.length, ...replaced)
  if (!replaced.some(part => part.includes(title)))
    sections.head.push(title)
  sections.head.push(head.tags)
  sections.bodyPrepend.push(head.noscript)
  if (!sections.htmlAttrs.some(part => /\blang=/.test(part)))
    sections.htmlAttrs.push(`lang="${head.lang}"`)
}

/** The path of a request line, as the app's pages know it. */
export function requestPath(url: string | undefined): string {
  return normalizePath(url ?? '/')
}
