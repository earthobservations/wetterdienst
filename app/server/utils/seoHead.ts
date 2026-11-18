// The head and a text for a crawler that runs no script (GH-3497). The app is a single-page app (`ssr: false`), so
// the page it serves is the same shell for every path, and what a page is called and what it is about is set by
// script, which a link preview (Slack, Mastodon, a messenger) and some search engines do not run. The server writes
// the tags of the path into the shell as it sends it (`server/plugins/seo-head.ts`), and a `<noscript>` block with
// the page's name, what it is about and links to the other pages. The script then replaces them in the language
// the visitor is shown (`app/app.vue`).
//
// The head is written in the language the app will render for the request (GH-4106): the rule that picks it is the
// app's own (`shared/utils/language.ts`), over the same locales (`shared/utils/locales.ts`) and catalogs, so the
// shell and the page agree about the language of one URL.
import type { LocaleCode } from '../../shared/utils/locales'
import type { SeoProvider } from '../../shared/utils/seo'
import cs from '../../i18n/locales/cs.json'
import da from '../../i18n/locales/da.json'
import deHh from '../../i18n/locales/de-hh.json'
import de from '../../i18n/locales/de.json'
import en from '../../i18n/locales/en.json'
import es from '../../i18n/locales/es.json'
import fr from '../../i18n/locales/fr.json'
import it from '../../i18n/locales/it.json'
import lb from '../../i18n/locales/lb.json'
import nl from '../../i18n/locales/nl.json'
import pl from '../../i18n/locales/pl.json'
import { LOCALES } from '../../shared/utils/locales'
import { canonicalUrl, findProvider, findSeoRoute, HOME_TITLE_KEY, isNotIndexed, normalizePath, providerPath, providerSeoText, SEO_ROUTES, siteOrigin } from '../../shared/utils/seo'

export type SeoLocale = LocaleCode

const MESSAGES: Record<SeoLocale, unknown> = { 'de': de, 'en': en, 'fr': fr, 'es': es, 'it': it, 'pl': pl, 'nl': nl, 'cs': cs, 'da': da, 'lb': lb, 'de-hh': deHh }
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

/** A text of a catalog with its `{slots}` filled in, as vue-i18n does for the script's. */
function translate(locale: SeoLocale, key: string, values: Record<string, string> = {}): string {
  return message(locale, key).replace(/\{(\w+)\}/g, (slot, name: string) => values[name] ?? slot)
}

/** `og:locale` takes a language and a territory with an underscore: the locale's `de-DE`, as `de_DE` (`app/app.vue`) */
function ogLocale(locale: SeoLocale): string {
  return (LOCALES.find(entry => entry.code === locale)?.language ?? 'de-DE').replace('-', '_')
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
 * @param providers The providers of the backend, whose pages are named by their provider
 * @returns The text of `<title>`
 */
export function pageTitle(locale: SeoLocale, path: string, providers: readonly SeoProvider[] = []): string {
  const provider = findProvider(path, providers)
  if (provider)
    return providerSeoText(provider, locale, (key, values) => translate(locale, key, values)).title
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
 * @param providers The providers of the backend (`server/utils/seoProviders.ts`), none if its list is not known
 * @returns The title, the tags and the text. The page of a provider of the list is told by its provider (GH-4119). A
 * path that is no page of the index (the page of an id the list does not have, a path the router does not know) is
 * told as the site: its own page tells more once the script has run, and a canonical link that named the home page
 * for a path that is not would be wrong.
 */
export function seoHead(path: string, locale: SeoLocale, siteUrl: unknown, providers: readonly SeoProvider[] = []): SeoHead {
  const provider = findProvider(path, providers)
  const route = findSeoRoute(path)
  const noindex = isNotIndexed(path)
  const providerText = provider ? providerSeoText(provider, locale, (key, values) => translate(locale, key, values)) : undefined
  const description = providerText?.description ?? message(locale, route?.description ?? 'seo.description')
  const title = providerText?.title ?? pageTitle(locale, path)
  const canonicalPath = provider ? providerPath(provider.provider) : route?.path
  const origin = siteOrigin(siteUrl)
  const image = `${origin}/apple-touch-icon.png`
  const meta = (attribute: 'name' | 'property', name: string, content: string) =>
    `<meta ${attribute}="${name}" content="${escapeHtml(content)}">`

  const tags = [
    meta('name', 'description', description),
    ...(noindex ? [meta('name', 'robots', 'noindex')] : []),
    ...(canonicalPath ? [`<link rel="canonical" href="${escapeHtml(canonicalUrl(siteUrl, canonicalPath))}">`] : []),
    meta('property', 'og:type', 'website'),
    meta('property', 'og:site_name', SITE_NAME),
    meta('property', 'og:title', title),
    meta('property', 'og:description', description),
    ...(canonicalPath ? [meta('property', 'og:url', canonicalUrl(siteUrl, canonicalPath))] : []),
    meta('property', 'og:locale', ogLocale(locale)),
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
