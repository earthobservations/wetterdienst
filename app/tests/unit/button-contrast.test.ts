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

// The colours of the app are tokens of main.css (GH-3518): read from there, so that a change of a shade is held to
// the ratios it has to keep
const css = readFileSync(fileURLToPath(new URL('../../app/assets/css/main.css', import.meta.url)), 'utf-8')
function token(name: string): string {
  const value = new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, 'i').exec(css)?.[1]
  if (!value)
    throw new Error(`--${name} is not a colour of main.css`)
  return value
}
// the `.dark { ... }` block of the file: the night's tokens
const nightStart = css.indexOf('.dark {')
const night = css.slice(nightStart, css.indexOf('}', nightStart))
function darkToken(name: string): string {
  const value = new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, 'i').exec(night)?.[1]
  if (!value)
    throw new Error(`--${name} is not a colour of main.css at night`)
  return value
}
const brand = (shade: number) => token(`color-brand-${shade}`)
const ink = (shade: number) => token(`color-ink-${shade}`)
const WHITE = '#ffffff'

describe('the solid primary button (app.config.ts)', () => {
  // light: a white label on the logo's blue, hovered shade 700, pressed shade 800;
  // dark: a navy label on shade 400, hovered shade 300, pressed shade 200
  it.each([
    ['light, at rest', WHITE, 600],
    ['light, hovered', WHITE, 700],
    ['light, pressed', WHITE, 800],
    ['dark, at rest', 'navy', 400],
    ['dark, hovered', 'navy', 300],
    ['dark, pressed', 'navy', 200],
  ] as const)('has a label that clears 4.5:1 on its fill, %s', (_state, label, shade) => {
    const text = label === 'navy' ? ink(950) : label
    expect(contrast(text, brand(shade))).toBeGreaterThanOrEqual(4.5)
  })

  it('is the logo\'s blue', () => {
    expect(brand(600).toLowerCase()).toBe('#2e6fd1')
    expect(css).toMatch(/--ui-primary:\s*var\(--color-brand-600\)/)
  })
})

describe('text in the colours of the app', () => {
  const PAPER = ink(50)
  it.each([
    ['body text on a card', ink(800), WHITE],
    ['muted text on a card', ink(600), WHITE],
    ['dimmed text on a card', ink(500), WHITE],
    ['dimmed text on the paper', ink(500), PAPER],
    ['dimmed text on a hovered field', ink(500), ink(100)],
    ['primary text on a card', brand(700), WHITE],
    ['primary text on its soft tint', brand(700), brand(100)],
    ['a hovered link on a card', brand(800), WHITE],
    ['muted text at night, on the page', ink(400), ink(950)],
    ['muted text at night, on the accented fill', ink(400), darkToken('ui-bg-accented')],
    ['primary text at night, on a card', brand(400), darkToken('ui-bg')],
  ])('clears 4.5:1: %s', (_what, text, ground) => {
    expect(contrast(text, ground)).toBeGreaterThanOrEqual(4.5)
  })

  // the edge of a field, a checkbox and a switch, and the focus ring: 3:1 (WCAG 1.4.11)
  it.each([
    ['the edge of a field on a card', token('ui-border-accented'), WHITE],
    ['the edge of a field on the paper', token('ui-border-accented'), PAPER],
    ['the focus ring on the paper', token('color-brand-700'), PAPER],
  ])('clears 3:1: %s', (_what, line, ground) => {
    expect(contrast(line, ground)).toBeGreaterThanOrEqual(3)
  })
})

describe('the tiles of the tools (GH-3650)', () => {
  // a tile is a mark beside a name that is always written, so it needs 3:1 as a non-text mark (WCAG 1.4.11) against what
  // it lies on, and its glyph 4.5:1 on its fill (the glyph is a picture of the name, and so held to text's ratio)
  const CARD = '#ffffff'
  const PAPER = ink(50)
  const NIGHT_CARD = darkToken('ui-bg')
  const NIGHT_PAGE = ink(950)

  it.each([
    ['by day, on a card', token('color-tile-map'), CARD],
    ['by day, on the paper', token('color-tile-map'), PAPER],
    ['at night, on a card', token('color-tile-map-night'), NIGHT_CARD],
    ['at night, on the page', token('color-tile-map-night'), NIGHT_PAGE],
  ])('has a violet map tile that clears 3:1 against what it lies on, %s', (_where, fill, ground) => {
    expect(contrast(fill, ground)).toBeGreaterThanOrEqual(3)
  })

  it.each([
    ['by day, white', token('color-tile-map'), WHITE],
    ['at night, navy', token('color-tile-map-night'), ink(950)],
  ])('has a glyph on the map tile that clears 4.5:1, %s', (_when, fill, glyph) => {
    expect(contrast(glyph, fill)).toBeGreaterThanOrEqual(4.5)
  })

  it('says in the stylesheet what the test holds: white on the day violet, navy on the night violet', () => {
    expect(css).toMatch(/\.tile-map\s*\{[^}]*--tile-fill:\s*var\(--color-tile-map\)[^}]*--tile-glyph:\s*#ffffff/)
    expect(css).toMatch(/\.dark \.tile-map\s*\{[^}]*--tile-fill:\s*var\(--color-tile-map-night\)[^}]*--tile-glyph:\s*var\(--color-ink-950\)/)
  })

  /** The hue of a colour, in degrees */
  function hue(hex: string) {
    const [r, g, b] = channels(hex).map(c => c! / 255) as [number, number, number]
    const max = Math.max(r, g, b)
    const delta = max - Math.min(r, g, b)
    const sector = max === r ? ((g - b) / delta) % 6 : max === g ? (b - r) / delta + 2 : (r - g) / delta + 4
    return (sector * 60 + 360) % 360
  }

  it('is in the gap of the colour wheel the issue names, between the rain\'s blue and the thermometer\'s coral (hue 250 to 280: violet-600 is 262, the lighter violet of the night 256), by day and at night', () => {
    for (const fill of [token('color-tile-map'), token('color-tile-map-night')]) {
      expect(hue(fill)).toBeGreaterThanOrEqual(250)
      expect(hue(fill)).toBeLessThanOrEqual(280)
    }
  })

  it('is far from the other four tiles in hue, 40 degrees at the least', () => {
    const distance = (a: number, b: number) => Math.min(Math.abs(a - b), 360 - Math.abs(a - b))
    for (const other of ['sun', 'rain', 'wind', 'heat'])
      expect(distance(hue(token('color-tile-map')), hue(token(`color-tile-${other}`))), other).toBeGreaterThanOrEqual(40)
  })
})

describe('the arrow buttons of the phone bar\'s chooser (GH-3846)', () => {
  // their edge is the muted text colour, on the row's raised background (1.4.11: 3:1)
  it('has the muted text colour as its edge', () => {
    expect(/\.bar-move \{[^}]*border: 1px solid var\(--ui-text-muted\)/.test(css)).toBe(true)
  })

  it.each([
    ['light, on the row', ink(600), ink(100)],
    ['light, on the button\'s own fill', ink(600), WHITE],
    ['dark, on the row', ink(400), darkToken('ui-bg-elevated')],
    ['dark, on the button\'s own fill', ink(400), darkToken('ui-bg')],
  ])('clears 3:1 against what it lies on, %s', (_where, edge, ground) => {
    expect(contrast(edge, ground)).toBeGreaterThanOrEqual(3)
  })
})

describe('the two lines of the bar\'s tools and the menu-only tools (GH-3934)', () => {
  // a line beside a tool in the Menu's sheet, and the dashed line of the chooser: non-text marks (WCAG 1.4.11), 3:1
  // against what they lie on, light and dark. The words a screen reader gets are the other half, and tested with the sheet.
  const day = css.slice(css.indexOf(':root,'), css.indexOf('.dark {'))
  const shade = (block: string, name: string) => brand(Number(new RegExp(`--${name}:\\s*var\\(--color-brand-(\\d+)\\)`).exec(block)?.[1]))
  const CARD = '#ffffff'
  const HOVERED_LINK = ink(100)
  const NIGHT_CARD = darkToken('ui-bg')
  const NIGHT_HOVERED_LINK = darkToken('ui-bg-elevated')

  it.each([
    ['the bar\'s line by day, on the sheet', shade(day, 'app-mark-bar'), CARD],
    ['the bar\'s line by day, on a hovered link', shade(day, 'app-mark-bar'), HOVERED_LINK],
    ['the menu-only line by day, on the sheet', shade(day, 'app-mark-menu'), CARD],
    ['the menu-only line by day, on a hovered link', shade(day, 'app-mark-menu'), HOVERED_LINK],
    ['the bar\'s line at night, on the sheet', shade(night, 'app-mark-bar'), NIGHT_CARD],
    ['the bar\'s line at night, on a hovered link', shade(night, 'app-mark-bar'), NIGHT_HOVERED_LINK],
    ['the menu-only line at night, on the sheet', shade(night, 'app-mark-menu'), NIGHT_CARD],
    ['the menu-only line at night, on a hovered link', shade(night, 'app-mark-menu'), NIGHT_HOVERED_LINK],
  ])('clears 3:1: %s', (_what, line, ground) => {
    expect(contrast(line, ground)).toBeGreaterThanOrEqual(3)
  })

  it('has two colours that are not one, by day and at night', () => {
    expect(shade(day, 'app-mark-bar')).not.toBe(shade(day, 'app-mark-menu'))
    expect(shade(night, 'app-mark-bar')).not.toBe(shade(night, 'app-mark-menu'))
  })

  it('has the bar\'s line the stronger of the two against the sheet, by day and at night', () => {
    expect(contrast(shade(day, 'app-mark-bar'), CARD)).toBeGreaterThan(contrast(shade(day, 'app-mark-menu'), CARD))
    expect(contrast(shade(night, 'app-mark-bar'), NIGHT_CARD)).toBeGreaterThan(contrast(shade(night, 'app-mark-menu'), NIGHT_CARD))
  })

  it('draws the menu-only line shorter than the bar\'s, so that the groups differ by shape as well (WCAG 1.4.1)', () => {
    const height = (rule: RegExp) => Number(rule.exec(css)?.[1])
    expect(height(/\.tool-mark\s*\{[^}]*height:\s*([\d.]+)rem/)).toBe(1.25)
    expect(height(/\.sheet-tool\[data-group="menu"\] \.tool-mark\s*\{[^}]*height:\s*([\d.]+)rem/)).toBe(0.75)
  })

  it('keeps the two lines apart in forced colours, where a background is replaced: text colour and grey', () => {
    const forced = css.slice(css.indexOf('@media (forced-colors: active)'))
    expect(forced).toMatch(/\.tool-mark\s*\{[^}]*forced-color-adjust:\s*none;[^}]*background:\s*CanvasText/)
    expect(forced).toMatch(/\.sheet-tool\[data-group="menu"\] \.tool-mark\s*\{[^}]*background:\s*GrayText/)
  })

  it('draws the chooser\'s dashed line in the bar\'s colour, so the sheet and the chooser mark the groups alike', () => {
    expect(css).toMatch(/\.bar-line\s*\{[^}]*border-top:\s*2px dashed var\(--app-mark-bar\)/)
    expect(css).toMatch(/\.tool-mark\s*\{[^}]*background:\s*var\(--app-mark-bar\)/)
    expect(css).toMatch(/\.sheet-tool\[data-group="menu"\] \.tool-mark\s*\{[^}]*background:\s*var\(--app-mark-menu\)/)
  })
})
