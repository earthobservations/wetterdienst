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

describe('the label of a solid primary button (--app-text-on-primary)', () => {
  const label = /--app-text-on-primary:\s*(#[0-9a-f]{6})/i.exec(css)?.[1]

  it('is set in main.css, for both colour modes', () => {
    expect(label).toBeDefined()
    // not redefined for .dark: one dark label serves the brand green and its lighter dark-mode shade
    expect(css).not.toMatch(/\.dark\s*\{[^}]*--app-text-on-primary/)
  })

  // Tailwind's green-500, the fill in light mode, over white; green-400, the fill in dark mode, over slate-900 (Nuxt UI's neutral)
  it.each([
    ['light', '#00c950', '#ffffff'],
    ['dark', '#05df72', '#0f172b'],
  ])('clears 4.5:1 on the %s fill and on its hover', (_mode, fill, page) => {
    expect(contrast(label!, fill)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(label!, over(fill, page))).toBeGreaterThanOrEqual(4.5)
  })

  it('is what white was not (the reason for the dark label)', () => {
    expect(contrast('#ffffff', '#00c950')).toBeLessThan(3)
  })
})
