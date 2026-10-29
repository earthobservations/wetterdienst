import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The search of the app (GH-3518), by keys alone (WCAG 2.1.1, 2.1.2, 2.4.3, 4.1.2): Ctrl+K / ⌘K and the masthead's
// button open it, the field is a combobox that controls a listbox, the arrow keys move the highlighted option and
// Enter takes it, the dialog keeps the focus, and Escape closes it and gives the focus back. The backend is answered
// in the browser (accessibility/mock-backend.ts), which has three forecast stations, Hamburg among them.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))

async function openHome(page: Page, baseURL: string) {
  await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL }])
  await mockBackend(page, baseURL)
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
}

/** The field, the list it controls and the option it names as highlighted */
function palette(page: Page) {
  const dialog = page.getByRole('dialog', { name: en.search.title })
  const field = dialog.getByRole('combobox', { name: en.search.label })
  const listbox = dialog.getByRole('listbox')
  const highlighted = async () => {
    const id = await field.getAttribute('aria-activedescendant')
    return id ? dialog.locator(`[id="${id}"]`) : null
  }
  return { dialog, field, listbox, highlighted }
}

test.describe('the search', () => {
  test('opens by Ctrl+K or ⌘K, finds a page and goes there by Enter', async ({ page, baseURL }) => {
    await openHome(page, baseURL!)
    await page.keyboard.press('ControlOrMeta+K')
    const { dialog, field, listbox, highlighted } = palette(page)
    await expect(dialog).toBeVisible()
    // the field has the focus, and is a combobox that names the list it controls
    await expect(field).toBeFocused()
    await expect(field).toHaveAttribute('aria-expanded', 'true')
    await expect(field).toHaveAttribute('aria-controls', (await listbox.getAttribute('id'))!)
    // the pages are there, each with a line on what it is for
    await expect(listbox.getByRole('option', { name: new RegExp(`^${en.nav.glossary}`) })).toBeVisible()

    await page.keyboard.type('glossary')
    const first = (await highlighted())!
    await expect(first).toHaveAttribute('aria-selected', 'true')
    await expect(first).toContainText(en.nav.glossary)
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/glossary$/)
    await expect(dialog).toBeHidden()
  })

  test('moves by the arrow keys, keeps the focus, and gives it back to its button on Escape', async ({ page, baseURL }) => {
    await openHome(page, baseURL!)
    const button = page.getByRole('banner').getByRole('button', { name: en.search.button, exact: true })
    await expect(button).toHaveAttribute('aria-haspopup', 'dialog')
    await button.focus()
    await page.keyboard.press('Enter')
    const { dialog, field, highlighted } = palette(page)
    await expect(field).toBeFocused()

    // the arrow keys move the highlighted option, one at a time, and round from the last to the first
    const ids: string[] = []
    for (let step = 0; step < 3; step++) {
      ids.push((await field.getAttribute('aria-activedescendant'))!)
      await page.keyboard.press('ArrowDown')
    }
    expect(new Set(ids).size).toBe(3)
    await page.keyboard.press('ArrowUp')
    await expect(field).toHaveAttribute('aria-activedescendant', ids[2]!)
    await expect((await highlighted())!).toHaveAttribute('aria-selected', 'true')

    // Tab through more stops than the dialog has: the focus never leaves it, forwards or back
    for (const key of ['Tab', 'Shift+Tab']) {
      for (let stop = 0; stop < 8; stop++) {
        await page.keyboard.press(key)
        expect(await dialog.evaluate(node => node.contains(document.activeElement))).toBe(true)
      }
    }
    await field.focus()
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect(button).toBeFocused()
  })

  test('finds a station of the forecast and opens its forecast', async ({ page, baseURL }) => {
    await openHome(page, baseURL!)
    await page.keyboard.press('ControlOrMeta+K')
    const { field, listbox } = palette(page)
    await page.keyboard.type('hamburg')
    const station = listbox.getByRole('option', { name: /HAMBURG-FUHLSBUETTEL/ })
    await expect(station).toBeVisible()
    const stationId = (await station.getAttribute('id'))!
    for (let step = 0; step < 10 && await field.getAttribute('aria-activedescendant') !== stationId; step++)
      await page.keyboard.press('ArrowDown')
    await expect(station).toHaveAttribute('aria-selected', 'true')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/meteogram\?station=10147/)
  })

  test('switches the appearance, and says what it found and what it did not', async ({ page, baseURL }) => {
    await openHome(page, baseURL!)
    await page.keyboard.press('ControlOrMeta+K')
    const { dialog, field } = palette(page)
    await page.keyboard.type('zzzz')
    await expect(field).toHaveAttribute('aria-expanded', 'false')
    await expect(dialog.getByRole('status')).toHaveText(en.search.empty.replace('{query}', 'zzzz'))

    await field.fill(en.settings.themeDark)
    await expect(dialog.getByRole('option', { name: new RegExp(`${en.settings.theme}: ${en.settings.themeDark}`) })).toHaveAttribute('aria-selected', 'true')
    await page.keyboard.press('Enter')
    await expect(page.locator('html')).toHaveClass(/dark/)
    await expect(dialog).toBeHidden()
  })
})
