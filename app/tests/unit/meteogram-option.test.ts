import type { OptionInput } from '../../app/utils/meteogram-option'
import * as SunCalc from 'suncalc'
import { describe, expect, it } from 'vitest'
import { EMPTY_CHART_THEME } from '../../app/utils/chart-theme'
import { loadEcharts } from '../../app/utils/echarts-loader'
import { hourFormatter } from '../../app/utils/format'
import { chartLayout, defaultWindow, GUTTER_RIGHT, HOUR_MS, plotWidthFor } from '../../app/utils/meteogram-geometry'
import { buildMeteogramModel } from '../../app/utils/meteogram-model'
import { bandColour, buildMeteogramOption, clampSpan, gutterLeftFor } from '../../app/utils/meteogram-option'
import { buildSeries } from '../../app/utils/meteogram-series'
import { meteogramUnits } from '../../app/utils/meteogram-units'
import { FORECAST_UNITS, forecastValues } from '../helpers/meteogram-forecast'

const echarts = loadEcharts()
const t = (key: string, named?: Record<string, unknown>) => key + (named?.unit ? ` ${named.unit}` : '')

const LIGHT = { ...EMPTY_CHART_THEME, text: 'rgb(15, 23, 43)', textStrong: 'rgb(0, 0, 0)', textMuted: 'rgb(90, 100, 120)', zeroline: 'rgb(90, 100, 120)' }
const DARK = { ...LIGHT, dark: true, text: 'rgb(226, 232, 240)', textStrong: 'rgb(255, 255, 255)' }

function build(options: { width?: number, hours?: number, theme?: typeof LIGHT, window?: { start: number, end: number }, now?: number | null, without?: string[] } = {}) {
  const { width = 800, hours = 240, theme = LIGHT, now = null, without = [] } = options
  const model = buildMeteogramModel({
    series: buildSeries(forecastValues({ hours, without }) as any),
    panels: { temp: true, wind: true, precip: true, cloud: true, pressure: true },
    horizonHours: null,
    zone: 'Europe/Berlin',
    language: 'en-GB',
    coords: { latitude: 52.5, longitude: 13.4 },
    sun: SunCalc as any,
    units: meteogramUnits(FORECAST_UNITS, t),
    t,
  })!
  const layout = chartLayout(model.panels, model.symbols.length > 0)
  const gutterLeft = gutterLeftFor(model)
  const plotPx = plotWidthFor(width, (model.maxTime - model.minTime) / HOUR_MS, gutterLeft)
  const window = options.window ?? defaultWindow({ start: model.minTime, end: model.maxTime }, plotPx)
  const input: OptionInput = {
    model,
    theme,
    layout,
    outerPx: plotPx + gutterLeft + GUTTER_RIGHT,
    plotPx,
    gutterLeft,
    window,
    now,
    fontFamily: 'sans-serif',
    locale: 'en',
    hourLabel: hourFormatter('en-GB', 'Europe/Berlin'),
    symbolUrl: (symbol, dark) => `/s/${dark ? 'd' : 'l'}/${symbol}.svg`,
  }
  const option = buildMeteogramOption(input)
  return { model, layout, option: option as any, input }
}

/** The option drawn to an SVG string in a document-less chart */
function draw(built: ReturnType<typeof build>) {
  const chart = echarts.init(null as any, null, { renderer: 'svg', ssr: true, width: built.input.outerPx, height: built.layout.height })
  chart.setOption(built.option)
  const svg = chart.renderToSVGString()
  chart.dispose()
  return svg
}
const texts = (svg: string) => [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(match => match[1]!.replaceAll('&amp;', '&'))
const count = (svg: string, pattern: RegExp) => (svg.match(pattern) ?? []).length

describe('the option', () => {
  it('has a grid for the header and one for each panel, at the fixed heights, whatever the width', () => {
    for (const width of [320, 800, 1400]) {
      const { option, layout } = build({ width })
      expect(option.grid).toHaveLength(6)
      expect(option.grid.map((g: any) => g.height)).toEqual([layout.header.height, 124, 88, 80, 156, 84])
    }
  })

  it('links every x axis in one zoom, on the window it is given', () => {
    const window = { start: Date.UTC(2026, 9, 2), end: Date.UTC(2026, 9, 3) }
    const { option } = build({ window })
    expect(option.dataZoom).toHaveLength(1)
    expect(option.dataZoom[0]).toMatchObject({ type: 'inside', xAxisIndex: [0, 1, 2, 3, 4, 5], startValue: window.start, endValue: window.end, filterMode: 'none' })
    for (const axis of option.xAxis)
      expect(axis).toMatchObject({ type: 'value', min: build().model.minTime, max: build().model.maxTime })
  })

  it('zooms by a pinch and Ctrl with the wheel, and not by the wheel alone or a drag, which are the page\'s and the scroll\'s', () => {
    const zoom = build().option.dataZoom[0]
    expect(zoom).toMatchObject({ zoomOnMouseWheel: 'ctrl', moveOnMouseMove: false, moveOnMouseWheel: false })
    // no closer than six hours, no further than the forecast
    expect(zoom.minValueSpan).toBe(6 * HOUR_MS)
  })

  it('has the axes of the panels over their ranges, the label colours of the series\' text', () => {
    const { option, model } = build()
    const [, wind, precip, , temp] = option.yAxis
    expect([wind.min, wind.max]).toEqual(model.axes.wind!.range)
    expect([precip.min, precip.max]).toEqual(model.axes.precip!.range)
    expect(temp.axisLabel.color).toBe('#dc2626')
    expect(wind.axisLabel.color).toBe('#0e7490')
    // the clouds' labels are the muted text
    expect(option.yAxis[3].axisLabel.color).toBe(LIGHT.textMuted)
    // and the dark scheme has the lighter ones
    expect(build({ theme: DARK }).option.yAxis[4].axisLabel.color).toBe('#f25b5b')
  })

  it('writes the labels with the language\'s separator and without a decimal where there is none to write', () => {
    const { option } = build()
    expect(option.yAxis[1].axisLabel.formatter(5)).toBe('5')
    expect(option.yAxis[1].axisLabel.formatter(2.5)).toBe('2.5')
    expect(option.yAxis[4].axisLabel.formatter(1013)).toBe('1,013')
  })

  it('has no animation, which a visitor who asked for less motion has nothing to switch off of, and every series is silent', () => {
    const { option } = build()
    expect(option.animation).toBe(false)
    expect(option.series.every((s: any) => s.animation === false || s.animation === undefined)).toBe(true)
    expect(option.series.every((s: any) => s.silent)).toBe(true)
  })

  it('has the smooth lines and the held steps, a stack of bars, and the custom series that the library has no kind for', () => {
    const { option } = build()
    const byId = (id: string) => option.series.find((s: any) => s.id === id)
    expect(byId('temp')).toMatchObject({ type: 'line', smooth: 0.4, smoothMonotone: 'x', step: false })
    expect(byId('tempMax')).toMatchObject({ type: 'line', step: 'start', lineStyle: { type: 'dashed' } })
    expect(byId('rain')).toMatchObject({ type: 'bar', stack: 'precipitation' })
    expect(byId('mixed')).toMatchObject({ type: 'bar', stack: 'precipitation' })
    for (const id of ['barbs', 'day-names', 'hours', 'symbols', 'backdrop-wind', 'backdrop-temp'])
      expect(byId(id), id).toMatchObject({ type: 'custom' })
    // each series in the grid of its panel
    expect(byId('temp').xAxisIndex).toBe(4)
    expect(byId('barbs').xAxisIndex).toBe(1)
    expect(byId('pressure').xAxisIndex).toBe(5)
  })

  it('has the lines in the colours of the scheme', () => {
    const light = build().option.series.find((s: any) => s.id === 'tempMax')
    const dark = build({ theme: DARK }).option.series.find((s: any) => s.id === 'tempMax')
    expect(light.lineStyle.color).toBe('#b91c1c')
    expect(dark.lineStyle.color).toBe('#fca5a5')
  })

  it('has a gutter that grows by a line where an axis title is broken in two', () => {
    const { model } = build()
    expect(gutterLeftFor({ ...model, axes: { wind: { ...model.axes.wind!, titleLines: 1 } } })).toBe(68)
    expect(gutterLeftFor({ ...model, axes: { wind: { ...model.axes.wind!, titleLines: 2 } } })).toBe(84)
  })

  it('has no symbols\' series where the forecast has none to draw them from', () => {
    const { option } = build({ without: ['weather_significant', 'cloud_cover_total', 'cloud_cover_below_2km', 'cloud_cover_between_2km_and_7km', 'cloud_cover_above_7km', 'precipitation_amount_significant_weather_last_1h'] })
    expect(option.series.some((s: any) => s.id === 'symbols')).toBe(false)
  })
})

describe('the bands', () => {
  it('cuts a span to the plot, and is none where it lies outside', () => {
    expect(clampSpan(-10, 50, 0, 100)).toEqual([0, 50])
    expect(clampSpan(80, 150, 0, 100)).toEqual([80, 100])
    expect(clampSpan(150, 200, 0, 100)).toBeNull()
    expect(clampSpan(-20, -5, 0, 100)).toBeNull()
    // a span given backwards is the same span
    expect(clampSpan(50, -10, 0, 100)).toEqual([0, 50])
  })

  it('fades the daylight by the cloud, and is a dim yellow on the dark page', () => {
    expect(bandColour(0, false)).toBe('rgba(253,244,180,0.550)')
    expect(bandColour(1, false)).toBe('rgba(253,244,180,0.200)')
    expect(bandColour(0, true)).toBe('rgba(250,204,21,0.083)')
  })
})

describe('the chart drawn', () => {
  it('names the days, the weekend among them, and the hours on the clock of the station', () => {
    const svg = draw(build())
    const all = texts(svg)
    expect(all).toContain('Thu 01/10')
    expect(all).toContain('Fri 02/10')
    // the window is the first 72 hours at 10 px an hour: a label every 6 hours, at the station's hours
    expect(all).toContain('06:00')
    expect(all).toContain('18:00')
    expect(all).not.toContain('07:00')
  })

  it('draws the days\' names in the red of the weekend in the colour that reads on the page', () => {
    const svg = draw(build({ window: { start: Date.UTC(2026, 9, 2), end: Date.UTC(2026, 9, 8) } }))
    expect(svg).toMatch(/fill="#dc2626"[^>]*>Sat 03\/10/)
  })

  it('labels the hours as often as there is room: every hour at 60 px an hour, every third at 20 and every sixth at 10', () => {
    const day = Date.UTC(2026, 9, 2)
    // the steps between the hours that are written, which the window's width in hours decides (722 px of plot)
    const steps = (hours: number) => {
      const labels = texts(draw(build({ window: { start: day, end: day + hours * HOUR_MS } }))).filter(text => /^\d{2}:00$/.test(text)).map(text => Number(text.slice(0, 2)))
      expect(labels.length, `${hours} h`).toBeGreaterThan(2)
      return [...new Set(labels.slice(1).map((hour, i) => (hour - labels[i]! + 24) % 24))]
    }
    expect(steps(12)).toEqual([1])
    expect(steps(36)).toEqual([3])
    expect(steps(72)).toEqual([6])
  })

  it('draws the wind barbs in the plot: pennants for the strong wind, none outside the window', () => {
    const svg = draw(build())
    // the wind of the fixture stays under 25 knots: barbs are lines, and a pennant is a polygon
    expect(count(svg, /<polygon/g)).toBe(0)
    const strong = build()
    // a barb at 60 knots, in the first hours, has a pennant
    for (const row of strong.option.series.find((s: any) => s.id === 'barbs').data.slice(0, 40))
      row[3] = 60
    expect(count(draw(strong), /<polygon/g)).toBeGreaterThan(0)
  })

  it('thins the barbs and the symbols to the room, and draws more of them zoomed in', () => {
    const wide = draw(build())
    const day = Date.UTC(2026, 9, 2)
    const near = draw(build({ window: { start: day, end: day + 12 * HOUR_MS } }))
    // at 10 px an hour a symbol is drawn every fourth hour in the window of 72 hours; at 60 px every hour of the twelve
    expect(count(wide, /<image/g)).toBeLessThanOrEqual(21)
    expect(count(wide, /<image/g)).toBeGreaterThanOrEqual(17)
    expect(count(near, /<image/g)).toBeGreaterThanOrEqual(10)
    expect(count(near, /<image/g)).toBeLessThanOrEqual(16)
  })

  it('points the symbols at the files of the mode of the page', () => {
    const light = draw(build())
    expect(light).toMatch(/href="\/s\/l\/\d+[dn]?\.svg"/)
    expect(draw(build({ theme: DARK }))).toMatch(/href="\/s\/d\/\d+[dn]?\.svg"/)
  })

  it('draws the line of now where the forecast spans it, and none where it does not', () => {
    const marked = (now: number) => build({ now }).option.series.find((s: any) => s.id === 'backdrop-wind').data.filter((row: number[]) => row[0] === 2)
    expect(marked(Date.UTC(2026, 9, 1, 12))).toEqual([[2, Date.UTC(2026, 9, 1, 12), 0, 0]])
    expect(marked(Date.UTC(2027, 0, 1))).toEqual([])
    // and it is drawn
    expect(draw(build({ now: Date.UTC(2026, 9, 1, 12) }))).toContain('stroke-width="1.5"')
  })

  it('draws the freezing point as a line of its own in the temperature panel', () => {
    expect(draw(build())).toContain(LIGHT.zeroline)
  })

  it('has every panel start at the same place: a long label does not shrink its grid, which would put its hours out of line', () => {
    // the pressure's labels are the widest ("1,013"), and its title is broken in two
    const built = build()
    const svg = draw(built)
    const starts = new Set([...svg.matchAll(/<path d="M([\d.]+) ([\d.]+)L([\d.]+) ([\d.]+)"/g)].filter(m => m[2] === m[4] && m[1] !== '0').map(m => m[1]))
    expect([...starts]).toEqual([String(built.input.gutterLeft)])
  })

  it('draws the whole of a ten-day forecast in a few tens of milliseconds', () => {
    const built = build()
    const start = performance.now()
    draw(built)
    expect(performance.now() - start).toBeLessThan(2000)
  })
})
