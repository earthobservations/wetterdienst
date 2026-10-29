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
// 75 % of the fill over the page: the hover state of Nuxt UI's solid button (bg-primary/75), which the app replaces
function over(fill: string, page: string) {
  const p = channels(page)
  return `#${channels(fill).map((c, i) => Math.round(0.75 * c + 0.25 * p[i]!).toString(16).padStart(2, '0')).join('')}`
}

const css = readFileSync(fileURLToPath(new URL('../../app/assets/css/main.css', import.meta.url)), 'utf-8')

/** A shade of the brand scale, as main.css defines it (`--color-brand-600: #2e6fd1`) */
function brand(shade: number): string {
  const found = new RegExp(`--color-brand-${shade}:\\s*(#[0-9a-f]{6})`, 'i').exec(css)?.[1]
  expect(found, `--color-brand-${shade} in main.css`).toBeDefined()
  return found!
}

/** A colour of main.css's blocks for a mode: the first block of `:root` or `.dark` that sets the variable, a hex or a brand shade */
function token(mode: 'light' | 'dark', name: string): string {
  const selector = mode === 'light' ? ':root' : '.dark'
  const blocks = [...css.matchAll(/^([^\n{]+)\{([^}]*)\}/gm)].filter(match => match[1]!.trim() === selector)
  const value = blocks.map(match => new RegExp(`${name}:\\s*([^;]+);`).exec(match[2]!)?.[1]?.trim()).find(Boolean)
  expect(value, `${name} for ${mode} mode in main.css`).toBeDefined()
  const shade = /--ui-color-primary-(\d+)/.exec(value!)?.[1]
  return shade ? brand(Number(shade)) : value!
}

// The page under a button: white in light mode, the app's dark page in dark mode
const PAGE = { light: '#ffffff', dark: token('dark', '--ui-bg') }

describe('the solid primary button (--app-text-on-primary, --app-primary-hover)', () => {
  it.each(['light', 'dark'] as const)('clears 4.5:1 on its fill and on its hovered fill in %s mode', (mode) => {
    const label = token(mode, '--app-text-on-primary')
    const fill = token(mode, '--ui-primary')
    const hover = token(mode, '--app-primary-hover')
    expect(contrast(label, fill)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(label, hover)).toBeGreaterThanOrEqual(4.5)
  })

  it('has the logo\'s blue as its fill in light mode', () => {
    expect(token('light', '--ui-primary')).toBe('#2e6fd1')
  })

  it('needs a hover of its own: Nuxt UI\'s, the fill at 75 % over the page, is under 4.5:1 with the label', () => {
    const label = token('light', '--app-text-on-primary')
    expect(contrast(label, over(token('light', '--ui-primary'), PAGE.light))).toBeLessThan(4.5)
  })
})
