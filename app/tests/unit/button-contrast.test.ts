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
// 75 % of the fill over the page: the hover state of Nuxt UI's own solid button (bg-primary/75)
function over(fill: string, page: string) {
  const p = channels(page)
  return `#${channels(fill).map((c, i) => Math.round(0.75 * c + 0.25 * p[i]!).toString(16).padStart(2, '0')).join('')}`
}

const css = readFileSync(fileURLToPath(new URL('../../app/assets/css/main.css', import.meta.url)), 'utf-8')
const config = readFileSync(fileURLToPath(new URL('../../app/app.config.ts', import.meta.url)), 'utf-8')

/** A shade of the brand blue, as main.css defines it */
function brand(shade: number) {
  const value = new RegExp(`--color-brand-${shade}:\\s*(#[0-9a-f]{6})`, 'i').exec(css)?.[1]
  expect(value, `--color-brand-${shade} in main.css`).toBeDefined()
  return value!
}

// Nuxt UI's `text-inverted`, the label of a solid button: white in light mode, slate-900 in dark mode
const WHITE = '#ffffff'
const SLATE_900 = '#0f172b'

describe('the brand blue of the solid primary button', () => {
  it('is the blue of the logo, with the navy of the logo as shade 900', () => {
    expect(brand(500).toLowerCase()).toBe('#2e6fd1')
    expect(brand(900).toLowerCase()).toBe('#17335f')
  })

  // the fill is shade 500 in light mode and 400 in dark mode (Nuxt UI's --ui-primary); hovered and pressed it is
  // the shade app.config.ts names
  it.each([
    ['light', WHITE, 500, 600],
    ['dark', SLATE_900, 400, 300],
  ] as const)('carries its label at 4.5:1 or more in %s mode, at rest and hovered', (_mode, label, rest, hovered) => {
    expect(contrast(label, brand(rest))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(label, brand(hovered))).toBeGreaterThanOrEqual(4.5)
  })

  it('is hovered by a shade of its own in app.config.ts, as the fade of Nuxt UI would not do', () => {
    expect(config).toContain('hover:bg-primary-600')
    expect(config).toContain('dark:hover:bg-primary-300')
    // 75 % of the blue over white is too light for a white label
    expect(contrast(WHITE, over(brand(500), WHITE))).toBeLessThan(4.5)
  })
})
