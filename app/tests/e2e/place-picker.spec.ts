import type { Page } from '@playwright/test'
import type { Asked } from './accessibility/ask-backend'
import { readFileSync } from 'node:fs'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { askHandlers } from './accessibility/ask-backend'
import { mockBackend } from './accessibility/mock-backend'
import { rankedStations } from './accessibility/place-backend'
import { expectAtLeastPx } from './target-size'

// The place picker of the Forecast, "Ask the weather" and the Explorer's interpolation (GH-3791), through the running app: the field, the app's own
// server (`GET /_search/places`) and the stand-in for Photon (`tests/e2e/mock-photon.mjs`, which the server is pointed at by `NUXT_PLACES_PHOTON_BASE`).
// The real Photon is never asked, and `tests/e2e/global-setup.ts` stops the run unless the server says it asks the stand-in. The rest of the backend is the
// accessibility spec's mock with the `stations` request ranked by the position, as the REST API ranks it, so nothing here reaches a provider either.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))

const PHOTON = `http://127.0.0.1:${process.env.E2E_PHOTON_PORT || Number(process.env.E2E_PORT || 4000) + 100}`

interface PhotonRequest { url: string, headers: Record<string, string | undefined> }

/** What the stand-in was asked for texts that start with `prefix` */
async function asked(prefix: string): Promise<PhotonRequest[]> {
  const all = await (await fetch(`${PHOTON}/__requests`)).json() as PhotonRequest[]
  return all.filter(request => (new URL(request.url, 'http://x').searchParams.get('q') ?? '').toLowerCase().startsWith(prefix))
}

/** A text (letters only: a number would make it look like a position) that no earlier run, test or reader has asked for, which the server keeps its answers for a day */
const fresh = (text: string) => `${text} ${Array.from({ length: 6 }, () => String.fromCharCode(97 + Math.floor(Math.random() * 26))).join('')}`

/** The requests of the page to the app's search of places, which a link that names its place must not make */
function noPlaceSearch(page: Page): () => string[] {
  const requests: string[] = []
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/_search/places')
      requests.push(request.url())
  })
  return () => requests
}

/** The mock backend with the stations ranked by a position and the places of the app's own server (the stand-in for Photon answers it) */
async function backend(page: Page, baseURL: string, language = 'en', stationQueries: Array<Record<string, string>> = [], questions: Asked[] = []) {
  await page.context().addCookies([{ name: 'wd_lang', value: language, url: baseURL }])
  return mockBackend(page, baseURL, {
    ...rankedStations(askHandlers(questions), stationQueries),
    '_search/places': async (_url, route) => (await route.fetch()).json(),
  })
}

test.describe('the Forecast finds places', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  async function openSearch(page: Page) {
    await page.addInitScript(() => localStorage.setItem('wd-station-picker', JSON.stringify({ forecast: 'list' })))
    await page.goto('/meteogram')
    const picker = page.getByTestId('station-picker')
    await picker.locator('button[aria-haspopup="listbox"]').first().click()
    const search = page.getByRole('combobox', { name: en.common.stationSearch }).or(page.locator('[role="listbox"]').locator('xpath=..').getByRole('combobox')).first()
    return { picker, search }
  }

  test('offers the places of the name typed next to the stations, with the credit, picks the closest forecast station and shows it with how far and how high', async ({ page, baseURL }) => {
    const queries: Array<Record<string, string>> = []
    await backend(page, baseURL!, 'en', queries)
    await openSearch(page)
    const text = fresh('bad tölz')
    await page.keyboard.type(text, { delay: 20 })
    const listbox = page.getByRole('listbox')
    // the places before the stations, each with what it is and where it lies
    await expect(listbox.getByRole('option', { name: /Bad Tölz/ }).first()).toBeVisible()
    await expect(listbox).toContainText('Town · Bayern, Germany')
    await expect(page.getByTestId('places-credit')).toHaveText('© OpenStreetMap contributors (ODbL) · places via Photon')
    await listbox.getByRole('option', { name: /^Bad Tölz.*Town/ }).first().click()

    // the place, its name and where it lies, and the stations near it
    const place = page.getByTestId('place-stations')
    await expect(place.getByTestId('place-name')).toHaveText('Bad Tölz')
    await expect(place.getByTestId('place-region')).toHaveText('Bayern, Germany')
    await expect(place.getByTestId('place-summary')).toContainText('Showing BAD TOELZ (M0814), the closest forecast station to Bad Tölz, 1.2 km away.')
    const rows = place.getByTestId('place-station-list').getByRole('listitem')
    await expect(rows).toHaveCount(4)
    await expect(rows.nth(0)).toContainText('BAD TOELZ (M0814)')
    await expect(rows.nth(0)).toContainText('closest')
    await expect(rows.nth(0)).toContainText('Height 668 m')
    await expect(rows.nth(0)).toHaveAttribute('aria-current', 'true')
    // the others, with their distance and their height against the closest station's (a place has none of its own)
    await expect(rows.nth(1)).toContainText('TEGERNSEE (M0818)')
    await expect(rows.nth(1)).toContainText('+67 m')
    await expect(rows.nth(2)).toContainText('KOCHEL AM SEE (M0816)')
    await expect(rows.nth(2)).toContainText('−54 m')
    // its forecast is the one shown, and the link carries the place without the name of any search
    await expect(page.getByRole('heading', { name: /BAD TOELZ/ }).or(page.getByText('BAD TOELZ').first())).toBeVisible()
    await expect(page).toHaveURL(/station=M0814/)
    const url = new URL(page.url())
    expect(Object.fromEntries(url.searchParams)).toMatchObject({ station: 'M0814', lat: '47.7610', lon: '11.5596', placeName: 'Bad Tölz', placeRegion: 'Bayern, Germany' })
    // the stations near the place were asked for by its position, from the forecast's own network
    expect(queries.at(-1)).toMatchObject({ provider: 'dwd', network: 'mosmix', rank: '5' })
    // Photon was asked once, for the text, by the app's own server: no cookie, no referrer, no address
    const [request] = await asked(text)
    expect(request).toBeDefined()
    expect([...new URL(request!.url, 'http://x').searchParams.keys()].sort()).toEqual(['lang', 'limit', 'q'])
    expect(request!.headers.cookie).toBeUndefined()
    expect(request!.headers.referer).toBeUndefined()
  })

  test('shows another station of the list on a press, keeps the place, and names the station chosen in the link', async ({ page, baseURL }) => {
    await backend(page, baseURL!)
    const { search } = await openSearch(page)
    await search.fill(fresh('bad tölz'))
    await page.getByRole('listbox').getByRole('option', { name: /^Bad Tölz.*Town/ }).first().click()
    const place = page.getByTestId('place-stations')
    await expect(place.getByTestId('place-name')).toHaveText('Bad Tölz')
    await place.getByRole('button', { name: 'Show the forecast of TEGERNSEE (M0818)' }).click()
    await expect(page).toHaveURL(/station=M0818/)
    await expect(place.getByTestId('place-name')).toHaveText('Bad Tölz')
    await expect(place.getByTestId('place-station-list').getByRole('listitem').nth(1)).toHaveAttribute('aria-current', 'true')
    expect(Object.fromEntries(new URL(page.url()).searchParams)).toMatchObject({ station: 'M0818', placeName: 'Bad Tölz' })
  })

  test('picking a station by name afterwards takes the place away, and with it the place of the link', async ({ page, baseURL }) => {
    await backend(page, baseURL!)
    const { picker, search } = await openSearch(page)
    await search.fill(fresh('bad tölz'))
    await page.getByRole('listbox').getByRole('option', { name: /^Bad Tölz.*Town/ }).first().click()
    await expect(page.getByTestId('place-stations')).toBeVisible()
    await picker.locator('button[aria-haspopup="listbox"]').first().click()
    await page.keyboard.type('HAMBURG')
    await page.getByRole('option', { name: /HAMBURG-FUHLSBUETTEL/ }).click()
    await expect(page.getByTestId('place-stations')).toHaveCount(0)
    await expect(page).toHaveURL(/station=10147/)
    expect([...new URL(page.url()).searchParams.keys()]).not.toContain('placeName')
  })

  test('says plainly where no forecast station is within 50 km, names the nearest, shows no forecast as the place\'s, and offers the nearest as the station\'s', async ({ page, baseURL }) => {
    await backend(page, baseURL!)
    const { search } = await openSearch(page)
    await search.fill(fresh('paris'))
    await page.getByRole('listbox').getByRole('option', { name: /^Paris.*City/ }).first().click()
    const place = page.getByTestId('place-stations')
    await expect(place.getByTestId('place-name')).toHaveText('Paris')
    await expect(place.getByTestId('place-region')).toHaveText('Île-de-France, France')
    const summary = place.getByTestId('place-summary')
    await expect(summary).toContainText('No forecast station is within 50 km of Paris.')
    await expect(summary).toContainText('KOCHEL AM SEE (M0816)')
    await expect(summary).toContainText('so its forecast is not the forecast of Paris and none is shown.')
    // no forecast: the page has no station and shows no chart
    await expect(page.locator('[role="figure"]')).toHaveCount(0)
    expect([...new URL(page.url()).searchParams.keys()]).not.toContain('station')
    // the nearest may still be opened, which says it is not the place's
    // the visible label is in its name, with the station and how far it is
    const anyway = place.getByRole('button', { name: /^Show anyway: the forecast of KOCHEL AM SEE \(M0816\), 681 km away, is not the forecast of Paris$/ })
    await expect(anyway).toHaveText('Show anyway')
    await anyway.click()
    await expect(page).toHaveURL(/station=M0816/)
    // the forecast is the station's and the box says so, not that none is shown
    await expect(summary).toContainText('Shown: the forecast of KOCHEL AM SEE (M0816), 681 km from Paris. It is not the forecast of Paris.')
    await expect(summary).not.toContainText('none is shown')
  })

  test('is opened from a link without asking Photon again: the place, its name and where it lies are in the link', async ({ page, baseURL }) => {
    const searched = noPlaceSearch(page)
    await backend(page, baseURL!)
    await page.addInitScript(() => localStorage.setItem('wd-station-picker', JSON.stringify({ forecast: 'list' })))
    await page.goto('/meteogram?lat=47.7610&lon=11.5596&placeName=Bad%20T%C3%B6lz&placeRegion=Bayern%2C%20Germany')
    const place = page.getByTestId('place-stations')
    await expect(place.getByTestId('place-name')).toHaveText('Bad Tölz')
    await expect(place.getByTestId('place-region')).toHaveText('Bayern, Germany')
    // the closest station is picked where the link names none
    await expect(page).toHaveURL(/station=M0814/)
    await expect(place.getByTestId('place-summary')).toContainText('closest forecast station to Bad Tölz')
    expect(searched()).toEqual([])
  })

  test('keeps the station, the run and the place of a link that names all three, and shows the link\'s station and not the closest', async ({ page, baseURL }) => {
    await backend(page, baseURL!)
    await page.addInitScript(() => localStorage.setItem('wd-station-picker', JSON.stringify({ forecast: 'list' })))
    await page.goto('/meteogram?station=M0818&issue=2026-10-14T09:00:00&horizon=3d&lat=47.7610&lon=11.5596&placeName=Bad%20T%C3%B6lz&placeRegion=Bayern%2C%20Germany')
    const place = page.getByTestId('place-stations')
    await expect(place.getByTestId('place-name')).toHaveText('Bad Tölz')
    await expect(place.getByTestId('place-station-list').getByRole('listitem').nth(1)).toHaveAttribute('aria-current', 'true')
    await expect(page.getByRole('combobox', { name: 'Model run' }).or(page.locator('#meteogram-run'))).toHaveValue('2026-10-14T09:00:00')
    await page.waitForTimeout(500)
    const query = Object.fromEntries(new URL(page.url()).searchParams)
    expect(query).toMatchObject({ station: 'M0818', issue: '2026-10-14T09:00:00', horizon: '3d', placeName: 'Bad Tölz', lat: '47.7610' })
  })

  test('is a combobox that keyboard alone operates, that says how many results there are, and whose targets are 24 px or more', async ({ page, baseURL }) => {
    await backend(page, baseURL!)
    const { picker } = await openSearch(page)
    await page.keyboard.type(fresh('bad tölz'), { delay: 20 })
    const listbox = page.getByRole('listbox')
    await expect(listbox.getByRole('option', { name: /Bad Tölz/ }).first()).toBeVisible()
    // the count of the results, said politely a moment after the last key
    await expect(picker.getByTestId('station-picker-results')).toHaveText(/^\d+ results?/)
    // arrow keys and Enter choose the first place
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('Enter')
    await expect(page.getByTestId('place-stations').getByTestId('place-name')).toHaveText('Bad Tölz')
    for (const button of await page.getByTestId('place-stations').getByRole('button').all()) {
      const box = (await button.boundingBox())!
      expectAtLeastPx(box.width, 24)
      expectAtLeastPx(box.height, 24)
    }
  })

  test('says in German what it says in English, with the place and the nearest station named', async ({ page, baseURL }) => {
    await backend(page, baseURL!, 'de')
    await page.addInitScript(() => localStorage.setItem('wd-station-picker', JSON.stringify({ forecast: 'list' })))
    await page.goto('/meteogram?lat=47.7610&lon=11.5596&placeName=Bad%20T%C3%B6lz&placeRegion=Bayern%2C%20Deutschland')
    const place = page.getByTestId('place-stations')
    await expect(place.getByTestId('place-summary')).toContainText('Gezeigt wird BAD TOELZ (M0814), die nächste Vorhersagestation zu Bad Tölz')
    await expect(place.getByTestId('place-summary')).toContainText('entfernt')
    await expect(place.getByTestId('place-region')).toHaveText('Bayern, Deutschland')
  })
})

test.describe('Ask the weather finds a town', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  async function openPlaceDialog(page: Page, baseURL: string, questions: Asked[] = [], language = 'en', stationQueries: Array<Record<string, string>> = []) {
    await backend(page, baseURL, language, stationQueries, questions)
    await page.addInitScript(() => {
      try {
        localStorage.removeItem('wd-place')
      }
      catch {}
    })
    await page.goto('/')
    await expect(page.getByTestId('ask')).toBeVisible()
    await page.getByTestId('place-button').click()
    await expect(page.getByRole('combobox')).toBeFocused()
  }

  test('makes the town typed the place of the questions, and the answers name the station used and how far it is', async ({ page, baseURL }) => {
    const questions: Asked[] = []
    const positioned: Array<Record<string, string>> = []
    await openPlaceDialog(page, baseURL!, questions, 'en', positioned)
    await page.keyboard.type(fresh('bad tölz'), { delay: 20 })
    const group = page.getByRole('group', { name: 'Places', exact: true })
    await expect(group).toBeVisible()
    await expect(page.getByTestId('places-credit')).toBeVisible()
    await group.getByRole('option').first().click()
    // the place of the questions is the town, with where it lies
    await expect(page.getByTestId('place-button')).toContainText('Bad Tölz')
    await expect(page.getByTestId('place-region')).toHaveText('Bayern, Germany')
    await expect(page.getByTestId('question-rain')).toContainText('Will it rain in Bad Tölz tomorrow?')
    // the link carries the town, so that a shared link needs no search
    expect(Object.fromEntries(new URL(page.url()).searchParams)).toMatchObject({ lat: '47.7610', lon: '11.5596', placeName: 'Bad Tölz', placeRegion: 'Bayern, Germany' })
    expect([...new URL(page.url()).searchParams.keys()]).not.toContain('place')

    // the forecast point, named with its distance from the town
    await page.getByTestId('question-rain').click()
    await expect(page.getByTestId('answer')).toContainText('the forecast point nearest to Bad Tölz')
    // the measurements, from the station nearest to the town, named with its distance from it
    await page.getByTestId('question-season').click()
    const station = page.getByTestId('answer-station')
    await expect(station).toContainText('Read at Andechs-Rothenfeld (00125), the weather station nearest to Bad Tölz,')
    await expect(station).toContainText('km away.')
    expect(questions.filter(entry => entry.path === 'values' && entry.query.stations === '00125').length).toBeGreaterThan(0)
    // the station is asked for by the town's position, one nearest
    expect(positioned.find(query => query.network === 'observation')).toMatchObject({ latitude: '47.761', longitude: '11.5596', rank: '5' })
  })

  test('says there is no weather station near a town that has none within 50 km, names the nearest, and gives no answer', async ({ page, baseURL }) => {
    const questions: Asked[] = []
    await openPlaceDialog(page, baseURL!, questions)
    await page.keyboard.type(fresh('paris'), { delay: 20 })
    await page.getByRole('group', { name: 'Places', exact: true }).getByRole('option').first().click()
    await page.getByTestId('question-season').click()
    const far = page.getByTestId('answer-far')
    await expect(far).toContainText('There is no weather station within 50 km of Paris.')
    await expect(far).toContainText('The nearest, Donaueschingen (Landeplatz) (00011), is')
    await expect(far).toContainText('so no answer is given.')
    await expect(page.getByTestId('answer-verdict')).toHaveCount(0)
    // nothing was fetched from a station that is another place's, and the live region says it
    expect(questions.filter(entry => entry.path === 'values')).toEqual([])
    await expect(page.getByTestId('answer-status')).toContainText('There is no weather station within 50 km of Paris.')
    // the forecast says so too, with no forecast shown
    await page.getByTestId('question-rain').click()
    await expect(page.getByTestId('answer')).toContainText('There is no forecast point within 50 km of Paris.')
    await expect(page.getByTestId('answer-verdict')).toHaveCount(0)
  })

  test('names the station and its distance on the row of the download question that opens DWD\'s measurements, for a town near one', async ({ page, baseURL }) => {
    await backend(page, baseURL!)
    await page.addInitScript(() => localStorage.removeItem('wd-place'))
    await page.goto('/?ask=download&lat=47.7610&lon=11.5596&placeName=Bad%20T%C3%B6lz&placeRegion=Bayern%2C%20Germany')
    const sources = page.getByTestId('answer-sources')
    const dwd = sources.getByRole('link', { name: /German Weather Service|DWD/ }).first()
    await expect(dwd).toContainText('Andechs-Rothenfeld, 37 km from Bad Tölz')
    await expect(dwd).not.toContainText('· Bad Tölz')
    expect(new URL((await dwd.getAttribute('href'))!, baseURL!).searchParams.get('stations')).toBe('00125')
  })

  test('offers no station on that row, and names none, for a town with none within 50 km', async ({ page, baseURL }) => {
    await backend(page, baseURL!)
    await page.addInitScript(() => localStorage.removeItem('wd-place'))
    await page.goto('/?ask=download&lat=48.8566&lon=2.3522&placeName=Paris&placeRegion=France')
    const dwd = page.getByTestId('answer-sources').getByRole('link', { name: /German Weather Service|DWD/ }).first()
    await expect(dwd).toBeVisible()
    await expect(dwd).not.toContainText('Paris')
    await expect(dwd).not.toContainText('Donaueschingen')
    expect(new URL((await dwd.getAttribute('href'))!, baseURL!).searchParams.has('stations')).toBe(false)
  })

  test('takes the town of a link without asking Photon again', async ({ page, baseURL }) => {
    const searched = noPlaceSearch(page)
    await backend(page, baseURL!, 'en', [], [])
    await page.addInitScript(() => localStorage.removeItem('wd-place'))
    await page.goto('/?ask=season&lat=47.7610&lon=11.5596&placeName=Bad%20T%C3%B6lz&placeRegion=Bayern%2C%20Germany')
    await expect(page.getByTestId('place-button')).toContainText('Bad Tölz')
    await expect(page.getByTestId('answer-station')).toContainText('Andechs-Rothenfeld (00125)')
    expect(searched()).toEqual([])
  })

  test('is a station again where a station is chosen after, and the town leaves the link', async ({ page, baseURL }) => {
    await openPlaceDialog(page, baseURL!)
    await page.keyboard.type(fresh('bad tölz'), { delay: 20 })
    await page.getByRole('group', { name: 'Places', exact: true }).getByRole('option').first().click()
    await expect(page.getByTestId('place-button')).toContainText('Bad Tölz')
    await page.getByTestId('place-button').click()
    await page.keyboard.type('Arkona')
    await page.getByRole('option', { name: /Arkona/ }).first().click()
    await expect(page.getByTestId('place-button')).toContainText('Arkona')
    await expect(page.getByTestId('place-region')).toHaveCount(0)
    await expect.poll(() => [...new URL(page.url()).searchParams.keys()].sort()).toEqual(['place'])
  })
})

test.describe('the Explorer\'s interpolation finds a place', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('fills the point with the place, shows its name and where it lies, says the temperature is not corrected for height, and carries it in the link', async ({ page, baseURL }) => {
    await backend(page, baseURL!)
    await page.goto('/explorer?mode=interpolation&provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_mean_2m')
    const field = page.getByTestId('place-field')
    await expect(field).toBeVisible()
    await field.click()
    await page.keyboard.type(fresh('bad tölz'), { delay: 20 })
    await page.getByRole('option', { name: /^Bad Tölz.*Town/ }).first().click()
    const shown = page.getByTestId('interpolation-place')
    await expect(shown.getByTestId('interpolation-place-name')).toHaveText('Bad Tölz')
    await expect(shown.getByTestId('interpolation-place-region')).toHaveText('Bayern, Germany')
    await expect(page.getByLabel(en.interpolation.latitude)).toHaveValue('47.761')
    await expect(page.getByLabel(en.interpolation.longitude)).toHaveValue('11.5596')
    // a place has no height: none is sent, and the answer says the temperature is not corrected
    await expect(page.getByLabel(en.interpolation.elevation)).toHaveValue('')
    await expect(page.getByTestId('interpolation-place-height')).toHaveText(en.place.notCorrected)
    await expect(page).toHaveURL(/placeName=/)
    const query = Object.fromEntries(new URL(page.url()).searchParams)
    expect(query).toMatchObject({ mode: 'interpolation', lat: '47.761', lon: '11.5596', placeName: 'Bad Tölz', placeRegion: 'Bayern, Germany' })
    expect(Object.keys(query)).not.toContain('elevation')
    // the coordinates typed over are no longer the place's
    await page.getByLabel(en.interpolation.latitude).fill('48.1')
    await expect(page.getByTestId('interpolation-place')).toHaveCount(0)
    await expect.poll(() => [...new URL(page.url()).searchParams.keys()]).not.toContain('placeName')
    expect([...new URL(page.url()).searchParams.keys()]).not.toContain('placeRegion')
  })

  test('shows the place of a link without asking Photon again', async ({ page, baseURL }) => {
    const searched = noPlaceSearch(page)
    await backend(page, baseURL!)
    await page.goto('/explorer?mode=summary&provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_mean_2m&interpolationSource=manual&lat=47.761&lon=11.5596&placeName=Bad%20T%C3%B6lz&placeRegion=Bayern%2C%20Germany')
    await expect(page.getByTestId('interpolation-place-name')).toHaveText('Bad Tölz')
    await expect(page.getByLabel(en.interpolation.latitude)).toHaveValue('47.761')
    expect(searched()).toEqual([])
  })

  test('is a combobox that the keyboard alone operates, with the credit under its list', async ({ page, baseURL }) => {
    await backend(page, baseURL!)
    await page.goto('/explorer?mode=interpolation&provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_mean_2m')
    await page.getByTestId('place-field').focus()
    await page.keyboard.press('Enter')
    await page.keyboard.type(fresh('bad tölz'), { delay: 20 })
    await expect(page.getByTestId('places-credit')).toBeVisible()
    await expect(page.getByTestId('place-field-results')).toHaveText(/^\d+ results?/)
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('Enter')
    await expect(page.getByTestId('interpolation-place-name')).toHaveText(/^Bad Tölz/)
  })
})
