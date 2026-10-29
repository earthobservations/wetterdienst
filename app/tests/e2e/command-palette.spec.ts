import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The app's search (CommandPalette.vue, GH-3518), by keys alone: a dialog that keeps the focus, with a combobox whose
// list box is named, whose active option moves by the arrow keys, which Enter takes and Escape leaves, giving the
// focus back to what opened it. The backend is the accessibility spec's mock, so this needs no backend.

test.use({ locale: 'en-GB' })

test.beforeEach(async ({ context, page, baseURL }) => {
  await context.addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])
  await mockBackend(page, baseURL!)
})

const dialog = (page: Page) => page.getByRole('dialog', { name: 'Search and commands' })
const field = (page: Page) => dialog(page).getByRole('combobox', { name: 'Search pages, settings and stations' })

/**
 * The rail's search button. By its shortcut rather than by role: while the dialog is open, the page behind it (the
 * rail too) is hidden from the accessibility tree
 */
const searchButton = (page: Page) => page.locator('header button[aria-keyshortcuts]')

/** The page is up, and so is the app that listens for the shortcut */
async function ready(page: Page) {
  await expect(page.getByRole('banner').getByRole('button', { name: 'Search', exact: true })).toBeVisible()
}

/** The option the combobox names as active */
async function activeOption(page: Page) {
  const id = await field(page).getAttribute('aria-activedescendant')
  expect(id).toBeTruthy()
  return page.locator(`[id="${id}"]`)
}

test('the search button opens it, the arrow keys move in it, the focus stays in it and Escape gives it back', async ({ page }) => {
  await page.goto('/')
  await ready(page)
  const button = searchButton(page)
  await expect(button).toHaveAttribute('aria-expanded', 'false')
  await button.focus()
  await page.keyboard.press('Enter')

  await expect(dialog(page)).toBeVisible()
  await expect(field(page)).toBeFocused()
  await expect(button).toHaveAttribute('aria-expanded', 'true')
  await expect(field(page)).toHaveAttribute('aria-expanded', 'true')
  const listId = await field(page).getAttribute('aria-controls')
  const list = page.locator(`[id="${listId}"]`)
  await expect(list).toHaveAttribute('role', 'listbox')
  await expect(list).toHaveAccessibleName('Results')

  // the first option is active, and it is the one that says so
  let active = await activeOption(page)
  await expect(active).toHaveAttribute('aria-selected', 'true')
  await expect(active).toContainText('Home')
  await page.keyboard.press('ArrowDown')
  active = await activeOption(page)
  await expect(active).toContainText('Forecast')
  await expect(active).toHaveAttribute('aria-selected', 'true')
  await expect(list.locator('[aria-selected="true"]')).toHaveCount(1)
  // up from the first goes round to the last
  await page.keyboard.press('ArrowUp')
  await page.keyboard.press('ArrowUp')
  await expect(await activeOption(page)).toContainText('Appearance')

  // Tab and Shift+Tab, more often than the dialog has stops: the focus never leaves it
  for (const key of ['Tab', 'Shift+Tab']) {
    for (let stop = 0; stop < 6; stop++) {
      await page.keyboard.press(key)
      expect(await dialog(page).evaluate(node => node.contains(document.activeElement))).toBe(true)
    }
  }

  await field(page).focus()
  await page.keyboard.press('Escape')
  await expect(dialog(page)).toBeHidden()
  await expect(button).toBeFocused()
})

test('Ctrl+K opens it from anywhere, and Enter opens the page that was found', async ({ page }) => {
  await page.goto('/')
  await ready(page)
  await page.keyboard.press('Control+k')
  await expect(field(page)).toBeFocused()

  await page.keyboard.type('parameter unit')
  await expect(await activeOption(page)).toContainText('Glossary')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/glossary$/)
  await expect(dialog(page)).toBeHidden()

  // nothing found is said, and the list is gone
  await page.keyboard.press('Control+k')
  await page.keyboard.type('zzzz')
  await expect(dialog(page).getByText('Nothing found.')).toBeVisible()
  await expect(field(page)).toHaveAttribute('aria-expanded', 'false')
  await expect(field(page)).not.toHaveAttribute('aria-activedescendant')
})

test('a station opens its forecast', async ({ page }) => {
  await page.goto('/glossary')
  await ready(page)
  await page.keyboard.press('Control+k')
  await page.keyboard.type('hamburg')
  const station = dialog(page).getByRole('option', { name: /HAMBURG-FUHLSBUETTEL/ })
  await expect(station).toBeVisible()
  // the stations come after the actions: move down until it is the active one
  for (let step = 0; step < 10 && await station.getAttribute('aria-selected') !== 'true'; step++)
    await page.keyboard.press('ArrowDown')
  await expect(station).toHaveAttribute('aria-selected', 'true')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/meteogram\?station=10147/)
  await expect(page.getByText('HAMBURG-FUHLSBUETTEL').first()).toBeVisible()

  // and from the forecast page itself, which stays and takes the other station
  await page.keyboard.press('Control+k')
  await page.keyboard.type('10384')
  const berlin = dialog(page).getByRole('option', { name: /BERLIN-TEMPELHOF/ })
  for (let step = 0; step < 10 && await berlin.getAttribute('aria-selected') !== 'true'; step++)
    await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/meteogram\?station=10384/)
  await expect(page.getByText('BERLIN-TEMPELHOF').first()).toBeVisible()
})

test('the appearance and the language are set from it', async ({ page }) => {
  await page.goto('/')
  await ready(page)
  await page.keyboard.press('Control+k')
  await page.keyboard.type('appearance dark')
  await expect(await activeOption(page)).toContainText('Appearance: Dark')
  await page.keyboard.press('Enter')
  await expect(page.locator('html')).toHaveClass(/dark/)

  await page.keyboard.press('Control+k')
  await page.keyboard.type('deutsch')
  const option = await activeOption(page)
  await expect(option).toContainText('Language: Deutsch')
  // the name of the language is marked as being in that language
  await expect(option.locator('[lang="de"]')).toHaveText('Deutsch')
  await page.keyboard.press('Enter')
  await expect(page.locator('html')).toHaveAttribute('lang', 'de')
})
