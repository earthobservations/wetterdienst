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

// a colour of the theme (`--color-brand-600: #2e6fd1`)
function token(name: string) {
  const hex = new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6})`, 'i').exec(css)?.[1]
  expect(hex, `--color-${name} in main.css`).toBeDefined()
  return hex!
}
// what a block of main.css (`:root {` or `.dark {`) says --app-text-on-primary is: a colour, or a token of the theme
function labelIn(selector: string) {
  const block = new RegExp(`^${selector.replace('.', '\\.')} \\{([^}]*)\\}`, 'm')
  const value = [...css.matchAll(new RegExp(block.source, 'gm'))]
    .map(match => /--app-text-on-primary:\s*([^\s;][^;]*);/.exec(match[1]!)?.[1])
    .find(Boolean)
  expect(value, `--app-text-on-primary in ${selector}`).toBeDefined()
  const token_ = /^var\(--color-([a-z0-9-]+)\)$/.exec(value!)?.[1]
  return token_ ? token(token_) : value!
}

describe('the label of a solid primary button (--app-text-on-primary)', () => {
  it('is set in main.css for both colour modes, and the hovered fill with it', () => {
    expect(labelIn(':root')).toMatch(/^#[0-9a-f]{6}$/i)
    expect(labelIn('.dark')).toMatch(/^#[0-9a-f]{6}$/i)
    expect(css).toMatch(/--app-primary-hover:\s*var\(--ui-color-primary-700\)/)
    expect(css).toMatch(/--app-primary-hover:\s*var\(--ui-color-primary-300\)/)
  })

  // light: the logo's blue (brand-600) is the fill and brand-700 the hovered fill; dark: brand-400 and brand-300
  it.each([
    ['light', ':root', 'brand-600', 'brand-700'],
    ['dark', '.dark', 'brand-400', 'brand-300'],
  ])('clears 4.5:1 on the %s fill and on its hover', (_mode, selector, fill, hover) => {
    const label = labelIn(selector)
    expect(contrast(label, token(fill))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(label, token(hover))).toBeGreaterThanOrEqual(4.5)
  })

  it('is the logo\'s blue, #2e6fd1, that the light fill is', () => {
    expect(token('brand-600').toLowerCase()).toBe('#2e6fd1')
  })

  // Nuxt UI's hovered fill is 75 % of the fill over the page: the reason the theme sets its own
  it('is what Nuxt UI\'s own hover (75 % of the fill over white) would not clear', () => {
    const [r, g, b] = channels(token('brand-600')).map(c => Math.round(0.75 * c + 0.25 * 255))
    const hovered = `#${[r, g, b].map(c => c!.toString(16).padStart(2, '0')).join('')}`
    expect(contrast(labelIn(':root'), hovered)).toBeLessThan(4.5)
  })
})
