import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// What a search engine and a link preview are told (GH-3497): the sitemap and robots.txt, the tags the server writes
// into the shell, and the page taking those tags over once its script has run, with none of them twice. The shell and
// the files are read without a browser (what a crawler that runs no script gets); the takeover needs one.

const HOST = 'https://wetterdienst.eobs.org'
// a German browser: a request with no language at all is told in English (tests/e2e/seo-language.spec.ts)
const GERMAN = { 'Accept-Language': 'de-DE,de;q=0.9' }

test.describe('the files', () => {
  test('serves a sitemap of the public pages, as XML, and not the widget', async ({ request }) => {
    const response = await request.get('/sitemap.xml')
    expect(response.status()).toBe(200)
    expect(response.headers()['content-type']).toContain('application/xml')

    const body = await response.text()
    const locs = [...body.matchAll(/<loc>([^<]+)<\/loc>/g)].map(match => match[1])
    expect(locs).toContain(`${HOST}/`)
    expect(locs).toContain(`${HOST}/explorer`)
    expect(locs).toContain(`${HOST}/glossary`)
    expect(locs).toContain(`${HOST}/measurement`)
    expect(body).not.toContain('/widget')
    expect(body).not.toContain('/_swagger-ui')
  })

  test('names the sitemap in robots.txt', async ({ request }) => {
    const response = await request.get('/robots.txt')
    expect(response.status()).toBe(200)
    expect(response.headers()['content-type']).toContain('text/plain')
    expect(await response.text()).toContain(`Sitemap: ${HOST}/sitemap.xml`)
  })

  for (const path of ['/sitemap_index.xml', '/ads.txt', '/nothing.xml']) {
    test(`answers ${path} with a 404, not a 200 with the page`, async ({ request }) => {
      const response = await request.get(path)
      expect(response.status()).toBe(404)
    })
  }
})

test.describe('the shell', () => {
  test('carries the title, description, canonical link and social tags of the path, without a script', async ({ request }) => {
    const html = await (await request.get('/about', { headers: GERMAN })).text()

    expect(html).toContain('<title>Über uns - Wetterdienst</title>')
    expect(html).toMatch(/<meta name="description" content="[^"]+">/)
    expect(html).toContain(`href="${HOST}/about"`)
    expect(html).toContain('<meta property="og:title" content="Über uns - Wetterdienst">')
    expect(html).toContain('<meta name="twitter:card" content="summary">')
    expect(html).toContain('<noscript>')
    expect(html).toContain('<html lang="de"')
  })

  test('asks for the widget to be left out of the index, by tag and by header', async ({ request }) => {
    const response = await request.get('/widget')
    expect(response.headers()['x-robots-tag']).toBe('noindex')
    expect(await response.text()).toContain('<meta name="robots" content="noindex">')
  })
})

/** The tags that the server writes and the page sets, one list so that none can be forgotten */
const TAGS = [
  'meta[name="description"]',
  'link[rel="canonical"]',
  'meta[property="og:type"]',
  'meta[property="og:site_name"]',
  'meta[property="og:title"]',
  'meta[property="og:description"]',
  'meta[property="og:url"]',
  'meta[property="og:locale"]',
  'meta[property="og:image"]',
  'meta[name="twitter:card"]',
  'meta[name="twitter:title"]',
  'meta[name="twitter:description"]',
  'meta[name="twitter:image"]',
]

test.describe('the page taking the tags over', () => {
  async function counts(page: import('@playwright/test').Page, selectors: string[]) {
    return page.evaluate(list => list.map(selector => document.head.querySelectorAll(selector).length), selectors)
  }

  test('has each tag once after a direct load and after a client-side navigation', async ({ page, context, baseURL }) => {
    await mockBackend(page, baseURL!)
    await context.addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])

    await page.goto('/about')
    await page.waitForLoadState('networkidle')
    expect(await counts(page, TAGS)).toEqual(TAGS.map(() => 1))
    await expect(page).toHaveTitle('About - Wetterdienst')
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', `${HOST}/about`)

    await page.locator('a[href="/glossary"]:visible').first().click()
    await page.waitForURL('**/glossary')
    await expect(page).toHaveTitle('Glossary - Wetterdienst')
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', `${HOST}/glossary`)
    expect(await counts(page, TAGS)).toEqual(TAGS.map(() => 1))
    expect(await counts(page, ['title'])).toEqual([1])
    // nothing else of the server's is left beside them: the same number of tags of each family as of the list
    expect(await counts(page, ['meta[property^="og:"]', 'meta[name^="twitter:"]'])).toEqual([
      TAGS.filter(tag => tag.includes('og:')).length,
      TAGS.filter(tag => tag.includes('twitter:')).length,
    ])
    // and they say what the page they are on says, not what the page before did
    await expect(page.locator('meta[property="og:title"]')).toHaveAttribute('content', 'Glossary - Wetterdienst')
    await expect(page.locator('meta[name="twitter:title"]')).toHaveAttribute('content', 'Glossary - Wetterdienst')
    await expect(page.locator('meta[property="og:url"]')).toHaveAttribute('content', `${HOST}/glossary`)
  })

  test('drops the noindex of the shell when the visitor leaves a page that had it', async ({ page, context, baseURL }) => {
    await mockBackend(page, baseURL!)
    await context.addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])

    await page.goto('/settings')
    await page.waitForLoadState('networkidle')
    expect(await counts(page, ['meta[name="robots"]', 'link[rel="canonical"]'])).toEqual([1, 0])

    await page.locator('a[href="/about"]').first().click()
    await page.waitForURL('**/about')
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', `${HOST}/about`)
    expect(await counts(page, ['meta[name="robots"]'])).toEqual([0])
  })
})

// The page of each provider of the backend (GH-4119): the server reads the list from the backend (the one this suite
// runs against) for the shell and the sitemap, so the pages are those of `GET /api/providers`, whichever they are.
test.describe('the pages of the providers', () => {
  const escape = (text: string) => text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;')
  const pattern = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

  test('has a title, a description, a canonical link and a sitemap entry of its own for every provider', async ({ request }) => {
    const { providers } = await (await request.get('/api/providers')).json() as { providers: { provider: string, name_english: string }[] }
    const sitemap = await (await request.get('/sitemap.xml')).text()
    const home = await (await request.get('/', { headers: GERMAN })).text()
    expect(providers.length).toBeGreaterThan(0)

    for (const { provider, name_english: name } of providers) {
      expect(sitemap, provider).toContain(`<loc>${HOST}/providers/${provider}</loc>`)
      const response = await request.get(`/providers/${provider}`, { headers: GERMAN })
      expect(response.status(), provider).toBe(200)
      const html = await response.text()
      expect(html, provider).toContain(`<title>${escape(name)} - Wetterdienst</title>`)
      expect(html, provider).toContain(`rel="canonical" href="${HOST}/providers/${provider}">`)
      expect(html, provider).toContain(`<meta property="og:url" content="${HOST}/providers/${provider}">`)
      expect(html, provider).toContain(`<meta property="og:title" content="${escape(name)} - Wetterdienst">`)
      expect(html, provider).toMatch(new RegExp(`<meta name="description" content="${pattern(escape(name))} \\([^"]+\\) bei Wetterdienst: [^"]+">`))
      // none of them is the home page's head
      expect(html, provider).not.toContain(home.match(/<meta name="description" content="([^"]*)">/)![0])
    }
  })

  test('says its sentence in English where the visitor asks for it', async ({ request }) => {
    const html = await (await request.get('/providers/dwd', { headers: { cookie: 'wd_lang=en' } })).text()

    expect(html).toMatch(/<meta name="description" content="[^"]+ \([^"]+\) on Wetterdienst: [^"]+, with licence and credit line\./)
    expect(html).toContain('<html lang="en"')
  })

  test('keeps an id the backend does not have out of the sitemap and tells it as the site, as before', async ({ request }) => {
    const sitemap = await (await request.get('/sitemap.xml')).text()
    const response = await request.get('/providers/nowhere-at-all')
    const html = await response.text()

    expect(sitemap).not.toContain('nowhere-at-all')
    expect(response.status()).toBe(200)
    expect(html).not.toContain('rel="canonical"')
    expect(html).toContain('<title>Wetterdienst – ')
  })

  test('is taken over by the page with each tag once, and the title of the provider', async ({ page, context, baseURL }) => {
    await mockBackend(page, baseURL!)
    await context.addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])

    await page.goto('/providers/dwd')
    await page.waitForLoadState('networkidle')

    await expect(page).toHaveTitle('German Weather Service - Wetterdienst')
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', `${HOST}/providers/dwd`)
    await expect(page.locator('meta[property="og:url"]')).toHaveAttribute('content', `${HOST}/providers/dwd`)
    await expect(page.locator('meta[name="description"]')).toHaveAttribute('content', /^German Weather Service \(Germany\) on Wetterdienst: /)
    const selectors = [...TAGS, 'title']
    const counts = await page.evaluate(list => list.map(selector => document.head.querySelectorAll(selector).length), selectors)
    expect(counts).toEqual(selectors.map(() => 1))
  })
})
