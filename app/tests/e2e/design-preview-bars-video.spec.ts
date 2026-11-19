import type { Page } from '@playwright/test'
import { copyFileSync, mkdirSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'

// Design preview of GH-4226 (a commit of its own, removed in the next one): the screenshots of the pull request.
const OUT = new URL('../../design-preview/4226/', import.meta.url).pathname
mkdirSync(OUT, { recursive: true })

async function open(page: Page, baseURL: string, path: string, mode: 'light' | 'dark', size: { width: number, height: number }) {
  await page.setViewportSize(size)
  await page.context().addCookies([{ name: 'wd_lang', value: 'en', url: baseURL }])
  await page.addInitScript(m => localStorage.setItem('nuxt-color-mode', m), mode)
  await mockBackend(page, baseURL)
  await page.goto(path)
  // the dev server's floating toolbar is no part of the app
  await page.addStyleTag({ content: '#nuxt-devtools-container { display: none !important }' })
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('button', { name: 'Search' })).toBeEnabled()
  await page.waitForTimeout(600)
  // the reader's first input: only a scroll that follows one hides the bars
  await page.mouse.move(200, 400)
  await page.mouse.wheel(0, 1)
}
const scrollTo = (page: Page, y: number) => page.evaluate(top => window.scrollTo({ top, behavior: 'instant' }), y)
const settle = (page: Page) => page.waitForTimeout(500)


test.use({ viewport: { width: 390, height: 780 }, video: { mode: 'on', size: { width: 390, height: 780 } } })
test('down and up again', async ({ page, baseURL }) => {
    await open(page, baseURL!, '/about', 'light', { width: 390, height: 780 })
    await page.mouse.move(200, 400)
    for (let step = 0; step < 9; step++) {
      await page.mouse.wheel(0, 70)
      await page.waitForTimeout(60)
    }
    await page.waitForTimeout(900)
    for (let step = 0; step < 4; step++) {
      await page.mouse.wheel(0, -70)
      await page.waitForTimeout(60)
    }
    await page.waitForTimeout(900)
    for (let step = 0; step < 9; step++) {
      await page.mouse.wheel(0, 70)
      await page.waitForTimeout(60)
    }
    await page.waitForTimeout(700)
    const video = page.video()!
    await page.close()
    copyFileSync(await video.path(), `${OUT}scroll-light-phone.webm`)
  })
