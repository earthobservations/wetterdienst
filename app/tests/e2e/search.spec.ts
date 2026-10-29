import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The search of the app (components/AppSearch.vue, GH-3518), driven by keys alone: a dialog with a combobox whose
// listbox holds the pages, the appearance, the languages and the forecast stations. The backend is the spec's own
// (`mockBackend`), so the stations are the four MOSMIX stations it answers with.

test.describe('the search', () => {
  test.describe.configure({ timeout: 60_000 })

  test.beforeEach(async ({ context, page, baseURL }) => {
    await context.addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])
    await mockBackend(page, baseURL!)
  })

  const dialog = (page: import('@playwright/test').Page) => page.getByRole('dialog', { name: 'Search' })
  const field = (page: import('@playwright/test').Page) => page.getByRole('combobox', { name: 'Search' })
  /** Ctrl+K (⌘K on a Mac), once the app has started: with `ssr: false` its listener is in place when the rail is drawn */
  async function shortcut(page: import('@playwright/test').Page) {
    await expect(page.locator('header button[aria-keyshortcuts]')).toBeVisible()
    await page.keyboard.press('ControlOrMeta+k')
    await expect(dialog(page)).toBeVisible()
  }

  test('opens from the rail\'s button, keeps the focus, and Escape closes it and gives the focus back', async ({ page }) => {
    await page.goto('/')
    // by its shortcut, not by role: while the dialog is open the page behind it is hidden from the accessibility tree
    const button = page.locator('header button[aria-keyshortcuts]')
    await expect(button).toHaveAccessibleName('Search')
    await expect(button).toHaveAttribute('aria-expanded', 'false')
    await button.focus()
    await page.keyboard.press('Enter')

    await expect(dialog(page)).toBeVisible()
    await expect(field(page)).toBeFocused()
    await expect(field(page)).toHaveAttribute('aria-expanded', 'true')
    await expect(button).toHaveAttribute('aria-expanded', 'true')
    // Tab through more stops than the dialog has: the focus never leaves it, forwards or back
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

  test('opens with Ctrl+K or ⌘K from anywhere on a page, a field too', async ({ page }) => {
    await page.goto('/glossary')
    const search = page.getByRole('textbox').first()
    await search.focus()
    await shortcut(page)
    await expect(dialog(page)).toBeVisible()
    await expect(field(page)).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(dialog(page)).toBeHidden()
    await expect(search).toBeFocused()
  })

  test('moves the active option by the arrow keys and opens a page by Enter', async ({ page }) => {
    await page.goto('/')
    await shortcut(page)
    await expect(field(page)).toBeFocused()

    const options = page.getByRole('option')
    await expect(options.first()).toHaveAttribute('aria-selected', 'true')
    await page.keyboard.press('ArrowDown')
    await expect(options.nth(1)).toHaveAttribute('aria-selected', 'true')
    await expect(options.first()).toHaveAttribute('aria-selected', 'false')
    // the field names the active option
    const second = await options.nth(1).getAttribute('id')
    await expect(field(page)).toHaveAttribute('aria-activedescendant', second!)
    // ArrowUp from the first wraps round to the last
    await page.keyboard.press('ArrowUp')
    await page.keyboard.press('ArrowUp')
    await expect(options.last()).toHaveAttribute('aria-selected', 'true')

    await field(page).fill('glossary')
    await expect(options.first()).toContainText('Glossary')
    await expect(options.first()).toHaveAttribute('aria-selected', 'true')
    await expect(page.getByRole('status').filter({ hasText: /^Results: \d+$/ })).toHaveText('Results: 1')
    await page.keyboard.press('Enter')
    await expect(dialog(page)).toBeHidden()
    await expect(page).toHaveURL(/\/glossary$/)
  })

  test('finds a forecast station by its name, umlaut or not, and opens its forecast', async ({ page }) => {
    await page.goto('/')
    await shortcut(page)
    await field(page).fill('münchen')
    const station = page.getByRole('group', { name: 'Forecast stations' }).getByRole('option')
    await expect(station).toHaveCount(1)
    await expect(station).toContainText('MUENCHEN-STADT')
    await expect(station).toHaveAttribute('aria-selected', 'true')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/meteogram\?station=10865$/)
  })

  test('sets the appearance and the language', async ({ page }) => {
    await page.goto('/')
    await shortcut(page)
    await field(page).fill('dark')
    await expect(page.getByRole('option').first()).toContainText('Dark')
    await page.keyboard.press('Enter')
    await expect(page.locator('html')).toHaveClass(/dark/)

    await shortcut(page)
    await field(page).fill('deutsch')
    await page.keyboard.press('Enter')
    await expect(page.locator('html')).toHaveAttribute('lang', 'de')
  })

  test('says so when nothing matches, and the list is gone', async ({ page }) => {
    await page.goto('/')
    await shortcut(page)
    await field(page).fill('qqqqzzzz')
    await expect(page.getByText('Nothing matches your search.')).toBeVisible()
    await expect(page.getByRole('listbox')).toHaveCount(0)
    await expect(field(page)).toHaveAttribute('aria-expanded', 'false')
  })

  test('is in the bar of a narrow window, beside the menu', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')
    // by its shortcut, not by role: while the dialog is open the page behind it is hidden from the accessibility tree
    const button = page.locator('header button[aria-keyshortcuts]')
    await button.click()
    await expect(dialog(page)).toBeVisible()
    await expect(field(page)).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(button).toBeFocused()
  })
})
