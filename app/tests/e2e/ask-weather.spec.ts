import type { Page } from '@playwright/test'
import type { Asked } from './accessibility/ask-backend'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { askHandlers } from './accessibility/ask-backend'
import { ApiFailure, mockBackend } from './accessibility/mock-backend'

// Ask the weather (GH-3518): the home page's suggestions, each answered from the data, with the way into the tool
// that holds it. The backend is the mock of the accessibility spec with the answers of the questions, so nothing here
// reaches a provider.

const en = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/en.json', import.meta.url)), 'utf-8'))
const de = JSON.parse(readFileSync(fileURLToPath(new URL('../../i18n/locales/de.json', import.meta.url)), 'utf-8'))

async function home(page: Page, baseURL: string, path = '/', language = 'en') {
  const asked: Asked[] = []
  await page.context().addCookies([{ name: 'wd_lang', value: language, url: baseURL }])
  const backend = await mockBackend(page, baseURL, askHandlers(asked))
  await page.addInitScript(() => {
    try {
      localStorage.removeItem('wd-place')
    }
    catch {}
  })
  await page.goto(path)
  await expect(page.getByTestId('ask')).toBeVisible()
  return { asked, backend }
}

const questions = (page: Page) => page.getByTestId('questions')
const chip = (page: Page, id: string) => page.getByTestId(`question-${id}`)
const askedValues = (asked: Asked[]) => asked.filter(entry => entry.path === 'values')

test.describe('the suggestions', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('are a list of buttons, none pressed, and ask nothing until one is picked', async ({ page, baseURL }) => {
    const { asked } = await home(page, baseURL!)
    const list = questions(page)
    await expect(list.getByRole('listitem')).toHaveCount(4)
    await expect(list.getByRole('button')).toHaveCount(4)
    for (const id of ['rain', 'summer', 'wind', 'download'])
      await expect(chip(page, id)).toHaveAttribute('aria-pressed', 'false')
    await expect(chip(page, 'rain')).toContainText('Will it rain in Kiel-Holtenau tomorrow?')
    await expect(page.getByTestId('ask-idle')).toHaveText(en.ask.idle)
    await expect(page.getByTestId('answer')).toHaveCount(0)
    // nothing about the weather has been asked of the backend
    expect(asked.filter(entry => entry.path === 'values' || entry.path === 'coverage')).toEqual([])
  })

  test('answer the rain question from the forecast nearest the place, and lead into the forecast', async ({ page, baseURL }) => {
    const { asked, backend } = await home(page, baseURL!)
    await chip(page, 'rain').click()
    await expect(chip(page, 'rain')).toHaveAttribute('aria-pressed', 'true')
    await expect(page).toHaveURL(/\?ask=rain$/)
    const verdict = page.getByTestId('answer-verdict')
    await expect(verdict).toHaveText(en.ask.rain.yes)
    const answer = page.getByTestId('answer')
    await expect(answer.getByRole('heading', { level: 3 })).toHaveText('Will it rain in Kiel-Holtenau tomorrow?')
    await expect(answer).toContainText('Forecast for KIEL-HOLTENAU, the forecast point nearest to Kiel-Holtenau (0.6 km away).')
    await expect(answer.getByRole('figure')).toBeVisible()
    // the forecast of that very point is where it leads, and the link carries the forecast's tile
    const link = answer.getByRole('link', { name: en.ask.rain.open })
    await expect(link).toHaveAttribute('href', '/meteogram?station=10046')
    // the live region says the verdict
    await expect(page.getByTestId('answer-status')).toHaveText(en.ask.rain.yes)
    // asked of the forecast of the place's position, then of that point's values
    expect(asked.find(entry => entry.path === 'stations' && entry.query.network === 'mosmix')?.query).toMatchObject({ latitude: '54.3776', longitude: '10.1424', rank: '1' })
    expect(askedValues(asked)[0]!.query).toMatchObject({ network: 'mosmix', stations: '10046' })
    expect(backend.unanswered).toEqual([])
  })

  test('answer whether last summer was hotter, and lead into the monthly means and the stripes', async ({ page, baseURL }) => {
    const { asked } = await home(page, baseURL!)
    await chip(page, 'summer').click()
    await expect(page.getByTestId('answer-verdict')).toContainText('Yes, ')
    await expect(page.getByTestId('answer-verdict')).toContainText('warmer than usual')
    const answer = page.getByTestId('answer')
    await expect(answer).toContainText('Number 1 of')
    const monthly = answer.getByRole('link', { name: en.ask.summer.open })
    const href = new URL((await monthly.getAttribute('href'))!, baseURL!)
    expect(href.pathname).toBe('/explorer')
    expect(Object.fromEntries(href.searchParams)).toMatchObject({ mode: 'station', provider: 'dwd', network: 'observation', resolution: 'monthly', dataset: 'climate_summary', parameters: 'temperature_air_mean_2m', stations: '02564' })
    await expect(answer.getByRole('link', { name: en.ask.summer.stripes })).toHaveAttribute('href', '/stripes?kind=temperature&station=02564')
    expect(askedValues(asked)[0]!.query).toMatchObject({ parameters: 'monthly/climate_summary/temperature_air_mean_2m', stations: '02564' })
  })

  test('answer how windy a day was, for a day the reader can change', async ({ page, baseURL }) => {
    const { asked } = await home(page, baseURL!, '/?ask=wind&day=2025-12-26')
    await expect(chip(page, 'wind')).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByTestId('answer-verdict')).toHaveText(en.ask.wind.stormy)
    await expect(page.getByTestId('answer')).toContainText('Strongest gust 21.6 m/s, Beaufort 9.')
    await expect(chip(page, 'wind')).toContainText('How windy was it on 26 December?')
    expect(askedValues(asked)[0]!.query.timestamp).toBe('2025-12-19/2026-01-02')

    await page.getByLabel(en.ask.wind.dayLabel, { exact: true }).fill('2025-12-20')
    await expect(page).toHaveURL(/day=2025-12-20/)
    await expect(page.getByTestId('answer-verdict')).toHaveText(en.ask.wind.calm)
    const link = page.getByTestId('answer').getByRole('link', { name: en.ask.wind.open })
    const href = new URL((await link.getAttribute('href'))!, baseURL!)
    expect(Object.fromEntries(href.searchParams)).toMatchObject({ resolution: 'daily', parameters: 'wind_gust_max,wind_speed_mean', startDate: '2025-12-13', endDate: '2025-12-27' })
  })

  test('answer where hourly temperatures can be downloaded, each source leading into the Explorer filled in', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    await chip(page, 'download').click()
    await expect(page.getByTestId('answer-verdict')).toHaveText('Weather services that publish hourly air temperature: 2.')
    const sources = page.getByTestId('answer-sources').getByRole('link')
    await expect(sources).toHaveCount(2)
    // the place's own service first
    await expect(sources.first()).toContainText('DWD')
    const href = new URL((await sources.first().getAttribute('href'))!, baseURL!)
    expect(href.pathname).toBe('/explorer')
    expect(Object.fromEntries(href.searchParams)).toMatchObject({ provider: 'dwd', network: 'observation', resolution: 'hourly', dataset: 'temperature_air', parameters: 'temperature_air_mean_2m', stations: '02564' })
  })

  test('close when pressed again, and one opens in place of the other', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    await chip(page, 'summer').click()
    await expect(page.getByTestId('answer')).toBeVisible()
    await chip(page, 'wind').click()
    await expect(chip(page, 'summer')).toHaveAttribute('aria-pressed', 'false')
    await expect(chip(page, 'wind')).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByTestId('answer')).toHaveCount(1)
    await chip(page, 'wind').click()
    await expect(page.getByTestId('answer')).toHaveCount(0)
    await expect(page).not.toHaveURL(/ask=/)
    await expect(page.getByTestId('ask-idle')).toBeVisible()
  })

  test('are worked with the keyboard, and the focus stays on the one pressed', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    await page.getByTestId('place-button').focus()
    await page.keyboard.press('Tab')
    await expect(chip(page, 'rain')).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(chip(page, 'summer')).toBeFocused()
    await page.keyboard.press('Space')
    await expect(chip(page, 'summer')).toHaveAttribute('aria-pressed', 'true')
    await expect(chip(page, 'summer')).toBeFocused()
    await expect(page.getByTestId('answer-verdict')).toBeVisible()
    await expect(chip(page, 'summer')).toBeFocused()
    // the next Tab stop is the next suggestion, the answer's links come after the list
    await page.keyboard.press('Tab')
    await expect(chip(page, 'wind')).toBeFocused()
  })

  test('say so where the backend cannot answer, with a way to ask again', async ({ page, baseURL }) => {
    const { backend } = await home(page, baseURL!)
    const values = backend.handlers.values!
    backend.handlers.values = () => new ApiFailure(422, 'The request could not be processed.')
    await chip(page, 'summer').click()
    await expect(page.getByTestId('answer').getByText(en.ask.failed)).toBeVisible()
    backend.handlers.values = values
    await page.getByTestId('answer').getByRole('button', { name: en.common.retry }).click()
    await expect(page.getByTestId('answer-verdict')).toContainText('Yes, ')
  })

  test('open from a link, for the place the link names', async ({ page, baseURL }) => {
    const { asked } = await home(page, baseURL!, '/?ask=summer&place=00183')
    await expect(page.getByTestId('place-button')).toContainText('Arkona')
    await expect(chip(page, 'summer')).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByTestId('answer-verdict')).toBeVisible()
    expect(askedValues(asked).at(-1)!.query.stations).toBe('00183')
  })

  test('are in the language of the page', async ({ page, baseURL }) => {
    await home(page, baseURL!, '/', 'de')
    await expect(page.getByRole('heading', { level: 2, name: de.ask.title })).toBeVisible()
    await expect(chip(page, 'rain')).toContainText('Regnet es morgen in Kiel-Holtenau?')
    await chip(page, 'rain').click()
    await expect(page.getByTestId('answer-verdict')).toHaveText(de.ask.rain.yes)
  })
})

test.describe('the place', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('is chosen from the stations the backend finds by name, and the answers are about it', async ({ page, baseURL }) => {
    const { asked } = await home(page, baseURL!)
    const button = page.getByTestId('place-button')
    await expect(button).toContainText('Kiel-Holtenau')
    await button.click()
    const dialog = page.getByRole('dialog')
    const field = dialog.getByRole('combobox')
    await expect(field).toBeFocused()
    await expect(dialog).toContainText(en.ask.placeHint)
    await field.fill('ar')
    const options = dialog.getByRole('option')
    // Arkona reports; Artern stopped reporting in 2018 and is left out
    await expect(options).toHaveCount(1)
    await expect(options.first()).toContainText('Arkona')
    await expect(field).toHaveAttribute('aria-activedescendant', /.+/)
    await page.keyboard.press('Enter')
    await expect(dialog).toHaveCount(0)
    // the focus is back where it was
    await expect(button).toBeFocused()
    await expect(button).toContainText('Arkona')
    await expect(page).toHaveURL(/place=00183/)
    await expect(chip(page, 'rain')).toContainText('Will it rain in Arkona tomorrow?')

    await chip(page, 'summer').click()
    await expect(page.getByTestId('answer-verdict')).toBeVisible()
    expect(askedValues(asked).at(-1)!.query.stations).toBe('00183')
    // the place stays for the next visit
    await page.reload()
    await expect(page.getByTestId('place-button')).toContainText('Arkona')
  })

  test('is closed with Escape and changes nothing', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    const button = page.getByTestId('place-button')
    await button.click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await expect(button).toBeFocused()
    await expect(button).toContainText('Kiel-Holtenau')
  })

  test('says so where nothing is found', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    await page.getByTestId('place-button').click()
    await page.getByRole('dialog').getByRole('combobox').fill('zzzz')
    await expect(page.getByRole('dialog')).toContainText(en.shell.searchEmpty)
  })
})

test.describe('on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('the suggestions and an answer fit the width', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    for (const id of ['rain', 'summer', 'wind', 'download']) {
      await chip(page, id).click()
      await expect(page.getByTestId('answer')).toBeVisible()
      await expect(page.getByTestId('answer-status')).not.toBeEmpty()
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow, id).toBeLessThanOrEqual(0)
    }
    // each suggestion is a target of 44 px or more (WCAG 2.5.8 asks 24)
    for (const box of await Promise.all(['rain', 'summer', 'wind', 'download'].map(id => chip(page, id).boundingBox())))
      expect(box!.height).toBeGreaterThanOrEqual(44)
  })
})
