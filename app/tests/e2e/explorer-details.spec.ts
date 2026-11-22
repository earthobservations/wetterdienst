import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The Explorer's value details (GH-4296): split by station, the difference of two stations, a sum only for a parameter that adds up.
// The API is answered by the mock backend, so the spec needs nothing but the app.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))
const de = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/de.json', import.meta.url)), 'utf-8'))

const PARAMETERS = 'temperature_air_mean_2m,precipitation_height'
const path = (stations: string) => `/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=${PARAMETERS}&mode=station&stations=${stations}`

async function showDetails(page: Page, baseURL: string, stations: string, language = 'en') {
  await page.context().addCookies([{ name: 'wd_lang', value: language, url: baseURL }])
  await mockBackend(page, baseURL)
  await page.goto(path(stations))
  const messages = language === 'de' ? de : en
  await page.getByRole('button', { name: messages.common.fetch, exact: true }).click()
  await expect(page.getByRole('table').first()).toBeVisible()
  await page.getByRole('button', { name: messages.explorer.valuesDetails, exact: true }).click()
  const details = page.getByTestId('value-details')
  await expect(details).toBeVisible()
  return details
}

test.describe('value details of two stations', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('are one row for each station of each parameter, with the difference of the second less the first under them', async ({ page, baseURL }) => {
    const details = await showDetails(page, baseURL!, '00011,00044')
    const groups = details.getByTestId('value-details-group')
    await expect(groups).toHaveCount(2)
    for (const index of [0, 1])
      await expect(groups.nth(index).getByTestId('value-details-row')).toHaveCount(2)
    await expect(groups.nth(0).getByTestId('value-details-station')).toHaveText([/^1\.Donaueschingen \(Landeplatz\)\s*00011$/, /^2\.Großenkneten\s*00044$/])
    await expect(details.getByTestId('value-details-order')).toContainText('first Donaueschingen (Landeplatz) (00011), second Großenkneten (00044)')
    await expect(groups.nth(0).getByTestId('value-details-difference')).toContainText('Difference (2 − 1)')
  })

  test('has the second station less the first: a rise where the second reads higher, written with its sign', async ({ page, baseURL }) => {
    const details = await showDetails(page, baseURL!, '00011,00044')
    // the mock reads a station other than 00011 a few degrees higher: the mean of the first parameter's difference is a rise
    const difference = details.getByTestId('value-details-difference').first()
    await expect(difference.locator('td').nth(2)).toHaveText(/^\+\d+\.\d\d$/)
    // and the rows above it are the first station's and then the second's, in the order of the sentence
    await expect(details.getByTestId('value-details-group').first().getByTestId('value-details-station')).toContainText(['00011', '00044'])
  })

  test('has a sum, and its difference with a share of the first, for the rain and none for the temperature', async ({ page, baseURL }) => {
    const details = await showDetails(page, baseURL!, '00011,00044')
    // the groups are by name: the precipitation first
    const [rain, temperature] = [details.getByTestId('value-details-group').nth(0), details.getByTestId('value-details-group').nth(1)]
    await expect(rain.getByTestId('value-details-row').nth(0).getByTestId('value-details-sum')).toHaveText(/^\d+\.\d\d$/)
    await expect(rain.getByTestId('value-details-difference').getByTestId('value-details-sum')).toHaveText(/^\+\d+\.\d\d\s*\(\+\d+\.\d%\)\s*$/)
    await expect(rain.getByTestId('value-details-share')).toBeVisible()
    for (const sum of await temperature.getByTestId('value-details-sum').all()) {
      await expect(sum).toContainText('no sum for this parameter')
      await expect(sum).toHaveText(/—/)
    }
    await expect(details.getByTestId('value-details-sum-note')).toBeVisible()
  })

  test('is a labelled table: a region that takes the focus, headers with a scope, the stations as headers of their rows', async ({ page, baseURL }) => {
    const details = await showDetails(page, baseURL!, '00011,00044')
    const region = details.getByRole('region', { name: en.explorer.valuesDetails })
    await region.focus()
    await expect(region).toBeFocused()
    await expect(details.locator('thead th')).toHaveCount(9)
    for (const header of await details.locator('thead th').all())
      await expect(header).toHaveAttribute('scope', 'col')
    await expect(details.locator('tbody th[scope="row"]')).toHaveCount(6)
    await expect(details.locator('tbody th[scope="rowgroup"]')).toHaveCount(2)
  })

  test('is in the language of the page, with its decimal comma', async ({ page, baseURL }) => {
    const details = await showDetails(page, baseURL!, '00011,00044', 'de')
    await expect(details.getByTestId('value-details-order')).toContainText('erste Donaueschingen (Landeplatz) (00011), zweite Großenkneten (00044)')
    await expect(details.getByTestId('value-details-difference').first()).toContainText('Differenz (2 − 1)')
    await expect(details.getByTestId('value-details-difference').first().locator('td').nth(2)).toHaveText(/^\+\d+,\d\d$/)
  })
})

test.describe('value details of one station', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('are its rows with its name and id, and no order and no difference', async ({ page, baseURL }) => {
    const details = await showDetails(page, baseURL!, '00011')
    await expect(details.getByTestId('value-details-row')).toHaveCount(2)
    await expect(details.getByTestId('value-details-station').first()).toHaveText(/^Donaueschingen \(Landeplatz\)\s*00011$/)
    await expect(details.getByTestId('value-details-order')).toHaveCount(0)
    await expect(details.getByTestId('value-details-difference')).toHaveCount(0)
  })
})

test.describe('value details on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('scroll in their own box, and the page does not scroll sideways', async ({ page, baseURL }) => {
    const details = await showDetails(page, baseURL!, '00011,00044')
    await expect(details.getByTestId('value-details-difference').first()).toBeVisible()
    const widths = await page.evaluate(() => ({ page: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }))
    expect(widths.page).toBeLessThanOrEqual(widths.window)
    const region = details.getByRole('region', { name: en.explorer.valuesDetails })
    const box = await region.boundingBox()
    expect(box!.x + box!.width).toBeLessThanOrEqual(390)
  })
})
