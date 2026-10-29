import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// The command palette (GH-3518), by keys alone: the search button of the header and Ctrl+K open it, it is the ARIA
// combobox with a list box (the focus stays in the field, the arrow keys move the active option, Enter runs it), the
// dialog keeps the focus, Escape closes it and the focus goes back to where it was. Then what it finds: a page, a
// station, a stretch of time on the axis, the appearance and the language. The backend is the accessibility spec's
// mock, so nothing here needs one running.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))
const TITLE: string = en.palette.title

test.use({ locale: 'en-GB' })

test.beforeEach(async ({ context, baseURL }) => {
  await context.addCookies([{ name: 'wd_lang', value: 'en', url: baseURL! }])
  await context.addInitScript(() => localStorage.setItem('nuxt-color-mode', 'light'))
})

const dialogOf = (page: Page) => page.getByRole('dialog', { name: TITLE })
const fieldOf = (page: Page) => dialogOf(page).getByRole('combobox', { name: TITLE })

/** The option the field says is active, by its `aria-activedescendant` */
async function activeOption(page: Page) {
  const id = await fieldOf(page).getAttribute('aria-activedescendant')
  expect(id, 'the field names an active option').toBeTruthy()
  return page.locator(`[id="${id}"]`)
}

async function openByShortcut(page: Page) {
  await page.keyboard.press('Control+k')
  await expect(fieldOf(page)).toBeFocused()
}

test('opens by its button, is a combobox with a list box, keeps the focus and gives it back', async ({ page, baseURL }) => {
  await mockBackend(page, baseURL!)
  await page.goto('/')
  const trigger = page.getByTestId('search-trigger')
  await expect(trigger).toBeVisible()
  await expect(trigger).toHaveAttribute('aria-haspopup', 'dialog')
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')

  await trigger.focus()
  await page.keyboard.press('Enter')
  const dialog = dialogOf(page)
  const field = fieldOf(page)
  await expect(dialog).toBeVisible()
  await expect(field).toBeFocused()
  await expect(trigger).toHaveAttribute('aria-expanded', 'true')

  // the field controls the list, which is expanded, and names its active option, the only one selected
  const listbox = dialog.getByRole('listbox')
  await expect(field).toHaveAttribute('aria-expanded', 'true')
  await expect(field).toHaveAttribute('aria-autocomplete', 'list')
  await expect(field).toHaveAttribute('aria-controls', (await listbox.getAttribute('id'))!)
  const first = await activeOption(page)
  await expect(first).toHaveAttribute('role', 'option')
  await expect(first).toHaveAttribute('aria-selected', 'true')
  await expect(listbox.locator('[role="option"][aria-selected="true"]')).toHaveCount(1)
  // the groups of options are named
  for (const group of await listbox.getByRole('group').all())
    await expect(group).toHaveAccessibleName(/\S/)

  // the arrow keys move the active option, and come round at the ends
  const firstId = await field.getAttribute('aria-activedescendant')
  await page.keyboard.press('ArrowDown')
  await expect(field).not.toHaveAttribute('aria-activedescendant', firstId!)
  await expect(await activeOption(page)).toHaveAttribute('aria-selected', 'true')
  await page.keyboard.press('ArrowUp')
  await expect(field).toHaveAttribute('aria-activedescendant', firstId!)
  await page.keyboard.press('ArrowUp')
  const last = listbox.getByRole('option').last()
  await expect(field).toHaveAttribute('aria-activedescendant', (await last.getAttribute('id'))!)
  await expect(field).toBeFocused()

  // Tab never leaves the dialog, forwards or back
  for (const key of ['Tab', 'Shift+Tab']) {
    for (let stop = 0; stop < 6; stop++) {
      await page.keyboard.press(key)
      expect(await dialog.evaluate(node => node.contains(document.activeElement))).toBe(true)
    }
  }

  // Escape closes it, and the focus is back on the button
  await field.focus()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(trigger).toBeFocused()
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')
})

test('opens by Ctrl+K wherever the focus is, and gives the focus back there', async ({ page, baseURL }) => {
  await mockBackend(page, baseURL!)
  await page.goto('/glossary')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  const link = page.getByTestId('time-rail').getByRole('link').first()
  await link.focus()

  await openByShortcut(page)
  // the shortcut again closes it
  await page.keyboard.press('Control+k')
  await expect(dialogOf(page)).toBeHidden()
  await expect(link).toBeFocused()

  await openByShortcut(page)
  await page.keyboard.press('Escape')
  await expect(dialogOf(page)).toBeHidden()
  await expect(link).toBeFocused()
})

test('finds a page and goes there by Enter', async ({ page, baseURL }) => {
  await mockBackend(page, baseURL!)
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await openByShortcut(page)
  await page.keyboard.type('glossary')
  await expect(await activeOption(page)).toContainText(en.nav.glossary)
  // what each page is for, in one line
  await expect(await activeOption(page)).toContainText(en.palette.pages.glossary)
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/glossary$/)
  await expect(dialogOf(page)).toBeHidden()
})

test('finds a station of the forecast, and moves along the axis of time with it', async ({ page, baseURL }) => {
  await mockBackend(page, baseURL!)
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await openByShortcut(page)
  await page.keyboard.type('hamburg')
  const group = dialogOf(page).getByRole('group', { name: en.palette.groupForecastStations })
  await expect(group.getByRole('option', { name: /HAMBURG-FUHLSBUETTEL/ })).toBeVisible()
  await expect(await activeOption(page)).toContainText('HAMBURG-FUHLSBUETTEL')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/meteogram\?station=10147/)

  // the next 24 hours of the same station
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await openByShortcut(page)
  await page.keyboard.type(en.palette.time.next24h)
  await expect(await activeOption(page)).toContainText(en.palette.time.next24h)
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/meteogram\?station=10147&horizon=24/)
})

test('switches the appearance and the language', async ({ page, baseURL }) => {
  await mockBackend(page, baseURL!)
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.locator('html')).not.toHaveClass(/dark/)

  await openByShortcut(page)
  await page.keyboard.type(en.settings.themeDark)
  await expect(await activeOption(page)).toContainText(en.settings.themeDark)
  await page.keyboard.press('Enter')
  await expect(page.locator('html')).toHaveClass(/dark/)
  await expect(dialogOf(page)).toBeHidden()

  await openByShortcut(page)
  await page.keyboard.type('Deutsch')
  await page.keyboard.press('Enter')
  await expect(page.locator('html')).toHaveAttribute('lang', 'de')
})

test('says so when nothing is found, and the list is then collapsed', async ({ page, baseURL }) => {
  await mockBackend(page, baseURL!)
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await openByShortcut(page)
  await page.keyboard.type('zzzzqqq')
  await expect(dialogOf(page).getByText(en.palette.empty).first()).toBeVisible()
  await expect(fieldOf(page)).toHaveAttribute('aria-expanded', 'false')
  await expect(fieldOf(page)).not.toHaveAttribute('aria-activedescendant', /.+/)
})
