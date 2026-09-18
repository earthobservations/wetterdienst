import { readFileSync } from 'node:fs'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

// What the backend serves and what the app can name, checked against each other.
//
// The app labels every canonical parameter and every unit type in eleven languages, and names
// every provider on its home page. Nothing in the app's own unit tests can notice when one of
// those is added upstream: they read the catalogs and hold the locales to each other, so a new
// name in the backend leaves every catalog untouched, the parity green, and the name falling back
// to a prettified English id in all eleven languages.
//
// That direction is checked here rather than from the Python suite, which has no business reading
// `app/`. The E2E workflow's path filter already covers `src/wetterdienst/**` for the same reason
// this test exists -- the suite runs the app against a backend started from there -- so a change
// that adds a parameter runs this.

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:3000'

const glossaryEn = fileURLToPath(new URL('../../i18n/glossary/en.ts', import.meta.url))
const localeEn = fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url))
const homePage = fileURLToPath(new URL('../../app/pages/index.vue', import.meta.url))

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
// `/api/coverage` walks every provider in the registry -- seconds warm, and the CI cache is cold
const SLOW = { timeout: 120_000 }

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

  test('the home page lists every provider', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/coverage`, SLOW)
    expect(response.ok(), 'the backend did not serve /api/coverage').toBeTruthy()
    const registered = new Set(Object.keys(await response.json() as Record<string, unknown>))
    expect(registered.size, 'coverage came back empty').toBeGreaterThan(0)

    // written out in index.vue rather than fetched: a static claim about what the app offers, and
    // so the one place in the app that can silently fall behind the registry
    const block = readFileSync(homePage, 'utf-8').split('const providers = [')[1]?.split(']')[0] ?? ''
    const listed = new Set([...block.matchAll(/key: '([a-z]+)'/g)].map(match => match[1] as string))

    const missing = [...registered].filter(name => !listed.has(name)).sort()
    const stale = [...listed].filter(name => !registered.has(name)).sort()
    expect(missing, 'providers the home page does not mention').toEqual([])
    expect(stale, 'providers the home page mentions but the registry does not have').toEqual([])
  })
})
