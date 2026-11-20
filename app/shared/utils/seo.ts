// What a search engine and a link preview are told about the app (GH-3497): which pages are public, what each is
// called and described as, which one stays out of the index, and the sitemap and robots.txt that follow from that.
// One list for the browser (`app/app.vue`, the tags of the page the visitor is on), the server (`server/plugins/
// seo-head.ts`, the tags of the HTML a crawler that runs no script gets, and the two files), and the tests.

/**
 * The origin the hosted instance answers on. It is the default of `runtimeConfig.public.siteUrl`
 * (`NUXT_PUBLIC_SITE_URL`): an instance of its own sets its address there, so its canonical links, its sitemap and
 * its robots.txt name itself and not the hosted one.
 */
export const DEFAULT_SITE_URL = 'https://wetterdienst.eobs.org'

export interface SeoRoute {
  /** The path of the page, which is also the path of its canonical link and of its entry in the sitemap */
  path: string
  /** Other paths that show the same page; they name `path` as their canonical link */
  aliases?: readonly string[]
  /** The key of the catalog (`i18n/locales`) of the page's title; the home page is `seo.title` */
  title: string
  /** The key of the catalog of the page's description */
  description: string
}

/**
 * The pages that are in the index and in the sitemap. A page of `app/pages` is either here or in `NOT_INDEXED`
 * (or is `/providers/[provider]`, whose paths the backend's list of providers makes, `providerIds` below):
 * `tests/unit/seo.test.ts` holds the pages to that, so a new page cannot forget to say what it is.
 */
export const SEO_ROUTES: readonly SeoRoute[] = [
  { path: '/', title: 'seo.title', description: 'seo.description' },
  { path: '/explorer', title: 'explorer.title', description: 'seo.pages.explorer' },
  { path: '/meteogram', title: 'meteogram.title', description: 'seo.pages.meteogram' },
  { path: '/stripes', title: 'stripes.title', description: 'seo.pages.stripes' },
  { path: '/history', title: 'history.title', description: 'seo.pages.history' },
  { path: '/map', title: 'mapTool.title', description: 'seo.pages.map' },
  { path: '/radar', title: 'radar.title', description: 'seo.pages.radar' },
  { path: '/api', title: 'api.title', description: 'seo.pages.api' },
  { path: '/providers', title: 'providers.title', description: 'seo.pages.providers' },
  { path: '/glossary', title: 'glossary.title', description: 'seo.pages.glossary' },
  { path: '/measurement', title: 'measurement.title', description: 'seo.pages.measurement' },
  { path: '/about', title: 'about.title', description: 'seo.pages.about' },
  { path: '/support', title: 'support.title', description: 'seo.pages.support' },
  { path: '/impressum', title: 'impressum.title', description: 'seo.description' },
  { path: '/datenschutz', aliases: ['/privacy'], title: 'footer.privacy', description: 'seo.description' },
]

/** The pages that exist and are left out of the index, each with the reason. They are not in the sitemap. */
export const NOT_INDEXED: Readonly<Record<string, string>> = {
  '/widget': 'the forecast of /meteogram without the page around it, for other sites to frame; not a page to find',
  '/settings': 'the visitor\'s own settings, kept in their browser; nothing a search could show',
}

/** The key of the title of the home page, which is not a page's name and is not followed by the app's name */
export const HOME_TITLE_KEY = 'seo.title'

/**
 * A path as the routes are written: no query or fragment, no trailing slash (but the root).
 *
 * @param path A request path or a route's path
 * @returns The path, `/` for the root
 */
export function normalizePath(path: string): string {
  const bare = (path.split(/[?#]/, 1)[0] ?? '').replace(/\/+$/, '')
  return bare === '' ? '/' : bare
}

/**
 * The indexed page a path shows.
 *
 * @param path A request path or a route's path
 * @returns The page, or `undefined` for one that is not in the index (or that is no page)
 */
export function findSeoRoute(path: string): SeoRoute | undefined {
  // the router takes `/About` for `/about`, so the lookup does; the canonical link is the route's own path
  const wanted = normalizePath(path).toLowerCase()
  return SEO_ROUTES.find(route => route.path === wanted || route.aliases?.includes(wanted))
}

/** The catalog key of each kind of network, reusing the names the home page gives the kinds of data */
export const NETWORK_KIND_KEYS = {
  observation: 'home.kindObservationsTitle',
  forecast: 'home.kindForecastsTitle',
  derived: 'providers.kindDerived',
  radar: 'home.kindRadarTitle',
  alerts: 'home.kindAlertsTitle',
  storm_cells: 'providers.kindStormCells',
} as const

/** The key of the catalog of the description of a provider's page; `{provider}` and `{kinds}` are filled in */
export const PROVIDER_DESCRIPTION_KEY = 'seo.providerDescription'

/** The key of the catalog of the word that joins the last two kinds of data: "and" */
const KINDS_AND_KEY = 'seo.kindsAnd'

/** The part of a provider as `GET /api/providers` answers it that its page's head is made of */
export interface SeoProvider {
  /** The id in the path: `dwd` */
  provider: string
  name_english: string
  country: string
  country_code: string | null
  networks: readonly { kind: string }[]
}

// the ids the backend has are lower case words; the one that is read from a path or an answer is held to that, so
// nothing else (a `..`, a `%`, markup) can become a sitemap entry or a canonical link
const PROVIDER_ID = /^[a-z][a-z0-9_-]*$/

/**
 * The id a provider's page path names (`/providers/dwd`), lower case as the page reads it, whether or not the
 * provider exists.
 *
 * @param path A request path or a route's path
 * @returns The id, or `undefined` for a path that is not one level under `/providers`
 */
export function providerIdOfPath(path: string): string | undefined {
  const id = /^\/providers\/([^/]+)$/.exec(normalizePath(path).toLowerCase())?.[1]
  return id && PROVIDER_ID.test(id) ? id : undefined
}

/** The path of a provider's page, which is also its canonical path and its sitemap entry. */
export function providerPath(id: string): string {
  return `/providers/${id}`
}

/**
 * The provider whose page a path is.
 *
 * @param path A request path or a route's path
 * @param providers The providers of the backend
 * @returns The provider, or `undefined` for a path that is no provider's page (an unknown id included)
 */
export function findProvider(path: string, providers: readonly SeoProvider[]): SeoProvider | undefined {
  const id = providerIdOfPath(path)
  return id === undefined ? undefined : providers.find(provider => provider.provider === id)
}

/** The ids of a list the backend answered, those that can be paths, in the order of the list. */
export function providerIds(providers: readonly SeoProvider[]): string[] {
  return providers.map(provider => provider.provider).filter(id => PROVIDER_ID.test(id))
}

/** The name of a country in a language, as the browser and Node know it; the backend's English one if they do not. */
function countryName(provider: SeoProvider, language: string): string {
  if (!provider.country_code)
    return ''
  try {
    return new Intl.DisplayNames([language], { type: 'region' }).of(provider.country_code) ?? provider.country
  }
  catch {
    return provider.country
  }
}

/**
 * The title and the description of a provider's page, the one text for the server's shell and the script's head. The
 * provider keeps its name; the sentence around it, the country and the kinds of data are in the language.
 *
 * @param provider The provider
 * @param language The code of the locale, `de` or `de-hh`: the country's name is written in it
 * @param translate The catalog of the locale: a key and the values for its `{slots}`, as `t` of vue-i18n takes them
 * @returns The title as a page of the app is titled, and the description
 */
export function providerSeoText(
  provider: SeoProvider,
  language: string,
  translate: (key: string, values?: Record<string, string>) => string,
): { title: string, description: string } {
  const country = countryName(provider, language)
  // the kinds as nouns in the middle of a sentence (`seo.kinds.*`), not the capitalised names of the home page
  const kinds = [...new Set(provider.networks.map(network => network.kind))]
    .map(kind => Object.hasOwn(NETWORK_KIND_KEYS, kind) ? translate(`seo.kinds.${kind}`) : kind)
  // joined by the catalog's own word for "and", with no comma before it; `Intl.ListFormat` is not used, since its
  // patterns for some of the app's languages are not words (Luxembourgish prints `a(n)`)
  const last = kinds.pop()
  const list = kinds.length > 0 ? `${kinds.join(', ')} ${translate(KINDS_AND_KEY)} ${last}` : (last ?? '')
  return {
    title: `${provider.name_english} - Wetterdienst`,
    description: translate(PROVIDER_DESCRIPTION_KEY, {
      provider: country ? `${provider.name_english} (${country})` : provider.name_english,
      kinds: list,
    }),
  }
}

/**
 * Whether a page asks a search engine to leave it out of the index.
 *
 * @param path A request path or a route's path
 * @returns True for the pages of `NOT_INDEXED`
 */
export function isNotIndexed(path: string): boolean {
  return Object.hasOwn(NOT_INDEXED, normalizePath(path).toLowerCase())
}

/**
 * The address a site is reached at, as a bare origin: no trailing slash, and the hosted instance's where the
 * setting is empty or no http(s) URL (a mistyped one would put its text in every canonical link).
 *
 * @param value The `siteUrl` of the runtime configuration
 * @returns The origin, such as `https://wetterdienst.eobs.org`
 */
export function siteOrigin(value: unknown): string {
  if (typeof value !== 'string')
    return DEFAULT_SITE_URL
  try {
    const url = new URL(value.trim())
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.origin : DEFAULT_SITE_URL
  }
  catch {
    return DEFAULT_SITE_URL
  }
}

/**
 * The canonical link of a page.
 *
 * @param siteUrl The `siteUrl` of the runtime configuration
 * @param path The path of the page
 * @returns The absolute URL; the home page's ends in the slash of the root
 */
export function canonicalUrl(siteUrl: unknown, path: string): string {
  const route = findSeoRoute(path)
  const wanted = route ? route.path : normalizePath(path)
  return `${siteOrigin(siteUrl)}${wanted}`
}

/**
 * Text as it may stand in XML. An origin can hold `&`, `'` and `"` (`new URL('https://a&b.example').origin` keeps them).
 *
 * @param text Any text
 * @returns The text with the five characters XML reserves written as entities
 */
export function escapeXml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll('\'', '&apos;')
}

/**
 * The sitemap of the indexed pages (https://www.sitemaps.org/protocol.html): their canonical URLs, nothing else. No
 * `lastmod`, `changefreq` or `priority`, which the app has no true value for.
 *
 * @param siteUrl The `siteUrl` of the runtime configuration
 * @param providers The ids of the providers of the backend, each with a page of its own (`providerIds`); none if the
 * list is not known, which leaves the fixed pages
 * @returns The XML document
 */
export function sitemapXml(siteUrl: unknown, providers: readonly string[] = []): string {
  const paths = [...SEO_ROUTES.map(route => route.path), ...providers.filter(id => PROVIDER_ID.test(id)).map(providerPath)]
  const urls = paths.map(path => `  <url><loc>${escapeXml(`${siteOrigin(siteUrl)}${path}`)}</loc></url>`)
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...urls,
    '</urlset>',
    '',
  ].join('\n')
}

/**
 * The robots.txt: every crawler may fetch everything (the pages need `/_nuxt` and `/api` to draw anything, so
 * neither is closed to a crawler that runs scripts), and the sitemap is named.
 *
 * @param siteUrl The `siteUrl` of the runtime configuration
 * @returns The text
 */
export function robotsTxt(siteUrl: unknown): string {
  return `User-agent: *\nDisallow:\n\nSitemap: ${siteOrigin(siteUrl)}/sitemap.xml\n`
}

/**
 * Whether a path asks for a text or XML file the app does not have. The SPA answers an unknown path with its shell
 * and a 200, which a crawler reads as a (broken) file of that name: a `/sitemap_index.xml` is no HTML page.
 *
 * @param path A request path
 * @returns True for a `.xml` or `.txt` path, which is a file or a 404 and never the shell
 */
export function isTextFilePath(path: string): boolean {
  return /\.(?:xml|txt)$/i.test(normalizePath(path))
}
