import type { ModelInput } from '../../app/utils/meteogram-model'
import type { OptionInput } from '../../app/utils/meteogram-option'
import { readFileSync } from 'node:fs'
import * as SunCalc from 'suncalc'
import { describe, expect, it } from 'vitest'
import { EMPTY_CHART_THEME, SERIES_LABEL } from '../../app/utils/chart-theme'
import { loadEcharts } from '../../app/utils/echarts-loader'
import { hourFormatter } from '../../app/utils/format'
import { METEOGRAM_SERIES, meteogramValuesQuery, MOSMIX_METEOGRAM } from '../../app/utils/meteogram'
import { chartLayout, GUTTER_RIGHT, HOUR_MS, PANEL_HEIGHT, PANEL_ORDER, plotWidthFor, toggleOf } from '../../app/utils/meteogram-geometry'
import { buildMeteogramModel, readoutValue } from '../../app/utils/meteogram-model'
import { buildMeteogramOption, gutterLeftFor, THUNDER_ALPHA, toneColor } from '../../app/utils/meteogram-option'
import { buildSeries } from '../../app/utils/meteogram-series'
import { meteogramTable } from '../../app/utils/meteogram-summary'
import { planThunder, THUNDER_LEVELS, THUNDER_THRESHOLD, thunderLevel } from '../../app/utils/meteogram-thunder'
import { meteogramUnits } from '../../app/utils/meteogram-units'
import { parameters } from '../../i18n/glossary/en'
import { FORECAST_START, FORECAST_UNITS, forecastValues } from '../helpers/meteogram-forecast'

// The thunderstorm band of the forecast (GH-4090): the hours in which MOSMIX's hourly probability of a thunderstorm (`wwT`) reaches
// 10 %, as bars in a thin panel under the precipitation, which goes with the precipitation's switch.

const t = (key: string, named?: Record<string, unknown>) => Object.entries(named ?? {}).reduce((text, [name, value]) => `${text} ${name}=${String(value)}`, key)
const t0 = new Date(FORECAST_START).getTime()
const all = { temp: true, wind: true, precip: true, snow: true, cloud: true, pressure: true }
const percent = (value: number) => value
const at = (hour: number) => t0 + hour * HOUR_MS

/** A thunderstorm on the afternoon of the second day: 12 % at 15:00, 35 % at 16:00, 70 % at 17:00, 25 % at 18:00, and 1 % at the hours around */
const STORM: Record<number, number> = { 39: 12, 40: 35, 41: 70, 42: 25 }
const storm = (hour: number) => STORM[hour] ?? (hour % 7 === 0 ? 1 : 0)

function series(options: Parameters<typeof forecastValues>[0] = {}) {
  return buildSeries(forecastValues({ hours: 120, ...options }) as any)
}

function input(overrides: Partial<ModelInput> & { units?: Record<string, string> } = {}): ModelInput {
  const { units = FORECAST_UNITS, ...rest } = overrides
  return {
    series: series({ thunder: storm }),
    panels: all,
    horizonHours: null,
    zone: 'Europe/Berlin',
    language: 'en-GB',
    coords: { latitude: 52.5, longitude: 13.4 },
    sun: SunCalc as any,
    units: meteogramUnits(units, t),
    t,
    ...rest,
  }
}
const model = (overrides: Parameters<typeof input>[0] = {}) => buildMeteogramModel(input(overrides))!

describe('the request and the series of the thunderstorm probability', () => {
  it('asks for the hourly element of MOSMIX-L in the meteogram\'s own request, by its canonical name back', () => {
    expect(MOSMIX_METEOGRAM.parameters).toContain('wwt')
    expect(meteogramValuesQuery('10382', { units: {}, convertUnits: true }).parameters!.split(',')).toContain('hourly/large/wwt')
    expect(METEOGRAM_SERIES.thunder[0]).toBe('probability_thunder_last_1h')
    expect(Object.hasOwn(parameters, METEOGRAM_SERIES.thunder[0])).toBe(true)
  })

  it('asks for the hourly one only: the 6, 12 and 24 hour probabilities are not part of the request', () => {
    expect(MOSMIX_METEOGRAM.parameters.filter(parameter => parameter.startsWith('wwt'))).toEqual(['wwt'])
  })
})

describe('the classes of a probability', () => {
  it('has a threshold of 10 % and steps at 30 and 60', () => {
    expect(THUNDER_THRESHOLD).toBe(10)
    expect(THUNDER_LEVELS).toEqual([10, 30, 60])
  })

  it.each([
    [0, 0],
    [1, 0],
    [9, 0],
    [9.99, 0],
    [10, 1],
    [29, 1],
    [30, 2],
    [59, 2],
    [60, 3],
    [100, 3],
  ])('puts %s %% in class %s', (value, level) => {
    expect(thunderLevel(value)).toBe(level)
  })
})

describe('the hours of the band', () => {
  it('is a cell over the hour before each stamp that reaches the threshold, as the hour DWD writes it at is the one before it', () => {
    const plan = planThunder(series({ thunder: storm }), percent)!
    expect(plan.cells.map(cell => [cell.start, cell.end, cell.percent, cell.level])).toEqual([
      [at(38), at(39), 12, 1],
      [at(39), at(40), 35, 2],
      [at(40), at(41), 70, 3],
      [at(41), at(42), 25, 1],
    ])
    expect(plan.peak).toMatchObject({ end: at(41), percent: 70 })
  })

  it('has no cell for the 1 and 2 % that MOSMIX gives on a calm day, and no band at all where there are no more', () => {
    expect(planThunder(series({ thunder: hour => hour % 3 === 0 ? 2 : 1 }), percent)).toBeNull()
    expect(planThunder(series({ thunder: () => 9 }), percent)).toBeNull()
    expect(planThunder(series({ thunder: () => 10 }), percent)!.cells).toHaveLength(121)
  })

  it('has none for a forecast without the series', () => {
    expect(planThunder(series(), percent)).toBeNull()
    expect(planThunder(new Map(), percent)).toBeNull()
  })

  it('keeps the first of equal peaks, and reads a value that the answer has in another unit by what it is in percent', () => {
    const plan = planThunder(series({ thunder: hour => hour === 20 || hour === 60 ? 50 : 0 }), percent)!
    expect(plan.peak.end).toBe(at(20))
    // the answer in oktas (1/8): 4 of 8 is 50 %
    const eighths = planThunder(series({ thunder: hour => hour === 20 ? 4 : 0 }), value => value / 8 * 100)!
    expect(eighths.cells).toHaveLength(1)
    expect(eighths.cells[0]).toMatchObject({ value: 4, percent: 50, level: 2 })
  })

  it('counts only the hours that begin before the horizon', () => {
    const forecast = series({ thunder: hour => hour === 60 ? 40 : hour === 100 ? 40 : 0 })
    expect(planThunder(forecast, percent, at(72))!.cells.map(cell => cell.end)).toEqual([at(60)])
    // the hour that ends at the horizon begins before it, the one that begins at it does not
    expect(planThunder(forecast, percent, at(60))!.cells).toHaveLength(1)
    expect(planThunder(forecast, percent, at(59))).toBeNull()
  })

  it('leaves out an hour without a value: there is no probability of 0 for it', () => {
    const values = forecastValues({ hours: 48, thunder: hour => hour === 10 ? 40 : hour === 11 ? 40 : 0 }) as any[]
    const kept = values.filter(v => !(v.parameter === 'probability_thunder_last_1h' && v.timestamp.includes('T11:')))
    expect(planThunder(buildSeries(kept), percent)!.cells.map(cell => cell.end)).toEqual([at(10)])
  })
})

// The four probabilities of MOSMIX-L in the run of 03 UTC on 2026-11-17 (the stub of the backend's tests), two stations
describe('the real run: which of the four the forecast can be drawn from, and how late in the run', () => {
  const run = JSON.parse(readFileSync(new URL('../helpers/mosmix-thunder-runs.json', import.meta.url), 'utf8')) as { issue: string, stations: Record<string, Record<string, [number, number][]>> }
  const issue = new Date(run.issue).getTime()
  const hoursOf = (station: string, parameter: string) => run.stations[station]![parameter]!.map(([hour]) => hour)

  it('has the hourly probability at every hour from +1 h to +247 h, at both stations: it does not thin out late in the run', () => {
    for (const station of ['10382', '10961'])
      expect(hoursOf(station, 'probability_thunder_last_1h')).toEqual(Array.from({ length: 247 }, (_, i) => i + 1))
  })

  it('has the 6 hour probability thin to every third hour at one station, and the 12 and 24 hour ones at 6 and 12 hours: the hourly one is the only complete series', () => {
    const six = hoursOf('10382', 'probability_thunder_last_6h')
    expect(six.slice(0, 12)).toEqual(Array.from({ length: 12 }, (_, i) => i + 1))
    expect(six.at(-1)).toBe(246)
    expect(six.length).toBeLessThan(120)
    expect(hoursOf('10382', 'probability_thunder_last_12h').slice(0, 4)).toEqual([3, 9, 15, 21])
    expect(hoursOf('10382', 'probability_thunder_last_24h').slice(0, 4)).toEqual([9, 21, 33, 45])
    // and a station can have none of the two longer ones
    expect(run.stations['10961']!.probability_thunder_last_12h).toEqual([])
  })

  it('has no hour of 10 % or more at either station: a calm week has no band', () => {
    for (const station of ['10382', '10961']) {
      const values = run.stations[station]!.probability_thunder_last_1h!
      expect(Math.max(...values.map(([, value]) => value))).toBeLessThan(THUNDER_THRESHOLD)
      const forecast = buildSeries(values.map(([hour, value]) => ({ parameter: 'probability_thunder_last_1h', timestamp: new Date(issue + hour * HOUR_MS).toISOString(), value })) as any)
      expect(planThunder(forecast, percent)).toBeNull()
    }
  })

  it('draws a risk in the last hour of the run, which a series that stopped early would not', () => {
    const values = run.stations['10382']!.probability_thunder_last_1h!.map(([hour, value]) => [hour, hour === 247 ? 45 : value] as const)
    const forecast = buildSeries(values.map(([hour, value]) => ({ parameter: 'probability_thunder_last_1h', timestamp: new Date(issue + hour * HOUR_MS).toISOString(), value })) as any)
    const plan = planThunder(forecast, percent)!
    expect(plan.cells).toHaveLength(1)
    expect(plan.cells[0]).toMatchObject({ end: issue + 247 * HOUR_MS, percent: 45, level: 2 })
  })
})

describe('the thunderstorm panel of the model', () => {
  it('is a plot under the precipitation, after it in the order and with its switch', () => {
    expect(PANEL_ORDER.indexOf('thunder')).toBe(PANEL_ORDER.indexOf('precip') + 1)
    expect(toggleOf('thunder')).toBe('precip')
    expect(model().panels).toEqual(['wind', 'precip', 'thunder', 'cloud', 'temp', 'pressure'])
  })

  it('has the cells of the plan, over their hours, and an axis of 0 to 100 % with its own title and the unit on a second line', () => {
    const m = model()
    expect(m.thunder!.cells).toHaveLength(4)
    expect(m.axes.thunder).toMatchObject({ range: [0, 100], title: 'meteogram.chart.axisThunder unit=\n%', label: 'fuchsia', decimals: 0, splits: 2 })
  })

  it('is absent where no hour reaches the threshold, and where the forecast has no series: the chart is as it was', () => {
    for (const m of [model({ series: series({ thunder: hour => hour % 5 === 0 ? 3 : 0 }) }), model({ series: series() })]) {
      expect(m.panels).toEqual(['wind', 'precip', 'cloud', 'temp', 'pressure'])
      expect(m.thunder).toBeNull()
      expect(m.readout.some(r => r.id === 'thunder')).toBe(false)
    }
  })

  it('goes with the precipitation: off with it, on with it, and alone when it is the only one on', () => {
    expect(model({ panels: { ...all, precip: false } }).panels).not.toContain('thunder')
    expect(model({ panels: { ...all, precip: false } }).thunder).toBeNull()
    expect(model({ panels: { temp: false, wind: false, precip: true, snow: false, cloud: false, pressure: false } }).panels).toEqual(['precip', 'thunder'])
  })

  it('is judged by the hours the horizon shows: a storm beyond it is no panel', () => {
    expect(model({ horizonHours: 24 }).panels).not.toContain('thunder')
    expect(model({ horizonHours: 72 }).panels).toContain('thunder')
  })

  it('has a readout of the probability of every hour of the run, those under the threshold included, and none of the band\'s cells in the series of the lines', () => {
    const m = model()
    const row = m.readout.find(r => r.id === 'thunder')!
    expect(row).toMatchObject({ panel: 'thunder', tone: 'thunder', hover: 'meteogram.chart.hoverThunder', unit: '%', mode: 'exact' })
    expect(row.x).toHaveLength(121)
    expect(readoutValue(row, at(41))).toBe(70)
    expect(readoutValue(row, at(7))).toBe(1)
    expect(readoutValue(row, at(8))).toBe(0)
    // 0 is a value: a dry hour of a panel that is shown says 0
    expect(readoutValue(row, at(50))).toBe(0)
    // an instant that is no stamp has none
    expect(readoutValue(row, at(41) + 30 * 60_000)).toBeNull()
    expect(m.series.some(s => s.id === 'thunder')).toBe(false)
  })

  it('stands in the layout at its own height, between the precipitation and the cloud cover', () => {
    const layout = chartLayout(model().panels, true)
    expect(layout.rows.map(row => row.id)).toEqual(['wind', 'precip', 'thunder', 'cloud', 'temp', 'pressure'])
    expect(PANEL_HEIGHT.thunder).toBe(44)
    const [precip, thunder] = [layout.rows[1]!, layout.rows[2]!]
    expect(thunder.top).toBe(precip.top + precip.height + 14)
  })

  it('writes the probability in the unit of the answer: a fraction of 1 is a hundred percent, and an okta an eighth', () => {
    const fractions = model({ units: { ...FORECAST_UNITS, probability_thunder_last_1h: '-', cloud_cover_total: '-' }, series: new Map([...series({ thunder: () => 0 })].map(([name, s]) => [name, name === 'probability_thunder_last_1h' ? { x: s.x, y: s.y.map((_, i) => i === 40 ? 0.6 : 0) } : s])) })
    // the unit of a fraction is the one the answer states for the cloud cover and the humidity before it
    expect(fractions.thunder!.cells).toHaveLength(1)
    expect(fractions.axes.thunder!.range).toEqual([0, 1])
  })
})

describe('the table and the sentence of the thunderstorm band', () => {
  const context = (overrides: Partial<Parameters<typeof meteogramTable>[1]> = {}) => ({ panels: { ...all, temp: false, wind: false, cloud: false, pressure: false, snow: false }, horizonHours: null, zone: 'UTC', formatLanguage: 'en-GB', locale: 'en', units: meteogramUnits(FORECAST_UNITS, t), t, widget: false, ...overrides })

  it('has a column of the hourly probability with the precipitation\'s, whether or not an hour reaches the threshold', () => {
    for (const thunder of [storm, () => 1]) {
      const table = meteogramTable(series({ thunder }), context())!
      expect(table.columns.at(-1)).toBe('meteogram.chart.seriesThunder unit=%')
    }
    // and none for a forecast without it, or with the precipitation off
    expect(meteogramTable(series(), context())!.columns.join()).not.toContain('Thunder')
    expect(meteogramTable(series({ thunder: storm }), context({ panels: { ...all, precip: false, temp: true } }))!.columns.join()).not.toContain('Thunder')
  })

  it('writes the probability of each hour: 70 at the hour of the peak, and a dash where there is none', () => {
    const table = meteogramTable(series({ thunder: storm }), context({ horizonHours: 48 }))!
    const column = table.columns.length - 1
    const rows = table.rows
    const peak = rows.find(row => row[column] === '70')
    expect(peak).toBeDefined()
    expect(rows.filter(row => row[column] !== '–').length).toBe(49)
  })

  it('says the likeliest hour in the description of the chart, and that there is none where the chart draws no band', () => {
    expect(meteogramTable(series({ thunder: storm }), context())!.summary).toContain('meteogram.chart.summaryThunder max=70% time=')
    expect(meteogramTable(series({ thunder: () => 2 }), context())!.summary).toContain('meteogram.chart.summaryNoThunder threshold=10%')
    // nothing of it where the forecast has none, or the precipitation is off
    expect(meteogramTable(series(), context())!.summary).not.toContain('Thunder')
    expect(meteogramTable(series({ thunder: storm }), context({ panels: { ...all, precip: false } }))!.summary).not.toContain('Thunder')
  })

  it('counts the horizon in the sentence as the chart does', () => {
    expect(meteogramTable(series({ thunder: storm }), context({ horizonHours: 24 }))!.summary).toContain('summaryNoThunder')
    expect(meteogramTable(series({ thunder: storm }), context({ horizonHours: 72 }))!.summary).toContain('summaryThunder max=70%')
  })
})

describe('the thunderstorm band drawn', () => {
  const echarts = loadEcharts()
  const LIGHT = { ...EMPTY_CHART_THEME, text: 'rgb(15, 23, 43)', textStrong: 'rgb(0, 0, 0)', textMuted: 'rgb(90, 100, 120)', zeroline: 'rgb(90, 100, 120)' }
  const DARK = { ...LIGHT, dark: true, text: 'rgb(226, 232, 240)', textStrong: 'rgb(255, 255, 255)' }

  function build(theme: typeof LIGHT = LIGHT, overrides: Parameters<typeof model>[0] = {}) {
    const m = model(overrides)
    const layout = chartLayout(m.panels, m.symbols.length > 0)
    const gutterLeft = gutterLeftFor(m, 'en')
    const plotPx = plotWidthFor(800, (m.maxTime - m.minTime) / HOUR_MS, gutterLeft)
    const built: OptionInput = {
      model: m,
      theme,
      layout,
      outerPx: plotPx + gutterLeft + GUTTER_RIGHT,
      plotPx,
      gutterLeft,
      window: { start: m.minTime, end: m.maxTime },
      now: null,
      fontFamily: 'sans-serif',
      locale: 'en',
      hourLabel: hourFormatter('en-GB', 'Europe/Berlin'),
      symbolUrl: (symbol, dark) => `/s/${dark ? 'd' : 'l'}/${symbol}.svg`,
    }
    return { m, layout, built, option: buildMeteogramOption(built) as any }
  }
  const drawn = (b: ReturnType<typeof build>) => {
    const chart = echarts.init(null as any, null, { renderer: 'svg', ssr: true, width: b.built.outerPx, height: b.layout.height })
    chart.setOption(b.option)
    const svg = chart.renderToSVGString()
    const px = (time: number, grid: number) => chart.convertToPixel({ xAxisIndex: grid } as any, time) as unknown as number
    const py = (value: number, grid: number) => chart.convertToPixel({ yAxisIndex: grid } as any, value) as unknown as number
    return { svg, px, py }
  }

  it('has a grid of 44 px and an axis in the label colour of the band, and the zoom over its x axis too', () => {
    const { option } = build()
    // the header, then wind, precip, thunder, cloud, temp, pressure
    expect(option.grid.map((g: any) => g.height).slice(1)).toEqual([124, 88, 44, 80, 156, 84])
    expect(option.yAxis[3].axisLabel.color).toBe(SERIES_LABEL.fuchsia.light)
    expect([option.yAxis[3].min, option.yAxis[3].max]).toEqual([0, 100])
    expect(build(DARK).option.yAxis[3].axisLabel.color).toBe(SERIES_LABEL.fuchsia.dark)
    expect(option.dataZoom[0].xAxisIndex).toEqual([0, 1, 2, 3, 4, 5, 6])
  })

  it('has no series for a forecast without a risk, and so no extra grid', () => {
    const { option } = build(LIGHT, { series: series({ thunder: () => 1 }) })
    expect(option.series.some((s: any) => s.id === 'thunder')).toBe(false)
    expect(option.grid).toHaveLength(6)
  })

  it('draws a custom series of the cells in the grid of the band, each with its window, value and class', () => {
    const { option, m } = build()
    const band = option.series.find((s: any) => s.id === 'thunder')
    expect(band).toMatchObject({ type: 'custom', xAxisIndex: 3, yAxisIndex: 3, silent: true, clip: true })
    expect(band.data).toEqual(m.thunder!.cells.map(cell => [cell.start, cell.end, cell.value, cell.level]))
  })

  /** The boxes and the opacity of the rects painted in `colour`: `M300.3 358.7l5.4 0l0 5.3l-5.4 0Z` is 5.4 px wide and 5.3 high from y 358.7 */
  const bars = (svg: string, colour: string) => [...svg.matchAll(new RegExp(`<path d="M([\\d.]+) ([\\d.]+)l([\\d.]+) 0l0 ([\\d.]+)l[^"]*" fill="${colour}"(?: fill-opacity="([\\d.]+)")?`, 'g'))]
    .map(match => ({ left: Number(match[1]), top: Number(match[2]), width: Number(match[3]), height: Number(match[4]), opacity: Number(match[5] ?? 1) }))

  it('draws each hour as a bar over the hour it covers, as high as its probability and in the shade of its class', () => {
    const b = build()
    const { svg, px, py } = drawn(b)
    const found = bars(svg, toneColor('thunder', false))
    const grid = 1 + b.m.panels.indexOf('thunder')
    const cells = b.m.thunder!.cells
    expect(found).toHaveLength(cells.length)
    cells.forEach((cell, i) => {
      const box = found[i]!
      // centred over (T - 1 h, T], 0.9 of an hour wide
      expect(box.left + box.width / 2, `hour ending ${new Date(cell.end).toISOString()}`).toBeCloseTo(px(cell.start + HOUR_MS / 2, grid), 0)
      expect(box.width).toBeCloseTo(0.9 * (px(cell.end, grid) - px(cell.start, grid)), 0)
      // as high as the axis says, from the foot of the panel
      expect(box.height).toBeCloseTo(py(0, grid) - py(cell.value, grid), 0)
      expect(box.opacity).toBeCloseTo(THUNDER_ALPHA[cell.level], 2)
    })
    // the 70 % is higher than the 35 %, which is higher than the 12 %: two cues that agree
    expect(found[2]!.height).toBeGreaterThan(found[1]!.height)
    expect(found[1]!.height).toBeGreaterThan(found[0]!.height)
    expect(found[2]!.opacity).toBeGreaterThan(found[1]!.opacity)
    expect(found[1]!.opacity).toBeGreaterThan(found[0]!.opacity)
  })

  it('draws no bar for the hours under the threshold', () => {
    const { svg } = drawn(build())
    // 120 hours, 5 hours of 1 % and 4 of the storm: four bars
    expect(bars(svg, toneColor('thunder', false))).toHaveLength(4)
  })

  it('titles the band in its colour, with the unit on a line of its own', () => {
    const { svg } = drawn(build())
    const turned = [...svg.matchAll(/<text[^>]*transform="matrix\(0,-1,1,0,([\d.-]+),([\d.-]+)\)"[^>]*fill="([^"]*)"[^>]*>([^<]*)<\/text>/g)].map(match => ({ colour: match[3], text: match[4] }))
    expect(turned).toEqual(expect.arrayContaining([
      { colour: SERIES_LABEL.fuchsia.light, text: 'meteogram.chart.axisThunder unit=' },
      { colour: SERIES_LABEL.fuchsia.light, text: '%' },
    ]))
  })

  // WCAG 1.4.11: a bar is a graphic that carries the information, 3:1 on the paper (the card) even in the lightest shade, and the text that names it 4.5:1
  describe.each([['light', false, '#ffffff'], ['dark', true, '#12233f']] as const)('in the %s scheme', (_name, dark, paper) => {
    const channels = (hex: string) => [1, 3, 5].map(i => Number.parseInt(hex.slice(i, i + 2), 16))
    const luminance = (rgb: number[]) => {
      const [r, g, b] = rgb.map(c => c / 255).map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
      return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
    }
    const contrast = (a: number[], b: number[]) => {
      const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
      return (hi! + 0.05) / (lo! + 0.05)
    }
    /** The colour of a bar of the opacity over the paper */
    const over = (colour: string, alpha: number) => channels(colour).map((c, i) => alpha * c + (1 - alpha) * channels(paper)[i]!)

    it.each([1, 2, 3] as const)('draws the shade of class %s at 3:1 or more on the paper', (level) => {
      expect(contrast(over(toneColor('thunder', dark), THUNDER_ALPHA[level]), channels(paper))).toBeGreaterThanOrEqual(3)
    })

    it('writes the axis\' text at 4.5:1 or more on the paper', () => {
      expect(contrast(channels(SERIES_LABEL.fuchsia[dark ? 'dark' : 'light']), channels(paper))).toBeGreaterThanOrEqual(4.5)
    })

    it('draws the bars in the colour of the scheme', () => {
      const svg = drawn(build(dark ? DARK : LIGHT)).svg
      expect(bars(svg, toneColor('thunder', dark))).toHaveLength(4)
    })
  })
})
