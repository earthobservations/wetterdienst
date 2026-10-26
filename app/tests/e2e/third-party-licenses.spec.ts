import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { DEVELOPMENT_NOTICE, needsMoreThanNotice } from '../../modules/third-party-licenses/licenses'

// The third-party notices of the browser bundle (GH-3469), served at `/third-party-licenses.txt` and linked from the
// footer. The file is made by the production build from the packages its chunks and assets hold
// (`modules/third-party-licenses`), so these tests read the file of the build the suite runs against (in CI the
// production build; the development server answers a note instead, and the tests that need the build skip).

const APP = fileURLToPath(new URL('../..', import.meta.url))
const pkg = JSON.parse(readFileSync(join(APP, 'package.json'), 'utf8'))
const lockfile = readFileSync(join(APP, 'pnpm-lock.yaml'), 'utf8')

/**
 * The production dependencies of package.json that are not in the file, each with the reason. Everything else in
 * `dependencies` has to be: a new dependency is either in the bundle, and so in the file, or a line here.
 */
const NOT_IN_THE_BUNDLE: Record<string, string> = {
  '@tailwindcss/vite': 'a Vite plugin that runs in the build; the CSS it makes is tailwindcss\'s',
  '@vueuse/nuxt': 'a Nuxt module that registers the auto-imports of @vueuse/core; the code that runs is @vueuse/core\'s',
  'nuxt-security': 'a Nuxt module whose headers and middleware run on the server',
}

interface Entry { name: string, version: string, license: string, body: string }

function entries(text: string): Entry[] {
  return text.split(/^={78}\n(?=@?[^@\s]+@\S+\nLicence: )/m).slice(1).map((section) => {
    const [, name, version, license] = section.match(/^(@?[^@\s]+)@(\S+)\nLicence: (.*)\n/) ?? []
    return { name: name!, version: version!, license: license === 'not declared by the package' ? '' : license!, body: section }
  })
}

test.describe('the footer', () => {
  test('links the file, next to the privacy policy', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    const link = page.getByRole('contentinfo').locator('a[href="/third-party-licenses.txt"]')
    await expect(link).toBeVisible()
    await expect(link).toHaveText(/licen[cs]es/i)
  })

  test('is not on the widget, which has no footer', async ({ page }) => {
    await page.goto('/widget?station=10381')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('contentinfo')).toHaveCount(0)
    await expect(page.locator('a[href="/third-party-licenses.txt"]')).toHaveCount(0)
  })
})

test.describe('the file', () => {
  test('is a text, served by the app itself', async ({ request }) => {
    const response = await request.get('/third-party-licenses.txt')

    expect(response.status()).toBe(200)
    expect(response.headers()['content-type']).toMatch(/^text\/plain/)
  })

  test('lists every production dependency that reaches the bundle, with a licence text that asks for a notice only', async ({ request }) => {
    const text = await (await request.get('/third-party-licenses.txt')).text()
    test.skip(text === DEVELOPMENT_NOTICE, 'the development server has no bundle to read the notices from')

    const listed = entries(text)
    expect(listed.length).toBeGreaterThan(10)
    const names = new Set(listed.map(entry => entry.name))

    // a dependency of package.json is in the file, or named above with the reason it is not
    for (const name of Object.keys(pkg.dependencies)) {
      if (name in NOT_IN_THE_BUNDLE)
        expect(names.has(name), `${name} is in the file, so ${NOT_IN_THE_BUNDLE[name]} is stale`).toBe(false)
      else
        expect(names.has(name), `${name} is a dependency that is not in /third-party-licenses.txt: add it to NOT_IN_THE_BUNDLE with the reason if it is not served to the browser`).toBe(true)
    }
    for (const name of Object.keys(NOT_IN_THE_BUNDLE))
      expect(pkg.dependencies, `${name} is no dependency any more`).toHaveProperty(name)

    // the file is of this lockfile, not of an older install
    for (const entry of listed)
      expect(lockfile.includes(`${entry.name}@${entry.version}`), `${entry.name}@${entry.version} is not in pnpm-lock.yaml`).toBe(true)

    // every entry carries the text of a licence, not only a name
    for (const entry of listed)
      expect(entry.body, entry.name).not.toContain('ships no licence file')

    // the ones that need more than a notice (LGPL, MPL, an advertising clause, an unknown licence) are a decision
    const notices = listed.map(entry => ({ ...entry, homepage: '', texts: [] }))
    expect(needsMoreThanNotice(notices).map(entry => `${entry.name}@${entry.version}: ${entry.license}`)).toEqual([])
  })

  test('has the notice of Leaflet, which the bundle used to drop', async ({ request }) => {
    const text = await (await request.get('/third-party-licenses.txt')).text()
    test.skip(text === DEVELOPMENT_NOTICE, 'the development server has no bundle to read the notices from')

    const leaflet = entries(text).find(entry => entry.name === 'leaflet')!
    expect(leaflet.license).toBe('BSD-2-Clause')
    expect(leaflet.body).toContain('Redistributions in binary form must reproduce the above copyright notice')
  })
})
