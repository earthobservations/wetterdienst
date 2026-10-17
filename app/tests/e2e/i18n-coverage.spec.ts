import { readFileSync } from 'node:fs'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

// What the backend serves and what the app can name, checked against each other.
//
// The app labels every canonical parameter and every unit type in eleven languages (the providers
// on its home page are the backend's own list, and the last test below holds the page to it).
// Nothing in the app's own unit tests can notice when one of those is added upstream: they read the catalogs and hold the locales to each other, so a new
// name in the backend leaves every catalog untouched, the parity green, and the name falling back
// to a prettified English id in all eleven languages.
//
// That direction is checked here rather than from the Python suite, which has no business reading
// `app/`. The E2E workflow's path filter already covers `src/wetterdienst/**` for the same reason
// this test exists -- the suite runs the app against a backend started from there -- so a change
// that adds a parameter runs this.

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:7890'

const glossaryEn = fileURLToPath(new URL('../../i18n/glossary/en.ts', import.meta.url))
const localeEn = fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url))

interface GlossaryEntry { name: string, unit_type: string }

/** The keys of one `export const <name>` record in a glossary module. */
function glossaryKeys(name: string): Set<string> {
  const source = readFileSync(glossaryEn, 'utf-8')
  const block = source.split(`export const ${name}`)[1]?.split('export const')[0] ?? ''
  return new Set([...block.matchAll(/^ {2}'?([a-z0-9_]+)'?:/gm)].map(match => match[1] as string))
}

/** `energy_per_area` -> `unitEnergyPerArea`, the key `useUnitTypeLabel` builds. */
function settingsKey(type: string): string {
  return `unit${type.replace(/(?:^|_)(\w)/g, (_, c: string) => c.toUpperCase())}`
}

// the first call of a run pays for whatever the endpoint has to build before it can answer, and
// `/api/coverage` walks every provider in the registry -- seconds warm, and the CI cache is cold.
// It checks no credential over the network (GH-2564, GH-2641)
//
// the test's own budget has to be raised with it: the request allowance cannot outlast the test
// holding it, and the config sets no `timeout` of its own, so every test here had Playwright's
// thirty seconds however long a request was allowed to wait
const SLOW = { timeout: 120_000 }

test.describe.configure({ timeout: 150_000 })

async function glossary(request: { get: (url: string, options?: object) => Promise<{ ok: () => boolean, json: () => Promise<unknown> }> }) {
  const response = await request.get(`${BACKEND_URL}/api/glossary`, SLOW)
  expect(response.ok(), 'the backend did not serve /api/glossary').toBeTruthy()
  return await response.json() as GlossaryEntry[]
}

test.describe('the app can name what the backend serves', () => {
  test('every canonical parameter has a label', async ({ request }) => {
    const served = new Set((await glossary(request)).map(entry => entry.name))
    expect(served.size, 'the glossary came back empty').toBeGreaterThan(0)
    const labelled = glossaryKeys('parameters')

    // named rather than asserted on directly: comparing the sets prints both of them, which buries
    // the one name that differs among five hundred that do not
    const unlabelled = [...served].filter(name => !labelled.has(name)).sort()
    const stale = [...labelled].filter(name => !served.has(name)).sort()
    expect(unlabelled, 'canonical parameters with no app label -- add them to i18n/glossary/*.ts').toEqual([])
    expect(stale, 'app labels for parameters the backend no longer serves').toEqual([])
  })

  test('every unit type has a label', async ({ request }) => {
    const served = [...new Set((await glossary(request)).map(entry => entry.unit_type))].sort()
    expect(served.length, 'no unit types came back').toBeGreaterThan(0)
    const settings = JSON.parse(readFileSync(localeEn, 'utf-8')).settings ?? {}

    const missing = served.filter(type => !settings[settingsKey(type)]?.trim())
    expect(missing, 'unit types with no app label -- add settings.unit* to i18n/locales/*.json').toEqual([])
  })

  // The resolutions and datasets of every network, by the networks that serve them. The coverage of
  // a network is metadata the backend holds, so asking for all of them downloads nothing. A network
  // without timeseries (radar, alerts) has none to answer with.
  async function served(request: { get: (url: string, options?: object) => Promise<{ ok: () => boolean, status: () => number, json: () => Promise<unknown> }> }) {
    const providers = await (await request.get(`${BACKEND_URL}/api/coverage`, SLOW)).json() as Record<string, Record<string, unknown>>
    const resolutions = new Map<string, string[]>()
    const datasets = new Map<string, string[]>()
    for (const [provider, networks] of Object.entries(providers)) {
      for (const network of Object.keys(networks)) {
        const response = await request.get(`${BACKEND_URL}/api/coverage?provider=${provider}&network=${network}`, SLOW)
        // radar and alerts are no timeseries networks and answer 404; any other failure is a failure
        if (response.status() === 404)
          continue
        expect(response.ok(), `the backend did not serve the coverage of ${provider}/${network}`).toBeTruthy()
        const coverage = await response.json() as Record<string, { datasets: Record<string, unknown> }>
        for (const [resolution, { datasets: named }] of Object.entries(coverage)) {
          resolutions.set(resolution, [...resolutions.get(resolution) ?? [], `${provider}/${network}`])
          for (const dataset of Object.keys(named))
            datasets.set(dataset, [...datasets.get(dataset) ?? [], `${provider}/${network}/${resolution}`])
        }
      }
    }
    return { resolutions, datasets }
  }

  test('every resolution has a label', async ({ request }) => {
    const { resolutions } = await served(request)
    expect(resolutions.size, 'no resolutions came back').toBeGreaterThan(0)
    const labelled = glossaryKeys('resolutions')

    const unlabelled = [...resolutions.keys()].filter(name => !labelled.has(name)).sort()
    const stale = [...labelled].filter(name => !resolutions.has(name)).sort()
    expect(unlabelled, 'resolutions with no app label -- add them to i18n/glossary/*.ts').toEqual([])
    expect(stale, 'app labels for resolutions no network serves').toEqual([])
  })

  test('every dataset has a label', async ({ request }) => {
    const { datasets } = await served(request)
    expect(datasets.size, 'no datasets came back').toBeGreaterThan(0)
    const labelled = glossaryKeys('datasets')

    const unlabelled = [...datasets.keys()].filter(name => !labelled.has(name)).sort()
    const stale = [...labelled].filter(name => !datasets.has(name)).sort()
    expect(unlabelled, 'datasets with no app label -- add them to i18n/glossary/*.ts').toEqual([])
    expect(stale, 'app labels for datasets no network serves').toEqual([])
  })

  test('the providers page can draw every provider it is served', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/providers`, SLOW)
    expect(response.ok(), 'the backend did not serve /api/providers').toBeTruthy()
    const { providers } = await response.json() as { providers: Array<{ provider: string, country_code: string | null }> }
    const coverage = await (await request.get(`${BACKEND_URL}/api/coverage`, SLOW)).json() as Record<string, unknown>

    expect(providers.map(provider => provider.provider).sort(), 'the providers the registry has').toEqual(Object.keys(coverage).sort())
    // a flag is drawn from two capital letters (null is a provider of several countries, which gets the globe)
    const odd = providers.filter(provider => provider.country_code !== null && !/^[A-Z]{2}$/.test(provider.country_code)).map(provider => provider.provider)
    expect(odd, 'providers whose country_code is no ISO 3166-1 alpha-2 code').toEqual([])
  })

  test('the home page lists every provider, and counts them', async ({ page, request }) => {
    const response = await request.get(`${BACKEND_URL}/api/coverage`, SLOW)
    expect(response.ok(), 'the backend did not serve /api/coverage').toBeTruthy()
    const registered = Object.keys(await response.json() as Record<string, unknown>).sort()
    expect(registered.length, 'coverage came back empty').toBeGreaterThan(0)

    // read off the page, not off its source: the providers are the backend's (`/api/providers`), so what
    // this holds is that the page shows every provider of the registry, each as a link to its own page, and
    // that the number it states is that of the registry
    await page.goto('/')
    const chips = page.locator('[data-testid="home-providers"] a')
    await expect(chips.first()).toBeVisible({ timeout: 30_000 })
    const listed = (await chips.evaluateAll(anchors => anchors.map(anchor => anchor.getAttribute('href')?.replace('/providers/', '') ?? ''))).sort()
    expect(listed, 'the providers the home page links to, against those of the registry').toEqual(registered)

    // the first of the four numbers is the count of the providers
    const stat = page.locator('.text-2xl').first()
    await expect(stat).toHaveText(String(registered.length))

    // and the second is the count of the parameters, the backend's own: not a number the page was written with
    const catalogue = await request.get(`${BACKEND_URL}/api/providers`, SLOW)
    expect(catalogue.ok(), 'the backend did not serve /api/providers').toBeTruthy()
    const { metadata } = await catalogue.json() as { metadata: { counts: { parameters: number } } }
    expect(metadata.counts.parameters, '/api/providers counted no parameters').toBeGreaterThan(0)
    await expect(page.locator('.text-2xl').nth(1)).toHaveText(String(metadata.counts.parameters))
  })
})
