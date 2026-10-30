import type { Layout } from 'plotly.js-basic-dist-min'

// The colours around the data of a Plotly chart (its paper and plot, text, grid and axis lines, hover
// label and modebar), taken from the app's CSS tokens for the colour scheme in force, so that a chart
// follows light and dark like the page and a redesign changes `--app-chart-*` in main.css alone. The
// series and the stripes' palette are data and stay each chart's own.
//
// Plotly parses hex, rgb(), hsl() and named colours, not the oklch() and color-mix() the tokens are
// written in, so a token is resolved to rgb() through a canvas pixel (`resolveColor`).

/** The theme's colours and the CSS custom property each is read from */
export const CHART_TOKENS = {
  paper: '--app-chart-paper',
  plot: '--app-chart-plot',
  text: '--app-chart-text',
  textStrong: '--app-chart-text-strong',
  textMuted: '--app-chart-text-muted',
  grid: '--app-chart-grid',
  axis: '--app-chart-axis',
  zeroline: '--app-chart-zeroline',
  hoverBg: '--app-chart-hover-bg',
  hoverBorder: '--app-chart-hover-border',
  hoverText: '--app-chart-hover-text',
  modebar: '--app-chart-modebar',
  modebarActive: '--app-chart-modebar-active',
} as const

export type ChartColor = keyof typeof CHART_TOKENS

/** The chart's colours as rgb() strings, an empty one where the token is not set; and whether the page is dark */
export type ChartTheme = Record<ChartColor, string> & { dark: boolean }

/** A theme with no colours set: a layout made of it leaves Plotly's defaults alone (server side, or no stylesheet) */
export const EMPTY_CHART_THEME: ChartTheme = {
  ...(Object.fromEntries(Object.keys(CHART_TOKENS).map(key => [key, ''])) as Record<ChartColor, string>),
  dark: false,
}

/** Reads the theme: `read` answers the value of a custom property, `resolve` turns a CSS colour into one Plotly parses */
export function readChartTheme(read: (property: string) => string, resolve: (color: string) => string, dark: boolean): ChartTheme {
  const theme = { ...EMPTY_CHART_THEME, dark }
  for (const key of Object.keys(CHART_TOKENS) as ChartColor[]) {
    const value = read(CHART_TOKENS[key]).trim()
    theme[key] = value ? resolve(value) : ''
  }
  return theme
}

let probe: CanvasRenderingContext2D | null | undefined

/** A CSS colour in any syntax the browser knows (oklch(), color-mix(), var() resolved) as rgb(), by drawing it; unchanged where it is no colour */
export function resolveColor(color: string): string {
  if (probe === undefined) {
    try {
      probe = document.createElement('canvas').getContext('2d', { willReadFrequently: true })
    }
    catch {
      probe = null
    }
  }
  if (!probe)
    return color
  // an assignment the canvas cannot parse is ignored, so a colour is valid if the two probes agree
  probe.fillStyle = '#000'
  probe.fillStyle = color
  const onBlack = probe.fillStyle
  probe.fillStyle = '#fff'
  probe.fillStyle = color
  if (onBlack !== probe.fillStyle)
    return color
  probe.clearRect(0, 0, 1, 1)
  probe.fillRect(0, 0, 1, 1)
  const [r, g, b, a] = probe.getImageData(0, 0, 1, 1).data
  return a === 255 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${Number((a! / 255).toFixed(3))})`
}

/** The theme of the document in the browser: the page is dark where Nuxt's colour mode has put `dark` on <html> */
export function readDocumentChartTheme(): ChartTheme {
  const root = document.documentElement
  const style = getComputedStyle(root)
  return readChartTheme(property => style.getPropertyValue(property), resolveColor, root.classList.contains('dark'))
}

/** `color` (an rgb() or rgba()) at `alpha`, for a hairline or a wash drawn from a text colour */
export function withAlpha(color: string, alpha: number): string {
  const match = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/.exec(color)
  return match ? `rgba(${match[1]}, ${match[2]}, ${match[3]}, ${alpha})` : color
}

/** Transparent, for what lies on the paper (a legend, the modebar) and so follows it */
export const TRANSPARENT = 'rgba(0, 0, 0, 0)'

// the colours that are set, nested objects included, so that a key without one is left out and Plotly's default stays
function defined<T extends Record<string, unknown>>(values: T): Partial<T> {
  const kept: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(values)) {
    const inner = isObject(value) ? defined(value) : value
    if (inner !== '' && inner !== undefined && !(isObject(inner) && Object.keys(inner).length === 0))
      kept[key] = inner
  }
  return kept as Partial<T>
}

// No `tickcolor`: Plotly draws tick marks for an axis given one, which would add them to charts that
// have none. `linecolor` does the same for the axis line, so a chart that wants no line says
// `showline: false` (the explorer, the stripes), as one that wants it gets the theme's colour.
function axisTheme(theme: ChartTheme) {
  return defined({
    gridcolor: theme.grid,
    linecolor: theme.axis,
    zerolinecolor: theme.zeroline,
    spikecolor: theme.axis,
    tickfont: { color: theme.textMuted },
    title: { font: { color: theme.text } },
  })
}

/**
 * The layout of a chart's chrome in `theme`. Every axis is given by `axisNames` (`xaxis`, `yaxis2`), as
 * Plotly has no layout-wide axis default.
 */
export function chartThemeLayout(theme: ChartTheme, axisNames: string[] = ['xaxis', 'yaxis']): Partial<Layout> {
  const layout: Record<string, unknown> = defined({
    paper_bgcolor: theme.paper,
    plot_bgcolor: theme.plot,
    font: defined({ color: theme.text }),
    legend: defined({ font: defined({ color: theme.text }), bgcolor: theme.paper ? TRANSPARENT : '', bordercolor: theme.paper ? TRANSPARENT : '' }),
    hoverlabel: defined({ bgcolor: theme.hoverBg, bordercolor: theme.hoverBorder, font: defined({ color: theme.hoverText }) }),
    modebar: defined({ bgcolor: theme.paper ? TRANSPARENT : '', color: theme.modebar, activecolor: theme.modebarActive }),
  })
  for (const name of axisNames)
    layout[name] = axisTheme(theme)
  return defined(layout) as Partial<Layout>
}

const AXIS = /^[xy]axis\d*$/

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function mergeDeep(base: Record<string, unknown>, over: Record<string, unknown>): Record<string, unknown> {
  const merged: Record<string, unknown> = { ...base }
  for (const [key, value] of Object.entries(over)) {
    const current = merged[key]
    // a title written as a string is the text of one
    const left = key === 'title' && typeof current === 'string' ? { text: current } : current
    const right = key === 'title' && typeof value === 'string' ? { text: value } : value
    merged[key] = isObject(left) && isObject(right) ? mergeDeep(left, right) : right
  }
  return merged
}

/**
 * `layout` with the chrome of `theme` under it: what the chart sets itself (a font size, an axis it
 * hides) wins, what it leaves open is the theme's. The axes of the layout, and `xaxis` and `yaxis`, are themed.
 */
export function themedLayout<L extends object>(layout: L, theme: ChartTheme): L {
  const axisNames = [...new Set(['xaxis', 'yaxis', ...Object.keys(layout).filter(key => AXIS.test(key))])]
  return mergeDeep(chartThemeLayout(theme, axisNames) as Record<string, unknown>, layout as Record<string, unknown>) as L
}

function flatten(prefix: string, value: unknown, into: Record<string, string>) {
  if (isObject(value)) {
    for (const [key, inner] of Object.entries(value))
      flatten(`${prefix}.${key}`, inner, into)
  }
  else if (typeof value === 'string') {
    into[prefix] = value
  }
}

/**
 * The same chrome as flat attribute paths (`xaxis.gridcolor`) for `Plotly.relayout`, which sets each
 * path alone, where a nested object would replace an axis with its range and type.
 */
export function chartThemeRelayout(theme: ChartTheme, axisNames: string[] = ['xaxis', 'yaxis']): Record<string, string> {
  const update: Record<string, string> = {}
  for (const [key, value] of Object.entries(chartThemeLayout(theme, axisNames)))
    flatten(key, value, update)
  return update
}

/** The axes a drawn chart has (`xaxis`, `yaxis`, `yaxis2`), read from Plotly's layout of the element */
export function drawnAxisNames(element: unknown): string[] {
  const full = (element as { _fullLayout?: Record<string, unknown> } | null)?._fullLayout
  return full ? Object.keys(full).filter(key => AXIS.test(key)) : []
}

/** Gives a drawn chart the chrome of `theme` without drawing it again, so that its zoom stays */
export async function restyleChart(plotly: { relayout: (element: any, update: any) => Promise<unknown> }, element: unknown, theme: ChartTheme) {
  const axisNames = drawnAxisNames(element)
  // a chart not drawn (yet) is drawn in the theme of the moment it is
  if (axisNames.length === 0)
    return
  await plotly.relayout(element, chartThemeRelayout(theme, axisNames))
}
