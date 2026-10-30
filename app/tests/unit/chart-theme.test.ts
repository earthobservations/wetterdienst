import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { CHART_TOKENS, chartThemeLayout, chartThemeRelayout, drawnAxisNames, EMPTY_CHART_THEME, readChartTheme, restyleChart, themedLayout, withAlpha } from '../../app/utils/chart-theme'

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
    '--app-chart-hover-bg': 'oklch(0.97 0.01 248)',
    '--app-chart-hover-border': 'oklch(0.87 0.02 253)',
    '--app-chart-hover-text': 'oklch(0.37 0.04 257)',
    '--app-chart-modebar': 'oklch(0.52 0.04 257)',
    '--app-chart-modebar-active': 'oklch(0.5 0.15 150)',
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
    '--app-chart-hover-bg': 'oklch(0.28 0.04 260)',
    '--app-chart-hover-border': 'oklch(0.37 0.04 257)',
    '--app-chart-hover-text': 'oklch(0.93 0.01 256)',
    '--app-chart-modebar': 'oklch(0.71 0.04 257)',
    '--app-chart-modebar-active': 'oklch(0.8 0.2 150)',
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
    for (const key of ['paper', 'plot', 'text', 'textMuted', 'grid', 'axis', 'hoverBg'] as const)
      expect(dark[key], key).not.toBe(light[key])
  })
})

describe('chartThemeLayout', () => {
  it.each(['light', 'dark'] as const)('maps the %s theme onto the chrome of the layout', (scheme) => {
    const theme = themeOf(scheme)
    const layout = chartThemeLayout(theme, ['xaxis', 'yaxis', 'yaxis2']) as Record<string, any>
    expect(layout.paper_bgcolor).toBe(theme.paper)
    expect(layout.plot_bgcolor).toBe(theme.plot)
    expect(layout.font.color).toBe(theme.text)
    expect(layout.legend.font.color).toBe(theme.text)
    // a legend and the modebar lie on the paper and follow it
    expect(layout.legend.bgcolor).toBe('rgba(0, 0, 0, 0)')
    expect(layout.modebar).toEqual({ bgcolor: 'rgba(0, 0, 0, 0)', color: theme.modebar, activecolor: theme.modebarActive })
    expect(layout.hoverlabel).toEqual({ bgcolor: theme.hoverBg, bordercolor: theme.hoverBorder, font: { color: theme.hoverText } })
    for (const axis of ['xaxis', 'yaxis', 'yaxis2']) {
      expect(layout[axis].gridcolor).toBe(theme.grid)
      expect(layout[axis].linecolor).toBe(theme.axis)
      expect(layout[axis].zerolinecolor).toBe(theme.zeroline)
      expect(layout[axis].spikecolor).toBe(theme.axis)
      // none that makes Plotly draw what the chart does not: tick marks, or an axis line, come with their colour
      expect(layout[axis].tickcolor).toBeUndefined()
      expect(layout[axis].tickfont.color).toBe(theme.textMuted)
      expect(layout[axis].title.font.color).toBe(theme.text)
    }
  })

  it('sets nothing where the theme has no colours, so that Plotly keeps its defaults', () => {
    expect(chartThemeLayout(EMPTY_CHART_THEME)).toEqual({})
    expect(chartThemeRelayout(EMPTY_CHART_THEME)).toEqual({})
  })
})

describe('themedLayout', () => {
  const theme = themeOf('dark')

  it('keeps what the chart sets itself and fills in what it leaves open', () => {
    const themed = themedLayout({
      margin: { l: 60 },
      font: { family: 'Arial', size: 14, color: 'rgb(1, 2, 3)' },
      xaxis: { type: 'date', range: [0, 1], gridcolor: 'rgb(9, 9, 9)' },
      yaxis3: { zeroline: true },
    } as any, theme) as Record<string, any>
    expect(themed.margin).toEqual({ l: 60 })
    expect(themed.font).toEqual({ family: 'Arial', size: 14, color: 'rgb(1, 2, 3)' })
    expect(themed.xaxis).toMatchObject({ type: 'date', range: [0, 1], gridcolor: 'rgb(9, 9, 9)', linecolor: theme.axis })
    // an axis of the layout is themed, not only x and y
    expect(themed.yaxis3).toMatchObject({ zeroline: true, gridcolor: theme.grid })
    expect(themed.yaxis).toMatchObject({ gridcolor: theme.grid })
    expect(themed.paper_bgcolor).toBe(theme.paper)
  })

  it('turns an axis title written as a string into the text of one, to give it a colour', () => {
    const themed = themedLayout({ xaxis: { title: 'Date' } } as any, theme) as Record<string, any>
    expect(themed.xaxis.title).toEqual({ text: 'Date', font: { color: theme.text } })
  })

  it('does not change the layout it is given', () => {
    const layout = { xaxis: { title: 'Date' } }
    themedLayout(layout as any, theme)
    expect(layout).toEqual({ xaxis: { title: 'Date' } })
  })
})

describe('chartThemeRelayout', () => {
  it('is the same chrome as flat attribute paths, which Plotly sets one by one', () => {
    const theme = themeOf('light')
    const update = chartThemeRelayout(theme, ['xaxis', 'yaxis2'])
    expect(update).toMatchObject({
      'paper_bgcolor': theme.paper,
      'plot_bgcolor': theme.plot,
      'font.color': theme.text,
      'xaxis.gridcolor': theme.grid,
      'xaxis.tickfont.color': theme.textMuted,
      'yaxis2.title.font.color': theme.text,
      'hoverlabel.bgcolor': theme.hoverBg,
      'hoverlabel.font.color': theme.hoverText,
      'modebar.color': theme.modebar,
    })
    // a path, never an object that would replace an axis with its range and type
    expect(Object.values(update).every(value => typeof value === 'string')).toBe(true)
  })

  it('restyles the axes a chart has drawn, and nothing of a chart not drawn', async () => {
    const calls: unknown[][] = []
    const plotly = { relayout: async (...args: unknown[]) => void calls.push(args) }
    const drawn = { _fullLayout: { xaxis: {}, yaxis: {}, yaxis2: {}, margin: {}, xaxis_not: {} } }
    expect(drawnAxisNames(drawn)).toEqual(['xaxis', 'yaxis', 'yaxis2'])
    await restyleChart(plotly, drawn, themeOf('dark'))
    await restyleChart(plotly, {}, themeOf('dark'))
    await restyleChart(plotly, null, themeOf('dark'))
    expect(calls).toHaveLength(1)
    expect(calls[0]![0]).toBe(drawn)
    expect(calls[0]![1]).toHaveProperty(['yaxis2.gridcolor'], themeOf('dark').grid)
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
  const css = readFileSync(fileURLToPath(new URL('../../app/assets/css/main.css', import.meta.url)), 'utf-8')

  it.each(Object.entries(CHART_TOKENS))('%s is set from a Nuxt UI token (or the focus ring) on :root', (_key, property) => {
    const value = new RegExp(`${property}:\\s*var\\((--[a-z-]+)\\)`).exec(css)?.[1]
    expect(value, property).toMatch(/^--(ui|app-focus)-/)
  })

  it('does not redefine any of them for .dark: the Nuxt UI tokens they are made of switch by themselves', () => {
    const dark = [...css.matchAll(/\.dark\s*\{([^}]*)\}/g)].map(match => match[1]).join('\n')
    expect(dark).not.toContain('--app-chart-')
  })

  it('has no hex colour for the chart chrome: a redesign changes one place', () => {
    const block = [...css.matchAll(/--app-chart-[a-z-]+:([^;]+);/g)].map(match => match[1])
    expect(block.length).toBe(Object.keys(CHART_TOKENS).length)
    expect(block.some(value => /#[0-9a-f]{3,8}\b/i.test(value!))).toBe(false)
  })
})
