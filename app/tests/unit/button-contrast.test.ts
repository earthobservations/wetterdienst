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

const css = readFileSync(fileURLToPath(new URL('../../app/assets/css/main.css', import.meta.url)), 'utf-8')
const config = readFileSync(fileURLToPath(new URL('../../app/app.config.ts', import.meta.url)), 'utf-8')

/** A colour of the theme, as main.css writes it (`--color-brand-600: #2459b0`) */
function token(name: string): string {
  const found = new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6})`, 'i').exec(css)?.[1]
  expect(found, `--color-${name} in main.css`).toBeDefined()
  return found!
}

const WHITE = '#ffffff'

describe('the colours of the controls (main.css, app.config.ts)', () => {
  it('fill a solid primary button with shade 600 on light and 300 on dark, and hover a shade further', () => {
    expect(css).toMatch(/:root\s*\{[^}]*--ui-primary:\s*var\(--ui-color-primary-600\)/)
    expect(css).toMatch(/\.dark\s*\{[^}]*--ui-primary:\s*var\(--ui-color-primary-300\)/)
    expect(config).toContain('hover:bg-(--ui-color-primary-700)')
    expect(config).toContain('dark:hover:bg-(--ui-color-primary-200)')
  })

  // the label is Nuxt UI's text-inverted: white on light, the neutral-900 of the dark page on dark
  it.each([
    ['light, at rest', WHITE, 'brand-600'],
    ['light, hovered', WHITE, 'brand-700'],
    ['dark, at rest', 'gray-900', 'brand-300'],
    ['dark, hovered', 'gray-900', 'brand-200'],
  ])('gives its label 4.5:1 and more, %s', (_state, label, fill) => {
    const text = label.startsWith('#') ? label : token(label)
    expect(contrast(text, token(fill))).toBeGreaterThanOrEqual(4.5)
  })

  it('writes text in the primary colour that clears 4.5:1 on the page and on its tint', () => {
    // light: shade 700 on white and on shade 50; dark: shade 300 on the page (neutral-900) and its raised surface (800)
    expect(contrast(token('brand-700'), WHITE)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(token('brand-700'), token('brand-50'))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(token('brand-300'), token('gray-900'))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(token('brand-300'), token('gray-800'))).toBeGreaterThanOrEqual(4.5)
  })

  it('draws the focus ring at 3:1 and more against the page', () => {
    expect(contrast(token('brand-700'), WHITE)).toBeGreaterThanOrEqual(3)
    expect(contrast(token('brand-300'), token('gray-900'))).toBeGreaterThanOrEqual(3)
  })

  it('keeps muted text at 4.5:1 on the page, on its tinted surfaces and in dark mode', () => {
    expect(contrast(token('gray-500'), WHITE)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(token('gray-500'), token('gray-50'))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(token('gray-500'), token('gray-100'))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(token('gray-400'), token('gray-900'))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(token('gray-400'), token('gray-800'))).toBeGreaterThanOrEqual(4.5)
  })

  it('gives the icons of the question tiles 3:1 and more on their tiles (the logo\'s four colours)', () => {
    const night = token('brand-950')
    expect(contrast(night, token('sun'))).toBeGreaterThanOrEqual(3)
    expect(contrast(night, token('wind'))).toBeGreaterThanOrEqual(3)
    expect(contrast(night, token('warmth'))).toBeGreaterThanOrEqual(3)
    expect(contrast(WHITE, token('rain'))).toBeGreaterThanOrEqual(3)
  })
})
