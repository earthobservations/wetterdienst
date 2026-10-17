import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// Nothing the app runs comes from another origin (GH-3094): the SQL panel's DuckDB-wasm and the `/docs` page's
// Swagger UI are files of the app, and the Content Security Policy allows no CDN. Both are used here for real,
// in a browser that holds the app to its policy, and every request that leaves the origin is a failure.

// The icons are fetched from Iconify at run time (no icon set is installed to serve them): they are data, GH-3111
const ICON_API = 'https://api.iconify.design'

/** What a page asks for beyond its own origin, and what its Content Security Policy refused */
function watch(page: Page, origin: string) {
  const foreign: string[] = []
  page.on('request', (request) => {
    const url = request.url()
    if (new URL(url).origin !== origin && !url.startsWith('data:') && !url.startsWith('blob:') && request.resourceType() !== 'image' && !url.startsWith(`${ICON_API}/`))
      foreign.push(url)
  })
  return {
    foreign,
    refused: () => page.evaluate(() => (window as unknown as { __csp?: string[] }).__csp ?? []),
  }
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (event) => {
      const w = window as unknown as { __csp?: string[] }
      ;(w.__csp ??= []).push(`${event.violatedDirective}: ${event.blockedURI} ${event.sourceFile}:${event.lineNumber} ${event.sample}`)
    })
  })
})

test.describe('Swagger UI on /docs', () => {
  test('lists the API from the app\'s own files, with no request to another origin', async ({ page, baseURL }) => {
    const seen = watch(page, new URL(baseURL!).origin)
    await page.goto('/docs')

    await expect(page.locator('.swagger-ui .opblock').first()).toBeVisible()
    expect(await page.locator('.swagger-ui .opblock').count()).toBeGreaterThan(5)
    expect(seen.foreign).toEqual([])
    expect(await seen.refused()).toEqual([])
  })

  test('answers the page with a policy of its own', async ({ request }) => {
    const response = await request.get('/docs')
    const policy = response.headers()['content-security-policy']

    expect(policy).toContain('default-src \'none\'')
    expect(policy).not.toMatch(/jsdelivr|unsafe-eval/)
    const html = await response.text()
    expect(html).toContain('/_swagger-ui/swagger-ui-bundle.js')
    expect(html).not.toContain('jsdelivr')
  })
})

test.describe('the SQL panel', () => {
  test('runs a query in DuckDB-wasm served by the app, under the app\'s policy', async ({ page, baseURL }) => {
    const origin = new URL(baseURL!).origin
    const seen = watch(page, origin)
    // the panel's texts are looked for in English
    await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: origin }])
    const workers: string[] = []
    page.on('worker', worker => workers.push(worker.url()))
    await mockBackend(page, baseURL!)

    await page.goto('/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m,temperature_air_mean_2m&mode=station&stations=00011')
    await page.getByRole('button', { name: 'Show', exact: true }).click()
    await expect(page.getByRole('table').first()).toBeVisible()

    await page.getByRole('button', { name: 'Transform with SQL Query' }).click()
    await page.getByPlaceholder('Enter your SQL query here...').fill('SELECT * FROM data LIMIT 1')
    await page.getByRole('button', { name: 'Run Query' }).click()

    await expect(page.getByText('Query executed successfully: 1 row(s) returned')).toBeVisible({ timeout: 60_000 })
    expect(workers).toHaveLength(1)
    expect(new URL(workers[0]!).origin).toBe(origin)
    expect(seen.foreign).toEqual([])
    expect(await seen.refused()).toEqual([])
  })
})
