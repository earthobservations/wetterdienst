import type { Page } from '@playwright/test'
import type { Asked } from './accessibility/ask-backend'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { DateTime } from 'luxon'
import { defaultSeason } from '../../app/utils/answers'
import { askHandlers, lastSummerYear } from './accessibility/ask-backend'
import { ApiFailure, mockBackend } from './accessibility/mock-backend'
import { expectAtLeastPx } from './target-size'

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
    for (const id of ['rain', 'season', 'wind', 'download'])
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
    // the old link asks about the summer, whatever season the question opens on
    const { asked } = await home(page, baseURL!, '/?ask=summer')
    await expect(page.getByTestId('answer-verdict')).toContainText('Yes, ')
    await expect(page.getByTestId('answer-verdict')).toContainText('warmer than usual')
    const answer = page.getByTestId('answer')
    await expect(answer).toContainText('Number 1 of')
    const monthly = answer.getByRole('link', { name: en.ask.season.open })
    const href = new URL((await monthly.getAttribute('href'))!, baseURL!)
    expect(href.pathname).toBe('/explorer')
    expect(Object.fromEntries(href.searchParams)).toMatchObject({ mode: 'station', provider: 'dwd', network: 'observation', resolution: 'monthly', dataset: 'climate_summary', parameters: 'temperature_air_mean_2m', stations: '02564' })
    await expect(answer.getByRole('link', { name: en.ask.season.stripes })).toHaveAttribute('href', '/stripes?kind=temperature&station=02564')
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
    await chip(page, 'season').click()
    await expect(page.getByTestId('answer')).toBeVisible()
    await chip(page, 'wind').click()
    await expect(chip(page, 'season')).toHaveAttribute('aria-pressed', 'false')
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
    // "Use my location" (GH-3651) follows the place: its button (the box and the note come after a press, GH-4011), then the suggestions
    await page.keyboard.press('Tab')
    await expect(page.getByTestId('use-my-location-button')).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(chip(page, 'rain')).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(chip(page, 'season')).toBeFocused()
    await page.keyboard.press('Space')
    await expect(chip(page, 'season')).toHaveAttribute('aria-pressed', 'true')
    await expect(chip(page, 'season')).toBeFocused()
    await expect(page.getByTestId('answer-verdict')).toBeVisible()
    await expect(chip(page, 'season')).toBeFocused()
    // the next Tab stop is the next suggestion, the answer's links come after the list
    await page.keyboard.press('Tab')
    await expect(chip(page, 'wind')).toBeFocused()
  })

  test('say so where the backend cannot answer, with a way to ask again', async ({ page, baseURL }) => {
    const { backend } = await home(page, baseURL!)
    const values = backend.handlers.values!
    backend.handlers.values = () => new ApiFailure(422, 'The request could not be processed.')
    await chip(page, 'season').click()
    await expect(page.getByTestId('answer').getByText(en.ask.failed)).toBeVisible()
    backend.handlers.values = values
    await page.getByTestId('answer').getByRole('button', { name: en.common.retry }).click()
    await expect(page.getByTestId('answer-verdict')).toContainText(/^(Yes|No), /)
  })

  test('open from a link, for the place the link names', async ({ page, baseURL }) => {
    const { asked } = await home(page, baseURL!, '/?ask=summer&place=00183')
    await expect(page.getByTestId('place-button')).toContainText('Arkona')
    await expect(chip(page, 'season')).toHaveAttribute('aria-pressed', 'true')
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

test.describe('the explanation under an answer (GH-3764)', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('is a button that opens a region, with the numbers, the sources, the data, the terms and the limits', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    await chip(page, 'season').click()
    await expect(page.getByTestId('answer-verdict')).toBeVisible()
    const button = page.getByTestId('explanation-button')
    const region = page.getByTestId('explanation-region')
    await expect(button).toHaveText(en.ask.explain.button)
    await expect(button).toHaveAttribute('aria-expanded', 'false')
    await expect(region).toBeHidden()
    await button.click()
    await expect(button).toHaveAttribute('aria-expanded', 'true')
    await expect(region).toBeVisible()
    // the region is the one the button controls, and is named by it
    await expect(button).toHaveAttribute('aria-controls', (await region.getAttribute('id'))!)
    await expect(region).toHaveAttribute('aria-labelledby', (await button.getAttribute('id'))!)
    await expect(page.getByTestId('explanation-numbers')).toContainText('1991')
    await expect(page.getByTestId('explanation-numbers')).toContainText('Kiel-Holtenau')
    // the choices that are wetterdienst's own are marked, and the others name their work and link to its entry
    await expect(page.getByTestId('own-mark').first()).toHaveText(en.ask.explain.own)
    await expect(region.getByRole('link', { name: /WMO-No\. 1203 \(2017\)/ }).first()).toHaveAttribute('href', '/methods#work-wmo-1203')
    await expect(page.getByTestId('explanation-explorer')).toHaveAttribute('href', /\/explorer\?.*stations=02564/)
    await expect(region.getByRole('link', { name: 'Climate normals' })).toHaveAttribute('href', '/measurement#normals')
    await expect(page.getByTestId('explanation-limits').getByRole('listitem').first()).toBeVisible()
    await expect(page.getByTestId('explanation-full')).toHaveAttribute('href', '/methods#season')
    // pressed again it closes
    await button.click()
    await expect(button).toHaveAttribute('aria-expanded', 'false')
    await expect(region).toBeHidden()
  })

  test('is worked with the keyboard, and follows the link to the method of the chip', async ({ page, baseURL }) => {
    await home(page, baseURL!, '/?ask=wind')
    await expect(page.getByTestId('answer-verdict')).toBeVisible()
    const button = page.getByTestId('explanation-button')
    await button.focus()
    await page.keyboard.press('Enter')
    await expect(button).toHaveAttribute('aria-expanded', 'true')
    await expect(button).toBeFocused()
    await expect(page.getByTestId('explanation-numbers')).toContainText('Beaufort')
    await page.getByTestId('explanation-full').click()
    await expect(page).toHaveURL(/\/methods#wind$/)
    await expect(page.locator('#wind-title')).toBeFocused()
  })

  test('is in the language of the page, German where the text is, with the note where it is not', async ({ page, baseURL }) => {
    await home(page, baseURL!, '/?ask=rain', 'de')
    await expect(page.getByTestId('answer-verdict')).toBeVisible()
    await page.getByTestId('explanation-button').click()
    await expect(page.getByTestId('explanation-button')).toHaveText(de.ask.explain.button)
    await expect(page.getByTestId('explanation-numbers')).toContainText('Vorhersagepunkt')
    await expect(page.getByTestId('explanation-note')).toHaveCount(0)
    await page.context().addCookies([{ name: 'wd_lang', value: 'fr', url: baseURL! }])
    await page.goto('/?ask=rain')
    await page.getByTestId('explanation-button').click()
    // a language with no text of its own: the note, and the text in English, marked as such
    await expect(page.getByTestId('explanation-note')).toBeVisible()
    await expect(page.getByTestId('explanation-numbers').locator('li[lang="en"]').first()).toBeVisible()
    // the labels around the text are the interface's own and say no language of their own (WCAG 3.1.2)
    await expect(page.getByTestId('explanation-button')).not.toHaveAttribute('lang', /.+/)
    await expect(page.locator('[data-testid="explanation-region"] h5').first()).not.toHaveAttribute('lang', /.+/)
    await expect(page.locator('[data-testid="explanation-region"] section[lang]')).toHaveCount(0)
  })

  test('is on every chip, the list of services included', async ({ page, baseURL }) => {
    await home(page, baseURL!)
    for (const id of ['rain', 'season', 'wind', 'download']) {
      await chip(page, id).click()
      await expect(page.getByTestId('answer-verdict')).toBeVisible()
      await expect(page.getByTestId('explanation-button')).toBeVisible()
      await chip(page, id).click()
    }
  })

  test('fits a phone\'s width, opened', async ({ page, baseURL }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await home(page, baseURL!, '/?ask=summer')
    await expect(page.getByTestId('answer-verdict')).toBeVisible()
    await page.getByTestId('explanation-button').click()
    await expect(page.getByTestId('explanation-region')).toBeVisible()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
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

    await chip(page, 'season').click()
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
    for (const id of ['rain', 'season', 'wind', 'download']) {
      await chip(page, id).click()
      await expect(page.getByTestId('answer')).toBeVisible()
      await expect(page.getByTestId('answer-status')).not.toBeEmpty()
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow, id).toBeLessThanOrEqual(0)
    }
    // each suggestion is a target of 44 px or more (WCAG 2.5.8 asks 24)
    for (const box of await Promise.all(['rain', 'season', 'wind', 'download'].map(id => chip(page, id).boundingBox())))
      expectAtLeastPx(box!.height, 44)
  })
})

// The labels of the answers' bar charts (GH-3893): the boxes of the text as the browser sets it, not an estimate of it
interface Box { left: number, right: number, top: number, bottom: number }
async function chartBoxes(page: Page) {
  return await page.getByRole('figure').evaluate((figure) => {
    const ink = (element: Element): Box => {
      const range = document.createRange()
      range.selectNodeContents(element)
      const { left, right, top, bottom } = range.getBoundingClientRect()
      return { left, right, top, bottom }
    }
    const box = (element: Element | null): Box => {
      const { left, right, top, bottom } = element!.getBoundingClientRect()
      return { left, right, top, bottom }
    }
    const labels = [...figure.querySelectorAll('[data-testid="answer-bars-label"]')].map(element => ({ text: element.textContent!, ...ink(element) }))
    const values = [...figure.querySelectorAll('[data-testid="answer-bars-values"] [data-kind]')].map(element => ({ kind: element.getAttribute('data-kind')!, text: element.textContent!, ...ink(element) }))
    const zero = figure.querySelector('[data-testid="answer-bars-zero"]')
    return {
      labels,
      values,
      plot: box(figure.querySelector('[data-testid="answer-bars-plot"]')),
      zeroLine: zero ? box(zero) : null,
      figure: box(figure),
      page: document.documentElement.clientWidth,
    }
  })
}
const overlap = (a: Box, b: Box) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom

test.describe('the labels of the answers\' charts', () => {
  for (const [width, language] of [[320, 'en'], [320, 'de'], [320, 'de-hh'], [320, 'lb'], [320, 'it'], [320, 'fr'], [1280, 'en']] as const) {
    test(`do not touch each other and sit where they belong, at ${width} px in ${language}`, async ({ page, baseURL }) => {
      await page.setViewportSize({ width, height: 900 })
      await home(page, baseURL!, '/', language)
      let before = ''
      for (const id of ['season', 'rain', 'wind']) {
        await chip(page, id).click()
        // the chart of this question, not the one of the last
        const caption = page.getByRole('figure').locator('figcaption')
        await expect(caption).toBeVisible()
        if (before)
          await expect(caption).not.toHaveText(before)
        before = (await caption.textContent())!
        await expect(page.getByRole('figure').getByTestId('answer-bars-label').first()).toBeVisible()
        const chart = await chartBoxes(page)
        const where = `${id} at ${width} px in ${language}`
        const labels = chart.labels.sort((a, b) => a.left - b.left)
        expect(labels.length, where).toBeGreaterThan(1)
        // the text of two labels, with a pixel between
        for (let at = 1; at < labels.length; at += 1)
          expect(labels[at - 1]!.right + 1, `${where}: ${labels[at - 1]!.text} and ${labels[at]!.text}`).toBeLessThanOrEqual(labels[at]!.left)
        // the labels stay inside the plot's width, and the page does not scroll sideways
        for (const label of labels) {
          expect(label.left, where).toBeGreaterThanOrEqual(chart.plot.left - 1)
          expect(label.right, where).toBeLessThanOrEqual(chart.plot.right + 1)
        }
        expect(chart.figure.right, where).toBeLessThanOrEqual(chart.page)
        // the value labels are on the height of the plot (the year labels are under it), and none is over another
        for (const value of chart.values) {
          expect(value.top, `${where}: ${value.text}`).toBeGreaterThanOrEqual(chart.plot.top - 1)
          expect(value.bottom, `${where}: ${value.text}`).toBeLessThanOrEqual(chart.plot.bottom + 1)
          expect(value.right, `${where}: ${value.text}`).toBeLessThanOrEqual(chart.plot.left)
        }
        for (const [at, value] of chart.values.entries()) {
          for (const other of chart.values.slice(at + 1))
            expect(overlap(value, other), `${where}: ${value.text} and ${other.text}`).toBe(false)
        }
        if (id === 'season') {
          // the bars hang from a line, and the line has its 0
          const zero = chart.values.find(value => value.kind === 'zero')
          expect(zero, where).toBeDefined()
          expect(chart.zeroLine, where).not.toBeNull()
          expect(Math.abs((zero!.top + zero!.bottom) / 2 - chart.zeroLine!.top), where).toBeLessThanOrEqual(8)
          expect(chart.labels.map(label => label.text), where).toContain(String(lastSummerYear()))
        }
      }
    })
  }
})

// The season and the reference period (GH-3764, step 2a): two labelled selects under the question, which the question's own button does not hold
test.describe('the season and the reference period', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  const seasonSelect = (page: Page) => page.getByRole('combobox', { name: en.ask.season.seasonLabel })
  const refSelect = (page: Page) => page.getByRole('combobox', { name: en.ask.season.refLabel })

  test('are two labelled selects, and a choice changes the question, the answer and the link, with no new request', async ({ page, baseURL }) => {
    const { asked } = await home(page, baseURL!, '/?ask=season&season=summer')
    await expect(page.getByTestId('answer-verdict')).toBeVisible()
    await expect(seasonSelect(page)).toHaveValue('summer')
    await expect(refSelect(page)).toHaveValue('1991-2020')
    await expect(refSelect(page).locator('option')).toHaveText(['1961–1990', '1971–2000', '1981–2010', '1991–2020'])
    // the controls are not in the button, which stays one pressed button
    await expect(chip(page, 'season').locator('select')).toHaveCount(0)
    await expect(chip(page, 'season')).toHaveAttribute('aria-pressed', 'true')
    const requests = askedValues(asked).length

    await seasonSelect(page).selectOption('winter')
    await expect(chip(page, 'season')).toHaveText('Was last winter colder than usual here?')
    await expect(page.locator('#answer-heading')).toHaveText('Was last winter colder than usual here?')
    await expect(page).toHaveURL(/\?ask=season&season=winter$/)
    // the mock winter is warmer than the normal: the answer to "colder" is no
    await expect(page.getByTestId('answer-verdict')).toContainText('No, ')
    await expect(page.getByTestId('answer-verdict')).toContainText('warmer than usual')
    await refSelect(page).selectOption('1961-1990')
    await expect(page).toHaveURL(/\?ask=season&season=winter&ref=1961-1990$/)
    const answer = page.getByTestId('answer')
    await expect(answer).toContainText('the winters from 1960/61 to 1989/90 averaged')
    await expect(answer.getByRole('figure').locator('figcaption')).toHaveText('Each winter against the average of 1960/61 to 1989/90, in °C')
    await expect(answer).toContainText(/Winter \d{4}\/\d{2} \(December to February\) averaged/)
    // the live region says the new verdict
    await expect(page.getByTestId('answer-status')).toHaveText((await page.getByTestId('answer-verdict').textContent())!.trim())
    // the whole record served every choice: nothing was asked again
    expect(askedValues(asked)).toHaveLength(requests)

    // the disclosure says which season and which normal were used, and the page of the methods is linked
    await page.getByTestId('explanation-button').click()
    await expect(page.getByTestId('explanation-numbers')).toContainText('Compared with the winters of 1960/61 to 1989/90: the mean of 30 winters')
    await expect(page.getByTestId('explanation-full')).toHaveAttribute('href', '/methods#season')
  })

  test('read the link of a season and a normal, and the link of the old question', async ({ page, baseURL }) => {
    await home(page, baseURL!, '/?ask=season&season=autumn&ref=1981-2010')
    await expect(chip(page, 'season')).toHaveText('Was last autumn warmer than usual here?')
    await expect(seasonSelect(page)).toHaveValue('autumn')
    await expect(refSelect(page)).toHaveValue('1981-2010')
    await expect(page.getByTestId('answer')).toContainText('the autumns from 1981 to 2010 averaged')
    // a name that is none gives the defaults
    await page.goto('/?ask=season&season=monsoon&ref=1950-1979')
    // the season completed most recently
    await expect(seasonSelect(page)).toHaveValue(defaultSeason(DateTime.now()))
    await expect(refSelect(page)).toHaveValue('1991-2020')
    // `?ask=summer` is the summer against the newest normal, the chip pressed
    await page.goto('/?ask=summer')
    await expect(chip(page, 'season')).toHaveAttribute('aria-pressed', 'true')
    await expect(chip(page, 'season')).toHaveText('Was last summer hotter than usual here?')
    await expect(page.getByTestId('answer')).toContainText('the summers from 1991 to 2020 averaged')
  })

  test('grey out a normal the station has too few seasons of, with the reason in the option and on the line under the choices, and a link that names it gets the normal the question opens on', async ({ page, baseURL }) => {
    // Arkona's record starts in 1975: 16 of the 30 winters of 1961 to 1990
    await home(page, baseURL!, '/?ask=season&season=winter&ref=1961-1990&place=00183')
    const first = refSelect(page).locator('option').first()
    await expect(first).toBeDisabled()
    await expect(first).toHaveText('1961–1990 = 1960/61–1989/90 (only 16 of 30 seasons here, 20 needed)')
    await expect(refSelect(page).locator('option').nth(1)).toBeEnabled()
    // the link named a normal that has too little data here: the newest is shown, and the line under the choices says so
    await expect(refSelect(page)).toHaveValue('1991-2020')
    const note = page.getByTestId('choice-note')
    await expect(note).toHaveAttribute('role', 'status')
    await expect(note).toContainText('1961–1990 = 1960/61–1989/90 has too little data here for this season: 16 of its 30 seasons, 20 needed. Showing instead: 1991–2020 = 1990/91–2019/20.')
    await expect(note).toContainText('Greyed out: too few seasons at this station. A normal needs 20 of its 30 seasons.')
    await expect(page.getByTestId('answer-verdict')).toBeVisible()
    await refSelect(page).selectOption('1971-2000')
    await expect(note).not.toContainText('has too little data')
    await expect(note).toContainText('Greyed out')
  })

  test('grey out a season the station has too little of, with the reason in the option, and a link that names it gets the season the question opens on, with a line that says so', async ({ page, baseURL }) => {
    // Aue has the winters from 2018/19 on only
    await home(page, baseURL!, '/?ask=season&season=winter&place=00205')
    await expect(page.getByTestId('place-button')).toContainText('Aue')
    const winter = seasonSelect(page).locator('option[value="winter"]')
    await expect(winter).toBeDisabled()
    await expect(winter).toHaveText(/^Winter \(only \d+ complete seasons here\)$/)
    await expect(seasonSelect(page)).not.toHaveValue('winter')
    const note = page.getByTestId('choice-note')
    await expect(note).toContainText('Winter has too little data here to compare. Showing instead:')
    await expect(note).toContainText('Greyed out')
    await expect(page.getByTestId('answer-verdict')).toBeVisible()
    // the other seasons can be chosen
    await seasonSelect(page).selectOption('spring')
    await expect(chip(page, 'season')).toContainText('spring')
  })

  test('say nothing under the choices where nothing is greyed out', async ({ page, baseURL }) => {
    await home(page, baseURL!, '/?ask=season&season=summer')
    await expect(page.getByTestId('answer-verdict')).toBeVisible()
    await expect(page.getByTestId('choice-note')).toHaveText('')
  })

  test('are in German, with the season in the one sentence', async ({ page, baseURL }) => {
    await home(page, baseURL!, '/?ask=season&season=winter', 'de')
    await expect(chip(page, 'season')).toHaveText('War der letzte Winter hier kälter als sonst?')
    await expect(page.getByRole('combobox', { name: de.ask.season.seasonLabel })).toHaveValue('winter')
    await expect(page.getByRole('combobox', { name: de.ask.season.refLabel })).toBeVisible()
    await expect(page.getByTestId('answer')).toContainText(/Der Winter \d{4}\/\d{2} \(Dezember bis Februar\) hatte im Mittel/)
  })

  test('is reached from the keyboard: the controls follow the button, each with its label', async ({ page, baseURL }) => {
    await home(page, baseURL!, '/?ask=season')
    await expect(page.getByTestId('answer-verdict')).toBeVisible()
    await seasonSelect(page).focus()
    await expect(seasonSelect(page)).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(refSelect(page)).toBeFocused()
  })
})

test.describe('the season and the reference period on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  for (const language of ['en', 'de', 'es', 'pl']) {
    test(`fit the width, with controls of 44 px, in ${language}`, async ({ page, baseURL }) => {
      await home(page, baseURL!, '/?ask=season&season=winter&ref=1961-1990&place=00183', language)
      await expect(page.getByTestId('answer')).toBeVisible()
      const choices = page.getByTestId('answer-choices')
      await expect(choices).toBeVisible()
      for (const select of await choices.locator('select').all()) {
        const box = (await select.boundingBox())!
        expectAtLeastPx(box.height, 44)
        expect(box.x + box.width, 'inside the page').toBeLessThanOrEqual(390)
      }
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow).toBeLessThanOrEqual(0)
    })
  }

  test('draw the labels of a winter chart, two years each, without touching', async ({ page, baseURL }) => {
    await page.setViewportSize({ width: 320, height: 900 })
    await home(page, baseURL!, '/?ask=season&season=winter')
    await expect(page.getByRole('figure').getByTestId('answer-bars-label').first()).toBeVisible()
    const chart = await chartBoxes(page)
    const labels = chart.labels.sort((a, b) => a.left - b.left)
    expect(labels.length).toBeGreaterThan(1)
    for (let at = 1; at < labels.length; at += 1)
      expect(labels[at - 1]!.right + 1, `${labels[at - 1]!.text} and ${labels[at]!.text}`).toBeLessThanOrEqual(labels[at]!.left)
    expect(chart.labels.map(label => label.text).some(text => /^\d{4}\/\d{2}$/.test(text))).toBe(true)
  })
})
