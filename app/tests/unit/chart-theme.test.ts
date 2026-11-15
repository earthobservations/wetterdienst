import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { CHART_TOKENS, EMPTY_CHART_THEME, parseCssColor, readChartTheme, SERIES_LABEL, seriesLabelColor, withAlpha } from '../../app/utils/chart-theme'

// The custom properties as the browser would answer them in each colour scheme, in the syntax the
// tokens are written in (oklch), and the resolver standing in for the canvas that turns them into rgb()
const SCHEMES: Record<'light' | 'dark', Record<string, string>> = {
  light: {
    '--app-chart-paper': 'rgb(255, 255, 255)',
    '--app-chart-plot': 'rgb(255, 255, 255)',
    '--app-chart-text': 'oklch(0.37 0.04 257)',
    '--app-chart-text-strong': 'oklch(0.21 0.04 266)',
    '--app-chart-text-muted': 'oklch(0.52 0.04 257)',
    '--app-chart-grid': 'oklch(0.87 0.02 253)',
    '--app-chart-axis': 'oklch(0.52 0.04 257)',
    '--app-chart-zeroline': 'oklch(0.52 0.04 257)',
  },
  dark: {
    '--app-chart-paper': 'oklch(0.21 0.04 266)',
    '--app-chart-plot': 'oklch(0.21 0.04 266)',
    '--app-chart-text': 'oklch(0.93 0.01 256)',
    '--app-chart-text-strong': 'rgb(255, 255, 255)',
    '--app-chart-text-muted': 'oklch(0.71 0.04 257)',
    '--app-chart-grid': 'oklch(0.37 0.04 257)',
    '--app-chart-axis': 'oklch(0.71 0.04 257)',
    '--app-chart-zeroline': 'oklch(0.71 0.04 257)',
  },
}
// a stand-in for the canvas: every CSS colour becomes an rgb() named after it, so that a test can tell which token went where
const resolve = (color: string) => (color.startsWith('rgb(') ? color : `rgb(<${color}>)`)
const themeOf = (scheme: 'light' | 'dark') => readChartTheme(property => ` ${SCHEMES[scheme][property] ?? ''} `, resolve, scheme === 'dark')

describe('readChartTheme', () => {
  it('reads every token of the list, resolved, and says whether the page is dark', () => {
    const dark = themeOf('dark')
    expect(dark.dark).toBe(true)
    for (const key of Object.keys(CHART_TOKENS) as (keyof typeof CHART_TOKENS)[])
      expect(dark[key], key).toBe(resolve(SCHEMES.dark[CHART_TOKENS[key]]!))
    expect(themeOf('light').dark).toBe(false)
  })

  it('leaves a colour empty where the token is not set', () => {
    const theme = readChartTheme(() => '', resolve, false)
    expect(theme).toEqual(EMPTY_CHART_THEME)
  })

  it('differs between light and dark in the paper, the text and the grid', () => {
    const [light, dark] = [themeOf('light'), themeOf('dark')]
    for (const key of ['paper', 'plot', 'text', 'textMuted', 'grid', 'axis'] as const)
      expect(dark[key], key).not.toBe(light[key])
  })
})

describe('parseCssColor', () => {
  it.each([
    ['rgb(15, 23, 43)', 'rgb(15, 23, 43)'],
    ['rgb(15 23 43)', 'rgb(15, 23, 43)'],
    ['rgba(15, 23, 43, 0.5)', 'rgba(15, 23, 43, 0.5)'],
    ['rgb(15 23 43 / 50%)', 'rgba(15, 23, 43, 0.5)'],
    ['rgba(15, 23, 43, 1)', 'rgb(15, 23, 43)'],
  ])('reads the rgb() a browser answers for %s', (computed, expected) => {
    expect(parseCssColor(computed)).toBe(expected)
  })

  it.each([
    // what a browser answers for a colour written in oklch() and mixed in sRGB
    ['color(srgb 0.0588235 0.0901961 0.168627)', 'rgb(15, 23, 43)'],
    ['color(srgb 1 1 1)', 'rgb(255, 255, 255)'],
    ['color(srgb 0 0 0)', 'rgb(0, 0, 0)'],
    ['color(srgb 0.0588235 0.0901961 0.168627 / 0.5)', 'rgba(15, 23, 43, 0.5)'],
    ['color(srgb 1 0 0 / 25%)', 'rgba(255, 0, 0, 0.25)'],
    ['color(srgb 50% 0% 100%)', 'rgb(128, 0, 255)'],
    // a low alpha is kept as it is (a canvas pixel rounds it to 0.012 or 0.016)
    ['color(srgb 0.2 0.4 0.6 / 0.0137)', 'rgba(51, 102, 153, 0.014)'],
    ['color(srgb 0.2 0.4 0.6 / 0)', 'rgba(51, 102, 153, 0)'],
  ])('reads %s', (computed, expected) => {
    expect(parseCssColor(computed)).toBe(expected)
  })

  it('clamps a colour outside the sRGB gamut, which a mix of an oklch() colour can be', () => {
    expect(parseCssColor('color(srgb -0.02 0.5 1.03)')).toBe('rgb(0, 128, 255)')
    expect(parseCssColor('color(srgb 0.5 0.5 0.5 / 1.5)')).toBe('rgb(128, 128, 128)')
  })

  it.each(['', 'oklch(0.2 0.04 266)', 'color(display-p3 1 0 0)', 'color(srgb 1 0)', 'color(srgb 1 0 x)', 'rgb(1, 2)', 'rgb(1, 2, 3, 4, 5)', 'red', 'color(srgb %  0 0)'])('answers nothing for %j, so that a chart gets no colour', (computed) => {
    expect(parseCssColor(computed)).toBe('')
  })
})

describe('withAlpha', () => {
  it('writes an rgb() colour at an alpha', () => {
    expect(withAlpha('rgb(55, 65, 81)', 0.08)).toBe('rgba(55, 65, 81, 0.08)')
    expect(withAlpha('rgba(244, 244, 245, 0.5)', 0.2)).toBe('rgba(244, 244, 245, 0.2)')
  })

  it('leaves what it cannot read as it is', () => {
    expect(withAlpha('', 0.5)).toBe('')
    expect(withAlpha('oklch(0.5 0.1 100)', 0.5)).toBe('oklch(0.5 0.1 100)')
  })
})

describe('the tokens in main.css', () => {
  // without its comments, which name the properties and say what they are for
  const css = readFileSync(fileURLToPath(new URL('../../app/assets/css/main.css', import.meta.url)), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '')
  // every declaration of a chart token, with the at-rule it is in, if any
  const declarations = [...css.matchAll(/(--app-chart-[a-z-]+):([^;]+);/g)].map(match => ({
    property: match[1]!,
    value: match[2]!.trim(),
  }))

  it.each(Object.entries(CHART_TOKENS))('%s is declared once, from a Nuxt UI token (or the focus ring)', (_key, property) => {
    const own = declarations.filter(declaration => declaration.property === property)
    // once: a second declaration, for `.dark`, `:root.dark`, `html.dark` or a media query, would be a second place
    expect(own, property).toHaveLength(1)
    expect(own[0]!.value, property).toMatch(/^var\(--(ui|app-focus)-[a-z0-9-]+\)$/)
  })

  it('declares them on :root and on .light and .dark, which Nuxt UI\'s tokens switch on, and in no media query', () => {
    expect(/([^{}]+)\{[^{}]*--app-chart-paper:/.exec(css)?.[1]?.replace(/\s+/g, '')).toBe(':root,.light,.dark')
    // a media query (prefers-color-scheme, print) with a rule of its own inside
    const queries = css.match(/@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/g) ?? []
    expect(queries.filter(query => query.includes('--app-chart-'))).toEqual([])
  })

  it('lists every property of the theme and no other', () => {
    expect(declarations.map(declaration => declaration.property).sort()).toEqual(Object.values(CHART_TOKENS).sort())
  })
})

// The text that names a series is held to 4.5:1 on the paper (WCAG 1.4.3, GH-3618). The paper is the page's:
// white, and slate-900 (#0f172b, `--ui-bg` of the dark mode, as button-contrast.test.ts has it);
// tests/e2e/chart-theme.spec.ts holds the drawn charts.
describe('the colours of the text that names a series', () => {
  // the paper of a chart is the card it stands on (--ui-bg): white, and the logo's night blue
  const PAPER = { light: '#ffffff', dark: '#12233f' }
  const luminance = (hex: string) => {
    const [r, g, b] = [1, 3, 5].map(i => Number.parseInt(hex.slice(i, i + 2), 16) / 255).map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
    return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
  }
  const contrast = (a: string, b: string) => {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
    return (hi! + 0.05) / (lo! + 0.05)
  }

  it.each(Object.keys(SERIES_LABEL) as (keyof typeof SERIES_LABEL)[])('read on the light and the dark paper for %s', (series) => {
    expect(contrast(seriesLabelColor(series, false), PAPER.light)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(seriesLabelColor(series, true), PAPER.dark)).toBeGreaterThanOrEqual(4.5)
  })

  it('are the series\' own hue: the dark paper keeps the colour of the line, the light one is a darker step of it', () => {
    expect(SERIES_LABEL.cyan.dark).toBe('#06b6d4')
    expect(SERIES_LABEL.lime.dark).toBe('#84cc16')
    for (const { light, dark } of Object.values(SERIES_LABEL))
      expect(luminance(light)).toBeLessThan(luminance(dark))
  })
})
