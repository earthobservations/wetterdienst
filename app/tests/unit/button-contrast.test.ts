import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// WCAG 2.x relative luminance and contrast ratio of two #rrggbb colours
function channels(hex: string) {
  return [1, 3, 5].map(i => Number.parseInt(hex.slice(i, i + 2), 16))
}
function luminance(hex: string) {
  const [r, g, b] = channels(hex).map(c => c / 255).map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
}
function contrast(a: string, b: string) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi! + 0.05) / (lo! + 0.05)
}
/** `share` of `fill` over `page`, as a translucent colour is drawn */
function over(fill: string, page: string, share: number) {
  const p = channels(page)
  return `#${channels(fill).map((c, i) => Math.round(share * c + (1 - share) * p[i]!).toString(16).padStart(2, '0')).join('')}`
}

// The tokens of GH-3518 as main.css defines them: the colours are read from the file, so that a shade changed
// there is held to the ratios here
const css = readFileSync(fileURLToPath(new URL('../../app/assets/css/main.css', import.meta.url)), 'utf-8')
function token(name: string) {
  const value = new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6})`, 'i').exec(css)?.[1]
  if (!value)
    throw new Error(`no --color-${name} in main.css`)
  return value
}
const brand = (shade: number) => token(`brand-${shade}`)
const ink = (shade: number) => token(`ink-${shade}`)
const WHITE = '#ffffff'

describe('the logo\'s colours', () => {
  it('are the tokens: the blue is the primary fill, the navy the footer', () => {
    expect(brand(600)).toBe('#2e6fd1')
    expect(token('navy')).toBe('#17335f')
    expect(token('sun')).toBe('#ffc93c')
    expect(token('lagoon')).toBe('#2bb3a3')
    expect(token('ember')).toBe('#f0543c')
  })

  it('keep gray as the ink scale, so the classes written by hand are of the same family', () => {
    for (const shade of [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950])
      expect(token(`gray-${shade}`)).toBe(ink(shade))
  })
})

describe('a solid primary button', () => {
  // light: a white label on shade 600, 700 hovered and 800 pressed (app.config.ts); dark: the dark label of
  // Nuxt UI (ink-900) on shade 400, and 300 hovered and pressed
  it.each([
    ['light, at rest', WHITE, 600],
    ['light, hovered', WHITE, 700],
    ['light, pressed', WHITE, 800],
  ])('has a label of 4.5:1 and more, %s', (_state, label, shade) => {
    expect(contrast(label, brand(shade))).toBeGreaterThanOrEqual(4.5)
  })

  it.each([400, 300])('has a label of 4.5:1 and more in dark mode, on shade %i', (shade) => {
    expect(contrast(ink(900), brand(shade))).toBeGreaterThanOrEqual(4.5)
  })

  it('is darker hovered, where Nuxt UI\'s 75 % of the fill would be under 4.5:1', () => {
    expect(contrast(WHITE, over(brand(600), WHITE, 0.75))).toBeLessThan(4.5)
    const config = readFileSync(fileURLToPath(new URL('../../app/app.config.ts', import.meta.url)), 'utf-8')
    expect(config).toContain('hover:bg-primary-700')
    expect(config).toContain('dark:hover:bg-primary-300')
  })
})

describe('text and focus on the page', () => {
  it('has primary text of 4.5:1 on white and on the tint of a hovered soft button', () => {
    expect(contrast(brand(700), WHITE)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(brand(700), over(brand(600), WHITE, 0.15))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(brand(400), ink(900))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(brand(400), over(brand(400), ink(900), 0.15))).toBeGreaterThanOrEqual(4.5)
  })

  it('has muted text of 4.5:1 on the cards, the page and a hovered field', () => {
    // a quarter of the way from ink-500 to ink-600 (--ui-text-muted; mixed in oklab there, close to this)
    const muted = over(ink(600), ink(500), 0.25)
    for (const background of [WHITE, ink(50), ink(100)])
      expect(contrast(muted, background)).toBeGreaterThanOrEqual(4.5)
    for (const background of [ink(900), ink(800), ink(950)])
      expect(contrast(ink(400), background)).toBeGreaterThanOrEqual(4.5)
  })

  it('has a focus ring of 3:1 on the page, the cards and the footer', () => {
    for (const background of [WHITE, ink(50), brand(50)])
      expect(contrast(brand(700), background)).toBeGreaterThanOrEqual(3)
    for (const background of [ink(900), ink(950), brand(950)])
      expect(contrast(brand(400), background)).toBeGreaterThanOrEqual(3)
    for (const background of [token('navy'), brand(950)])
      expect(contrast(token('sun'), background)).toBeGreaterThanOrEqual(3)
  })

  it('has the footer\'s text of 4.5:1 on its navy, in both modes', () => {
    for (const background of [token('navy'), brand(950)]) {
      expect(contrast(ink(200), background)).toBeGreaterThanOrEqual(4.5)
      expect(contrast(token('sun'), background)).toBeGreaterThanOrEqual(4.5)
    }
  })
})

describe('the sky', () => {
  // every colour of the band (main.css, .wd-sky), and what is laid over it: the header and the head of a page,
  // in ink-600 and stronger on light (text-toned), ink-300 and stronger on dark, the focus ring, and the eyebrow
  const sky = (dark: boolean) => [...css.matchAll(/^(\.dark )?\.wd-sky[^{]*\{([^}]*)\}/gm)]
    .filter(match => Boolean(match[1]) === dark)
    .flatMap(match => [...match[2]!.matchAll(/--sky-(?:top|mid):\s*(#[0-9a-f]{6})/gi)].map(colour => colour[1]!))

  it('has colours for both modes', () => {
    expect(sky(false).length).toBeGreaterThanOrEqual(18)
    expect(sky(true).length).toBeGreaterThanOrEqual(18)
  })

  it.each(sky(false))('keeps the text, the eyebrow and the focus ring readable on %s (light)', (background) => {
    expect(contrast(ink(600), background)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(brand(700), background)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(brand(700), background)).toBeGreaterThanOrEqual(3)
  })

  it.each(sky(true))('keeps the text, the eyebrow and the focus ring readable on %s (dark)', (background) => {
    expect(contrast(ink(300), background)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(brand(300), background)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(brand(400), background)).toBeGreaterThanOrEqual(3)
  })
})
