import type { Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
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

for (const mode of ['light', 'dark'] as const) {
  test(`phone ${mode}`, async ({ page, baseURL }) => {
    const shot = (name: string) => page.screenshot({ path: `${OUT}${name}-${mode}-phone.png` })
    await open(page, baseURL!, '/about', mode, { width: 390, height: 780 })
    await shot('1-top')
    await scrollTo(page, 500)
    await settle(page)
    await shot('2-scrolled-down')
    await scrollTo(page, 440)
    await settle(page)
    await shot('3-scrolled-up')
    await page.getByRole('button', { name: 'Search' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.keyboard.type('exp')
    await page.waitForTimeout(500)
    await shot('4-search')
    await page.keyboard.press('Escape')

    await open(page, baseURL!, '/map', mode, { width: 390, height: 780 })
    await expect(page.getByTestId('map-screen').locator('.leaflet-container')).toBeVisible()
    await page.waitForTimeout(800)
    await shot('5-map')
  })
  test(`wider ${mode}`, async ({ page, baseURL }) => {
    for (const [name, size] of [['tablet', { width: 820, height: 1000 }], ['desktop', { width: 1280, height: 800 }]] as const) {
      await open(page, baseURL!, '/about', mode, size)
      await scrollTo(page, 500)
      await settle(page)
      await page.screenshot({ path: `${OUT}6-scrolled-${mode}-${name}.png` })
    }
  })
}

test('the slide, in frames', async ({ page, baseURL }) => {
  await open(page, baseURL!, '/about', 'light', { width: 390, height: 780 })
  await scrollTo(page, 500)
  // the transition paused at a third and at two thirds of its way
  for (const [name, at] of [['a', 50], ['b', 110]] as const) {
    await page.evaluate((t) => {
      for (const animation of document.getAnimations()) {
        animation.pause()
        animation.currentTime = t
      }
    }, at)
    await page.waitForTimeout(100)
    await page.screenshot({ path: `${OUT}7-slide-${name}-light-phone.png` })
  }
})
