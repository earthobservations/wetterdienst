import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { checkRunningYear, readFromMirror } from '../helpers/ghcn-source'
import { mockBackend } from './accessibility/mock-backend'

// The climate stripes without the backend's stripes routes (GH-4258): the app makes them itself, from the generic API
// (`/api/stations`, `/api/values`) and, for NOAA's GHCN daily, from its own server (`/_ghcn/annual`, `/_ghcn/stations`), which
// calculates the annual values from the daily ones. This spec runs against the real backend, and fails on any request to a stripes
// route of it: such a request is refused here, counted, and the page must work all the same, its views, its exports and the map's
// GHCN layer.

// the labels are English: a browser of another language gets the app in it
test.use({ locale: 'en-US' })

/** The requests of the page to a stripes route of the backend (`/api/stripes/*`, `/api/v1/stripes/*`), which are refused and counted */
async function refuseStripesRoutes(page: Page) {
  const hits: string[] = []
  await page.route(/\/api\/(?:v1\/)?stripes/, async (route) => {
    hits.push(route.request().url())
    await route.abort()
  })
  return hits
}

/** The chart, once it is drawn: the SVG is in its canvas */
const chartSvg = (page: Page) => page.locator('.sc-canvas[data-drawn="true"] svg').first()

async function saveFrom(page: Page, menuLabel: string, item: string) {
  await page.getByRole('button', { name: menuLabel }).click()
  const saved = page.waitForEvent('download')
  await page.getByRole('menuitem', { name: item }).click()
  return saved
}

test.describe('DWD\'s stripes, made by the app of the annual values of the generic API', () => {
  test('are shown, saved as an image and as a table, with no request to a stripes route of the backend', async ({ page }) => {
    const hits = await refuseStripesRoutes(page)
    const asked: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('/api/'))
        asked.push(request.url())
    })

    await page.goto('/stripes?kind=temperature&station=01048')
    await page.getByRole('button', { name: 'Show', exact: true }).click()
    await expect(chartSvg(page)).toBeVisible({ timeout: 60_000 })
    await expect(page.getByTestId('stripes-reference')).toContainText('Relative to the mean of 1971–2000')

    // the years are the annual values of the station, the stations the annual record's historical and recent period
    const values = asked.map(url => new URL(url)).filter(url => url.pathname.endsWith('/values'))
    expect(values).toHaveLength(1)
    expect(Object.fromEntries(values[0]!.searchParams)).toMatchObject({ provider: 'dwd', network: 'observation', parameters: 'annual/climate_summary/temperature_air_mean_2m', periods: 'historical', stations: '01048' })
    const lists = asked.map(url => new URL(url)).filter(url => url.pathname.endsWith('/stations'))
    expect(lists.map(url => url.searchParams.get('periods')).sort()).toEqual(['historical', 'recent'])

    // the image, in each of its formats
    for (const [item, extension] of [['Download as PNG', 'png'], ['Download as JPG', 'jpeg'], ['Download as SVG', 'svg']] as const) {
      const download = await saveFrom(page, 'Download image', item)
      expect(download.suggestedFilename()).toMatch(new RegExp(`^climate_stripes_temperature_01048_.+\\.${extension}$`))
      const file = readFileSync((await download.path())!)
      expect(file.length).toBeGreaterThan(1000)
      if (extension === 'svg')
        expect(file.toString('utf8')).toContain('Climate stripes')
    }

    // the table of the years, as a file with its credit and licence
    await page.getByRole('radio', { name: 'Table', exact: true }).click()
    const table = await saveFrom(page, 'Download table', 'Download as CSV')
    expect(table.suggestedFilename()).toMatch(/^climate_stripes_temperature_01048_.+\.csv$/)
    const csv = readFileSync((await table.path())!, 'utf8')
    const comments = csv.split('\n').filter(line => line.replace('﻿', '').startsWith('# '))
    expect(comments.join('\n')).toContain('Source: Deutscher Wetterdienst')
    expect(comments.join('\n')).toContain('Creative Commons Attribution 4.0 International')
    expect(comments.join('\n')).toContain('Colours: the mean of 1971–2000')
    expect(csv.split('\n').filter(line => /^\d{4},/.test(line)).length).toBeGreaterThan(50)

    expect(hits).toEqual([])
  })

  test('give the precipitation the same way', async ({ page }) => {
    const hits = await refuseStripesRoutes(page)
    await page.goto('/stripes?kind=precipitation&station=01048')
    await page.getByRole('button', { name: 'Show', exact: true }).click()
    await expect(chartSvg(page)).toBeVisible({ timeout: 60_000 })
    expect(hits).toEqual([])
  })

  test('tell a window of years that ends before it starts, before any value is asked for', async ({ page }) => {
    const hits = await refuseStripesRoutes(page)
    const asked: string[] = []
    page.on('request', (request) => {
      if (/\/api\/(?:v1\/)?values$/.test(new URL(request.url()).pathname))
        asked.push(request.url())
    })
    await page.goto('/stripes?kind=temperature&station=01048&start_year=1990&end_year=1990')
    await page.getByRole('button', { name: 'Show', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText('end_year: Input should be greater than start_year (1990)')
    expect(asked).toEqual([])
    expect(hits).toEqual([])
  })
})

test.describe('the stripes of NOAA\'s GHCN daily, calculated from the days by the app\'s own server', () => {
  // a station's days are read from NOAA by the backend and its years calculated, which takes some seconds the first time
  test.setTimeout(240_000)
  const LINK = '/stripes?kind=temperature&provider=noaa&network=ghcn&station=USW00094728'

  test('are shown, with the method of the days, and saved as an image and as a table', async ({ page }) => {
    const hits = await refuseStripesRoutes(page)
    const asked: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('/_ghcn/') || request.url().includes('/api/'))
        asked.push(new URL(request.url()).pathname)
    })

    await page.goto(LINK)
    await page.getByRole('button', { name: 'Show', exact: true }).click()
    await expect(chartSvg(page)).toBeVisible({ timeout: 200_000 })
    await expect(page.getByTestId('stripes-method')).toContainText('midrange of the daily maximum and minimum')

    // the years came from the app's own server, and the list of the stations too: no read of the generic API's 133,000 stations
    expect(asked).toContain('/_ghcn/annual')
    expect(asked).toContain('/_ghcn/stations')
    expect(asked.filter(path => path.endsWith('/api/stations') || path === '/api/stations')).toEqual([])
    expect(asked.some(path => path.endsWith('/values'))).toBe(false)

    const png = await saveFrom(page, 'Download image', 'Download as PNG')
    expect(png.suggestedFilename()).toMatch(/^climate_stripes_temperature_USW00094728_.+\.png$/)
    const svg = await saveFrom(page, 'Download image', 'Download as SVG')
    const text = readFileSync((await svg.path())!, 'utf8')
    expect(text).toContain('Source: NOAA NCEI, GHCN-Daily')
    expect(text).toContain('Temperature: midpoint of daily max and min (GHCN)')

    await page.getByRole('radio', { name: 'Table', exact: true }).click()
    const table = await saveFrom(page, 'Download table', 'Download as CSV')
    const csv = readFileSync((await table.path())!, 'utf8')
    expect(csv).toContain('NOAA National Centers for Environmental Information')
    expect(csv).toContain('Creative Commons Zero')
    // New York's record starts in 1869, and its running year has no value yet
    expect(csv.split('\n').filter(line => /^\d{4},/.test(line)).length).toBeGreaterThan(100)

    expect(hits).toEqual([])
  })

  test('are given by the server of the app as small answers, which it keeps', async ({ request }, testInfo) => {
    const first = await request.get('/_ghcn/annual?kind=temperature&station=USW00094728&unit_targets=%7B%22temperature%22%3A%22degree_celsius%22%7D', { timeout: 200_000 })
    expect(first.status()).toBe(200)
    const body = await first.json()
    expect(body.series).toEqual({ station_id: 'USW00094728', parameter: 'temperature_air_mean_2m', unit: '°C', method: 'midrange' })
    expect(body.metadata.provider.attribution).toContain('NOAA')
    expect(body.values.length).toBeGreaterThan(100)
    // a few kilobytes where the days are megabytes
    expect((await first.body()).length).toBeLessThan(60_000)
    // the year that is running is no year with a value until it is complete. While NCEI is down the backend reads the AWS mirror,
    // whose file may end in an earlier year; the app's answer says so in its `metadata.warnings` (GH-4390), and the running year is
    // then not asked for (GH-4387). Where NCEI answered it still is.
    const mirror = readFromMirror(body)
    const { checked, problem } = checkRunningYear(body.values, new Date().getUTCFullYear(), mirror)
    expect(problem).toBeNull()
    if (!checked)
      testInfo.annotations.push({ type: 'running-year-not-checked', description: 'NCEI did not answer (source-fallback): the file is the AWS mirror\'s, which may end before the running year (GH-4387)' })
    // an answer read from the mirror is kept for 5 minutes, not an hour, so that the full record is back when NCEI is (GH-4390)
    expect(first.headers()['cache-control']).toBe(mirror ? 'public, max-age=300' : 'public, max-age=3600')

    const started = Date.now()
    const second = await request.get('/_ghcn/annual?kind=temperature&station=USW00094728&unit_targets=%7B%22temperature%22%3A%22degree_celsius%22%7D')
    expect(await second.json()).toEqual(body)
    // served from the server's memory: no read of the days again
    expect(Date.now() - started).toBeLessThan(2000)
  })

  test('are refused for what the server cannot read, as problems', async ({ request }) => {
    const kind = await request.get('/_ghcn/annual?kind=wind&station=USW00094728')
    expect(kind.status()).toBe(422)
    expect((await kind.json()).type).toBe('urn:wetterdienst:problem:invalid-parameters')
    const station = await request.get('/_ghcn/annual?kind=temperature&station=USW99999999', { timeout: 200_000 })
    expect([404, 200]).toContain(station.status())
    if (station.status() === 404)
      expect((await station.json()).detail).toContain('USW99999999')
  })
})

test.describe('the map\'s GHCN layer and its stripes', () => {
  test.setTimeout(240_000)
  test.use({ viewport: { width: 1440, height: 900 } })

  test('show the stripes of a station of GHCN daily in the panel, with no request to a stripes route', async ({ page }) => {
    const hits = await refuseStripesRoutes(page)
    await page.goto('/map?layer=ghcn&station=USW00094728&lat=40.7789&lon=-73.9692')
    const stripes = page.getByTestId('map-card-stripes')
    await expect(stripes.getByRole('img')).toBeVisible({ timeout: 200_000 })
    await expect(page.getByTestId('map-stripes-method')).toContainText('midrange')
    await expect(stripes.locator('.map-stripes span').first()).toBeVisible()
    expect(await stripes.locator('.map-stripes span').count()).toBeGreaterThan(100)
    expect(hits).toEqual([])
  })

  test('show the stripes of a station of DWD in the panel, from the annual values of the generic API', async ({ page }) => {
    const hits = await refuseStripesRoutes(page)
    await page.goto('/map?layer=measured&station=01048&lat=51.1278&lon=13.7543')
    const stripes = page.getByTestId('map-card-stripes')
    await expect(stripes.getByRole('img')).toBeVisible({ timeout: 120_000 })
    expect(hits).toEqual([])
  })
})

test.describe('stripes of GHCN daily read from the mirror of NOAA\'s data on AWS (a stubbed answer, GH-4390)', () => {
  // NCEI is down at the time of the test, whatever the real one is: the app's server's answer is the stub's, and says the days came from the mirror
  const NOTICE = 'Read from the mirror of NOAA\'s data on AWS; the most recent days may be missing.'

  /** Every request to the API and the app's own server is answered by the stub; `/_ghcn/annual` carries the mirror's warning */
  async function mirrorStub(page: Page, baseURL: string | undefined) {
    const backend = await mockBackend(page, baseURL!)
    const annual = backend.handlers['_ghcn/annual']!
    backend.handlers['_ghcn/annual'] = async (url, route) => ({ ...(await annual(url, route) as object), mirror: true })
    return backend
  }

  test('say so near the source, and where the record ends, on the page and in the saved files', async ({ page, baseURL }) => {
    await mirrorStub(page, baseURL)
    await page.goto('/stripes?kind=temperature&provider=noaa&network=ghcn&station=USW00094728')
    await page.getByRole('button', { name: 'Show', exact: true }).click()
    await expect(chartSvg(page)).toBeVisible({ timeout: 60_000 })
    // the stub's record ends in 2024, before the last complete year
    await expect(page.getByTestId('stripes-mirror')).toHaveText(`${NOTICE} The record shown ends in 2024.`)

    const svg = await saveFrom(page, 'Download image', 'Download as SVG')
    // the image breaks a long line, so the lines of text are read as one text
    const lines = [...readFileSync((await svg.path())!, 'utf8').matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(match => match[1]!.replaceAll('&#39;', '\''))
    expect(lines.join(' ')).toContain(`${NOTICE} The record shown ends in 2024.`)

    await page.getByRole('radio', { name: 'Table', exact: true }).click()
    await expect(page.getByTestId('stripes-mirror')).toBeVisible()
    const table = await saveFrom(page, 'Download table', 'Download as CSV')
    const csv = readFileSync((await table.path())!, 'utf8')
    expect(csv).toContain(`# ${NOTICE} The record shown ends in 2024.`)
    expect(csv).toContain('NOAA National Centers for Environmental Information')
  })

  test('say so in the map\'s panel, under the band', async ({ page, baseURL }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await mirrorStub(page, baseURL)
    await page.goto('/map?layer=ghcn&station=USW00094728&lat=40.7789&lon=-73.9692')
    await expect(page.getByTestId('map-card-stripes').getByRole('img')).toBeVisible({ timeout: 60_000 })
    await expect(page.getByTestId('map-stripes-mirror')).toHaveText(`${NOTICE} The record shown ends in 2024.`)
  })

  // every language of the app: the line is in the reader's own, and it fits a phone's width (WCAG 1.4.10 Reflow) on the page and in the map's panel
  for (const language of ['en', 'de', 'de-hh', 'fr', 'es', 'it', 'nl', 'pl', 'cs', 'da', 'lb']) {
    test(`say it in ${language} within the width of a phone`, async ({ page, context, baseURL }) => {
      const catalog = JSON.parse(readFileSync(fileURLToPath(new URL(`../../i18n/locales/${language}.json`, import.meta.url)), 'utf8')) as { common: { fetch: string }, stripes: { mirrorNoteEnds: string } }
      const expected = catalog.stripes.mirrorNoteEnds.replace('{year}', '2024')
      await context.addCookies([{ name: 'wd_lang', value: language, url: baseURL! }])
      await page.setViewportSize({ width: 320, height: 844 })
      await mirrorStub(page, baseURL)
      await page.goto('/stripes?kind=temperature&provider=noaa&network=ghcn&station=USW00094728')
      await page.getByRole('button', { name: catalog.common.fetch, exact: true }).click()
      await expect(chartSvg(page)).toBeVisible({ timeout: 60_000 })
      await expect(page.getByTestId('stripes-mirror')).toHaveText(expected)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)

      await page.goto('/map?layer=ghcn&station=USW00094728&lat=40.7789&lon=-73.9692')
      await expect(page.getByTestId('map-stripes-mirror')).toHaveText(expected, { timeout: 60_000 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
    })
  }

  test('say nothing where the answer has no such warning', async ({ page, baseURL }) => {
    await mockBackend(page, baseURL!)
    await page.goto('/stripes?kind=temperature&provider=noaa&network=ghcn&station=USW00094728')
    await page.getByRole('button', { name: 'Show', exact: true }).click()
    await expect(chartSvg(page)).toBeVisible({ timeout: 60_000 })
    await expect(page.getByTestId('stripes-method')).toBeVisible()
    await expect(page.getByTestId('stripes-mirror')).toHaveCount(0)
  })
})
