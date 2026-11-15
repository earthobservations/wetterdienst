import type { ExplorerSeries } from '../../app/utils/explorer-model'
import type { ExplorerOptionInput } from '../../app/utils/explorer-option'
import { describe, expect, it } from 'vitest'
import { EMPTY_CHART_THEME } from '../../app/utils/chart-theme'
import { loadEcharts } from '../../app/utils/echarts-loader'
import { boundsOf, seriesColour } from '../../app/utils/explorer-model'
import { buildExplorerOption, cursorUpdate, EXPLORER_FONT_FAMILY, explorerFrame, fitText, hasTimeOfDay, legendLayout, momentLabel, tickLabel, timeAtX, timeTicks, valueFormat, xOfTime } from '../../app/utils/explorer-option'

const echarts = loadEcharts()

const LIGHT = { ...EMPTY_CHART_THEME, text: 'rgb(15, 23, 43)', textMuted: 'rgb(90, 100, 120)', grid: 'rgb(200, 205, 215)', zeroline: 'rgb(90, 100, 120)', paper: 'rgb(255, 255, 255)' }
const DARK = { ...LIGHT, dark: true, text: 'rgb(226, 232, 240)', paper: 'rgb(15, 23, 43)' }

const HOUR = 3_600_000
const DAY = 24 * HOUR
const START = Date.UTC(2026, 8, 1)

function series(id: string, y: (number | null)[], over: Partial<ExplorerSeries> = {}, step = DAY): ExplorerSeries {
  return { id, name: id, colorIndex: 0, kind: 'values', x: y.map((_, i) => START + i * step), y, ...over }
}

// a text measure that needs no canvas: 7 px a character
const measure = (text: string) => text.length * 7

function input(all: ExplorerSeries[], over: Partial<ExplorerOptionInput> = {}): ExplorerOptionInput {
  const bounds = boundsOf(all)!
  return { series: all, hidden: new Set(), theme: LIGHT, window: bounds, bounds, width: 704, height: 400, large: false, locale: 'en', measure, ...over }
}

function build(all: ExplorerSeries[], over: Partial<ExplorerOptionInput> = {}) {
  const i = input(all, over)
  const frame = explorerFrame(i)
  return { input: i, frame, option: buildExplorerOption(i, frame) as any }
}

function svgOf(i: ExplorerOptionInput, option: unknown): string {
  const chart = echarts.init(null as any, null, { renderer: 'svg', ssr: true, width: i.width, height: i.height })
  try {
    chart.setOption(option as any)
    return chart.renderToSVGString()
  }
  finally {
    chart.dispose()
  }
}

const TEMPERATURE = series('00011 - Temperature', [3, 5, 8, 6, 9, 12, 10], { name: '00011 - Temperature' })
const RAIN = series('00011 - Rain', [0, 2, 0, 5, 1, 0, 0], { name: '00011 - Rain', colorIndex: 1 })

describe('the option of the chart', () => {
  it('draws a line for each series, with its colour in the scheme, and markers where the series are few', () => {
    const { option } = build([TEMPERATURE, RAIN])
    const lines = option.series.filter((s: any) => s.type === 'line' && s.id !== 'zero')
    expect(lines.map((s: any) => s.id)).toEqual(['00011 - Temperature', '00011 - Rain'])
    expect(lines[0].lineStyle).toMatchObject({ color: seriesColour(0, false), width: 2 })
    expect(lines[1].lineStyle.color).toBe(seriesColour(1, false))
    expect(lines.every((s: any) => s.showSymbol === true && s.symbolSize === 6)).toBe(true)
    // the dark page has the dark colours of the same hues
    expect(build([TEMPERATURE, RAIN], { theme: DARK }).option.series[1].lineStyle.color).toBe(seriesColour(1, true))
  })

  it('draws a chart of many points as a thin line with no markers', () => {
    const { option } = build([TEMPERATURE], { large: true })
    expect(option.series[0]).toMatchObject({ showSymbol: false, lineStyle: { width: 1 } })
  })

  it('draws a trendline dashed, thick and on top of the values, without markers', () => {
    const trend = series('t', [3, 11], { kind: 'trend', name: 'T (Trendline)', x: [START, START + 6 * DAY] })
    const { option } = build([TEMPERATURE, trend])
    const [values, line] = option.series
    expect(line).toMatchObject({ id: 't', showSymbol: false, lineStyle: { width: 4, type: 'dashed' } })
    expect(line.z).toBeGreaterThan(values.z)
  })

  it('breaks the line where a value is missing, which the library does where it is told not to connect', () => {
    const { option } = build([series('g', [1, 2, null, 4, 5])])
    expect(option.series[0].connectNulls).toBe(false)
    expect(option.series[0].data.map((point: any) => point[1])).toEqual([1, 2, null, 4, 5])
    // and in the drawing: the line is two pieces
    const { input: i } = build([series('g', [1, 2, null, 4, 5])])
    const svg = svgOf(i, build([series('g', [1, 2, null, 4, 5])]).option)
    const line = [...svg.matchAll(/<path[^>]*d="([^"]*)"[^>]*stroke="#3b82f6"/g)].map(match => match[1]!).find(d => d.startsWith('M') && d.includes('L'))!
    // two pieces: one move for each
    expect((line.match(/M/g) ?? []).length).toBe(2)
  })

  it('leaves out the series the legend turned off, and scales the y axis to those that are on', () => {
    const big = series('big', [100, 200, 300])
    const on = build([TEMPERATURE, big])
    const off = build([TEMPERATURE, big], { hidden: new Set(['big']) })
    expect(on.option.series.some((s: any) => s.id === 'big')).toBe(true)
    expect(off.option.series.some((s: any) => s.id === 'big')).toBe(false)
    expect(off.option.yAxis[0].max).toBeLessThan(on.option.yAxis[0].max)
    // it is still in the legend, turned off
    expect(off.frame.legend.items.map(item => item.id)).toEqual(['00011 - Temperature', 'big'])
  })

  it('has a y axis of round numbers that holds every value, and one that follows the window', () => {
    const { option, frame } = build([TEMPERATURE])
    expect(option.yAxis[0]).toMatchObject({ min: 2, max: 12, interval: 2 })
    expect(frame.yLabels).toEqual(['2', '4', '6', '8', '10', '12'])
    const zoomed = build([TEMPERATURE], { window: { start: START + 3 * DAY, end: START + 5 * DAY } })
    // days 2 to 6 are drawn (one point beyond each edge): 8, 6, 9, 12, 10
    expect(zoomed.option.yAxis[0].min).toBeGreaterThanOrEqual(4)
    expect(zoomed.option.yAxis[0].max).toBeLessThanOrEqual(12)
  })

  it('writes the numbers of the axis in the language of the page', () => {
    const small = series('s', [0.1, 0.25, 0.4])
    expect(build([small]).frame.yLabels.join(' ')).toMatch(/0\.\d/)
    expect(build([small], { locale: 'de' }).frame.yLabels.join(' ')).toMatch(/0,\d/)
    expect(valueFormat('de').format(12.3)).toBe('12,3')
    expect(valueFormat('en').format(12.3)).toBe('12.3')
    expect(valueFormat('en').format(12)).toBe('12')
  })

  it('draws the zero line where the axis holds zero and not where it does not', () => {
    expect(build([series('z', [-3, 4, 2])]).option.series.some((s: any) => s.id === 'zero')).toBe(true)
    expect(build([series('p', [1013, 1020, 1030])]).option.series.some((s: any) => s.id === 'zero')).toBe(false)
  })

  it('makes room at the left for the widest label of the axis, and the plot is the rest', () => {
    const narrow = build([series('n', [1, 2, 3])]).frame
    const wide = build([series('w', [100_000, 250_000, 400_000])]).frame
    expect(wide.plot.left).toBeGreaterThan(narrow.plot.left)
    for (const frame of [narrow, wide])
      expect(frame.plot.left + frame.plot.width + 20).toBe(704)
  })

  it('has the time axis in UTC, from the first moment to the last, with Intl labels', () => {
    const { option, input: i } = build([TEMPERATURE])
    expect(option.useUTC).toBe(true)
    expect(option.xAxis[0]).toMatchObject({ type: 'time', min: START, max: START + 6 * DAY })
    const label = option.xAxis[0].axisLabel.formatter(START + 2 * DAY)
    expect(label).toBe('Sep 3')
    expect(i.window).toEqual({ start: START, end: START + 6 * DAY })
  })

  it('zooms with a pinch and Ctrl with the wheel, and a drag is the component\'s box', () => {
    const { option } = build([TEMPERATURE])
    expect(option.dataZoom[0]).toMatchObject({ type: 'inside', filterMode: 'none', zoomOnMouseWheel: 'ctrl', moveOnMouseMove: false, startValue: START, endValue: START + 6 * DAY })
    expect(option.dataZoom[0].minValueSpan).toBe(3 * DAY)
  })

  it('does not animate (prefers-reduced-motion has nothing to switch off), and is the page\'s own paper unless a saved image gives one', () => {
    const { option } = build([TEMPERATURE])
    expect(option.animation).toBe(false)
    expect(option.series.every((s: any) => s.animation === false)).toBe(true)
    expect(option.backgroundColor).toBe('transparent')
    expect(build([TEMPERATURE], { background: 'rgb(255, 255, 255)' }).option.backgroundColor).toBe('rgb(255, 255, 255)')
    expect(option.textStyle.fontFamily).toBe(EXPLORER_FONT_FAMILY)
  })

  it('writes the text in the colours of the theme: the labels in the muted text colour, the grid in the grid colour', () => {
    const { option } = build([TEMPERATURE], { theme: DARK })
    expect(option.xAxis[0].axisLabel.color).toBe(DARK.textMuted)
    expect(option.yAxis[0].axisLabel.color).toBe(DARK.textMuted)
    expect(option.xAxis[0].splitLine.lineStyle.color).toBe(DARK.grid)
  })
})

describe('the drawing', () => {
  it('has the legend, the labels of both axes and a line for each series in the SVG', () => {
    const { input: i, option } = build([TEMPERATURE, RAIN])
    const svg = svgOf(i, option)
    expect(svg).toContain('00011 - Temperature')
    expect(svg).toContain('00011 - Rain')
    expect(svg).toContain('15')
    expect(svg).toContain('Sep')
    expect(svg).toContain(seriesColour(0, false))
    expect(svg).toContain(seriesColour(1, false))
  })

  it('has the paper of a saved image as a background', () => {
    const { input: i, option } = build([TEMPERATURE], { background: 'rgb(255, 255, 255)' })
    expect(svgOf(i, option)).toContain('rgb(255, 255, 255)')
  })

  it('draws the crosshair and a dot for each row where a moment is given, and nothing where it is not', () => {
    const { input: i, option } = build([TEMPERATURE, RAIN])
    const none = svgOf(i, option)
    const chart = echarts.init(null as any, null, { renderer: 'svg', ssr: true, width: i.width, height: i.height })
    try {
      chart.setOption(option)
      chart.setOption(cursorUpdate(LIGHT, START + 2 * DAY, [{ colorIndex: 0, value: 8 }, { colorIndex: 1, value: 0 }]) as any)
      const marked = chart.renderToSVGString()
      expect((marked.match(/<circle/g) ?? []).length).toBeGreaterThan((none.match(/<circle/g) ?? []).length)
      expect(marked.length).toBeGreaterThan(none.length)
      chart.setOption(cursorUpdate(LIGHT, null, []) as any)
      expect(chart.renderToSVGString().length).toBeLessThan(marked.length)
    }
    finally {
      chart.dispose()
    }
  })
})

describe('the legend', () => {
  const names = [{ id: 'a', name: 'Station A' }, { id: 'b', name: 'Station B' }]

  it('puts the items in a row in the middle of the chart where they fit', () => {
    const { items, height } = legendLayout(names, 704, measure)
    expect(items).toHaveLength(2)
    expect(items[0]!.y).toBe(items[1]!.y)
    expect(items[1]!.x).toBeGreaterThan(items[0]!.x + items[0]!.width)
    const left = items[0]!.x
    const right = 704 - (items[1]!.x + items[1]!.width)
    expect(Math.abs(left - right)).toBeLessThan(1)
    expect(height).toBeGreaterThan(0)
  })

  it('wraps into rows on a phone, and the plot gets the rest of the height', () => {
    const many = Array.from({ length: 6 }, (_, i) => ({ id: `s${i}`, name: `00011 - Mean air temperature ${i}` }))
    const narrow = legendLayout(many, 320, measure)
    const wide = legendLayout(many, 1000, measure)
    expect(new Set(narrow.items.map(item => item.y)).size).toBeGreaterThan(new Set(wide.items.map(item => item.y)).size)
    expect(narrow.height).toBeGreaterThan(wide.height)
    for (const item of narrow.items) {
      expect(item.x).toBeGreaterThanOrEqual(0)
      expect(item.x + item.width).toBeLessThanOrEqual(320)
    }
  })

  it('cuts a name that is wider than the chart, with an ellipsis', () => {
    const long = 'x'.repeat(200)
    const { items } = legendLayout([{ id: 'l', name: long }], 320, measure)
    expect(items[0]!.text.endsWith('…')).toBe(true)
    expect(items[0]!.width).toBeLessThanOrEqual(320)
    expect(fitText('short', 100, '13px Arial', 13, measure)).toBe('short')
  })

  it('has no height without series', () => {
    expect(legendLayout([], 704, measure)).toEqual({ items: [], height: 0 })
  })

  it('keeps the plot at 120 px or more, whatever the legend takes, and grows the chart for it', () => {
    const many = Array.from({ length: 30 }, (_, i) => series(`s${i}`, [1, 2, 3], { name: `A long name of the series number ${i}` }))
    const { frame } = build(many, { width: 320 })
    expect(frame.plot.height).toBeGreaterThanOrEqual(120)
    expect(frame.height).toBeGreaterThan(400)
    // and it is the 400 px of the page where the legend is short
    expect(build([TEMPERATURE]).frame.height).toBe(400)
  })
})

describe('the frame', () => {
  it('maps a moment to a pixel and back', () => {
    const { frame, input: i } = build([TEMPERATURE])
    expect(xOfTime(START, frame, i.window)).toBe(frame.plot.left)
    expect(xOfTime(START + 6 * DAY, frame, i.window)).toBeCloseTo(frame.plot.left + frame.plot.width)
    expect(timeAtX(xOfTime(START + 2 * DAY, frame, i.window), frame, i.window)).toBeCloseTo(START + 2 * DAY)
  })

  it('draws what it has of the window and no more of a long series', () => {
    const long: ExplorerSeries = { id: 'l', name: 'l', colorIndex: 0, kind: 'values', x: Array.from({ length: 87_600 }, (_, i) => START + i * HOUR), y: Array.from({ length: 87_600 }, (_, i) => Math.sin(i / 50)) }
    const { frame } = build([long])
    expect(frame.drawn.get('l')!.x.length).toBeLessThan(4 * 704)
  })
})

describe('the times', () => {
  it('writes the ticks of a window by what it spans', () => {
    expect(tickLabel(Date.UTC(2020, 0, 1), 5000 * DAY, 'en')).toBe('2020')
    expect(tickLabel(Date.UTC(2020, 5, 1), 300 * DAY, 'en')).toBe('Jun 2020')
    expect(tickLabel(Date.UTC(2020, 5, 1), 60 * DAY, 'en')).toBe('Jun 1, 2020')
    expect(tickLabel(Date.UTC(2020, 5, 1), 10 * DAY, 'en')).toBe('Jun 1')
    // under three days: the hour, and the day where it is midnight
    expect(tickLabel(Date.UTC(2020, 5, 1, 6), 2 * DAY, 'en')).toBe('06:00')
    expect(tickLabel(Date.UTC(2020, 5, 2), 2 * DAY, 'en')).toBe('Jun 2')
    expect(tickLabel(Date.UTC(2020, 5, 1), 300 * DAY, 'de')).toMatch(/Juni?\.? 2020/)
  })

  it('names a moment of a daily series by its day and one of an hourly series with its time in UTC', () => {
    expect(hasTimeOfDay([TEMPERATURE])).toBe(false)
    expect(hasTimeOfDay([series('h', [1, 2], {}, HOUR)])).toBe(true)
    expect(momentLabel(START, 'en', false)).toBe('Sep 1, 2026')
    expect(momentLabel(START + 14 * HOUR, 'en', true)).toBe('Sep 1, 2026, 14:00 UTC')
  })
})

describe('the ticks of the time axis', () => {
  const YEAR = 365 * DAY

  it('are at the beginnings of the hours, days, Mondays, months or years of UTC, about one for each 90 px', () => {
    const hours = timeTicks({ start: START + 5 * 60_000, end: START + 11 * HOUR }, 700)
    expect(hours.every(t => t % HOUR === 0)).toBe(true)
    expect(timeTicks({ start: START, end: START + 12 * DAY }, 700).every(t => t % DAY === 0)).toBe(true)
    // a window of 40 days: weeks, from a Monday (1 Sept 2026 is a Tuesday)
    const weeks = timeTicks({ start: START, end: START + 40 * DAY }, 700)
    expect(weeks.every(t => new Date(t).getUTCDay() === 1)).toBe(true)
    const months = timeTicks({ start: Date.UTC(2026, 0, 15), end: Date.UTC(2026, 11, 20) }, 700)
    expect(months.every(t => new Date(t).getUTCDate() === 1)).toBe(true)
    expect(months.length).toBeLessThanOrEqual(7)
    const years = timeTicks({ start: Date.UTC(2016, 0, 1), end: Date.UTC(2025, 11, 30) }, 700)
    expect(years.map(t => new Date(t).getUTCFullYear())).toEqual([2016, 2018, 2020, 2022, 2024])
    expect(YEAR).toBeGreaterThan(0)
  })

  it('are each moment once, in order, inside the window, and fewer where the plot is narrow', () => {
    const win = { start: Date.UTC(2026, 0, 3), end: Date.UTC(2026, 6, 9) }
    const wide = timeTicks(win, 900)
    const narrow = timeTicks(win, 300)
    for (const ticks of [wide, narrow]) {
      expect(ticks).toEqual([...new Set(ticks)].sort((a, b) => a - b))
      expect(ticks.every(t => t >= win.start && t <= win.end)).toBe(true)
    }
    expect(narrow.length).toBeLessThan(wide.length)
  })

  it('make the grid lines of the drawing the same ones, evenly spaced, with none a few px from another (month starts and the end of the axis are no extra)', () => {
    // a window of three months in the middle of a longer chart: the library's own ticks had added every month start and the axis end
    const long = series('m', Array.from({ length: 400 }, (_, i) => i % 9), {}, DAY)
    const bounds = boundsOf([long])!
    const win = { start: bounds.start + 20 * DAY + 5 * HOUR, end: bounds.start + 140 * DAY + 7 * HOUR }
    const { input: i, frame, option } = build([long], { window: win, bounds })
    const svg = svgOf(i, option)
    const verticals = [...svg.matchAll(/<path d="M([\d.]+) ([\d.]+)L\1 ([\d.]+)"[^>]*stroke="rgb\(200, 205, 215\)"/g)].map(match => Number(match[1])).sort((a, b) => a - b)
    const ticks = timeTicks(win, frame.plot.width)
    expect(verticals).toHaveLength(ticks.length)
    for (const [index, x] of verticals.entries())
      expect(Math.abs(x - xOfTime(ticks[index]!, frame, win))).toBeLessThan(1)
    const gaps = verticals.slice(1).map((x, k) => x - verticals[k]!)
    // weeks are all of a length, and no two lines are closer than a week
    expect(Math.min(...gaps)).toBeGreaterThan(0.95 * Math.max(...gaps))
  })
})
