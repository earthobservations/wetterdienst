import type { Layout } from 'plotly.js-basic-dist-min'

// The colours around the data of a Plotly chart (its paper and plot, text, grid and axis lines, hover
// label and modebar), taken from the app's CSS tokens for the colour scheme in force, so that a chart
// follows light and dark like the page and a redesign changes `--app-chart-*` in main.css alone. The
// series and the stripes' palette are data and stay each chart's own.
//
// Plotly parses hex, rgb(), hsl() and named colours, not the oklch() and color-mix() the tokens are
// written in, so a token is resolved to rgb() by the browser's own computed value of a probe element
// (`resolveColor`): no canvas, whose pixels a browser that resists fingerprinting scrambles.

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

/**
 * A computed CSS colour as rgb() (or rgba() with an alpha below 1), clamped to the sRGB gamut, or '' where it
 * is none we read. A browser answers `rgb(15, 23, 43)`, `rgba(...)`, or, for a colour written in another space
 * and mixed in sRGB, `color(srgb 0.06 0.09 0.17)` with an alpha after a slash.
 */
export function parseCssColor(computed: string): string {
  const match = /^(rgba?\(|color\(\s*srgb\s)([^()]*)\)$/i.exec(computed.trim())
  if (!match)
    return ''
  const parts = match[2]!.trim().split(/[\s,/]+/)
  if (parts.length !== 3 && parts.length !== 4)
    return ''
  const srgb = match[1]!.toLowerCase().startsWith('color')
  // a number, or a percentage of `full`, clamped to 0..full; NaN where it is neither
  const read = (part: string, full: number) => {
    const percent = part.endsWith('%')
    const n = Number(percent ? part.slice(0, -1) : part)
    return part === '' || part === '%' || Number.isNaN(n) ? Number.NaN : Math.min(full, Math.max(0, percent ? n * full / 100 : n))
  }
  const [red, green, blue] = parts.slice(0, 3).map(part => Math.round(read(part, srgb ? 1 : 255) * (srgb ? 255 : 1)))
  const alpha = parts[3] === undefined ? 1 : read(parts[3], 1)
  if ([red, green, blue, alpha].some(n => Number.isNaN(n)))
    return ''
  return alpha < 1 ? `rgba(${red}, ${green}, ${blue}, ${Number(alpha.toFixed(3))})` : `rgb(${red}, ${green}, ${blue})`
}

let probe: HTMLElement | undefined

/**
 * A CSS colour in any syntax the browser knows (oklch(), color-mix()) as rgb(), by asking the browser for
 * the computed colour of a hidden element, mixed in sRGB so that it is written in it. '' where the browser
 * does not know it, so that Plotly keeps its own default rather than get a colour it cannot parse.
 */
export function resolveColor(color: string): string {
  if (!probe) {
    probe = document.createElement('span')
    probe.hidden = true
    document.documentElement.appendChild(probe)
  }
  // an assignment the browser cannot parse is ignored, so the colour is reset to see that it was taken
  probe.style.color = ''
  probe.style.color = `color-mix(in srgb, ${color} 100%, transparent)`
  if (!probe.style.color)
    return ''
  return parseCssColor(getComputedStyle(probe).color)
}

/**
 * The theme of the document in the browser: the page is dark where Nuxt's colour mode has put `dark` on <html>.
 * With a `scheme`, the theme of that scheme whatever the page shows: what a saved or printed chart is drawn
 * in. The tokens switch on a `.light` or `.dark` class on any element (main.css), so a probe with the class
 * is asked.
 */
export function readDocumentChartTheme(scheme?: 'light' | 'dark'): ChartTheme {
  const root = document.documentElement
  let element: HTMLElement = root
  if (scheme) {
    element = document.createElement('div')
    element.className = scheme
    element.hidden = true
    root.appendChild(element)
  }
  try {
    const style = getComputedStyle(element)
    return readChartTheme(property => style.getPropertyValue(property), resolveColor, scheme ? scheme === 'dark' : root.classList.contains('dark'))
  }
  finally {
    if (scheme)
      element.remove()
  }
}

/** `color` (an rgb() or rgba()) at `alpha`, for a hairline or a wash drawn from a text colour */
export function withAlpha(color: string, alpha: number): string {
  const match = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/.exec(color)
  return match ? `rgba(${match[1]}, ${match[2]}, ${match[3]}, ${alpha})` : color
}

/**
 * The colours of the text that names a series (a y axis' title and tick labels, the weekend's day label, the
 * stripes' availability label): the series' own hue, at 4.5:1 or more on the paper (WCAG 1.4.3, GH-3618).
 * The series themselves (their lines, bars and swatches) keep their colours, which are data and need 3:1
 * only. On white the series' colours are 2.0:1 to 3.8:1, so the light ones are the same hues one or two
 * steps darker (Tailwind's 700 for cyan and lime, 600 for blue and red, amber 700 for the gold of the
 * availability line); on the dark paper they are the series' own colours, 4.7:1 to 9.0:1. Held to the
 * drawn charts by `tests/e2e/chart-theme.spec.ts`.
 */
export const SERIES_LABEL = {
  cyan: { light: '#0e7490', dark: '#06b6d4' },
  lime: { light: '#4d7c0f', dark: '#84cc16' },
  blue: { light: '#2563eb', dark: '#3b82f6' },
  red: { light: '#dc2626', dark: '#ef4444' },
  gold: { light: '#b45309', dark: '#daa520' },
} as const

export type SeriesLabel = keyof typeof SERIES_LABEL

/** The colour of the text that names the `series` on a paper that is `dark` or not */
export function seriesLabelColor(series: SeriesLabel, dark: boolean): string {
  return SERIES_LABEL[series][dark ? 'dark' : 'light']
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

/** `over` laid over `base`, objects merged key by key and anything else (a string, a number, an array) replaced */
export function mergeLayouts<L extends object>(base: L, over: object): L {
  const merged: Record<string, unknown> = { ...(base as Record<string, unknown>) }
  for (const [key, value] of Object.entries(over)) {
    const current = merged[key]
    merged[key] = isObject(current) && isObject(value) ? mergeLayouts(current, value) : value
  }
  return merged as L
}

/**
 * `layout` with the chrome of `theme` under it: what the chart sets itself (a font size, an axis it
 * hides) wins, what it leaves open is the theme's. The axes of the layout, and `xaxis` and `yaxis`, are themed.
 */
export function themedLayout<L extends object>(layout: L, theme: ChartTheme): L {
  const axisNames = [...new Set(['xaxis', 'yaxis', ...Object.keys(layout).filter(key => AXIS.test(key))])]
  return mergeLayouts(chartThemeLayout(theme, axisNames), layout) as L
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

/** Gives a drawn chart the chrome of `theme` without drawing it again, so that its zoom stays; false where there was no chart to */
export async function restyleChart(plotly: { relayout: (element: any, update: any) => Promise<unknown> }, element: unknown, theme: ChartTheme): Promise<boolean> {
  const axisNames = drawnAxisNames(element)
  // a chart not drawn (yet) is drawn in the theme of the moment it is
  if (axisNames.length === 0)
    return false
  await plotly.relayout(element, chartThemeRelayout(theme, axisNames))
  return true
}
