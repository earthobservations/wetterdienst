import type { StripesDisplay, StripesOptionInput } from '../../app/utils/stripes-option'
import { describe, expect, it } from 'vitest'
import { EMPTY_CHART_THEME, seriesLabelColor } from '../../app/utils/chart-theme'
import { loadEcharts } from '../../app/utils/echarts-loader'
import { COLOR_MAPS, stripeColour } from '../../app/utils/stripes'
import { buildStripesModel, fullWindow } from '../../app/utils/stripes-model'
import { buildStripesOption, STRIPES_MAX_HEIGHT, STRIPES_MIN_HEIGHT, STRIPES_RATIO, stripesChartHeight, stripesLayout, stripesTexts, windowUpdate } from '../../app/utils/stripes-option'

const echarts = loadEcharts()

const LIGHT = { ...EMPTY_CHART_THEME, text: 'rgb(15, 23, 43)', textMuted: 'rgb(90, 100, 120)' }
const DARK = { ...LIGHT, dark: true, text: 'rgb(226, 232, 240)' }
const DISPLAY: StripesDisplay = { showTitle: true, showYears: true, showSource: true, showDataAvailability: true, showTimeseries: false, showTrendline: false }

// 1950 to 2024 with 1962 to 1964 missing
const MODEL = buildStripesModel(
  Array.from({ length: 75 }, (_, i) => 1950 + i)
    .filter(year => year < 1962 || year > 1964)
    .map(year => ({ timestamp: `${year}-01-01T00:00:00+00:00`, value: (year - 1950) / 10 })),
)!

function build(over: Partial<StripesOptionInput & { display: Partial<StripesDisplay> }> = {}) {
  const input: StripesOptionInput = {
    model: MODEL,
    kind: 'temperature',
    theme: LIGHT,
    width: 704,
    height: 600,
    window: fullWindow(MODEL),
    titleLines: ['Climate stripes (Temperature) for Donaueschingen, Germany (00011)'],
    availabilityText: 'Data availability',
    sourceText: 'Source: Deutscher Wetterdienst',
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
const texts = (svg: string) => [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(match => match[1]!)
const fills = (svg: string) => [...svg.matchAll(/<path d="M[^"]*" fill="(rgb\([^"]*\))"/g)].map(match => match[1]!)

describe('the layout', () => {
  it('keeps the margins and the rows below the plot the chart has always had', () => {
    const layout = stripesLayout(DISPLAY, 704, 600, 1)
    expect(layout.plot).toEqual({ left: 20, top: 30, width: 664, height: 600 - 30 - 80 })
    expect(layout.yearsTop - (layout.plot.top + layout.plot.height)).toBe(20)
    expect(layout.sourceTop - (layout.plot.top + layout.plot.height)).toBe(48)
    expect(layout.availabilityBottom - (layout.plot.top + layout.plot.height)).toBe(14)
  })

  it('knows where the stripes are in the plot: all of it, or between the margins the availability line lies in', () => {
    const plain = stripesLayout({ ...DISPLAY, showDataAvailability: false }, 704, 600, 1)
    expect(plain.stripes).toEqual({ top: plain.plot.top, height: plain.plot.height })
    const withLine = stripesLayout(DISPLAY, 704, 600, 1)
    // a margin of 20 px above and below, whatever the height (GH-4133: it was 5 % of it, which crowds the title on a small chart)
    expect(withLine.stripes.top).toBe(withLine.plot.top + 20)
    expect(withLine.stripes.height).toBe(withLine.plot.height - 40)
    const small = stripesLayout(DISPLAY, 390, 300, 1)
    expect(small.stripes.top - small.plot.top).toBe(20)
    expect(small.plot.height - small.stripes.height).toBe(40)
  })

  it('has a smaller top margin without a title, and more room below for a source that has none of the years above it', () => {
    expect(stripesLayout({ ...DISPLAY, showTitle: false }, 704, 550, 1).plot.top).toBe(20)
    const noYears = stripesLayout({ ...DISPLAY, showYears: false }, 704, 600, 1)
    expect(noYears.sourceTop - (noYears.plot.top + noYears.plot.height)).toBe(28)
    expect(stripesLayout({ ...DISPLAY, showSource: false }, 704, 600, 1).plot.height).toBe(600 - 30 - 60)
  })

  it('lowers a title of several lines and gives the top margin the room for them', () => {
    const layout = stripesLayout(DISPLAY, 320, 600, 3)
    expect(layout.plot.top).toBe(30 + 2 * 20 + 18)
    expect(layout.titleTop).toBe(24 + 18)
  })
})

describe('the height of the chart (GH-4133)', () => {
  /** How high the stripes come out of a chart of `width`: what the layout makes of the height the chart is given */
  const stripesOf = (display: StripesDisplay, width: number, lines = 1, clamp = true) => stripesLayout(display, width, stripesChartHeight(display, width, lines, { clamp }), lines).stripes

  it('gives the stripes the ratio of the page, whatever the width, between the least and the most they are high', () => {
    for (const width of [400, 704, 820]) {
      const stripes = stripesOf(DISPLAY, width)
      expect(stripes.height, `at ${width} px`).toBeGreaterThanOrEqual(STRIPES_MIN_HEIGHT)
      expect(stripes.height, `at ${width} px`).toBeLessThanOrEqual(STRIPES_MAX_HEIGHT)
      expect((width - 40) / stripes.height, `at ${width} px`).toBeCloseTo(STRIPES_RATIO, 1)
    }
  })

  it('puts the title, the years, the availability line and the source on top of the stripes, and not into them', () => {
    const plain = { ...DISPLAY, showTitle: false, showYears: false, showSource: false, showDataAvailability: false }
    // no title (20 px above), nothing below but its 60 px, no margins for the availability line: the stripes and nothing else
    expect(stripesChartHeight(plain, 704, 0)).toBe(20 + (704 - 40) / STRIPES_RATIO + 60)
    // each thing shown makes the chart higher and the stripes not
    for (const shown of [{ showTitle: true }, { showYears: true, showSource: true }, { showDataAvailability: true }]) {
      const display = { ...plain, ...shown }
      expect(stripesChartHeight(display, 704, 1), JSON.stringify(shown)).toBeGreaterThan(stripesChartHeight(plain, 704, 0))
      expect(stripesOf(display, 704).height).toBeCloseTo((704 - 40) / STRIPES_RATIO, 0)
    }
    // a title of three lines at a phone's width: the chart is higher by what the lines take, the stripes are the same
    expect(stripesChartHeight(DISPLAY, 390, 3) - stripesChartHeight(DISPLAY, 390, 1)).toBe(2 * 20 + 18)
    expect(stripesOf(DISPLAY, 390, 3).height).toBeCloseTo(stripesOf(DISPLAY, 390, 1).height, 0)
  })

  it('does not let the stripes get thinner than a stripe reads at, in a narrow window, nor taller than the most, in a wide one', () => {
    expect(stripesOf(DISPLAY, 320).height).toBe(STRIPES_MIN_HEIGHT)
    expect(stripesOf(DISPLAY, 3000).height).toBe(STRIPES_MAX_HEIGHT)
  })

  it('is not held to the least and the most for a saved image, which keeps the ratio at its own width', () => {
    // the camera's width: 1360 px of stripes over the ratio, a height that the page would not draw
    const stripes = stripesOf(DISPLAY, 1400, 1, false)
    expect(stripes.height).toBeCloseTo(1360 / STRIPES_RATIO, 0)
    expect(stripes.height).toBeGreaterThan(STRIPES_MAX_HEIGHT)
    expect(stripesOf(DISPLAY, 200, 1, false).height).toBeLessThan(STRIPES_MIN_HEIGHT)
  })

  it('is no longer the fixed 600 px (550 without a title) of before, at any width', () => {
    for (const width of [320, 390, 704, 820]) {
      expect(stripesChartHeight(DISPLAY, width, 1)).not.toBe(600)
      expect(stripesChartHeight({ ...DISPLAY, showTitle: false }, width, 0)).not.toBe(550)
    }
    expect(stripesChartHeight(DISPLAY, 390, 1)).toBeLessThan(stripesChartHeight(DISPLAY, 820, 1))
  })
})

describe('the option', () => {
  it('draws a stripe for each year in the colour of its place on the scale, and none for a year without a value', () => {
    const { input, option } = build()
    const svg = draw(input, option)
    const drawn = fills(svg)
    expect(drawn).toHaveLength(MODEL.years.length)
    const expected = MODEL.normalized.map(position => stripeColour(COLOR_MAPS.temperature, position).replaceAll(' ', ''))
    expect(drawn.map(colour => colour.replaceAll(' ', ''))).toEqual(expected)
  })

  it('uses the scale of the kind', () => {
    const { input, option } = build({ kind: 'precipitation' })
    expect(fills(draw(input, option))[0]!.replaceAll(' ', '')).toBe('rgb(84,48,5)')
  })

  it('makes stripes that meet share an edge, in whole pixels', () => {
    const { input, option } = build()
    const svg = draw(input, option)
    // a stripe is a path that starts at its left edge and runs its width to the right
    const rects = [...svg.matchAll(/<path d="M([\d.]+) [\d.]+l([\d.]+) 0l0 [\d.]+l-[\d.]+ 0Z" fill="rgb/g)].map(match => [Number(match[1]), Number(match[2])] as const)
    expect(rects.length).toBeGreaterThan(10)
    for (const [x, width] of rects) {
      expect(Number.isInteger(x)).toBe(true)
      expect(Number.isInteger(width)).toBe(true)
    }
  })

  it('writes the title, the years, the availability label and the source, as the page offers them', () => {
    const { input, option } = build()
    expect(texts(draw(input, option))).toEqual([
      'Climate stripes (Temperature) for Donaueschingen, Germany (00011)',
      '1950',
      '2024',
      'Data availability',
      'Source: Deutscher Wetterdienst',
    ])
  })

  it('leaves out what the page switches off', () => {
    const { input, option } = build({ display: { showTitle: false, showYears: false, showSource: false, showDataAvailability: false } })
    expect(texts(draw(input, option))).toEqual([])
    expect(option.series.map((s: any) => s.id)).toEqual(['stripes', 'labels'])
    expect(option.yAxis[0]).toMatchObject({ min: 0, max: 1 })
  })

  it('breaks the title into the lines it was given, one text for each', () => {
    const { input, option } = build({ titleLines: ['Climate stripes (Temperature) for', 'Donaueschingen, Germany', '(00011)'] })
    expect(texts(draw(input, option)).slice(0, 3)).toEqual(['Climate stripes (Temperature) for', 'Donaueschingen, Germany', '(00011)'])
  })

  it('draws the availability line in gold with a gap for each missing year, in the margin under the stripes', () => {
    const { option } = build()
    const availability = option.series.find((s: any) => s.id === 'availability')
    expect(availability.lineStyle).toMatchObject({ color: '#FFD700', width: 3 })
    expect(availability.data.filter((point: number[]) => point[1] === null).map((point: number[]) => point[0])).toEqual([1962, 1963, 1964])
    // the 20 px of margin above and below the stripes (450 px high here), in the units of the axis they run 0 to 1 in
    expect(option.yAxis[0].min).toBeCloseTo(-20 / 450)
    expect(option.yAxis[0].max).toBeCloseTo(1 + 20 / 450)
  })

  it('draws the timeseries in black, and the trend dashed over it only where both are asked for', () => {
    expect(build().option.series.map((s: any) => s.id)).toEqual(['stripes', 'availability', 'labels'])
    expect(build({ display: { showTimeseries: true } }).option.series.map((s: any) => s.id)).toEqual(['stripes', 'availability', 'timeseries', 'labels'])
    const { option } = build({ display: { showTimeseries: true, showTrendline: true } })
    expect(option.series.map((s: any) => s.id)).toEqual(['stripes', 'availability', 'timeseries', 'trend', 'labels'])
    const series = Object.fromEntries(option.series.map((s: any) => [s.id, s]))
    expect(series.timeseries.lineStyle).toMatchObject({ color: 'black', width: 2 })
    expect(series.trend.lineStyle).toMatchObject({ color: 'black', width: 4, type: [12, 12] })
    // a trendline is of the timeseries: asked for alone it is not drawn
    expect(build({ display: { showTrendline: true } }).option.series.map((s: any) => s.id)).not.toContain('trend')
  })

  it('has no paper of its own on the page, and the paper it is given in a saved image', () => {
    const background = (svg: string) => /^<svg[^>]*>\s*<rect[^>]*fill="([^"]*)"/.exec(svg)?.[1]
    const onPage = build()
    expect(onPage.option.backgroundColor).toBe('transparent')
    expect(background(draw(onPage.input, onPage.option))).toBe('none')
    const saved = build({ background: 'rgb(255, 255, 255)' })
    expect(saved.option.backgroundColor).toBe('rgb(255, 255, 255)')
    expect(background(draw(saved.input, saved.option))).toBe('rgb(255, 255, 255)')
  })

  it('draws no animation and no tooltip: the readout is the component\'s own', () => {
    const { option } = build()
    expect(option.animation).toBe(false)
    expect(option.tooltip).toBeUndefined()
    expect(option.series.every((s: any) => s.animation === false && s.silent === true)).toBe(true)
  })

  it('takes the colours of the text from the theme, and the availability label\'s from its series\' label colour', () => {
    const light = build()
    const dark = build({ theme: DARK })
    const byText = (input: StripesOptionInput) => Object.fromEntries(stripesTexts(input, stripesLayout(input.display, input.width, input.height, 1)).map(spec => [spec.text, spec.fill]))
    expect(byText(light.input)['1950']).toBe(LIGHT.text)
    expect(byText(dark.input)['1950']).toBe(DARK.text)
    expect(byText(light.input)['Source: Deutscher Wetterdienst']).toBe(LIGHT.textMuted)
    expect(byText(light.input)['Data availability']).toBe(seriesLabelColor('gold', false))
    expect(byText(dark.input)['Data availability']).toBe(seriesLabelColor('gold', true))
    // the stripes are data: the same in both schemes
    expect(fills(draw(light.input, light.option))).toEqual(fills(draw(dark.input, dark.option)))
  })

  it('names the first year with a stripe in the window where it starts in a gap', () => {
    const { input } = build({ window: { start: 1961.6, end: 1989.5 } })
    const layout = stripesLayout(input.display, input.width, input.height, 1)
    expect(stripesTexts(input, layout).filter(spec => /^\d{4}$/.test(spec.text)).map(spec => spec.text)).toEqual(['1965', '1989'])
  })

  it('names the first and the last year in the window, and puts the availability label at the first', () => {
    const { input } = build({ window: { start: 1969.5, end: 1989.5 } })
    const layout = stripesLayout(input.display, input.width, input.height, 1)
    const specs = stripesTexts(input, layout)
    expect(specs.filter(spec => /^\d{4}$/.test(spec.text)).map(spec => spec.text)).toEqual(['1970', '1989'])
    const label = specs.find(spec => spec.text === 'Data availability')!
    expect(label.x).toBeCloseTo(20 + (0.5 / 20) * 664)
  })

  it('sets the zoom to the window, and a move of the window changes the zoom and the years only', () => {
    const win = { start: 1969.5, end: 1989.5 }
    const { input, option } = build({ window: win })
    expect(option.dataZoom[0]).toMatchObject({ id: 'zoom', startValue: 1969.5, endValue: 1989.5, filterMode: 'none', zoomOnMouseWheel: 'ctrl', moveOnMouseMove: false })
    const update = windowUpdate(input) as any
    expect(update.dataZoom).toEqual([{ id: 'zoom', startValue: 1969.5, endValue: 1989.5 }])
    expect(update.series.map((s: any) => s.id)).toEqual(['labels'])
  })
})
