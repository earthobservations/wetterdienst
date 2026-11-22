import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The Explorer's value details (GH-4296): split by station, a sum only for a parameter that adds up. The API is answered by the
// mock backend, so the spec needs nothing but the app.

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

  test('are one row for each station of each parameter, in the order the stations are listed, and nothing compares them', async ({ page, baseURL }) => {
    const details = await showDetails(page, baseURL!, '00011,00044')
    const groups = details.getByTestId('value-details-group')
    await expect(groups).toHaveCount(2)
    for (const index of [0, 1])
      await expect(groups.nth(index).getByTestId('value-details-row')).toHaveCount(2)
    await expect(groups.nth(0).getByTestId('value-details-station')).toHaveText([/^Donaueschingen \(Landeplatz\),?\s*00011$/, /^Großenkneten,?\s*00044$/])
    await expect(details.getByTestId('value-details-difference')).toHaveCount(0)
    await expect(details.getByTestId('value-details-order')).toHaveCount(0)
  })

  test('has a sum for the rain and none for the temperature', async ({ page, baseURL }) => {
    const details = await showDetails(page, baseURL!, '00011,00044')
    // the groups are by name: the precipitation first
    const [rain, temperature] = [details.getByTestId('value-details-group').nth(0), details.getByTestId('value-details-group').nth(1)]
    await expect(rain.getByTestId('value-details-sum')).toHaveText([/^\d+\.\d\d$/, /^\d+\.\d\d$/])
    for (const sum of await temperature.getByTestId('value-details-sum').all()) {
      await expect(sum).toContainText('no sum for this parameter')
      await expect(sum).toHaveText(/—/)
    }
    await expect(details.getByTestId('value-details-sum-note')).toBeVisible()
  })

  test('is a table named by its caption: a box that takes the focus, headers with a scope, the stations as headers of their rows', async ({ page, baseURL }) => {
    const details = await showDetails(page, baseURL!, '00011,00044')
    const box = details.getByTestId('value-details-scroll')
    await box.focus()
    await expect(box).toBeFocused()
    await expect(details.getByRole('table', { name: en.explorer.valuesDetails })).toBeVisible()
    await expect(details.locator('thead th')).toHaveCount(9)
    for (const header of await details.locator('thead th').all())
      await expect(header).toHaveAttribute('scope', 'col')
    await expect(details.locator('tbody th[scope="row"]')).toHaveCount(4)
    await expect(details.locator('tbody th[scope="rowgroup"]')).toHaveCount(2)
  })

  test('is in the language of the page, with its decimal comma', async ({ page, baseURL }) => {
    const details = await showDetails(page, baseURL!, '00011,00044', 'de')
    await expect(details.getByTestId('value-details-group').first().getByTestId('value-details-sum').first()).toHaveText(/^\d+,\d\d$/)
    await expect(details.getByTestId('value-details-group').nth(1).getByTestId('value-details-sum').first()).toContainText('keine Summe für diesen Parameter')
  })
})

test.describe('value details of one station', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('are its rows with its name and id', async ({ page, baseURL }) => {
    const details = await showDetails(page, baseURL!, '00011')
    await expect(details.getByTestId('value-details-row')).toHaveCount(2)
    await expect(details.getByTestId('value-details-station').first()).toHaveText(/^Donaueschingen \(Landeplatz\),?\s*00011$/)
  })
})

test.describe('value details on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('scroll in their own box, and the page does not scroll sideways', async ({ page, baseURL }) => {
    const details = await showDetails(page, baseURL!, '00011,00044')
    await expect(details.getByTestId('value-details-row').first()).toBeVisible()
    const widths = await page.evaluate(() => ({ page: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }))
    expect(widths.page).toBeLessThanOrEqual(widths.window)
    const box = await details.getByTestId('value-details-scroll').boundingBox()
    expect(box!.x + box!.width).toBeLessThanOrEqual(390)
  })
})
