// The colours around the data of a chart (its paper and plot, text, grid and axis lines), taken from the
// app's CSS tokens for the colour scheme in force, so that a chart follows light and dark like the page
// and a redesign changes `--app-chart-*` in main.css alone. The series and the stripes' palette are data
// and stay each chart's own.
//
// The charts take hex, rgb(), hsl() and named colours, not the oklch() and color-mix() the tokens are
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
} as const

export type ChartColor = keyof typeof CHART_TOKENS

/** The chart's colours as rgb() strings, an empty one where the token is not set; and whether the page is dark */
export type ChartTheme = Record<ChartColor, string> & { dark: boolean }

/** A theme with no colours set: a chart drawn from it sets no colour (server side, or no stylesheet) */
export const EMPTY_CHART_THEME: ChartTheme = {
  ...(Object.fromEntries(Object.keys(CHART_TOKENS).map(key => [key, ''])) as Record<ChartColor, string>),
  dark: false,
}

/** Reads the theme: `read` answers the value of a custom property, `resolve` turns a CSS colour into one the charts parse */
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
 * does not know it, so that a chart is given no colour rather than one it cannot parse.
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
 * stripes' availability label): the series' own hue, at 4.5:1 or more on the paper (WCAG 1.4.3, GH-3618), and of the Forecast's icons and
 * panel toggles, which are the series' hue as a mark (GH-3642; `slate` is the cloud cover's, which has no label).
 * The series themselves (their lines, bars and swatches) keep their colours, which are data and need 3:1
 * only. On white the series' colours are 2.0:1 to 3.8:1, so the light ones are the same hues one or two
 * steps darker (Tailwind's 700 for cyan and lime, 600 for blue and red, amber 700 for the gold of the
 * availability line); on the dark paper (the card, #12233f, in the design of GH-3518) they are the series' own
 * colours, 4.8:1 to 8.0:1: cyan, lime and gold as drawn, blue and red a step lighter (the drawn ones are
 * 4.3:1 and 4.2:1 there). Held to the drawn charts by `tests/e2e/chart-theme.spec.ts`.
 */
export const SERIES_LABEL = {
  cyan: { light: '#0e7490', dark: '#06b6d4' },
  lime: { light: '#4d7c0f', dark: '#84cc16' },
  blue: { light: '#2563eb', dark: '#5b9cf8' },
  red: { light: '#dc2626', dark: '#f25b5b' },
  gold: { light: '#b45309', dark: '#daa520' },
  slate: { light: '#475569', dark: '#94a3b8' },
  // the snow panel's (GH-4091): the new snow's bars, which are also this colour (3:1 on the paper: 1.4.11), the snow depth's line and the chance's line
  indigo: { light: '#4f46e5', dark: '#818cf8' },
  teal: { light: '#0f766e', dark: '#2dd4bf' },
  // the thunderstorm band's (GH-4090): its bars, which are also this colour (3:1 on the paper), and the axis that names them
  fuchsia: { light: '#a21caf', dark: '#e879f9' },
} as const

export type SeriesLabel = keyof typeof SERIES_LABEL

/** The share of the label colour in the wash behind a toggle that is on (`panelToggleStyle`), and in its edge */
export const TOGGLE_WASH = 0.1
export const TOGGLE_EDGE = 0.4

/**
 * The style of a panel toggle that is on: the icon in the label `color` of its series, on a wash and in an edge of it
 * (the same colour, mixed with transparent). The icon is a non-text mark that carries the state, 3:1 (WCAG 1.4.11) on
 * the wash; `tests/unit/button-contrast.test.ts` holds that for every series, light and dark.
 */
export function panelToggleStyle(color: string): Record<string, string> {
  const mix = (share: number) => `color-mix(in srgb, ${color} ${share * 100}%, transparent)`
  return { color, backgroundColor: mix(TOGGLE_WASH), borderColor: mix(TOGGLE_EDGE) }
}

/** The colour of the text that names the `series` on a paper that is `dark` or not */
export function seriesLabelColor(series: SeriesLabel, dark: boolean): string {
  return SERIES_LABEL[series][dark ? 'dark' : 'light']
}
