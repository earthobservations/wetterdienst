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
/** A colour of the palettes of main.css (`--color-azure-600: #2e6fd1`) */
function color(name: string) {
  const value = new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6})`, 'i').exec(css)?.[1]
  expect(value, name).toBeDefined()
  return value!
}

// The fill of a solid primary button is the logo's blue (azure-600) in light mode and azure-400 in dark mode, hovered
// shade 700 and 300 (app.config.ts); its label is Nuxt UI's text-inverted, white in light mode and gray-900 in dark.
describe('the label of a solid primary button', () => {
  it('is on the shades main.css gives the fill, in both colour modes', () => {
    expect(css).toMatch(/:root\s*\{[^}]*--ui-primary:\s*var\(--ui-color-primary-600\)/)
    expect(css).toMatch(/\.dark\s*\{[^}]*--ui-primary:\s*var\(--ui-color-primary-400\)/)
  })

  it.each([
    ['light', '#ffffff', 'azure-600', 'azure-700'],
    ['dark', 'gray-900', 'azure-400', 'azure-300'],
  ])('clears 4.5:1 on the %s fill and on its hover', (_mode, label, fill, hover) => {
    const text = label.startsWith('#') ? label : color(label)
    expect(contrast(text, color(fill))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(text, color(hover))).toBeGreaterThanOrEqual(4.5)
  })

  it('would not clear it with the hover of Nuxt UI (the reason for the darker one)', () => {
    expect(contrast('#ffffff', over(color('azure-600'), '#ffffff'))).toBeLessThan(4.5)
  })
})

// The muted text of the pages (gray-500 in light mode, gray-400 in dark) on every surface it is drawn on
describe('muted text', () => {
  it.each([
    ['gray-500', '#ffffff'],
    ['gray-500', 'gray-50'],
    ['gray-500', 'gray-100'],
    ['gray-400', 'gray-900'],
    ['gray-400', 'gray-950'],
    ['gray-400', 'gray-800'],
  ])('%s clears 4.5:1 on %s', (text, surface) => {
    expect(contrast(color(text), surface.startsWith('#') ? surface : color(surface))).toBeGreaterThanOrEqual(4.5)
  })
})
