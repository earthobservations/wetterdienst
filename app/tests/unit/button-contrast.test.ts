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

/** A colour of the theme (`@theme static` in main.css), such as `--color-brand-600` */
function themeColor(name: string): string {
  const value = new RegExp(`${name}:\\s*(#[0-9a-f]{6});`, 'i').exec(css)?.[1]
  if (!value)
    throw new Error(`${name} is not a colour of the theme`)
  return value
}

/** The value of a custom property in the first block of `selector` that sets it, a theme colour read through */
function token(selector: ':root' | '.dark', name: string): string {
  const blocks = [...css.matchAll(new RegExp(`(?:^|\\n)${selector.replace('.', '\\.')} \\{([^}]*)\\}`, 'g'))].map(match => match[1]!)
  for (const block of blocks) {
    const value = new RegExp(`${name}:\\s*([^;]+);`).exec(block)?.[1]?.trim()
    if (value)
      return value.startsWith('var(--color-') ? themeColor(value.slice(4, -1)) : value
  }
  throw new Error(`${name} is not set for ${selector}`)
}

// The fill of a solid primary button is `--ui-primary`: the logo's blue (brand 600) on paper, brand 300 at night.
// Hovered, it is `--app-primary-hover` (app.config.ts), so the fill and its hover are both read from main.css.
describe('the label of a solid primary button (--app-text-on-primary)', () => {
  it.each([
    ['light', ':root', '--color-brand-600'],
    ['dark', '.dark', '--color-brand-300'],
  ] as const)('clears 4.5:1 on the %s fill and on its hover', (_mode, selector, fill) => {
    const label = token(selector, '--app-text-on-primary')
    const hover = token(selector, '--app-primary-hover')
    expect(contrast(label, themeColor(fill))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(label, hover)).toBeGreaterThanOrEqual(4.5)
  })

  it('is measured on the fills main.css sets', () => {
    expect(token(':root', '--ui-primary')).toBe('var(--ui-color-primary-600)')
    expect(token('.dark', '--ui-primary')).toBe('var(--ui-color-primary-300)')
  })

  it('is what Nuxt UI\'s own hover, 75 % of the fill over the page, was not (the reason for the hover colour)', () => {
    const fill = channels(themeColor('--color-brand-600'))
    const paper = channels('#fbfaf7')
    const over = `#${fill.map((c, i) => Math.round(0.75 * c + 0.25 * paper[i]!).toString(16).padStart(2, '0')).join('')}`
    expect(contrast('#ffffff', over)).toBeLessThan(4.5)
  })
})
