import type { SeoProvider } from '../../shared/utils/seo'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { message, pageTitle, seoHead } from '../../server/utils/seoHead'
import { FRESH_MS, loadProviders, resetProviders, RETRY_MS } from '../../server/utils/seoProviders'
import {
  DEFAULT_SITE_URL,
  findProvider,
  findSeoRoute,
  providerIdOfPath,
  providerIds,
  providerSeoText,
  SEO_ROUTES,
  sitemapXml,
} from '../../shared/utils/seo'

// The pages of the providers (GH-4119): `/providers/<id>` for each provider the backend lists gets a head of its own
// and an entry in the sitemap, built from that list, and falls back to what the paths had before where the list is not
// known or does not have the id. The fixed pages are tests/unit/seo.test.ts.

const APP = join(__dirname, '..', '..')

/** The providers of the backend, as far as the head reads them: `GET /api/providers`, cut to what it needs. */
const PROVIDERS: SeoProvider[] = [
  { provider: 'dwd', name_english: 'German Weather Service', country: 'Germany', country_code: 'DE', networks: [{ kind: 'observation' }, { kind: 'forecast' }, { kind: 'observation' }, { kind: 'derived' }] },
  { provider: 'metoffice', name_english: 'Met Office', country: 'United Kingdom', country_code: 'GB', networks: [{ kind: 'observation' }] },
  { provider: 'portugal_x', name_english: 'Portuguese Institute for Sea and Atmosphere & more', country: 'Portugal', country_code: 'PT', networks: [{ kind: 'observation' }, { kind: 'forecast' }, { kind: 'derived' }, { kind: 'radar' }, { kind: 'alerts' }] },
  { provider: 'world', name_english: 'World Service', country: '', country_code: null, networks: [{ kind: 'observation' }] },
]

/** What `GET /api/providers` answers. */
function providersAnswer(providers: unknown[] = PROVIDERS): Response {
  return new Response(JSON.stringify({ metadata: {}, providers }), { status: 200, headers: { 'content-type': 'application/json' } })
}

const ok = () => Promise.resolve(providersAnswer())
const down = () => Promise.reject(new TypeError('fetch failed'))
const locs = (xml: string) => [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(match => match[1])

describe('the page of a provider', () => {
  const tag = (tags: string, pattern: RegExp) => pattern.exec(tags)?.[1]
  const description = (tags: string) => tag(tags, /<meta name="description" content="([^"]*)">/)

  it('knows a path of its page, lower case as the page reads it, and no other', () => {
    expect(providerIdOfPath('/providers/dwd')).toBe('dwd')
    expect(providerIdOfPath('/providers/DWD/')).toBe('dwd')
    expect(providerIdOfPath('/providers/dwd?x=1')).toBe('dwd')
    for (const path of ['/providers', '/providers/', '/providers/dwd/x', '/provider/dwd', '/providers/..', '/providers/%3Cb%3E', '/about'])
      expect(providerIdOfPath(path), path).toBeUndefined()
    // the page of a provider is none of the fixed pages
    expect(findSeoRoute('/providers/dwd')).toBeUndefined()
  })

  it('finds the provider of the list, and not an id it does not have', () => {
    expect(findProvider('/providers/dwd', PROVIDERS)?.name_english).toBe('German Weather Service')
    expect(findProvider('/providers/Metoffice', PROVIDERS)?.provider).toBe('metoffice')
    expect(findProvider('/providers/nothing', PROVIDERS)).toBeUndefined()
    expect(findProvider('/providers/dwd', [])).toBeUndefined()
    // an inherited name is no provider
    expect(findProvider('/providers/constructor', PROVIDERS)).toBeUndefined()
  })

  it.each(['de', 'en'] as const)('gets a title, a description, a canonical link and the og and twitter tags of its own in %s', (locale) => {
    const head = seoHead('/providers/dwd', locale, DEFAULT_SITE_URL, PROVIDERS)
    const country = locale === 'de' ? 'Deutschland' : 'Germany'
    const kinds = locale === 'de' ? 'Messwerte, Vorhersagen und Abgeleitete Daten' : 'Measurements, Forecasts, and Derived data'

    // the provider keeps its name in the title, and each kind is named once however many networks it has
    expect(head.title).toBe('German Weather Service - Wetterdienst')
    const text = description(head.tags)!
    expect(text).toContain(`German Weather Service (${country})`)
    expect(text).toContain(kinds)
    expect(text).not.toContain('{')
    expect(text).not.toBe(message(locale, 'seo.description'))
    expect(tag(head.tags, /<link rel="canonical" href="([^"]*)">/)).toBe('https://wetterdienst.eobs.org/providers/dwd')
    expect(tag(head.tags, /<meta property="og:url" content="([^"]*)">/)).toBe('https://wetterdienst.eobs.org/providers/dwd')
    expect(tag(head.tags, /<meta property="og:title" content="([^"]*)">/)).toBe(head.title)
    expect(tag(head.tags, /<meta property="og:description" content="([^"]*)">/)).toBe(text)
    expect(tag(head.tags, /<meta name="twitter:title" content="([^"]*)">/)).toBe(head.title)
    expect(tag(head.tags, /<meta name="twitter:description" content="([^"]*)">/)).toBe(text)
    expect(tag(head.tags, /<meta property="og:locale" content="([^"]*)">/)).toBe(locale === 'de' ? 'de_DE' : 'en_GB')
    expect(head.tags).not.toContain('noindex')
    expect(head.noindex).toBe(false)
    expect(head.noscript).toContain('<h1>German Weather Service - Wetterdienst</h1>')
    expect(pageTitle(locale, '/providers/dwd', PROVIDERS)).toBe(head.title)
  })

  it('says its sentence in the language of the visitor, and keeps the provider\'s name', () => {
    expect(description(seoHead('/providers/dwd', 'de', DEFAULT_SITE_URL, PROVIDERS).tags))
      .toBe('German Weather Service (Deutschland) bei Wetterdienst: Messwerte, Vorhersagen und Abgeleitete Daten, mit Lizenz und Quellenangabe. Im Explorer oder über die REST-API öffnen.')
    expect(description(seoHead('/providers/metoffice', 'en', DEFAULT_SITE_URL, PROVIDERS).tags))
      .toBe('Met Office (United Kingdom) on Wetterdienst: Measurements, with licence and credit line. Open it in the Explorer or via the REST API.')
  })

  it('names itself by its canonical path whatever the case of the request', () => {
    const head = seoHead('/Providers/DWD/', 'en', DEFAULT_SITE_URL, PROVIDERS)
    expect(tag(head.tags, /<link rel="canonical" href="([^"]*)">/)).toBe('https://wetterdienst.eobs.org/providers/dwd')
  })

  it('leaves out the country of a provider that has none, and escapes the name', () => {
    const head = seoHead('/providers/world', 'en', DEFAULT_SITE_URL, PROVIDERS)
    expect(description(head.tags)).toMatch(/^World Service on Wetterdienst: Measurements,/)

    const amp = seoHead('/providers/portugal_x', 'en', DEFAULT_SITE_URL, PROVIDERS)
    expect(amp.title).toBe('Portuguese Institute for Sea and Atmosphere & more - Wetterdienst')
    expect(amp.tags).toContain('content="Portuguese Institute for Sea and Atmosphere &amp; more - Wetterdienst"')
    expect(amp.noscript).toContain('<h1>Portuguese Institute for Sea and Atmosphere &amp; more - Wetterdienst</h1>')
  })

  it.each(['de', 'en'] as const)('keeps its description to what a search engine shows, for the longest name and the most kinds of the backend in %s', (locale) => {
    // the backend's longest name (SMHI) and the provider with the most kinds of network (DWD), as `GET /api/providers` has them
    const longest: SeoProvider = { provider: 'smhi', name_english: 'Swedish Meteorological and Hydrological Institute', country: 'Sweden', country_code: 'SE', networks: [{ kind: 'observation' }] }
    const manyKinds: SeoProvider = { ...PROVIDERS[0]!, networks: ['observation', 'forecast', 'derived', 'radar', 'alerts'].map(kind => ({ kind })) }
    const translate = (key: string, values?: Record<string, string>) =>
      message(locale, key).replace(/\{(\w+)\}/g, (_, name: string) => values?.[name] ?? '')
    for (const provider of [longest, manyKinds])
      expect(providerSeoText(provider, locale, translate).description.length, provider.provider).toBeLessThanOrEqual(200)
  })

  it('tells the page of an id the list does not have, or no list at all, as it did: the site, with no canonical link', () => {
    for (const providers of [PROVIDERS, []]) {
      const head = seoHead('/providers/nothing', 'en', DEFAULT_SITE_URL, providers)
      expect(head.title).toBe(pageTitle('en', '/'))
      expect(head.tags).not.toContain('rel="canonical"')
      expect(head.tags).not.toContain('og:url')
      expect(head.tags).toContain(`content="${message('en', 'seo.description')}"`)
    }
    expect(seoHead('/providers/dwd', 'en', DEFAULT_SITE_URL).tags).not.toContain('rel="canonical"')
    // the page of the list of providers is a page of the index, and is not changed
    expect(seoHead('/providers', 'en', DEFAULT_SITE_URL, PROVIDERS).title).toBe('Providers - Wetterdienst')
  })

  it('has a description in every language of the app, with its two slots', () => {
    const directory = join(APP, 'i18n', 'locales')
    const names = readdirSync(directory).filter(name => name.endsWith('.json'))
    expect(names.length).toBeGreaterThan(2)
    for (const name of names) {
      const text = JSON.parse(readFileSync(join(directory, name), 'utf8')).seo.providerDescription as string
      expect(text, name).toContain('{provider}')
      expect(text, name).toContain('{kinds}')
    }
  })
})

describe('the list of providers of the head and the sitemap', () => {
  const T0 = 1_000_000
  const BACKEND = 'http://backend.test/api'

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    resetProviders()
  })

  /** A backend whose calls are answered by each of `answers` in turn, the last one for the rest. */
  function backend(...answers: (() => Promise<Response>)[]) {
    resetProviders()
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    let call = 0
    const fetch = vi.fn((..._args: unknown[]) => answers[Math.min(call++, answers.length - 1)]!())
    vi.stubGlobal('fetch', fetch)
    return fetch
  }

  it('is the backend\'s `/providers`, read once and kept for an hour', async () => {
    const fetch = backend(ok)

    const first = await loadProviders(BACKEND, T0)
    expect(first).toEqual(PROVIDERS)
    await loadProviders(BACKEND, T0 + 1000)
    await loadProviders(BACKEND, T0 + FRESH_MS - 1)

    expect(fetch).toHaveBeenCalledTimes(1)
    expect(String(fetch.mock.calls[0]![0])).toBe('http://backend.test/api/providers')
  })

  it('answers with the list it has at once when the hour is over, and reads the next in the background', async () => {
    const fetch = backend(ok, () => Promise.resolve(providersAnswer([PROVIDERS[1]])))
    await loadProviders(BACKEND, T0)

    expect(await loadProviders(BACKEND, T0 + FRESH_MS)).toHaveLength(PROVIDERS.length)
    expect(fetch).toHaveBeenCalledTimes(2)
    await vi.waitFor(async () => expect(await loadProviders(BACKEND, T0 + FRESH_MS + 1)).toHaveLength(1))
  })

  it('shares one call between requests that come while it is made', async () => {
    const fetch = backend(ok)
    const lists = await Promise.all([loadProviders(BACKEND, T0), loadProviders(BACKEND, T0), loadProviders(BACKEND, T0)])

    expect(fetch).toHaveBeenCalledTimes(1)
    for (const list of lists)
      expect(list).toHaveLength(PROVIDERS.length)
  })

  it('is empty, and not an error, where the backend is down, and does not ask again until a while has passed', async () => {
    const fetch = backend(down, ok)

    expect(await loadProviders(BACKEND, T0)).toEqual([])
    expect(await loadProviders(BACKEND, T0 + RETRY_MS - 1)).toEqual([])
    expect(fetch).toHaveBeenCalledTimes(1)

    // the next time, and the backend is back: the first list is waited for
    expect(await loadProviders(BACKEND, T0 + RETRY_MS)).toHaveLength(PROVIDERS.length)
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('keeps the list it has when a later call fails', async () => {
    backend(ok, down)
    await loadProviders(BACKEND, T0)

    expect(await loadProviders(BACKEND, T0 + FRESH_MS)).toHaveLength(PROVIDERS.length)
    await vi.waitFor(() => expect(console.warn).toHaveBeenCalled())
    expect(await loadProviders(BACKEND, T0 + FRESH_MS + 1)).toHaveLength(PROVIDERS.length)
  })

  it.each([
    ['an error status', () => Promise.resolve(new Response('{}', { status: 503 }))],
    ['a page of HTML', () => Promise.resolve(new Response('<html></html>', { status: 200, headers: { 'content-type': 'text/html' } }))],
    ['an answer that is no list', () => Promise.resolve(new Response(JSON.stringify({ providers: 'x' }), { status: 200 }))],
    ['an empty list', () => Promise.resolve(providersAnswer([]))],
  ])('does not take %s for a list', async (_name, answer) => {
    backend(answer)
    expect(await loadProviders(BACKEND, T0)).toEqual([])
  })

  it('does not take a row for a provider that has not its fields', async () => {
    backend(() => Promise.resolve(providersAnswer([null, 'x', { provider: 'dwd' }, PROVIDERS[1]])))
    expect((await loadProviders(BACKEND, T0)).map(provider => provider.provider)).toEqual(['metoffice'])
  })

  it('gives up on a backend that does not answer, and never waits longer than its limit', async () => {
    // a call that is ended by the signal it is given, as a real one is
    const fetch = backend(down)
    fetch.mockImplementation((_url: unknown, init?: unknown) => new Promise<Response>((_resolve, reject) => {
      (init as RequestInit).signal!.addEventListener('abort', () => reject(new DOMException('timed out', 'TimeoutError')))
    }))
    const started = Date.now()

    expect(await loadProviders(BACKEND, T0)).toEqual([])
    expect(Date.now() - started).toBeLessThan(5000)
  }, 10_000)
})

describe('the sitemap of the providers', () => {
  it('lists the page of each provider after the fixed pages, by its canonical URL', () => {
    const urls = locs(sitemapXml(DEFAULT_SITE_URL, providerIds(PROVIDERS)))

    expect(urls).toHaveLength(SEO_ROUTES.length + PROVIDERS.length)
    expect(urls.slice(0, SEO_ROUTES.length)).toEqual(locs(sitemapXml(DEFAULT_SITE_URL)))
    for (const provider of PROVIDERS)
      expect(urls).toContain(`https://wetterdienst.eobs.org/providers/${provider.provider}`)
    expect(new Set(urls).size).toBe(urls.length)
  })

  it('has the fixed pages where there is no list, and the address of the setting for the others', () => {
    expect(locs(sitemapXml(DEFAULT_SITE_URL))).toHaveLength(SEO_ROUTES.length)
    expect(locs(sitemapXml('https://weather.example.org/', ['dwd']))).toContain('https://weather.example.org/providers/dwd')
  })

  it('lists no id that cannot be a path', () => {
    expect(locs(sitemapXml(DEFAULT_SITE_URL, ['dwd', '../x', 'a b', '<b>', '', 'A']))).toHaveLength(SEO_ROUTES.length + 1)
    expect(providerIds([...PROVIDERS, { ...PROVIDERS[0]!, provider: '../x' }])).toEqual(['dwd', 'metoffice', 'portugal_x', 'world'])
  })
})

describe('the route of sitemap.xml', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    vi.resetModules()
  })

  async function serve(backend: () => Promise<Response>) {
    // a list of its own: the process keeps the one it has read
    vi.resetModules()
    const headers: Record<string, string> = {}
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.stubGlobal('defineEventHandler', (handler: unknown) => handler)
    vi.stubGlobal('useRuntimeConfig', () => ({ public: { siteUrl: 'https://weather.example.org' }, apiBase: 'http://backend.test/api' }))
    vi.stubGlobal('setResponseHeader', (_event: unknown, name: string, value: string) => {
      headers[name] = value
    })
    vi.stubGlobal('fetch', vi.fn(backend))
    const { default: handler } = await import('../../server/routes/sitemap.xml')
    return { body: String(await (handler as unknown as (event: unknown) => unknown)({})), headers }
  }

  it('has a page for each provider of the backend, so a provider it gains is in it with no edit', async () => {
    const { body, headers } = await serve(ok)

    expect(body).toBe(sitemapXml('https://weather.example.org', providerIds(PROVIDERS)))
    expect(locs(body)).toHaveLength(SEO_ROUTES.length + PROVIDERS.length)
    expect(locs(body)).toContain('https://weather.example.org/providers/dwd')
    expect(headers['cache-control']).toBe('public, max-age=3600')

    const more = await serve(() => Promise.resolve(providersAnswer([...PROVIDERS, { ...PROVIDERS[0], provider: 'newcomer' }])))
    expect(locs(more.body)).toContain('https://weather.example.org/providers/newcomer')
  })

  it('has the fixed pages alone, and is asked for again soon, where the backend cannot be reached', async () => {
    const { body, headers } = await serve(down)

    expect(body).toBe(sitemapXml('https://weather.example.org'))
    expect(locs(body)).toHaveLength(SEO_ROUTES.length)
    expect(headers['cache-control']).toBe('public, max-age=60')
  })
})

describe('the plugin that writes the shell, on the page of a provider', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    vi.resetModules()
  })

  async function render(path: string, backend: () => Promise<Response> = ok) {
    let hook: ((html: unknown, context: { event: unknown }) => Promise<void>) | undefined
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.stubGlobal('defineNitroPlugin', (plugin: (app: unknown) => void) => plugin({ hooks: { hook: (name: string, fn: typeof hook) => name === 'render:html' && (hook = fn) } }))
    vi.stubGlobal('getCookie', () => 'en')
    vi.stubGlobal('getRequestHeader', () => undefined)
    vi.stubGlobal('useRuntimeConfig', () => ({ public: { siteUrl: DEFAULT_SITE_URL }, apiBase: 'http://backend.test/api' }))
    vi.stubGlobal('appendResponseHeader', () => {})
    vi.stubGlobal('setResponseHeader', () => {})
    const fetch = vi.fn(backend)
    vi.stubGlobal('fetch', fetch)
    await import('../../server/plugins/seo-head')
    const html = { head: ['<title>Wetterdienst</title>'], bodyPrepend: [] as string[], htmlAttrs: [] as string[] }
    await hook!(html, { event: { path } })
    return { written: html.head.join(''), fetch }
  }

  it('writes the head of the provider', async () => {
    const { written, fetch } = await render('/providers/dwd')

    expect(written).toContain('<title>German Weather Service - Wetterdienst</title>')
    expect(written).toContain('<link rel="canonical" href="https://wetterdienst.eobs.org/providers/dwd">')
    expect(written).toContain('German Weather Service (Germany) on Wetterdienst: Measurements, Forecasts, and Derived data')
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(String(fetch.mock.calls[0]![0])).toBe('http://backend.test/api/providers')
  })

  it('writes the head of the site for an id the backend does not have', async () => {
    const { written } = await render('/providers/nothing')

    expect(written).toContain(`<title>${message('en', 'seo.title')}</title>`)
    expect(written).not.toContain('rel="canonical"')
  })

  it('writes the head of the site where the backend is down', async () => {
    const { written } = await render('/providers/dwd', down)

    expect(written).toContain(`<title>${message('en', 'seo.title')}</title>`)
    expect(written).not.toContain('rel="canonical"')
  })

  it.each(['/', '/about', '/providers', '/providers/dwd/x', '/stripes?station=1048'])('does not ask the backend for %s', async (path) => {
    const { fetch } = await render(path)
    expect(fetch).not.toHaveBeenCalled()
  })
})
