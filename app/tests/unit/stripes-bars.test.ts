import type { StripesDisplay, StripesOptionInput } from '../../app/utils/stripes-option'
import { describe, expect, it } from 'vitest'
import { EMPTY_CHART_THEME } from '../../app/utils/chart-theme'
import { loadEcharts } from '../../app/utils/echarts-loader'
import { STRIPE_PALETTES, stripeColour } from '../../app/utils/stripes'
import { anomalyAxis, barAxis, buildStripesModel, fullWindow } from '../../app/utils/stripes-model'
import { buildStripesOption, frameOf, stripesChartHeight, stripesGridLines, stripesLayout, stripesTexts, stripesZeroLine, windowUpdate } from '../../app/utils/stripes-option'
import { recordOf, stripesAnswer } from '../helpers/stripes-answer'

// The climate stripes drawn as bars and as bars with a scale (GH-4156): the height of a bar is the year's anomaly, as the
// backend gives it, its colour the year's class. The app calculates neither.

const echarts = loadEcharts()

const THEME = { ...EMPTY_CHART_THEME, text: 'rgb(15, 23, 43)', textMuted: 'rgb(90, 100, 120)', grid: '#cccccc', zeroline: '#333333' }
const DISPLAY: StripesDisplay = { showTitle: true, showYears: true, showSource: true, showDataAvailability: true }
const SUBTITLE = ['Relative to the mean of 1971–2000 [°C]']

// 1950 to 2024, cooler to warmer with a wobble, 1962 to 1964 missing; the classes and anomalies as the backend gives them
const ANSWER = stripesAnswer(recordOf(1950, 2024, year => 8 + (year - 1987) / 20 + Math.sin(year), [1962, 1963, 1964]))
const MODEL = buildStripesModel(ANSWER.values)!
const AXIS = barAxis(MODEL)

function build(over: Partial<StripesOptionInput & { display: Partial<StripesDisplay> }> = {}) {
  const input: StripesOptionInput = {
    model: MODEL,
    kind: 'temperature',
    theme: THEME,
    width: 704,
    height: 600,
    window: fullWindow(MODEL),
    titleLines: ['Climate stripes (Temperature) for Hohenpeißenberg, Germany (02290)'],
    availabilityText: 'Data availability',
    sourceText: 'Source: Deutscher Wetterdienst',
    variant: 'bars',
    subtitleLines: [],
    ...over,
    display: { ...DISPLAY, ...over.display },
  }
  return { input, option: buildStripesOption(input) as any }
}

function draw(input: StripesOptionInput, option: unknown) {
  const chart = echarts.init(null as any, null, { renderer: 'svg', ssr: true, width: input.width, height: input.height })
  chart.setOption(option as any)
  const svg = chart.renderToSVGString()
  chart.dispose()
  return svg
}

interface Bar { x: number, width: number, y: number, height: number, fill: string }
/** The bars (every filled rectangle of the chart but the gold availability line), as they are drawn, in the order of the years */
function barsOf(svg: string): Bar[] {
  return [...svg.matchAll(/<path d="M(-?[\d.]+) (-?[\d.]+)l([\d.]+) 0l0 ([\d.]+)l-[\d.]+ 0Z" fill="(#(?!FFD700)[0-9a-fA-F]{6})"/g)]
    .map(match => ({ x: Number(match[1]), y: Number(match[2]), width: Number(match[3]), height: Number(match[4]), fill: match[5]! }))
}
/** The lines of a stroke colour, as `[x1, y1, x2, y2]` */
function linesOf(svg: string, stroke: string) {
  return [...svg.matchAll(new RegExp(`<path d="M(-?[\\d.]+) (-?[\\d.]+)L(-?[\\d.]+) (-?[\\d.]+)"[^>]*stroke="${stroke}"`, 'g'))]
    .map(match => [Number(match[1]), Number(match[2]), Number(match[3]), Number(match[4])] as const)
}
const texts = (svg: string) => [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(match => match[1]!)
const seriesIds = (option: any) => option.series.map((s: any) => s.id)

describe('the series of a variant', () => {
  it('draws the stripes as they were: no bars, no zero line, no grid', () => {
    const { option } = build({ variant: 'stripes' })
    expect(seriesIds(option)).toEqual(['stripes', 'availability', 'labels'])
  })

  it('draws bars and the zero line over them in place of the stripes', () => {
    expect(seriesIds(build({ variant: 'bars' }).option)).toEqual(['bars', 'zeroline', 'availability', 'labels'])
  })

  it('draws a grid under the bars with a scale, and the zero line over them', () => {
    expect(seriesIds(build({ variant: 'barsScale', subtitleLines: SUBTITLE }).option)).toEqual(['bars', 'grid', 'zeroline', 'availability', 'labels'])
  })

  it('takes the stripes for a variant that is not given', () => {
    const { input } = build({ variant: undefined })
    expect(seriesIds(buildStripesOption(input))).toEqual(['stripes', 'availability', 'labels'])
  })
})

describe('the bars', () => {
  it('has a bar for each year with a value and none for a year without: 72 bars for 75 years less 3', () => {
    const { input, option } = build()
    const svg = draw(input, option)
    expect(barsOf(svg)).toHaveLength(MODEL.years.length)
    expect(MODEL.years).toHaveLength(72)
    // the three missing years are a gap of three bars' width between the bars of 1961 and 1965
    const bars = barsOf(svg)
    const before = bars[MODEL.years.indexOf(1961)]!
    const after = bars[MODEL.years.indexOf(1965)]!
    expect(after.x - (before.x + before.width)).toBeGreaterThanOrEqual(3 * before.width - 3)
  })

  it('puts each bar at the height of its anomaly, as the backend gives it, on the range of the axis', () => {
    const { option } = build()
    const bars = option.series.find((s: any) => s.id === 'bars')
    MODEL.years.forEach((year, index) => {
      const [at, height] = bars.data[index]
      expect(at).toBe(year)
      expect(height).toBeCloseTo((MODEL.anomalies[index]! - AXIS.min) / (AXIS.max - AXIS.min), 10)
    })
  })

  it('draws a warm year above the zero line and a cool one below it, each as many px high as its anomaly is', () => {
    const { input, option } = build()
    const svg = draw(input, option)
    const bars = barsOf(svg)
    const layout = stripesLayout(input.display, input.width, input.height, 1, 0, frameOf(input))
    const pxPerUnit = layout.stripes.height / (AXIS.max - AXIS.min)
    const zero = Math.round(layout.stripes.top + layout.stripes.height * (1 - (0 - AXIS.min) / (AXIS.max - AXIS.min)))
    let warm = 0
    let cool = 0
    MODEL.anomalies.forEach((anomaly, index) => {
      const bar = bars[index]!
      // within a pixel of the bar's height and of the pixels the two ends are rounded to
      expect(Math.abs(bar.height - Math.abs(anomaly) * pxPerUnit)).toBeLessThanOrEqual(1.5)
      if (anomaly > 0.05) {
        expect(bar.y + bar.height).toBe(zero)
        warm++
      }
      if (anomaly < -0.05) {
        expect(bar.y).toBe(zero + 1)
        cool++
      }
    })
    expect(warm).toBeGreaterThan(5)
    expect(cool).toBeGreaterThan(5)
  })

  it('colours each bar by the class of its year, the colours of the stripes', () => {
    const { input, option } = build()
    const fills = barsOf(draw(input, option)).map(bar => bar.fill.toLowerCase())
    expect(fills).toEqual(MODEL.classes.map(stripeClass => stripeColour('temperature', stripeClass).toLowerCase()))
    // and the colour is the stripes': the same year in both variants
    const stripes = build({ variant: 'stripes' })
    expect(barsOf(draw(stripes.input, stripes.option)).map(bar => bar.fill.toLowerCase())).toEqual(fills)
  })

  it('draws the zero line over the full width of the plot, where the bars start', () => {
    const { input, option } = build()
    const svg = draw(input, option)
    const layout = stripesLayout(input.display, input.width, input.height, 1, 0, frameOf(input))
    const zero = linesOf(svg, '#333333')
    expect(zero).toHaveLength(1)
    const [x0, y0, x1, y1] = zero[0]!
    expect([x0, x1]).toEqual([layout.plot.left, layout.plot.left + layout.plot.width])
    expect(y0).toBe(y1)
    // a half pixel under the bars' base, so that the line is one pixel crisp
    const base = barsOf(svg).find((bar, index) => MODEL.anomalies[index]! > 0.5)!
    expect(y0).toBeCloseTo(base.y + base.height + 0.5)
  })

  it('has no axes: no grid, no tick labels, the first and the last year at the ends as the stripes have them', () => {
    const { input, option } = build()
    const svg = draw(input, option)
    expect(linesOf(svg, '#cccccc')).toEqual([])
    expect(texts(svg).filter(text => /^\d{4}$/.test(text))).toEqual(['1950', '2024'])
    expect(texts(svg)).not.toContain('0')
    expect(stripesGridLines(input, stripesLayout(input.display, input.width, input.height, 1))).toEqual([])
  })

  it('is as high as the stripes are, and keeps their layout', () => {
    const stripes = stripesChartHeight(DISPLAY, 704, 1)
    expect(stripesChartHeight(DISPLAY, 704, 1, { frame: frameOf({ variant: 'bars' }) })).toBe(stripes)
    expect(stripesLayout(DISPLAY, 704, stripes, 1, 0, frameOf({ variant: 'bars' }))).toEqual(stripesLayout(DISPLAY, 704, stripes, 1))
  })

  it('draws no line over the bars (GH-4170): only the bars, the zero line, the availability line and the labels', () => {
    expect(build().option.series.map((s: any) => s.id)).toEqual(['bars', 'zeroline', 'availability', 'labels'])
    expect(build({ variant: 'barsScale', subtitleLines: SUBTITLE }).option.series.map((s: any) => s.id)).toEqual(['bars', 'grid', 'zeroline', 'availability', 'labels'])
  })
})

describe('the bars with a scale', () => {
  const scale = (over: Partial<StripesOptionInput & { display: Partial<StripesDisplay> }> = {}) => build({ variant: 'barsScale', subtitleLines: SUBTITLE, ...over })

  it('has a y axis in the unit of the anomaly: a label for each tick, at the grid line, with the sign and zero as 0', () => {
    const { input } = scale()
    const layout = stripesLayout(input.display, input.width, input.height, 1, 0, frameOf(input))
    const labels = stripesTexts(input, layout).filter(spec => spec.align === 'right' && spec.baseline === 'middle')
    expect(labels.map(spec => spec.text)).toEqual(AXIS.ticks.map(tick => tick === 0 ? '0' : `${tick > 0 ? '+' : '−'}${Math.abs(tick).toFixed(AXIS.decimals)}`))
    // right-aligned just left of the plot
    expect(new Set(labels.map(spec => spec.x))).toEqual(new Set([layout.plot.left - 8]))
    // each at the pixel of its grid line
    const lines = stripesGridLines(input, layout).filter(line => line.y0 === line.y1)
    expect(lines.map(line => Math.floor(line.y0))).toEqual(labels.map(spec => spec.y))
  })

  it('writes the numbers of the axis as the page says (its language and its decimals)', () => {
    const { input } = scale({ formatTick: (value, decimals) => `<${value.toFixed(decimals)}>` })
    const layout = stripesLayout(input.display, input.width, input.height, 1, 0, frameOf(input))
    expect(stripesTexts(input, layout).some(spec => spec.text === `<${AXIS.ticks[0]!.toFixed(AXIS.decimals)}>`)).toBe(true)
  })

  it('says what the bars are relative to under the title, and not in the other variants', () => {
    const { input } = scale()
    const layout = stripesLayout(input.display, input.width, input.height, 1, 0, frameOf(input))
    const subtitle = stripesTexts(input, layout).find(spec => spec.text === SUBTITLE[0])!
    expect(subtitle.y).toBeGreaterThan(layout.titleTop + 16)
    expect(subtitle.y + 13).toBeLessThanOrEqual(layout.stripes.top)
    expect(subtitle.fill).toBe(THEME.textMuted)
    const bars = build({ subtitleLines: SUBTITLE })
    expect(texts(draw(bars.input, bars.option))).not.toContain(SUBTITLE[0])
  })

  it('lowers the plot by the lines of the subtitle, and holds the stripes as high as ever', () => {
    const one = frameOf({ variant: 'barsScale', subtitleLines: ['a'] })
    const two = frameOf({ variant: 'barsScale', subtitleLines: ['a', 'b'] })
    const plain = stripesLayout(DISPLAY, 704, 600, 1, 0, frameOf({ variant: 'barsScale' }))
    const withOne = stripesLayout(DISPLAY, 704, 600, 1, 0, one)
    const withTwo = stripesLayout(DISPLAY, 704, 600, 1, 0, two)
    expect(withOne.plot.top).toBeGreaterThan(plain.plot.top)
    expect(withTwo.plot.top - withOne.plot.top).toBe(17)
    // the chart grows by what the lines take: the stripes keep their height
    const high = (frame: ReturnType<typeof frameOf>) => stripesChartHeight(DISPLAY, 704, 1, { clamp: false, frame })
    const stripesHeight = (frame: ReturnType<typeof frameOf>) => stripesLayout(DISPLAY, 704, high(frame), 1, 0, frame).stripes.height
    expect(stripesHeight(one)).toBeCloseTo(stripesHeight(two), 0)
    expect(high(two)).toBeGreaterThan(high(one))
  })

  it('makes room left of the plot for the labels and a little right of it', () => {
    const layout = stripesLayout(DISPLAY, 704, 600, 1, 0, frameOf({ variant: 'barsScale', subtitleLines: ['a'] }))
    expect(layout.plot.left).toBe(52)
    expect(layout.plot.width).toBe(704 - 52 - 24)
    expect(stripesLayout(DISPLAY, 704, 600, 1, 0, frameOf({ variant: 'bars' })).plot.left).toBe(20)
  })

  it('names round years along the axis in place of the first and the last, each a multiple of the step', () => {
    const { input, option } = scale()
    const svg = draw(input, option)
    const years = texts(svg).filter(text => /^\d{4}$/.test(text)).map(Number)
    expect(years).toEqual([1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020])
    expect(years).not.toContain(2024)
  })

  it('draws a vertical grid line at each of the round years, over the height of the bars, at the bar of the year', () => {
    const { input } = scale()
    const layout = stripesLayout(input.display, input.width, input.height, 1, 0, frameOf(input))
    const vertical = stripesGridLines(input, layout).filter(line => line.x0 === line.x1)
    expect(vertical).toHaveLength(8)
    vertical.forEach(line => expect([line.y0, line.y1]).toEqual([layout.stripes.top, layout.stripes.top + layout.stripes.height]))
    // 1950: the middle of its bar, which is half a bar from the plot's left edge
    expect(vertical[0]!.x0).toBeCloseTo(layout.plot.left + (0.5 / 75) * layout.plot.width, 0)
  })

  it('draws no year ticks and no vertical grid where the years are not shown, and keeps the y axis', () => {
    const { input } = scale({ display: { showYears: false } })
    const layout = stripesLayout(input.display, input.width, input.height, 1, 0, frameOf(input))
    expect(stripesTexts(input, layout).filter(spec => /^\d{4}$/.test(spec.text))).toEqual([])
    expect(stripesGridLines(input, layout).filter(line => line.x0 === line.x1)).toEqual([])
    expect(stripesGridLines(input, layout).filter(line => line.y0 === line.y1)).toHaveLength(AXIS.ticks.length)
  })

  it('moves the ticks and the vertical grid with the window, and gets finer in a zoomed one', () => {
    const win = { start: 2009.5, end: 2019.5 }
    const { input } = scale({ window: win })
    const update = windowUpdate(input) as any
    expect(update.series.map((s: any) => s.id)).toEqual(['labels', 'grid'])
    const layout = stripesLayout(input.display, input.width, input.height, 1, 0, frameOf(input))
    expect(stripesTexts(input, layout).filter(spec => /^\d{4}$/.test(spec.text)).map(spec => spec.text)).toEqual(['2010', '2011', '2012', '2013', '2014', '2015', '2016', '2017', '2018', '2019'])
    // the window's update of the other variants names no grid
    expect((windowUpdate(build().input) as any).series.map((s: any) => s.id)).toEqual(['labels'])
  })

  it('keeps the grid under the bars and the zero line over them', () => {
    const { option } = scale()
    const z = Object.fromEntries(option.series.map((s: any) => [s.id, s.z]))
    expect(z.grid).toBeLessThan(z.bars)
    expect(z.zeroline).toBeGreaterThan(z.bars)
  })

  it('draws the zero line too', () => {
    const { input } = scale()
    const layout = stripesLayout(input.display, input.width, input.height, 1, 0, frameOf(input))
    expect(stripesZeroLine(input, layout)).toHaveLength(1)
    expect(stripesZeroLine({ ...input, variant: 'stripes' }, layout)).toEqual([])
  })
})

/** A model of the years `first` on whose anomalies are `anomalies` (the value is 10 above the anomaly; the class is the middle one) */
function modelOf(anomalies: (number | null)[], first = 2000) {
  const items = anomalies.map((anomaly, index) => ({ timestamp: `${first + index}-01-01T00:00:00+00:00`, value: anomaly === null ? null : 10 + anomaly, anomaly, stripe_class: anomaly === null ? null : 8 }))
  return buildStripesModel(items)!
}

describe('no line over the bars or the stripes (GH-4170)', () => {
  const DARK = { ...THEME, dark: true, text: 'rgb(226, 232, 240)', textMuted: 'rgb(160, 170, 190)' }
  // 2000 to 2002 (a run), 2004 (alone), 2006 and 2007
  const gapped = modelOf([-1, 0.5, 1, null, -0.5, null, 1.5, 2])
  // what the settings or the link of an older version still say
  const old = { showTimeseries: true, showTrendline: true } as unknown as Partial<StripesDisplay>

  it.each(['stripes', 'bars', 'barsScale'] as const)('draws no series of a line, in the %s, in either scheme, whatever an older display asks for', (variant) => {
    for (const theme of [THEME, DARK, EMPTY_CHART_THEME]) {
      const { input, option } = build({ model: gapped, window: fullWindow(gapped), variant, theme, subtitleLines: variant === 'barsScale' ? SUBTITLE : [], display: old })
      expect(option.series.some((s: any) => s.type === 'line' || s.id === 'timeseries' || s.id === 'trend')).toBe(false)
      expect(draw(input, option)).not.toMatch(/stroke-dasharray/)
    }
  })
})

describe('a bar of a tiny anomaly and the zero line (GH-4156)', () => {
  // one bar a pixel high above the zero line, one a pixel high below it, and two of 2 and -2 to set the range
  const tiny = modelOf([2, -2, 0.001, -0.001])
  const rows = () => {
    const { input, option } = build({ model: tiny, window: fullWindow(tiny), display: { showDataAvailability: false } })
    const svg = draw(input, option)
    const layout = stripesLayout(input.display, input.width, input.height, 1, 0, frameOf(input))
    const axis = barAxis(tiny)
    const zero = Math.round(layout.stripes.top + layout.stripes.height * (1 - (0 - axis.min) / (axis.max - axis.min)))
    return { bars: barsOf(svg), zero }
  }

  it('is a px high, in the row over the zero line for a positive anomaly and in the row under it for a negative one', () => {
    const { bars, zero } = rows()
    expect(bars[2]!.height).toBe(1)
    expect(bars[2]!.y).toBe(zero - 1)
    expect(bars[3]!.height).toBe(1)
    expect(bars[3]!.y).toBe(zero + 1)
  })

  it('has the bars above and below as high as their anomalies, from the rows next to the line', () => {
    const { bars, zero } = rows()
    expect(bars[0]!.y + bars[0]!.height).toBe(zero)
    expect(bars[1]!.y).toBe(zero + 1)
    // the same number of px for the same anomaly up and down
    expect(bars[0]!.height).toBe(bars[1]!.height)
  })

  it('draws no bar of an anomaly of nought', () => {
    const none = modelOf([2, -2, 0])
    const { input, option } = build({ model: none, window: fullWindow(none) })
    expect(barsOf(draw(input, option))[2]!.height).toBe(0)
  })
})

describe('the axis of the bars', () => {
  it('is that of the anomalies of the years alone, zero included, whatever fit the years have', () => {
    // zeros and a jump at the end: a line fitted through them would lie at -2 in 2000, beyond the lowest anomaly
    const jump = modelOf([0, 0, 0, 0, 10])
    expect(barAxis(jump)).toEqual(anomalyAxis(jump.anomalies))
    expect(barAxis(jump).min).toBe(0)
  })
})

describe('precipitation as bars', () => {
  // the deviation from the reference, in mm: wet above the zero line, dry below it
  const answer = stripesAnswer(recordOf(1950, 2020, year => 900 + 40 * Math.sin(year / 3) * 5 + (year - 1985) * 3))
  const model = buildStripesModel(answer.values)!
  const axis = barAxis(model)

  it('colours the bars by the BrBG classes, brown for dry and teal for wet', () => {
    const { input, option } = build({ kind: 'precipitation', model, window: fullWindow(model) })
    const bars = barsOf(draw(input, option))
    expect(bars.map(bar => bar.fill.toLowerCase())).toEqual(model.classes.map(stripeClass => STRIPE_PALETTES.precipitation[stripeClass]!.toLowerCase()))
    expect(new Set(bars.map(bar => bar.fill.toLowerCase())).size).toBeGreaterThan(8)
  })

  it('draws a wet year above the zero line (a positive anomaly is up) and a dry one below it, the axis in mm', () => {
    const { input, option } = build({ kind: 'precipitation', model, window: fullWindow(model), variant: 'barsScale', subtitleLines: ['Relative to the mean of 1971–2000 [mm]'] })
    const svg = draw(input, option)
    const layout = stripesLayout(input.display, input.width, input.height, 1, 0, frameOf(input))
    const zero = Math.round(layout.stripes.top + layout.stripes.height * (1 - (0 - axis.min) / (axis.max - axis.min)))
    const bars = barsOf(svg)
    const wettest = model.anomalies.indexOf(Math.max(...model.anomalies))
    const driest = model.anomalies.indexOf(Math.min(...model.anomalies))
    expect(model.anomalies[wettest]).toBeGreaterThan(0)
    expect(bars[wettest]!.y + bars[wettest]!.height).toBe(zero)
    expect(bars[driest]!.y).toBe(zero + 1)
    // millimetres need no decimals
    expect(axis.decimals).toBe(0)
    expect(texts(svg)).toContain('0')
  })
})
