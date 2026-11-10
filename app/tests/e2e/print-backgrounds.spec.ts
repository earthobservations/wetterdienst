import type { Page } from '@playwright/test'
import { expect, test } from '@playwright/test'
import { mockBackend } from './accessibility/mock-backend'
import { pdfFillColors, pdfTextRuns } from './pdf-text'

// A print without background graphics (GH-3960). Chrome's print dialog has "Background graphics" off, and so has
// `page.pdf` unless it is asked for them: every background is left out. The icons of the app are masks over a
// background colour (@nuxt/icon), so they print as nothing; a label that is white on a solid fill (a solid button, a
// tool's tile) prints white on white; and so would the white text of the start page's navy band. The small marks
// keep their fill (`print-color-adjust: exact`, main.css), the band is white with an outline in print (index.vue).
//
// What this holds, on the pages that carry them, in a print from the light theme and from the dark one:
// - the computed style under the print medium: every icon is `exact`, and so is the fill behind everything that is
//   light (a white label, a white glyph), which is the rule that finds an element that is neither forced nor dark;
//   nothing light stands on the paper itself (white on white)
// - the PDF printed with `printBackground: false`: the fill of every such element is drawn in it, and so is the text
//   of the buttons (the labels are text in the PDF whatever their colour, so this alone would not see a white one)

const EXPLORER = '/explorer?provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m,temperature_air_mean_2m&mode=station&stations=00011'

interface Target {
  name: string
  path: string
  reach?: (page: Page) => Promise<void>
}

const PAGES: Target[] = [
  { name: 'the start page', path: '/' },
  {
    name: 'the explorer, with its table',
    path: EXPLORER,
    reach: async (page) => {
      await page.getByRole('button', { name: 'Show', exact: true }).click()
      await expect(page.getByRole('table').first()).toBeVisible()
    },
  },
  { name: 'the climate stripes', path: '/stripes?kind=temperature&station=00011' },
  { name: 'the meteogram', path: '/meteogram?station=01001' },
  { name: 'the about page', path: '/about' },
  { name: 'the API page', path: '/api' },
  { name: 'the glossary', path: '/glossary' },
  { name: 'the providers', path: '/providers' },
  { name: 'the settings', path: '/settings' },
  { name: 'the support page', path: '/support' },
]

type Rgb = [number, number, number]

interface Backing {
  /** What stands on the fill: a label or an icon, and what it stands on */
  what: string
  /** The `print-color-adjust` of the element that has the fill */
  adjust: string
  /** The paper itself: nothing has a fill behind it, or the fill is light */
  paper: boolean
}

interface Scan {
  icons: Array<{ icon: string, adjust: string }>
  /** Every light label or glyph and the fill it stands on */
  light: Backing[]
  /** The dark fills that something light stands on, which the PDF is looked into for */
  solids: Array<{ what: string, fill: Rgb }>
}

/** Reads the page under the print medium (the caller emulates it): the icons, and what stands on what */
async function scan(page: Page): Promise<Scan> {
  return page.evaluate(() => {
    const canvas = document.createElement('canvas').getContext('2d', { willReadFrequently: true })!
    // any colour Chrome writes (`rgb`, the `oklab` of a tint, `color(srgb ...)`) as sRGB 0 to 1, and its opacity
    const parse = (value: string): { rgb: Rgb, alpha: number } => {
      canvas.clearRect(0, 0, 1, 1)
      canvas.fillStyle = '#000000'
      canvas.fillStyle = value
      canvas.fillRect(0, 0, 1, 1)
      const [r, g, b, a] = canvas.getImageData(0, 0, 1, 1).data
      return { rgb: [r! / 255, g! / 255, b! / 255], alpha: a! / 255 }
    }
    const luminance = ([r, g, b]: Rgb) => {
      const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
      return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    }
    const label = (element: Element) => `${element.tagName.toLowerCase()}.${(element.getAttribute('class') ?? '').split(/\s+/).slice(0, 3).join('.')}`
    const visible = (element: Element) => {
      const box = element.getBoundingClientRect()
      const style = getComputedStyle(element)
      return box.width > 0 && box.height > 0 && style.display !== 'none' && style.visibility !== 'hidden'
    }
    /** The nearest element above `element` that has an opaque fill: what it stands on */
    const backing = (element: Element) => {
      for (let up = element.parentElement; up; up = up.parentElement) {
        const { rgb, alpha } = parse(getComputedStyle(up).backgroundColor)
        if (alpha > 0.5)
          return { element: up, rgb, adjust: getComputedStyle(up).getPropertyValue('print-color-adjust') }
      }
      return null
    }

    const result: Scan = { icons: [], light: [], solids: [] }
    const seen = new Set<Element>()
    const note = (element: Element, what: string, color: Rgb) => {
      if (luminance(color) <= 0.5)
        return
      const behind = backing(element)
      const paper = !behind || luminance(behind.rgb) > 0.5
      result.light.push({ what: `${what} on ${behind ? label(behind.element) : 'the paper'}`, adjust: behind?.adjust ?? 'economy', paper })
      if (behind && !paper && !seen.has(behind.element)) {
        seen.add(behind.element)
        result.solids.push({ what: label(behind.element), fill: behind.rgb })
      }
    }

    for (const element of document.querySelectorAll('#__nuxt *')) {
      if (element.closest('svg, .leaflet-container, .js-plotly-plot') || !visible(element))
        continue
      const style = getComputedStyle(element)
      if (element.classList.contains('iconify')) {
        result.icons.push({ icon: label(element), adjust: style.getPropertyValue('print-color-adjust') })
        // an icon is drawn in its background colour
        note(element, `icon ${label(element)}`, parse(style.backgroundColor).rgb)
      }
      else if ([...element.childNodes].some(node => node.nodeType === Node.TEXT_NODE && node.textContent?.trim())) {
        note(element, `text of ${label(element)}`, parse(style.color).rgb)
      }
    }
    return result
  })
}

async function printed(page: Page, baseURL: string, theme: 'light' | 'dark', target: Pick<Target, 'path' | 'reach'>) {
  await page.addInitScript(mode => localStorage.setItem('nuxt-color-mode', mode), theme)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await mockBackend(page, baseURL)
  await page.goto(target.path, { timeout: 60_000 })
  await target.reach?.(page)
  await page.waitForLoadState('networkidle')
  await page.emulateMedia({ media: 'print' })
  // the colours of the page, which the buttons and links transition to (a style read before is a mix of both)
  await page.evaluate(() => Promise.all(document.getAnimations().map(animation => animation.finished.catch(() => {}))))
}

const close = (a: Rgb, b: Rgb) => a.every((value, index) => Math.abs(value - b[index]!) < 0.003)

for (const theme of ['light', 'dark'] as const) {
  for (const target of PAGES) {
    test(`${target.name} keeps its icons and the labels on its fills when printed without background graphics, from the ${theme} theme`, async ({ page, baseURL, browserName }) => {
      test.skip(browserName !== 'chromium', 'page.pdf is Chromium\'s')
      await printed(page, baseURL!, theme, target)
      const found = await scan(page)

      // every icon is a mask over a background, and prints
      expect(found.icons.length, 'icons on the page').toBeGreaterThan(0)
      expect(found.icons.filter(({ adjust }) => adjust !== 'exact').map(({ icon }) => icon), 'icons that print without their fill').toEqual([])
      // nothing light is on the paper itself (it is white on white), and the fill a light thing stands on is forced
      expect(found.light.filter(({ paper }) => paper).map(({ what }) => what), 'light on the paper').toEqual([])
      expect(found.light.filter(({ adjust }) => adjust !== 'exact').map(({ what }) => what), 'light on a fill that is left out').toEqual([])

      // and the PDF, printed as Chrome prints by default: the fills those stand on are in it
      const fills = pdfFillColors(await page.pdf({ format: 'A4', printBackground: false }))
      expect(fills.length).toBeGreaterThan(0)
      const missing = found.solids.filter(({ fill }) => !fills.some(drawn => close(drawn, fill)))
      expect(missing.map(({ what, fill }) => `${what} ${fill.map(value => value.toFixed(3)).join(' ')}`), 'fills missing from the PDF').toEqual([])
    })
  }
}

test('the start page prints its band as black text on white with an outline, and the PDF has its text', async ({ page, baseURL, browserName }) => {
  test.skip(browserName !== 'chromium', 'page.pdf is Chromium\'s')
  await printed(page, baseURL!, 'light', PAGES[0]!)
  const band = await page.locator('.values-band').evaluate((element) => {
    const style = getComputedStyle(element)
    return {
      background: style.backgroundColor,
      color: style.color,
      heading: getComputedStyle(element.querySelector('.home-heading')!).color,
      border: style.borderTopWidth,
    }
  })
  // it costs no ink and needs no background graphics
  expect(band).toEqual({ background: 'rgb(255, 255, 255)', color: 'rgb(0, 0, 0)', heading: 'rgb(0, 0, 0)', border: '1px' })

  const words = pdfTextRuns(await page.pdf({ format: 'A4', printBackground: false })).map(run => run.text).join(' ')
  for (const heading of await page.locator('.values-band .home-heading').allInnerTexts())
    expect(words).toContain(heading.trim())
})

test('the explorer prints the label and the fill of its solid button without background graphics', async ({ page, baseURL, browserName }) => {
  test.skip(browserName !== 'chromium', 'page.pdf is Chromium\'s')
  await printed(page, baseURL!, 'light', { path: EXPLORER })
  const [fill, adjust] = await page.getByRole('button', { name: 'Show', exact: true }).evaluate((element) => {
    const style = getComputedStyle(element)
    return [style.backgroundColor, style.getPropertyValue('print-color-adjust')]
  })
  expect(adjust).toBe('exact')
  const rgb = fill!.match(/\d+/g)!.slice(0, 3).map(value => Number(value) / 255) as Rgb
  const pdf = await page.pdf({ format: 'A4', printBackground: false })
  expect(pdfFillColors(pdf).some(drawn => close(drawn, rgb)), `the fill ${fill} of the button`).toBe(true)
  expect(pdfTextRuns(pdf).some(run => run.text.trim() === 'Show')).toBe(true)
})
