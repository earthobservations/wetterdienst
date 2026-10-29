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
// 75 % of the fill over the page: the hover state of Nuxt UI's solid button (bg-primary/75)
function over(fill: string, page: string) {
  const p = channels(page)
  return `#${channels(fill).map((c, i) => Math.round(0.75 * c + 0.25 * p[i]!).toString(16).padStart(2, '0')).join('')}`
}

const css = readFileSync(fileURLToPath(new URL('../../app/assets/css/main.css', import.meta.url)), 'utf-8')

/** A colour of the theme in main.css (`--color-<name>`), or a colour written out */
function colour(name: string) {
  if (name.startsWith('#'))
    return name
  const value = new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6})`, 'i').exec(css)?.[1]
  if (!value)
    throw new Error(`no --color-${name} in main.css`)
  return value
}

// The solid primary button (app.config.ts, main.css, GH-3518): blue 700 with a white label on the white page of light
// mode, blue 300 with an ink label on the ink 900 page of dark mode; hovered, the fill goes a step further from the page
// (blue 800, blue 200), where Nuxt UI's own hover fades it to 75 %.
describe('the solid primary button', () => {
  it('has its fills and labels named in main.css', () => {
    expect(css).toMatch(/:root:not\(\.dark\)\s*\{[^}]*--ui-primary:\s*var\(--ui-color-primary-700\)/)
    expect(css).toMatch(/:root:not\(\.dark\)\s*\{[^}]*--app-primary-hover:\s*var\(--ui-color-primary-800\)/)
    expect(css).toMatch(/:root\.dark\s*\{[^}]*--ui-primary:\s*var\(--ui-color-primary-300\)/)
    expect(css).toMatch(/:root\.dark\s*\{[^}]*--app-primary-hover:\s*var\(--ui-color-primary-200\)/)
    expect(css).toMatch(/:root\s*\{\s*--app-text-on-primary:\s*#ffffff/)
    expect(css).toMatch(/\.dark\s*\{\s*--app-text-on-primary:\s*#0b1a33/)
  })

  it.each([
    ['light', 'brand-700', 'brand-800', '#ffffff', '#ffffff'],
    ['dark', 'brand-300', 'brand-200', '#0b1a33', 'ink-900'],
  ])('clears 4.5:1 for its label in %s mode, at rest and hovered, and 3:1 for its fill against the page', (_mode, fill, hover, label, page) => {
    expect(contrast(colour(label), colour(fill))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(colour(label), colour(hover))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(colour(fill), colour(page))).toBeGreaterThanOrEqual(3)
  })

  it('is what Nuxt UI\'s fading hover was not: a white label on 75 % of the light fill', () => {
    expect(contrast('#ffffff', over(colour('brand-700'), '#ffffff'))).toBeLessThan(4.5)
  })
})

// The text colours a page is set in, on the backgrounds they are set on (WCAG 1.4.3)
describe('the text colours of the theme', () => {
  it.each([
    ['ink on white', 'ink-900', '#ffffff'],
    ['muted text (ink 500) on white', 'ink-500', '#ffffff'],
    ['muted text on a hovered field (ink 100)', 'ink-500', 'ink-100'],
    ['a link (blue 700) on white', 'brand-700', '#ffffff'],
    ['a link on the footer (ink 50)', 'brand-700', 'ink-50'],
    ['dark: text (ink 100) on the page (ink 900)', 'ink-100', 'ink-900'],
    ['dark: muted text (ink 400) on the page', 'ink-400', 'ink-900'],
    ['dark: muted text on a card (ink 800)', 'ink-400', 'ink-800'],
    ['dark: a link (blue 300) on the page', 'brand-300', 'ink-900'],
    ['dark: a link (blue 400) on the page', 'brand-400', 'ink-900'],
    ['dark: a link on the footer (ink 800)', 'brand-300', 'ink-800'],
    ['the masthead: white on the navy', '#ffffff', 'brand-900'],
  ])('%s clears 4.5:1', (_what, text, background) => {
    expect(contrast(colour(text), colour(background))).toBeGreaterThanOrEqual(4.5)
  })

  it.each([
    ['the focus ring on light (ink 950 on white)', 'ink-950', '#ffffff'],
    ['the focus ring on dark (the yellow on ink 900)', 'sun', 'ink-900'],
    ['the focus ring on the masthead (the yellow on the navy)', 'sun', 'brand-900'],
    ['the edge of a field on light (ink 500 on white)', 'ink-500', '#ffffff'],
    ['the edge of a field on dark (ink 400 on ink 900)', 'ink-400', 'ink-900'],
  ])('%s clears 3:1', (_what, foreground, background) => {
    expect(contrast(colour(foreground), colour(background))).toBeGreaterThanOrEqual(3)
  })
})
