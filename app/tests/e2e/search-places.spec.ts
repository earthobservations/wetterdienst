import type { Page } from '@playwright/test'
import process from 'node:process'
import { expect, test } from '@playwright/test'
import { ApiFailure, mockBackend } from './accessibility/mock-backend'

// The places the search of the header finds by name (GH-3790, GH-3791), through the running app: the palette, the app's own server
// (`GET /_search/places`) and a stand-in for Photon (`tests/e2e/mock-photon.mjs`, which the server is pointed at by `NUXT_PLACES_PHOTON_BASE`).
// The real Photon is never asked. The rest of the backend is the accessibility spec's mock, so nothing here reaches a provider either.
//
// The stand-in keeps what it was asked, with the headers, which is what shows that nothing of the reader reaches it: the browser sends its
// cookie, its referrer and its language to the app's server, and the server asks Photon for the text and nothing else.

const PHOTON = `http://127.0.0.1:${process.env.E2E_PHOTON_PORT || Number(process.env.E2E_PORT || 4000) + 100}`

interface PhotonRequest { url: string, headers: Record<string, string | undefined> }

/** What the stand-in was asked for texts that start with `prefix`: other specs of a run may type in the search too */
async function asked(prefix: string): Promise<PhotonRequest[]> {
  const all = await (await fetch(`${PHOTON}/__requests`)).json() as PhotonRequest[]
  return all.filter(request => (new URL(request.url, 'http://x').searchParams.get('q') ?? '').toLowerCase().startsWith(prefix))
}

/** A text no earlier run, test or reader has asked for, which the server keeps its answers for a day: the answer is Photon's, not the cache's */
const fresh = (text: string) => `${text} ${Math.random().toString(36).slice(2, 8)}`

async function openSearch(page: Page, baseURL: string, language = 'en') {
  await page.context().addCookies([{ name: 'wd_lang', value: language, url: baseURL }])
  // the places are the real route's: the stand-in for the backend lets that one request through to the app's server
  await mockBackend(page, baseURL, { '_search/places': async (_url, route) => (await route.fetch()).json() })
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
  await page.keyboard.press('Control+k')
  await expect(page.getByRole('combobox')).toBeFocused()
}

test.describe.configure({ mode: 'serial' })

test.describe('the places of the search', () => {
  test.use({ viewport: { width: 1280, height: 800 } })

  test('are the ones OpenStreetMap has for a name, asked of Photon by the app\'s server, each with what it is and where it lies, and lead to the map at their point', async ({ page, baseURL }) => {
    await openSearch(page, baseURL!)
    const text = fresh('bad tölz')
    await page.keyboard.type(text, { delay: 25 })
    const group = page.getByRole('group', { name: 'Places', exact: true })
    await expect(group).toBeVisible()
    const options = group.getByRole('option')
    // the town, its county; the street, the café and the town's twin of the stand-in are left out
    await expect(options).toHaveCount(2)
    await expect(options.first()).toContainText('Bad Tölz')
    await expect(options.first()).toContainText('Town · Bayern, Germany')
    await expect(options.nth(1)).toContainText('County · Bayern, Germany')
    // the places lead the stations
    await expect(page.getByRole('group').first()).toHaveAccessibleName('Places')
    await options.first().click()
    await expect(page).toHaveURL(/\/map\?.*lat=47\.7614.*lon=11\.5583/)
  })

  test('are asked for once for the text, from three letters on and a moment after the last key, and again for a text that is a different one', async ({ page, baseURL }) => {
    await openSearch(page, baseURL!)
    const text = fresh('paris')
    // two letters are not asked for, and a text typed at a quick pace is one request
    await page.keyboard.type('pa')
    await page.waitForTimeout(900)
    expect(await asked('pa')).not.toEqual(expect.arrayContaining([expect.objectContaining({ url: expect.stringContaining('q=pa&') })]))
    await page.keyboard.type(text.slice(2), { delay: 25 })
    await expect(page.getByRole('group', { name: 'Places', exact: true })).toBeVisible()
    expect(await asked(text.toLowerCase())).toHaveLength(1)
  })

  test('are kept by the server for the text in any case and spacing, so that Photon is asked once', async ({ page, baseURL }) => {
    await openSearch(page, baseURL!)
    const text = fresh('paris')
    await page.keyboard.type(text)
    await expect(page.getByRole('group', { name: 'Places', exact: true })).toBeVisible()
    expect(await asked(text)).toHaveLength(1)
    // the same text in capitals and with doubled spaces, in a page of its own: the server's answer, not Photon's
    await page.reload()
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
    await page.keyboard.press('Control+k')
    await expect(page.getByRole('combobox')).toBeFocused()
    await page.keyboard.type(text.toUpperCase().replace(' ', '  '))
    await expect(page.getByRole('group', { name: 'Places', exact: true })).toBeVisible()
    expect(await asked(text)).toHaveLength(1)
  })

  test('are asked for in the language of the reader where Photon has it, and show what Photon names in it', async ({ page, baseURL }) => {
    await openSearch(page, baseURL!, 'de')
    const text = fresh('paris')
    await page.keyboard.type(text)
    const group = page.getByRole('group', { name: 'Orte', exact: true })
    await expect(group).toBeVisible()
    // Photon's names of the countries in German, and the words of the kinds from the catalog
    await expect(group.getByRole('option').first()).toContainText('Großstadt · Île-de-France, Frankreich')
    const [request] = await asked(text)
    expect(new URL(request!.url, 'http://x').searchParams.get('lang')).toBe('de')
    // a language Photon has none of is asked for in English
    await page.context().addCookies([{ name: 'wd_lang', value: 'cs', url: baseURL! }])
    await page.reload()
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
    await page.keyboard.press('Control+k')
    await expect(page.getByRole('combobox')).toBeFocused()
    const czech = fresh('paris')
    await page.keyboard.type(czech)
    await expect(page.getByRole('group', { name: 'Místa', exact: true })).toBeVisible()
    expect(new URL((await asked(czech))[0]!.url, 'http://x').searchParams.get('lang')).toBe('en')
  })

  test('send nothing of the reader to Photon: the text, the language and a limit, with a User-Agent that names the project, and no address, cookie, referrer or browser', async ({ page, baseURL }) => {
    await openSearch(page, baseURL!)
    const text = fresh('paris')
    await page.keyboard.type(text)
    await expect(page.getByRole('group', { name: 'Places', exact: true })).toBeVisible()
    const [request] = await asked(text)
    const params = new URL(request!.url, 'http://x').searchParams
    expect([...params.keys()].sort()).toEqual(['lang', 'limit', 'q'])
    expect(params.get('q')).toBe(text)
    const headers = request!.headers
    expect(headers['user-agent']).toMatch(/^wetterdienst-app \(\+https:\/\/github\.com\/earthobservations\/wetterdienst\)$/)
    expect(headers.accept).toBe('application/json')
    for (const name of ['x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto', 'x-real-ip', 'forwarded', 'cookie', 'referer', 'origin', 'authorization', 'x-request-id'])
      expect(headers[name], name).toBeUndefined()
    // what the reader's browser sent to the app's server is not what Photon got: not its language list, which Node's own `*` replaces
    expect(headers['accept-language'] ?? '*').toBe('*')
  })

  test('show the credit of the licence and the name of the service with the group, as links to their sites', async ({ page, baseURL }) => {
    await openSearch(page, baseURL!)
    await page.keyboard.type(fresh('paris'))
    const credit = page.getByTestId('places-credit')
    await expect(credit).toBeVisible()
    await expect(credit).toHaveText('© OpenStreetMap contributors (ODbL) · places via Photon')
    await expect(credit.getByRole('link', { name: '© OpenStreetMap contributors' })).toHaveAttribute('href', 'https://www.openstreetmap.org/copyright')
    await expect(credit.getByRole('link', { name: 'ODbL' })).toHaveAttribute('href', 'https://opendatacommons.org/licenses/odbl/1-0/')
    await expect(credit.getByRole('link', { name: 'Photon' })).toHaveAttribute('href', 'https://photon.komoot.io')
  })

  test('are not looked for for a position or a number, which are no names', async ({ page, baseURL }) => {
    await openSearch(page, baseURL!)
    const before = (await (await fetch(`${PHOTON}/__requests`)).json() as unknown[]).length
    await page.keyboard.type('52.5200, 13.4000')
    await expect(page.getByRole('option', { name: /52\.5200, 13\.4000/ })).toBeVisible()
    await page.waitForTimeout(900)
    await page.getByRole('combobox').fill('10381')
    await page.waitForTimeout(900)
    expect((await (await fetch(`${PHOTON}/__requests`)).json() as unknown[]).length).toBe(before)
  })

  test('are shown no group where the operator has switched the search of places off (the server says so), and are not asked for again', async ({ page, baseURL }) => {
    await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])
    let requests = 0
    await mockBackend(page, baseURL!, {
      '_search/places': (url) => {
        requests++
        return { query: url.searchParams.get('q'), state: 'off', places: [], attribution: '© OpenStreetMap contributors' }
      },
    })
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
    await page.keyboard.press('Control+k')
    await expect(page.getByRole('combobox')).toBeFocused()
    await page.keyboard.type('paris')
    await expect.poll(() => requests).toBe(1)
    await expect(page.getByRole('group', { name: 'Places', exact: true })).toHaveCount(0)
    await expect(page.getByTestId('places-credit')).toHaveCount(0)
    await page.getByRole('combobox').fill('bad tölz')
    await page.waitForTimeout(900)
    expect(requests).toBe(1)
  })

  test('are a problem the palette says in its live region where the server cannot ask Photon, and leave the rest of the search', async ({ page, baseURL }) => {
    await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])
    await mockBackend(page, baseURL!, {
      '_search/places': () => new ApiFailure(503, 'busy', { type: 'urn:wetterdienst:problem:places-busy', title: 'Service Unavailable', status: 503 }),
    })
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
    await page.keyboard.press('Control+k')
    await expect(page.getByRole('combobox')).toBeFocused()
    await page.keyboard.type('paris')
    await expect(page.getByRole('dialog').getByRole('status')).toContainText('Places could not be searched just now. Keep typing to try again.')
    await expect(page.getByRole('group', { name: 'Places', exact: true })).toHaveCount(0)
    // the search itself goes on
    await expect(page.getByRole('combobox')).toBeFocused()
  })
})

test.describe('the route of the places', () => {
  test('answers an invalid request as a 422 problem, as the backend does, and asks Photon nothing for it', async ({ request }) => {
    const before = (await (await fetch(`${PHOTON}/__requests`)).json() as unknown[]).length
    for (const query of ['', 'q=ab', 'q=52.5%2C13.4', `q=${'x'.repeat(101)}`, 'q=paris&lang=de%3Bdrop']) {
      const response = await request.get(`/_search/places?${query}`)
      expect(response.status(), query).toBe(422)
      expect(response.headers()['content-type']).toContain('application/problem+json')
      expect((await response.json()).type).toBe('urn:wetterdienst:problem:invalid-parameters')
    }
    expect((await (await fetch(`${PHOTON}/__requests`)).json() as unknown[]).length).toBe(before)
  })

  test('answers the places of a text with the credit of OpenStreetMap, and keeps them for the client for five minutes', async ({ request }) => {
    const response = await request.get(`/_search/places?q=${encodeURIComponent(fresh('bad tölz'))}&lang=en`)
    expect(response.status()).toBe(200)
    expect(response.headers()['cache-control']).toBe('private, max-age=300')
    const answer = await response.json()
    expect(answer.state).toBe('ok')
    expect(answer.attribution).toBe('© OpenStreetMap contributors')
    expect(answer.places.map((place: { name: string, kind: string }) => [place.name, place.kind])).toEqual([['Bad Tölz', 'town'], ['Landkreis Bad Tölz-Wolfratshausen', 'county']])
  })
})
