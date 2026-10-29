import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// The colours of the design (GH-3518), read from main.css, held to WCAG 2.2 AA: 4.5:1 for text, 3:1 for the focus
// indicator (1.4.11). Each pair is one the app draws; the scans of `pnpm test:a11y` measure the pages themselves.

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
// `alpha` of the colour over what lies under it: a tint (bg-primary/10) or Nuxt UI's hover (bg-primary/75)
function over(fill: string, under: string, alpha: number) {
  const u = channels(under)
  return `#${channels(fill).map((c, i) => Math.round(alpha * c + (1 - alpha) * u[i]!).toString(16).padStart(2, '0')).join('')}`
}

const css = readFileSync(fileURLToPath(new URL('../../app/assets/css/main.css', import.meta.url)), 'utf-8')
function token(name: string): string {
  const value = new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6})`, 'i').exec(css)?.[1]
  if (!value)
    throw new Error(`--color-${name} is not in main.css`)
  return value
}

const WHITE = '#ffffff'
const brand = (shade: number) => token(`brand-${shade}`)
const gray = (shade: number) => token(`gray-${shade}`)
const NAVY = token('navy')
const INK = token('tile-ink')
const DARK_PAGE = gray(900)

describe('the tokens', () => {
  it('are the colours of the logo', () => {
    expect([NAVY, brand(600), token('tile-sun'), token('tile-rain'), token('tile-wind'), token('tile-heat')].map(c => c.toLowerCase()))
      .toEqual(['#17335f', '#2e6fd1', '#ffc93c', '#2e6fd1', '#2bb3a3', '#f0543c'])
  })

  it('set the primary colour to shade 700 on light and 400 on dark, and a solid button\'s hover a shade outwards', () => {
    expect(css).toMatch(/:root\s*\{[^}]*--ui-primary:\s*var\(--ui-color-primary-700\)/)
    expect(css).toMatch(/\.dark\s*\{[^}]*--ui-primary:\s*var\(--ui-color-primary-400\)/)
    expect(css).toMatch(/:root\s*\{[^}]*--app-primary-hover:\s*var\(--ui-color-primary-800\)/)
    expect(css).toMatch(/\.dark\s*\{[^}]*--app-primary-hover:\s*var\(--ui-color-primary-300\)/)
  })
})

describe('a solid primary button (Nuxt UI\'s text-inverted label)', () => {
  it.each([
    ['light', WHITE, brand(700), brand(800)],
    ['dark', DARK_PAGE, brand(400), brand(300)],
  ])('clears 4.5:1 on the %s fill and on its hover', (_mode, label, fill, hover) => {
    expect(contrast(label, fill)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(label, hover)).toBeGreaterThanOrEqual(4.5)
  })

  it('would not on Nuxt UI\'s own hover, 75 % of the fill over the page (the reason for --app-primary-hover)', () => {
    expect(contrast(WHITE, over(brand(700), WHITE, 0.75))).toBeLessThan(4.5)
    expect(contrast(DARK_PAGE, over(brand(400), DARK_PAGE, 0.75))).toBeLessThan(4.5)
  })
})

describe('text in the primary colour', () => {
  it.each([
    ['light, on the page', brand(700), WHITE],
    ['light, on its own 15 % tint (a soft button, a badge)', brand(700), over(brand(700), WHITE, 0.15)],
    ['light, hovered link', brand(800), WHITE],
    ['dark, on the page', brand(400), DARK_PAGE],
    ['dark, on an elevated surface', brand(400), gray(800)],
    ['dark, on its own 15 % tint', brand(400), over(brand(400), DARK_PAGE, 0.15)],
    ['dark, hovered link', brand(300), DARK_PAGE],
  ])('clears 4.5:1 %s', (_where, text, background) => {
    expect(contrast(text, background)).toBeGreaterThanOrEqual(4.5)
  })
})

describe('the greys, turned towards the navy', () => {
  // muted and dimmed text on light: a quarter of the way from grey-500 to grey-600 (main.css), approximated here by
  // grey-500, the lighter end, which is the harder case
  it.each([
    ['light muted text on the page', gray(500), WHITE],
    ['light muted text on a muted surface', gray(500), gray(50)],
    ['light toned text on an elevated surface', gray(600), gray(100)],
    ['dark muted text on the page', gray(400), DARK_PAGE],
    ['dark muted text on an elevated surface', gray(400), gray(800)],
  ])('clear 4.5:1: %s', (_where, text, background) => {
    expect(contrast(text, background)).toBeGreaterThanOrEqual(4.5)
  })
})

describe('the rail and the navy band', () => {
  it.each([
    ['a label', WHITE, NAVY],
    ['an entry\'s label', gray(200), NAVY],
    ['an entry\'s label, hovered', WHITE, over(WHITE, NAVY, 0.08)],
    ['the page shown', WHITE, over(WHITE, NAVY, 0.12)],
    ['a group\'s heading', gray(300), NAVY],
  ])('clears 4.5:1 for %s', (_what, text, background) => {
    expect(contrast(text, background)).toBeGreaterThanOrEqual(4.5)
  })
})

describe('the tiles of the logo', () => {
  it.each([
    ['sun', INK],
    ['wind', INK],
    ['heat', INK],
    ['rain', WHITE],
  ])('carry text of 4.5:1 on the %s tile', (tile, text) => {
    expect(contrast(text, token(`tile-${tile}`))).toBeGreaterThanOrEqual(4.5)
  })
})

describe('the focus indicator', () => {
  it.each([
    ['light, on the page', brand(700), WHITE],
    ['light, on a muted surface', brand(700), gray(100)],
    ['dark, on the page', brand(300), DARK_PAGE],
    ['dark, on an elevated surface', brand(300), gray(800)],
    ['the rail, the logo\'s yellow on navy', token('tile-sun'), NAVY],
    ['the rail, on the page shown', token('tile-sun'), over(WHITE, NAVY, 0.12)],
  ])('has 3:1 %s', (_where, ring, background) => {
    expect(contrast(ring, background)).toBeGreaterThanOrEqual(3)
  })
})
