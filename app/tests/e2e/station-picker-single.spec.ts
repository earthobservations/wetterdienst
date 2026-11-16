import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The station picker names a single station once (GH-4151): where only one station can be picked (the forecast, the stripes) the
// search shows it, so the list has no chip block, and the map, which has no search, says it in one line. Several stations
// (the explorer) keep their chips. The API is answered by the mock backend, so the spec needs nothing but the app.

for (const width of [390, 1280]) {
  test.describe(`at ${width} px`, () => {
    test.use({ viewport: { width, height: 900 } })

    test('the stripes name their one station in the search in the list, and in one line on the map', async ({ page, baseURL }) => {
      await mockBackend(page, baseURL!)
      await page.addInitScript(() => localStorage.setItem('wd-station-picker', JSON.stringify({ stripes: 'list' })))
      await page.goto('/stripes?kind=temperature&station=00011')

      const picker = page.getByTestId('station-picker')
      // the station is the search's own text, and nothing else of the picker repeats it
      // (its accessible name is the label of the choice, "Station")
      const search = picker.getByRole('button', { name: 'Station', exact: true })
      // the first load of a page restores the station from the link once the list is in
      await expect(search).toContainText('(ID: 00011', { timeout: 30_000 })
      await expect(page.getByTestId('station-picker-chips')).toHaveCount(0)
      await expect(page.locator('[data-station-chip]')).toHaveCount(0)
      await expect(page.getByTestId('station-picker-selected')).toHaveCount(0)

      await picker.getByRole('radio', { name: 'Map', exact: true }).click()
      await expect(page.locator('.leaflet-container')).toBeVisible({ timeout: 30_000 })
      // the line names it once, with no button to take it out
      const line = page.getByTestId('station-picker-selected')
      await expect(line).toHaveCount(1)
      await expect(line).toContainText('Selected station:')
      await expect(line).toContainText('(00011)')
      await expect(line.getByRole('button')).toHaveCount(0)
      await expect(page.getByTestId('station-picker-chips')).toHaveCount(0)

      // and back in the list the search has it again
      await picker.getByRole('radio', { name: 'List', exact: true }).click()
      await expect(search).toContainText('(ID: 00011')
      await expect(page.getByTestId('station-picker-selected')).toHaveCount(0)
    })

    test('the explorer keeps the chips of its several stations, in the list and on the map', async ({ page, baseURL }) => {
      await mockBackend(page, baseURL!)
      await page.addInitScript(() => localStorage.setItem('wd-station-picker', JSON.stringify({ explorer: 'list' })))
      await page.goto('/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m,temperature_air_mean_2m&mode=station&stations=00011')

      const chips = page.getByTestId('station-picker-chips')
      await expect(chips.locator('[data-station-chip]')).toHaveCount(1, { timeout: 30_000 })
      await expect(chips.getByRole('heading', { level: 3 })).toHaveText('Selected Stations:')
      await expect(page.getByTestId('station-picker-selected')).toHaveCount(0)

      await page.getByTestId('station-picker').getByRole('radio', { name: 'Map', exact: true }).click()
      await expect(page.locator('.leaflet-container')).toBeVisible({ timeout: 30_000 })
      await expect(chips.locator('[data-station-chip]')).toHaveCount(1)
      await expect(page.getByTestId('station-picker-selected')).toHaveCount(0)
    })
  })
}
