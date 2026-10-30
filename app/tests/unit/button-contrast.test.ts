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
