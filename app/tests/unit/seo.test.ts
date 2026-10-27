import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { applySeoHead, message, pageTitle, pickLocale, seoHead } from '../../server/utils/seoHead'
import {
  canonicalUrl,
  DEFAULT_SITE_URL,
  escapeXml,
  findSeoRoute,
  isNotIndexed,
  isTextFilePath,
  NOT_INDEXED,
  robotsTxt,
  SEO_ROUTES,
  sitemapXml,
  siteOrigin,
} from '../../shared/utils/seo'

// What a search engine and a link preview are told about the app (GH-3497): the pages in the index, the sitemap and
// robots.txt that follow from them, the tags the server writes into the shell for a crawler that runs no script, and
// the 404 of a text file that is none.

const APP = join(__dirname, '..', '..')

/** A stand-in for `setResponseHeader` that keeps what it is given. */
function recordHeaders(headers: Record<string, string>) {
  return (_event: unknown, name: string, value: string) => {
    headers[name] = value
  }
}
const PAGES = join(APP, 'app', 'pages')

/** The paths of the pages of `app/pages`, as the router makes them from the file names; a `[param]` page is left out. */
function pagePaths(directory = PAGES, prefix = ''): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    if (entry.isDirectory())
      return pagePaths(join(directory, entry.name), `${prefix}/${entry.name}`)
    const name = entry.name.replace(/\.vue$/, '')
    if (name.startsWith('['))
      return []
    return [name === 'index' ? (prefix || '/') : `${prefix}/${name}`]
  })
}

describe('the list of pages', () => {
  it('names every page of the app, in the index or out of it with a reason', () => {
    const named = new Set([...SEO_ROUTES.map(route => route.path), ...Object.keys(NOT_INDEXED)])
    expect(pagePaths().filter(path => !named.has(path))).toEqual([])
    for (const [path, reason] of Object.entries(NOT_INDEXED))
      expect(reason.length, path).toBeGreaterThan(10)
  })

  it('has no page that is both in the index and out of it, and no path that is no page', () => {
    const pages = new Set(pagePaths())
    for (const route of SEO_ROUTES) {
      expect(NOT_INDEXED, route.path).not.toHaveProperty(route.path)
      expect(pages.has(route.path), route.path).toBe(true)
      // an alias is one the page itself declares (`definePageMeta({ alias })`)
      for (const alias of route.aliases ?? []) {
        const file = join(PAGES, `${route.path.slice(1)}.vue`)
        expect(readFileSync(file, 'utf8'), alias).toContain(`'${alias}'`)
      }
    }
    for (const path of Object.keys(NOT_INDEXED))
      expect(pages.has(path), path).toBe(true)
  })

  it('has a title and a description in German and English for every page', () => {
    for (const locale of ['de', 'en'] as const) {
      for (const route of SEO_ROUTES) {
        expect(message(locale, route.title), `${locale} ${route.title}`).not.toBe(route.title)
        expect(message(locale, route.description), `${locale} ${route.description}`).not.toBe(route.description)
        // a description that a search engine shows whole is about a line or two of a result
        expect(message(locale, route.description).length, `${locale} ${route.description}`).toBeLessThanOrEqual(200)
      }
      expect(message(locale, 'seo.noscript')).not.toBe('seo.noscript')
    }
  })
})

describe('the sitemap', () => {
  const locs = (xml: string) => [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(match => match[1])

  it('lists the pages of the index by their absolute canonical URL on the host', () => {
    const urls = locs(sitemapXml(DEFAULT_SITE_URL))
    expect(urls).toHaveLength(SEO_ROUTES.length)
    expect(urls).toContain('https://wetterdienst.eobs.org/')
    expect(urls).toContain('https://wetterdienst.eobs.org/explorer')
    expect(urls).toContain('https://wetterdienst.eobs.org/datenschutz')
    for (const url of urls)
      expect(url).toMatch(/^https:\/\/wetterdienst\.eobs\.org(?:\/[a-z]*)?$/)
  })

  it('lists neither the widget, nor the settings, nor an alias, nor a path of the API or the API reference', () => {
    const urls = locs(sitemapXml(DEFAULT_SITE_URL)).join('\n')
    for (const path of ['/widget', '/settings', '/privacy', '/docs', '/_swagger-ui', '/api/', '/mcp', '/openapi.json'])
      expect(urls, path).not.toContain(path)
    // `/api` is the page of the API's documentation, not an endpoint
    expect(urls).toContain('https://wetterdienst.eobs.org/api\n')
  })

  it('is a urlset of the sitemap protocol, and escapes nothing it has no need to', () => {
    const xml = sitemapXml(DEFAULT_SITE_URL)
    expect(xml.startsWith('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')).toBe(true)
    expect(xml.trimEnd().endsWith('</urlset>')).toBe(true)
  })

  it('takes the host from the setting, so an instance of its own names itself', () => {
    const urls = locs(sitemapXml('https://weather.example.org/'))
    expect(urls.map(url => new URL(url!).origin)).toEqual(urls.map(() => 'https://weather.example.org'))
    expect(urls[0]).toBe('https://weather.example.org/')
    expect(robotsTxt('https://weather.example.org/')).toContain('Sitemap: https://weather.example.org/sitemap.xml\n')
  })

  it('is well-formed XML with a host that holds characters XML reserves', () => {
    const xml = sitemapXml('https://a"b&c\'d.example')
    const urls = locs(xml)

    expect(urls[1]).toBe('https://a&quot;b&amp;c&apos;d.example/explorer')
    // every `&` starts an entity, and the entities read back as the host
    expect(xml).not.toMatch(/&(?!amp;|lt;|gt;|quot;|apos;)/)
    expect(urls[1]!.replaceAll('&quot;', '"').replaceAll('&apos;', '\'').replaceAll('&amp;', '&')).toBe('https://a"b&c\'d.example/explorer')
    expect(escapeXml('<a b="c">&\'')).toBe('&lt;a b=&quot;c&quot;&gt;&amp;&apos;')
  })

  it.each([undefined, '', 'not a url', 'ftp://example.org', 42])('falls back to the hosted instance for the setting %j', (value) => {
    expect(siteOrigin(value)).toBe(DEFAULT_SITE_URL)
  })
})

describe('robots.txt', () => {
  it('lets every crawler in, and names the sitemap', () => {
    const text = robotsTxt(DEFAULT_SITE_URL)
    expect(text).toMatch(/^User-agent: \*\nDisallow:\n/)
    expect(text).toContain('Sitemap: https://wetterdienst.eobs.org/sitemap.xml\n')
    // the pages draw nothing without /_nuxt and /api, and a crawler that runs scripts needs both
    expect(text).not.toMatch(/Disallow: \S/)
  })
})

describe('canonical links', () => {
  it('give a page its own address, and an alias the address of its page', () => {
    expect(canonicalUrl(DEFAULT_SITE_URL, '/about')).toBe('https://wetterdienst.eobs.org/about')
    expect(canonicalUrl(DEFAULT_SITE_URL, '/about/?x=1')).toBe('https://wetterdienst.eobs.org/about')
    expect(canonicalUrl(DEFAULT_SITE_URL, '/privacy')).toBe('https://wetterdienst.eobs.org/datenschutz')
    expect(canonicalUrl(DEFAULT_SITE_URL, '/')).toBe('https://wetterdienst.eobs.org/')
  })

  it('know the pages of the index, and the ones left out of it', () => {
    expect(findSeoRoute('/providers/')?.path).toBe('/providers')
    expect(findSeoRoute('/providers/dwd')).toBeUndefined()
    expect(findSeoRoute('/widget')).toBeUndefined()
    expect(isNotIndexed('/widget')).toBe(true)
    expect(isNotIndexed('/widget/?station=10381&theme=dark')).toBe(true)
    expect(isNotIndexed('/settings')).toBe(true)
    expect(isNotIndexed('/about')).toBe(false)
    // an inherited name is no page
    expect(isNotIndexed('/constructor')).toBe(false)
  })

  it('take /Widget for /widget, as the router does, and keep the canonical link in lower case', () => {
    expect(isNotIndexed('/Widget')).toBe(true)
    expect(isNotIndexed('/SETTINGS/')).toBe(true)
    expect(findSeoRoute('/ABOUT')?.path).toBe('/about')
    expect(findSeoRoute('/Privacy')?.path).toBe('/datenschutz')
    expect(canonicalUrl(DEFAULT_SITE_URL, '/ABOUT')).toBe('https://wetterdienst.eobs.org/about')
    expect(canonicalUrl(DEFAULT_SITE_URL, '/Privacy')).toBe('https://wetterdienst.eobs.org/datenschutz')

    const widget = seoHead('/Widget', 'en', DEFAULT_SITE_URL)
    expect(widget.noindex).toBe(true)
    expect(widget.tags).toContain('<meta name="robots" content="noindex">')
    expect(widget.tags).not.toContain('rel="canonical"')
    expect(seoHead('/ABOUT', 'en', DEFAULT_SITE_URL).tags).toContain('<link rel="canonical" href="https://wetterdienst.eobs.org/about">')
  })
})

describe('the tags of the shell', () => {
  const tag = (tags: string, pattern: RegExp) => pattern.exec(tags)?.[1]

  it('write the title, description, canonical link and the og and twitter tags of a page', () => {
    const head = seoHead('/about', 'de', DEFAULT_SITE_URL)

    expect(head.title).toBe('Über uns - Wetterdienst')
    expect(tag(head.tags, /<meta name="description" content="([^"]*)">/)).toBe(message('de', 'seo.pages.about'))
    expect(tag(head.tags, /<link rel="canonical" href="([^"]*)">/)).toBe('https://wetterdienst.eobs.org/about')
    expect(tag(head.tags, /<meta property="og:url" content="([^"]*)">/)).toBe('https://wetterdienst.eobs.org/about')
    expect(tag(head.tags, /<meta property="og:title" content="([^"]*)">/)).toBe('Über uns - Wetterdienst')
    expect(tag(head.tags, /<meta property="og:locale" content="([^"]*)">/)).toBe('de_DE')
    expect(tag(head.tags, /<meta property="og:image" content="([^"]*)">/)).toBe('https://wetterdienst.eobs.org/apple-touch-icon.png')
    expect(tag(head.tags, /<meta name="twitter:card" content="([^"]*)">/)).toBe('summary')
    expect(tag(head.tags, /<meta name="twitter:title" content="([^"]*)">/)).toBe('Über uns - Wetterdienst')
    expect(tag(head.tags, /<meta name="twitter:description" content="([^"]*)">/)).toBe(message('de', 'seo.pages.about'))
    expect(head.tags).not.toContain('noindex')
    expect(head.noindex).toBe(false)
  })

  it('name the site by the sentence that says what it is on the home page, and by its name after a page\'s', () => {
    expect(pageTitle('en', '/')).toBe('Wetterdienst – open weather and climate data from national weather services')
    expect(pageTitle('en', '/glossary')).toBe('Glossary - Wetterdienst')
    expect(pageTitle('de', '/datenschutz')).toBe('Datenschutz - Wetterdienst')
    expect(pageTitle('de', '/privacy')).toBe('Datenschutz - Wetterdienst')
  })

  it('ask for the widget and the settings to be left out of the index, and give them no canonical link', () => {
    for (const path of ['/widget', '/settings']) {
      const head = seoHead(path, 'en', DEFAULT_SITE_URL)
      expect(head.tags, path).toContain('<meta name="robots" content="noindex">')
      expect(head.tags, path).not.toContain('rel="canonical"')
      expect(head.noindex, path).toBe(true)
    }
  })

  it('tell a path that is no page as the site, with no canonical link that would name another page', () => {
    for (const path of ['/providers/dwd', '/nothing-here']) {
      const head = seoHead(path, 'en', DEFAULT_SITE_URL)
      expect(head.title, path).toBe(pageTitle('en', '/'))
      expect(head.tags, path).not.toContain('rel="canonical"')
      expect(head.tags, path).toContain(`content="${message('en', 'seo.description')}"`)
    }
  })

  it('escape what they are given', () => {
    // the path of the setting is dropped (only its origin is used); the title is the text of a page and is escaped
    const sections = { head: [] as string[], bodyPrepend: [] as string[], htmlAttrs: [] as string[] }
    applySeoHead(sections, { ...seoHead('/', 'en', 'https://example.org/"><script>'), title: 'a < b & "c"' })

    const written = sections.head.join('')
    expect(written).toContain('<title>a &lt; b &amp; &quot;c&quot;</title>')
    expect(written).not.toContain('<script>')
    expect(written).toContain('<link rel="canonical" href="https://example.org/">')
  })

  it('escape an origin that holds characters of markup: a host may have an ampersand, an apostrophe or a quotation mark', () => {
    // `new URL` accepts all three in a host and keeps them in `origin`
    const sections = { head: [] as string[], bodyPrepend: [] as string[], htmlAttrs: [] as string[] }
    applySeoHead(sections, seoHead('/about', 'en', 'https://a"b&c.example'))

    const written = sections.head.join('')
    expect(written).toContain('<link rel="canonical" href="https://a&quot;b&amp;c.example/about">')
    expect(written).toContain('<meta property="og:url" content="https://a&quot;b&amp;c.example/about">')
    expect(written).toContain('<meta property="og:image" content="https://a&quot;b&amp;c.example/apple-touch-icon.png">')
    // the host closes no attribute early: every quotation mark of the tags is one of a tag's own
    expect(written).not.toContain('a"b')
  })

  it('carry, for a browser without scripts, the name, the description and the links to the pages', () => {
    const { noscript } = seoHead('/about', 'en', DEFAULT_SITE_URL)

    expect(noscript.startsWith('<noscript>')).toBe(true)
    expect(noscript).toContain('<h1>About - Wetterdienst</h1>')
    expect(noscript).toContain(message('en', 'seo.pages.about'))
    expect(noscript).toContain(message('en', 'seo.noscript'))
    for (const route of SEO_ROUTES)
      expect(noscript, route.path).toContain(`<a href="${route.path}">`)
    expect(noscript).not.toContain('/widget')
  })

  it('go into the shell: the title of the app is replaced, the tags and the text are added, the language is set', () => {
    const sections = {
      head: ['<meta charset="utf-8"><title>Wetterdienst</title><link rel="icon" href="/icon.svg">'],
      bodyPrepend: [] as string[],
      htmlAttrs: [] as string[],
    }
    const head = seoHead('/about', 'en', DEFAULT_SITE_URL)

    applySeoHead(sections, head)

    const written = sections.head.join('')
    expect(written.match(/<title>/g)).toHaveLength(1)
    expect(written).toContain('<title>About - Wetterdienst</title>')
    expect(written).toContain('<link rel="icon" href="/icon.svg">')
    expect(written).toContain('<link rel="canonical" href="https://wetterdienst.eobs.org/about">')
    expect(sections.bodyPrepend).toEqual([head.noscript])
    expect(sections.htmlAttrs).toEqual(['lang="en"'])
  })

  it('go into a shell that has no title, and leave a language that is set', () => {
    const sections = { head: ['<meta charset="utf-8">'], bodyPrepend: [] as string[], htmlAttrs: ['lang="fr"'] }

    applySeoHead(sections, seoHead('/', 'de', DEFAULT_SITE_URL))

    expect(sections.head.join('')).toContain(`<title>${message('de', 'seo.title')}</title>`)
    expect(sections.htmlAttrs).toEqual(['lang="fr"'])
  })
})

describe('the language of the shell', () => {
  it('is the one the visitor chose, else English for a browser that asks for it first, else German', () => {
    expect(pickLocale('en', undefined)).toBe('en')
    expect(pickLocale('fr', 'en')).toBe('de')
    expect(pickLocale('de', 'en-GB,en;q=0.9')).toBe('de')
    expect(pickLocale(undefined, 'en-GB,en;q=0.9,de;q=0.8')).toBe('en')
    expect(pickLocale(undefined, 'en')).toBe('en')
    expect(pickLocale(undefined, 'de-DE,de;q=0.9,en;q=0.8')).toBe('de')
    expect(pickLocale(undefined, 'fr-FR')).toBe('de')
    // a weight on the first entry is not part of its tag
    expect(pickLocale(undefined, 'en;q=0.9')).toBe('en')
    expect(pickLocale(undefined, 'en;q=1.0,de;q=0.5')).toBe('en')
    expect(pickLocale(undefined, 'de;q=0.9')).toBe('de')
    expect(pickLocale(undefined, 'en-GB;q=0.8, de')).toBe('en')
    // a crawler sends neither
    expect(pickLocale(undefined, undefined)).toBe('de')
  })
})

describe('the plugin that writes the shell', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  async function render(path: string, options: { cookie?: string, acceptLanguage?: string, siteUrl?: string } = {}) {
    let hook: ((html: any, context: { event: any }) => void) | undefined
    const headers: Record<string, string> = {}
    vi.stubGlobal('defineNitroPlugin', (plugin: (app: any) => void) => plugin({ hooks: { hook: (name: string, fn: typeof hook) => name === 'render:html' && (hook = fn) } }))
    vi.stubGlobal('getCookie', () => options.cookie)
    vi.stubGlobal('getRequestHeader', (_event: unknown, name: string) => name === 'accept-language' ? options.acceptLanguage : undefined)
    vi.stubGlobal('useRuntimeConfig', () => ({ public: { siteUrl: options.siteUrl ?? DEFAULT_SITE_URL } }))
    vi.stubGlobal('appendResponseHeader', recordHeaders(headers))
    vi.stubGlobal('setResponseHeader', recordHeaders(headers))
    await import('../../server/plugins/seo-head')
    const html = { head: ['<title>Wetterdienst</title>'], bodyPrepend: [] as string[], htmlAttrs: [] as string[] }
    hook!(html, { event: { path } })
    return { html, headers }
  }

  it('answers the path with its own tags, and says that the answer depends on the cookie and the header', async () => {
    const { html, headers } = await render('/stripes?station=1048')

    expect(html.head.join('')).toContain('<title>Klimastreifen - Wetterdienst</title>')
    expect(html.head.join('')).toContain('<link rel="canonical" href="https://wetterdienst.eobs.org/stripes">')
    expect(html.htmlAttrs).toEqual(['lang="de"'])
    expect(headers.vary).toBe('Cookie, Accept-Language')
    expect(headers['x-robots-tag']).toBeUndefined()
  })

  it('answers in English where the visitor chose it, with the instance\'s own address', async () => {
    const { html } = await render('/', { cookie: 'en', siteUrl: 'https://weather.example.org' })

    expect(html.head.join('')).toContain('<title>Wetterdienst – open weather and climate data from national weather services</title>')
    expect(html.head.join('')).toContain('<link rel="canonical" href="https://weather.example.org/">')
    expect(html.htmlAttrs).toEqual(['lang="en"'])
  })

  it('asks, by header as well, for the widget to be left out of the index', async () => {
    const { html, headers } = await render('/widget?station=10381')

    expect(headers['x-robots-tag']).toBe('noindex')
    expect(html.head.join('')).toContain('<meta name="robots" content="noindex">')
  })

  it('does the same for the widget written /Widget, which the router shows as well', async () => {
    const { headers } = await render('/Widget')

    expect(headers['x-robots-tag']).toBe('noindex')
  })
})

describe('text files that are none', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  async function answer(path: string, method = 'GET') {
    vi.stubGlobal('defineEventHandler', (handler: unknown) => handler)
    vi.stubGlobal('createError', (options: { statusCode: number }) => Object.assign(new Error('error'), options))
    const { default: handler } = await import('../../server/middleware/text-files')
    try {
      return await (handler as unknown as (event: unknown) => unknown)({ path, method })
    }
    catch (error) {
      return error
    }
  }

  it.each(['/ads.txt', '/sitemap_index.xml', '/sitemap-0.xml', '/foo.xml', '/humans.txt', '/a/b/c.txt', '/Sitemap.XML', '/x.xml?y=1', '/_nuxt/x.txt'])('answers %s with a 404', async (path) => {
    expect(await answer(path)).toMatchObject({ statusCode: 404 })
    expect(await answer(path, 'HEAD')).toMatchObject({ statusCode: 404 })
  })

  it.each(['/sitemap.xml', '/robots.txt', '/third-party-licenses.txt', '/sitemap.xml?x=1', '/', '/about', '/explorer', '/api/values', '/openapi.json', '/icon.svg'])('lets %s through', async (path) => {
    expect(await answer(path)).toBeUndefined()
  })

  it('does not touch what is not asked for with GET or HEAD', async () => {
    expect(await answer('/ads.txt', 'POST')).toBeUndefined()
  })

  it('knows a text file by its ending', () => {
    expect(isTextFilePath('/a.xml')).toBe(true)
    expect(isTextFilePath('/a.txt?x=1')).toBe(true)
    expect(isTextFilePath('/a.html')).toBe(false)
    expect(isTextFilePath('/xml')).toBe(false)
    expect(isTextFilePath('/')).toBe(false)
  })
})

describe('the routes of sitemap.xml and robots.txt', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  async function serve(module: string, siteUrl: string) {
    const headers: Record<string, string> = {}
    vi.stubGlobal('defineEventHandler', (handler: unknown) => handler)
    vi.stubGlobal('useRuntimeConfig', () => ({ public: { siteUrl } }))
    vi.stubGlobal('setResponseHeader', recordHeaders(headers))
    const { default: handler } = await import(module)
    return { body: await (handler as (event: unknown) => unknown)({}), headers }
  }

  it('serve the sitemap as XML, with the address of the setting', async () => {
    const { body, headers } = await serve('../../server/routes/sitemap.xml', 'https://weather.example.org')
    expect(headers['content-type']).toBe('application/xml; charset=utf-8')
    expect(body).toBe(sitemapXml('https://weather.example.org'))
  })

  it('serve robots.txt as text, naming that sitemap', async () => {
    const { body, headers } = await serve('../../server/routes/robots.txt', 'https://weather.example.org')
    expect(headers['content-type']).toBe('text/plain; charset=utf-8')
    expect(body).toBe(robotsTxt('https://weather.example.org'))
    expect(String(body)).toContain('Sitemap: https://weather.example.org/sitemap.xml')
  })
})
