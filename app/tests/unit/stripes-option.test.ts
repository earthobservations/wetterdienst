import type { StripesDisplay, StripesOptionInput } from '../../app/utils/stripes-option'
import { describe, expect, it } from 'vitest'
import { EMPTY_CHART_THEME, seriesLabelColor } from '../../app/utils/chart-theme'
import { loadEcharts } from '../../app/utils/echarts-loader'
import { COLOR_MAPS, stripeColour } from '../../app/utils/stripes'
import { buildStripesModel, fullWindow } from '../../app/utils/stripes-model'
import { buildStripesOption, stripesLayout, stripesTexts, windowUpdate } from '../../app/utils/stripes-option'

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
    expect(option.yAxis[0]).toMatchObject({ min: -0.05, max: 1.05 })
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
