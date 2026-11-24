import type { ModelInput } from '../../app/utils/meteogram-model'
import type { OptionInput } from '../../app/utils/meteogram-option'
import * as SunCalc from 'suncalc'
import { describe, expect, it, vi } from 'vitest'
import { EMPTY_CHART_THEME, SERIES_LABEL } from '../../app/utils/chart-theme'
import { loadEcharts } from '../../app/utils/echarts-loader'
import { hourFormatter } from '../../app/utils/format'
import { METEOGRAM_SERIES, meteogramSnowQuery, meteogramUnitsKey, MOSMIX_SNOW_METEOGRAM, snowStationsQuery } from '../../app/utils/meteogram'
import { chartLayout, GUTTER_RIGHT, HOUR_MS, PANEL_HEIGHT, plotWidthFor } from '../../app/utils/meteogram-geometry'
import { buildMeteogramModel, readoutValue } from '../../app/utils/meteogram-model'
import { buildMeteogramOption, gutterLeftFor, LABEL_MARGIN, LABEL_SLACK_PX, labelWidthFor, labelWidthOf, tickFormatter, tickInterval, tickLabelsOf, TITLE_LEFT, TITLE_LINE_PX, TITLE_LINES, TITLE_TO_LABELS, toneColor } from '../../app/utils/meteogram-option'
import { buildSeries, isSnowStep, snowSeries } from '../../app/utils/meteogram-series'
import { meteogramTable } from '../../app/utils/meteogram-summary'
import { meteogramUnits, snowChanceAmount } from '../../app/utils/meteogram-units'
import { forgetSnowStations, SNOW_STATIONS_TTL_MS, snowStationIds } from '../../app/utils/snow-stations'
import { fromCanonical, toCanonical } from '../../app/utils/units'
import { parameters } from '../../i18n/glossary/en'
import { FORECAST_START, FORECAST_UNITS, forecastValues, SNOW_UNITS, snowForecastValues } from '../helpers/meteogram-forecast'

// The snow panel of the forecast (GH-4091): MOSMIX-SNOW's new snow as bars, its snow depth as a line and the chance of more than
// 10 cm as a line, for the stations that have a forecast of it, at the 3-hourly steps DWD gives all three at.

// a name carries the unit; the title of the chance carries the threshold, as the catalogue's "> {amount} new" does
const NB = '\u00A0'
const t = (key: string, named?: Record<string, unknown>) => key === 'meteogram.chart.axisSnowChance' ? `>${named?.amount} new` : key + (named?.unit ? ` ${named.unit}` : '')
const UNITS = { ...FORECAST_UNITS, ...SNOW_UNITS }
const t0 = new Date(FORECAST_START).getTime()
const all = { temp: true, wind: true, precip: true, snow: true, cloud: true, pressure: true }

/** The forecast and the snow forecast as the page hands them over: the snow clipped to the forecast and joined to it */
function joined(options: { snow?: ReturnType<typeof snowForecastValues>, hours?: number } = {}) {
  const forecast = buildSeries(forecastValues({ hours: options.hours ?? 120 }) as any)
  const span = { min: t0, max: t0 + (options.hours ?? 120) * HOUR_MS }
  const snow = snowSeries((options.snow ?? snowForecastValues({ offGrid: true })) as any, span)
  return new Map([...forecast, ...snow])
}

function input(overrides: Partial<Omit<ModelInput, 'units'>> & { units?: Record<string, string> } = {}): ModelInput {
  const { units = UNITS, ...rest } = overrides
  return {
    series: joined(),
    panels: all,
    horizonHours: null,
    zone: 'Europe/Berlin',
    language: 'en-GB',
    coords: { latitude: 47.4, longitude: 11.0 },
    sun: SunCalc as any,
    units: meteogramUnits(units, t),
    t,
    ...rest,
  }
}
const model = (overrides: Parameters<typeof input>[0] = {}) => buildMeteogramModel(input(overrides))!

describe('the steps of the snow forecast', () => {
  it('are the 00, 03, ..., 21 UTC ones, on the hour', () => {
    expect([0, 3, 6, 9, 12, 15, 18, 21].map(hour => isSnowStep(new Date(Date.UTC(2026, 10, 14, hour))))).toEqual(Array.from({ length: 8 }).fill(true))
    expect([1, 2, 4, 5, 7, 11, 13, 22, 23].map(hour => isSnowStep(new Date(Date.UTC(2026, 10, 14, hour))))).toEqual(Array.from({ length: 9 }).fill(false))
    // a stamp not on the hour is no step, and the steps are those of UTC and not of the station's clock
    expect(isSnowStep(new Date(Date.UTC(2026, 10, 14, 3, 30)))).toBe(false)
    expect(isSnowStep(new Date('2026-11-14T04:00:00+01:00'))).toBe(true)
  })

  it('are all that is kept of the three series, whatever else the run has stamped', () => {
    const values = snowForecastValues({ offGrid: true })
    // 48 hours: a value of each of the three series at every hour, where only every third is a step
    expect(values).toHaveLength(49 * 3)
    const kept = snowSeries(values as any, null)
    expect([...kept.keys()].sort()).toEqual([...MOSMIX_SNOW_METEOGRAM.parameters].sort())
    for (const series of kept.values()) {
      expect(series.x).toHaveLength(17)
      expect(series.x.every(isSnowStep)).toBe(true)
    }
    // the values of the off-steps are 99, 999 and 77: none of them is drawn
    expect(Math.max(...kept.get('snow_depth_new_last_3h')!.y)).toBeLessThan(10)
    expect(Math.max(...kept.get('snow_depth')!.y)).toBeLessThan(500)
    expect(Math.max(...kept.get('probability_snow_depth_new_gt_10cm_last_24h')!.y)).toBeLessThanOrEqual(100)
  })

  it('are the same for a run that has none between them', () => {
    expect(snowSeries(snowForecastValues() as any, null).get('snow_depth')!.x).toHaveLength(17)
  })

  it('leave out another parameter, a value that is none, and a series with no step', () => {
    const values = [
      ...snowForecastValues({ without: ['snow_depth'] }),
      { ...snowForecastValues()[0]!, parameter: 'temperature_air_2m' },
    ]
    values.find(v => v.parameter === 'snow_depth_new_last_3h')!.value = null
    const kept = snowSeries(values as any, null)
    expect(kept.has('snow_depth')).toBe(false)
    expect(kept.has('temperature_air_2m')).toBe(false)
    expect(kept.get('snow_depth_new_last_3h')!.x).toHaveLength(16)
    expect(snowSeries([], null).size).toBe(0)
  })

  it('are cut to the span of the forecast they join, so that the chart keeps its first and last hour', () => {
    // the run starts a day before the forecast does and reaches past it
    const span = { min: t0 + 6 * HOUR_MS, max: t0 + 24 * HOUR_MS }
    const kept = snowSeries(snowForecastValues() as any, span)
    const times = kept.get('snow_depth')!.x.map(d => d.getTime())
    expect(times[0]).toBe(span.min)
    expect(times.at(-1)).toBe(span.max)
    expect(times).toHaveLength(7)
  })
})

describe('the request of the snow forecast', () => {
  it('is for the dataset snow of dwd/mosmix, apart from the forecast\'s own, in the units the settings choose', () => {
    const query = meteogramSnowQuery('Z914', { units: { length_short: 'millimeter' }, convertUnits: true })
    expect(query).toMatchObject({ provider: 'dwd', network: 'mosmix', stations: 'Z914', shape: 'long', with_metadata: 'true', convert_units: 'true' })
    expect(query.parameters).toBe('hourly/snow/snow_depth_new_last_3h,hourly/snow/snow_depth,hourly/snow/probability_snow_depth_new_gt_10cm_last_24h')
    expect(JSON.parse(query.unit_targets!).length_short).toBe('millimeter')
  })

  it('asks for the stations of the dataset once and for all of them: the 15 with a snow forecast', () => {
    expect(snowStationsQuery()).toEqual({ provider: 'dwd', network: 'mosmix', parameters: 'hourly/snow', all: 'true' })
  })

  it('names three series that are canonical parameters, which the glossary holds to the backend', () => {
    for (const name of [...METEOGRAM_SERIES.snowNew, ...METEOGRAM_SERIES.snowDepth, ...METEOGRAM_SERIES.snowChance])
      expect(Object.hasOwn(parameters, name), name).toBe(true)
  })

  it('is fetched again for a change of the unit of the snow, and not for another length', () => {
    const key = (units: Record<string, string>) => meteogramUnitsKey({ units, convertUnits: true })
    expect(key({ length_short: 'meter' })).not.toBe(key({}))
    expect(key({ length_long: 'mile' })).toBe(key({}))
  })
})

describe('the units of the snow', () => {
  it('converts the lengths the settings offer to centimetres, which the thresholds are written in', () => {
    expect(toCanonical('length_short', 'm', 1.2)).toBe(120)
    expect(toCanonical('length_short', 'mm', 30)).toBe(3)
    expect(fromCanonical('length_short', 'mm', 10)).toBe(100)
    expect(fromCanonical('length_short', 'm', 10)).toBeCloseTo(0.1, 9)
    expect(toCanonical('length_short', 'km', 0.001)).toBe(100)
    expect(toCanonical('length_short', 'mi', 1)).toBe(160_934.4)
  })

  it('writes the threshold of the chance in the unit of the answer', () => {
    expect(snowChanceAmount(meteogramUnits(UNITS, t))).toBe(`10${NB}cm`)
    expect(snowChanceAmount(meteogramUnits({ ...UNITS, snow_depth: 'mm', snow_depth_new_last_3h: 'mm' }, t))).toBe(`100${NB}mm`)
    expect(snowChanceAmount(meteogramUnits({ ...UNITS, snow_depth: 'm', snow_depth_new_last_3h: 'm' }, t))).toBe(`0.1${NB}m`)
  })
})

describe('the snow panel of the model', () => {
  it('is three plots after the precipitation, for a forecast that has the snow series', () => {
    const m = model()
    expect(m.panels).toEqual(['wind', 'precip', 'snow', 'snowDepth', 'snowChance', 'cloud', 'temp', 'pressure'])
    const ids = (panel: string) => m.series.filter(s => s.panel === panel).map(s => s.id)
    expect(ids('snow')).toEqual(['snowNew'])
    expect(ids('snowDepth')).toEqual(['snowDepth'])
    expect(ids('snowChance')).toEqual(['snowChance'])
    expect(m.series.find(s => s.id === 'snowNew')).toMatchObject({ kind: 'bar', tone: 'snowNew', quantity: 'length_short' })
    expect(m.series.find(s => s.id === 'snowDepth')).toMatchObject({ kind: 'line', tone: 'snowDepth' })
    expect(m.series.find(s => s.id === 'snowChance')).toMatchObject({ kind: 'line', tone: 'snowChance', quantity: 'fraction' })
  })

  it('is absent for a forecast that has no snow series: another station looks as it did', () => {
    const m = model({ series: buildSeries(forecastValues({ hours: 120 }) as any) })
    expect(m.panels).toEqual(['wind', 'precip', 'cloud', 'temp', 'pressure'])
    expect(m.series.some(s => s.id.startsWith('snow') && s.panel !== 'precip')).toBe(false)
    expect(Object.keys(m.axes).some(panel => panel.startsWith('snow'))).toBe(false)
  })

  it('is absent where the toggle is off, all three plots of it', () => {
    expect(model({ panels: { ...all, snow: false } }).panels).toEqual(['wind', 'precip', 'cloud', 'temp', 'pressure'])
    expect(model({ panels: { ...all, snow: true, precip: false, wind: false, cloud: false, temp: false, pressure: false } }).panels).toEqual(['snow', 'snowDepth', 'snowChance'])
  })

  it('has a plot for each series the forecast has: the chance alone makes one', () => {
    const m = model({ series: joined({ snow: snowForecastValues({ without: ['snow_depth', 'snow_depth_new_last_3h'] }) }) })
    expect(m.panels).toContain('snowChance')
    expect(m.panels).not.toContain('snow')
    expect(m.panels).not.toContain('snowDepth')
  })

  it('draws a bar for every step, none of height where it did not snow, and the readout says 0 for it', () => {
    const m = model()
    const bars = m.series.find(s => s.id === 'snowNew')!
    expect(bars.data).toHaveLength(17)
    expect(bars.data.filter(([, amount]) => amount === null).length).toBeGreaterThan(5)
    expect(bars.data.filter(([, amount]) => amount !== null).every(([, amount]) => amount! > 0)).toBe(true)
    const readout = m.readout.find(r => r.id === 'snowNew')!
    expect(readoutValue(readout, t0)).toBe(0)
    expect(readoutValue(readout, t0 + 15 * HOUR_MS)).toBeGreaterThan(0)
  })

  it('reads the three values for an hour that has them, and none for the hours between', () => {
    const m = model()
    const at = (id: string, hours: number) => readoutValue(m.readout.find(r => r.id === id)!, t0 + hours * HOUR_MS)
    for (const id of ['snowNew', 'snowDepth', 'snowChance'])
      expect(at(id, 15), id).not.toBeNull()
    // the hours between two steps have no value of the snow, which the line is not read at either
    for (const id of ['snowNew', 'snowDepth', 'snowChance']) {
      expect(at(id, 16), id).toBeNull()
      expect(at(id, 17), id).toBeNull()
    }
    expect(at('snowChance', 15)).toBe(36)
    expect(m.readout.find(r => r.id === 'snowDepth')).toMatchObject({ mode: 'exact', panel: 'snowDepth', unit: 'cm' })
    expect(m.readout.find(r => r.id === 'snowChance')).toMatchObject({ unit: '%' })
  })

  it('has axes of their own, whatever size the numbers are: the depth does not flatten the new snow', () => {
    const { axes } = model()
    expect(axes.snow!.range[1]).toBeLessThan(10)
    expect(axes.snowDepth!.range[1]).toBeGreaterThan(120)
    expect(axes.snowChance!.range).toEqual([0, 100])
    // a tenth of a centimetre of new snow is written; the depth and the chance are whole numbers
    expect([axes.snow!.decimals, axes.snowDepth!.decimals, axes.snowChance!.decimals]).toEqual([1, 0, 0])
    expect(axes.snow).toMatchObject({ label: 'indigo', title: 'meteogram.chart.axisSnowNew\ncm' })
    expect(axes.snowDepth).toMatchObject({ label: 'teal', title: 'meteogram.chart.axisSnowDepth\ncm' })
    // the threshold on the first line and the unit of the chance on the second, like every other title
    expect(axes.snowChance).toMatchObject({ label: 'gold', title: `>10${NB}cm new\n%` })
  })

  it('writes the threshold in the unit the answer has', () => {
    const m = model({ units: { ...UNITS, snow_depth: 'mm', snow_depth_new_last_3h: 'mm' } })
    expect(m.axes.snowChance!.title).toBe(`>100${NB}mm new\n%`)
    expect(m.series.find(s => s.id === 'snowDepth')!.straight).toBe(true)
    expect(m.series.find(s => s.id === 'snowChance')!.straight).toBe(true)
  })

  it('does not move the chart\'s first and last hour, which are the forecast\'s', () => {
    const without = buildMeteogramModel(input({ series: buildSeries(forecastValues({ hours: 120 }) as any) }))!
    const withSnow = model()
    expect([withSnow.minTime, withSnow.maxTime]).toEqual([without.minTime, without.maxTime])
    expect(withSnow.stamps).toEqual(without.stamps)
  })

  it('cuts the snow at the horizon, as every series', () => {
    const m = model({ horizonHours: 24 })
    expect(m.series.find(s => s.id === 'snowDepth')!.data.at(-1)![0]).toBe(t0 + 24 * HOUR_MS)
  })

  it('has the plots at their own heights in the layout, one grid for each', () => {
    const layout = chartLayout(model().panels, true)
    expect(layout.rows.map(row => row.id)).toEqual(['wind', 'precip', 'snow', 'snowDepth', 'snowChance', 'cloud', 'temp', 'pressure'])
    expect(layout.rows.map(row => row.height)).toEqual([124, 88, 72, 72, 72, 80, 156, 84])
    expect(PANEL_HEIGHT.snow + PANEL_HEIGHT.snowDepth + PANEL_HEIGHT.snowChance).toBe(216)
  })

  it('is in the table of the values with a column for each series, the three steps of an hour alone having a value', () => {
    const series = joined()
    const table = meteogramTable(series, { panels: { ...all, temp: false, wind: false, precip: false, cloud: false, pressure: false }, horizonHours: 24, zone: 'UTC', formatLanguage: 'en-GB', locale: 'en', units: meteogramUnits(UNITS, t), t, widget: false })!
    expect(table.columns).toHaveLength(4)
    expect(table.columns.slice(1)).toEqual(['meteogram.chart.seriesSnowNew cm', 'meteogram.chart.seriesSnowDepth cm', 'meteogram.chart.seriesSnowChance %'])
    // a row for each of the 3-hourly steps of the first 24 hours: 9
    expect(table.rows).toHaveLength(9)
  })
})

describe('the snow panel drawn', () => {
  const echarts = loadEcharts()
  const LIGHT = { ...EMPTY_CHART_THEME, text: 'rgb(15, 23, 43)', textStrong: 'rgb(0, 0, 0)', textMuted: 'rgb(90, 100, 120)', zeroline: 'rgb(90, 100, 120)' }
  const DARK = { ...LIGHT, dark: true, text: 'rgb(226, 232, 240)', textStrong: 'rgb(255, 255, 255)' }

  function build(theme: typeof LIGHT = LIGHT, width = 800, overrides: Parameters<typeof model>[0] = {}) {
    const m = model(overrides)
    const layout = chartLayout(m.panels, m.symbols.length > 0)
    const gutterLeft = gutterLeftFor(m, 'en')
    const plotPx = plotWidthFor(width, (m.maxTime - m.minTime) / HOUR_MS, gutterLeft)
    const built: OptionInput = {
      model: m,
      theme,
      layout,
      outerPx: plotPx + gutterLeft + GUTTER_RIGHT,
      plotPx,
      gutterLeft,
      // the whole forecast in the window, so that a pixel is a fixed share of the forecast
      window: { start: m.minTime, end: m.maxTime },
      now: null,
      fontFamily: 'sans-serif',
      locale: 'en',
      hourLabel: hourFormatter('en-GB', 'Europe/Berlin'),
      symbolUrl: (symbol, dark) => `/s/${dark ? 'd' : 'l'}/${symbol}.svg`,
    }
    return { m, layout, built, option: buildMeteogramOption(built) as any }
  }
  const draw = (b: ReturnType<typeof build>) => {
    const chart = echarts.init(null as any, null, { renderer: 'svg', ssr: true, width: b.built.outerPx, height: b.layout.height })
    chart.setOption(b.option)
    const svg = chart.renderToSVGString()
    chart.dispose()
    return svg
  }
  /** The chart drawn, with the pixel an instant is at in the plot of a grid (0 is the header's, 1 the first plot's) */
  const drawn = (b: ReturnType<typeof build>) => {
    const chart = echarts.init(null as any, null, { renderer: 'svg', ssr: true, width: b.built.outerPx, height: b.layout.height })
    chart.setOption(b.option)
    const svg = chart.renderToSVGString()
    const px = (time: number, grid: number) => chart.convertToPixel({ xAxisIndex: grid } as any, time) as unknown as number
    return { svg, px, chart }
  }
  /** The boxes (left, width) of the bars painted in `colour` in the SVG: `M136.9 392l15.9 0l0 -16.1l-15.9 0Z` */
  const barBoxes = (svg: string, colour: string) => [...svg.matchAll(new RegExp(`<path d="M([\\d.]+) [\\d.]+l([\\d.]+) 0[^"]*" fill="${colour}"`, 'g'))].map(match => ({ left: Number(match[1]), width: Number(match[2]) }))

  it('has a grid and an axis for each plot, in the series\' own label colours', () => {
    const { option } = build()
    // the header, then wind, precip, snow, snowDepth, snowChance, cloud, temp, pressure
    expect(option.grid.map((g: any) => g.height).slice(1)).toEqual([124, 88, 72, 72, 72, 80, 156, 84])
    expect(option.yAxis[3].axisLabel.color).toBe(SERIES_LABEL.indigo.light)
    expect(option.yAxis[4].axisLabel.color).toBe(SERIES_LABEL.teal.light)
    expect(option.yAxis[5].axisLabel.color).toBe(SERIES_LABEL.gold.light)
    expect(build(DARK).option.yAxis[3].axisLabel.color).toBe(SERIES_LABEL.indigo.dark)
    expect(option.dataZoom[0].xAxisIndex).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8])
  })

  // GH-4091: ECharts 6 makes room for the bars at the ends of a value axis that carries them (`containShape`), which widened the x
  // extent of the plot of the bars and put its hours up to 15 px off the others'; the bars of a step were centred on its end
  it('has no axis that makes room for its bars: the same instant is at the same pixel in every plot', () => {
    const b = build()
    expect(b.option.xAxis.every((axis: any) => axis.containShape === false)).toBe(true)
    const { px } = drawn(b)
    const span = b.m.maxTime - b.m.minTime
    for (const time of [b.m.minTime, b.m.minTime + 5 * HOUR_MS, b.m.minTime + 30 * HOUR_MS, b.m.maxTime]) {
      const expected = b.built.gutterLeft + (time - b.m.minTime) / span * b.built.plotPx
      const xs = Array.from({ length: b.option.grid.length }, (_, grid) => px(time, grid))
      for (const [grid, x] of xs.entries())
        expect(x, `${new Date(time).toISOString()} in grid ${grid}`).toBeCloseTo(expected, 3)
    }
  })

  it('draws a bar of the new snow over the 3 hours it covers: centred on the middle of them, 0.9 of them wide', () => {
    const b = build()
    const { svg, px } = drawn(b)
    const bars = barBoxes(svg, toneColor('snowNew', false))
    // a bar for each step it snowed in, over (T - 3 h, T]
    const steps = b.m.readout.find(r => r.id === 'snowNew')!.x.filter((time, i) => b.m.readout.find(r => r.id === 'snowNew')!.y[i]! > 0)
    expect(bars).toHaveLength(steps.length)
    expect(steps.length).toBeGreaterThan(3)
    steps.forEach((time, i) => {
      const grid = 1 + b.m.panels.indexOf('snow')
      const centre = bars[i]!.left + bars[i]!.width / 2
      expect(centre, `bar of ${new Date(time).toISOString()}`).toBeCloseTo(px(time - 1.5 * HOUR_MS, grid), 0)
      expect(bars[i]!.width).toBeCloseTo(0.9 * (px(time, grid) - px(time - 3 * HOUR_MS, grid)), 0)
    })
  })

  it('draws a bar of the precipitation over the hour it covers: centred on T - 30 minutes, 0.9 of an hour wide', () => {
    const b = build()
    const { svg, px } = drawn(b)
    const grid = 1 + b.m.panels.indexOf('precip')
    let counted = 0
    for (const id of ['rain', 'mixed', 'snow'] as const) {
      const readout = b.m.readout.find(r => r.id === id)!
      const steps = readout.x.filter((_, i) => readout.y[i]! > 0)
      const bars = barBoxes(svg, toneColor(id, false))
      expect(bars, id).toHaveLength(steps.length)
      steps.forEach((time, i) => {
        counted++
        expect(bars[i]!.left + bars[i]!.width / 2, `${id} of ${new Date(time).toISOString()}`).toBeCloseTo(px(time - 0.5 * HOUR_MS, grid), 0)
        expect(bars[i]!.width).toBeCloseTo(0.9 * (px(time, grid) - px(time - HOUR_MS, grid)), 0)
      })
    }
    expect(counted).toBeGreaterThan(5)
  })

  it('writes the axes of the snow in the decimals of the unit: metres are not rounded to a whole number', () => {
    const scaled = joined().entries()
    const series = new Map([...scaled].map(([name, s]) => [name, name.startsWith('snow_depth') ? { x: s.x, y: s.y.map(v => v / 100) } : s]))
    const { option, m } = build(LIGHT, 800, { series, units: { ...UNITS, snow_depth: 'm', snow_depth_new_last_3h: 'm' } })
    expect([m.axes.snow!.decimals, m.axes.snowDepth!.decimals]).toEqual([3, 2])
    const label = (index: number, value: number) => option.yAxis[index].axisLabel.formatter(value)
    expect(label(3, 0.025)).toBe('0.025')
    expect(label(4, 1.75)).toBe('1.75')
    // in millimetres a whole number, in centimetres a tenth for the new snow and a whole number for the depth
    expect(build().m.axes.snow!.decimals).toBe(1)
  })

  it('writes the ticks of the cloud and the chance in the decimals of the unit: 0.5 under the fraction is not "1" (GH-4197)', () => {
    const fractionUnits = (unit: string) => ({ ...UNITS, ...Object.fromEntries(['cloud_cover_total', 'cloud_cover_below_2km', 'cloud_cover_between_2km_and_7km', 'cloud_cover_above_7km', 'probability_snow_depth_new_gt_10cm_last_24h'].map(name => [name, unit])) })
    const ticks = (unit: string) => {
      const { axes } = model({ units: fractionUnits(unit) })
      return [axes.cloud!, axes.snowChance!].map(axis => ({ decimals: axis.decimals, range: axis.range, ticks: [axis.range[0], (axis.range[0] + axis.range[1]) / 2, axis.range[1]].map(tickFormatter(axis)), labels: tickLabelsOf(axis) }))
    }
    // the axis is [0, 1] and its middle gridline is 0.5: written with no decimals it would read "1", the same as the top
    for (const axis of ticks('-')) {
      expect(axis.range).toEqual([0, 1])
      expect(axis.decimals).toBe(1)
      expect(axis.ticks).toEqual(['0', '0.5', '1'])
      expect(axis.labels).toEqual(['0', '0.5'])
    }
    // a percent has none: 0, 50 and 100
    for (const axis of ticks('%')) {
      expect(axis.decimals).toBe(0)
      expect(axis.ticks).toEqual(['0', '50', '100'])
    }
    // the okta: 0, 4 and 8, for the cloud cover and the chance alike
    for (const axis of ticks('1/8')) {
      expect(axis.decimals).toBe(0)
      expect(axis.ticks).toEqual(['0', '4', '8'])
    }
  })

  it('writes the pressure ticks in the decimals of the unit: 101.5 kPa is not "102" (GH-4212)', () => {
    // the pressure of the forecast, replaced by a flat run from `low` to `high` in `unit` (the axis is that ± 2 hPa)
    const pressure = (unit: string, low: number, high: number) => {
      const series = joined({ hours: 24 })
      const x = series.get('pressure_air_sea_level')!.x
      series.set('pressure_air_sea_level', { x, y: x.map((_, i) => i === 0 ? low : i === 1 ? high : (low + high) / 2) })
      const { axes } = model({ series, units: { ...UNITS, pressure_air_sea_level: unit } })
      return axes.pressure!
    }
    // the ticks as the chart draws them: the multiples of the step in the range, as written and as they are
    const ticksOf = (axis: ReturnType<typeof pressure>) => {
      const [min, max] = axis.range
      const step = tickInterval(max - min, axis.splits)
      const format = tickFormatter(axis)
      const out: { value: number, label: string }[] = []
      for (let k = Math.ceil(min / step - 1e-9); k * step < max + step * 1e-9; k++)
        out.push({ value: k * step, label: format(k * step) })
      return out
    }

    // the range of the issue: 100.9 to 101.9 (the data 101.1 to 101.7), whose middle tick is 101.5
    const issue = pressure('kPa', 101.1, 101.7)
    expect(issue.decimals).toBe(1)
    expect(issue.range[0]).toBeCloseTo(100.9, 9)
    expect(issue.range[1]).toBeCloseTo(101.9, 9)
    expect(ticksOf(issue).map(tick => tick.label)).toEqual(['101', '101.5'])
    // (the bottom, 100.9, is left out: it lies too near the tick 101 to be written beside it)
    expect(tickLabelsOf(issue)).toEqual(['101', '101.5'])
    // a narrower axis (data 101.1 to 101.45, so 100.9 to 101.65) has the step 0.3: its ticks 101.1 and 101.4 both read "101" before
    const stepThree = pressure('kPa', 101.1, 101.45)
    expect(tickInterval(stepThree.range[1] - stepThree.range[0], stepThree.splits)).toBeCloseTo(0.3, 9)
    expect(ticksOf(stepThree).map(tick => tick.label)).toEqual(['101.1', '101.4'])

    // the hectopascal and the pascal stay whole numbers: their step is a whole number, from 2 up
    for (const [unit, scale] of [['hPa', 10], ['Pa', 1000]] as const) {
      const axis = pressure(unit, 101.1 * scale, 101.2 * scale)
      expect(axis.decimals).toBe(0)
      // (the library writes 1,011 for 1011)
      expect(ticksOf(axis).map(tick => tick.label.replaceAll(',', ''))).toEqual(ticksOf(axis).map(tick => String(tick.value)))
    }

    // every range from a flat run to a spread of three kPa (30 hPa, 3000 Pa), at steps that are no round numbers: the ticks (and the
    // labels the chart draws) are distinct, and each reads back as the value it stands for at the decimals shown
    for (const [unit, scale] of [['kPa', 1], ['hPa', 10], ['Pa', 1000]] as const) {
      for (let low = 99.07; low <= 103.01; low += 0.41) {
        for (let spread = 0; spread <= 3; spread += 0.1875) {
          const axis = pressure(unit, low * scale, (low + spread) * scale)
          const ticks = ticksOf(axis)
          expect(ticks.length).toBeGreaterThanOrEqual(1)
          expect(new Set(ticks.map(tick => tick.label)).size).toBe(ticks.length)
          const labels = tickLabelsOf(axis)
          expect(new Set(labels).size).toBe(labels.length)
          for (const tick of ticks)
            expect(Math.abs(Number(tick.label.replaceAll(',', '')) - tick.value)).toBeLessThan(1e-9 * Math.max(1, Math.abs(tick.value)))
        }
      }
    }
  })

  it('leaves the gutter room for the pressure ticks written with their decimals (GH-4212)', () => {
    const kilopascal = (unit: string) => {
      const series = joined({ hours: 24 })
      const x = series.get('pressure_air_sea_level')!.x
      series.set('pressure_air_sea_level', { x, y: x.map((_, i) => i === 0 ? 101.1 : 101.7) })
      return model({ series, units: { ...UNITS, pressure_air_sea_level: unit } })
    }
    const m = kilopascal('kPa')
    const axis = m.axes.pressure!
    // "101.5" is the widest label of the two
    expect(tickLabelsOf(axis)).toEqual(['101', '101.5'])
    expect(labelWidthFor(axis)).toBe(labelWidthOf('101.5') + LABEL_SLACK_PX)
    expect(labelWidthFor(axis)).toBeGreaterThan(labelWidthOf('102') + LABEL_SLACK_PX)
    expect(gutterLeftFor(m)).toBeGreaterThanOrEqual(TITLE_LEFT + TITLE_LINES * TITLE_LINE_PX + TITLE_TO_LABELS + labelWidthFor(axis) + LABEL_MARGIN)
  })

  it('draws the snow depth and the chance as straight segments and not as a smooth curve', () => {
    const { option } = build()
    const byId = (id: string) => option.series.find((s: any) => s.id === id)
    expect(byId('snowDepth').smooth).toBe(false)
    expect(byId('snowChance').smooth).toBe(false)
    // the others keep theirs
    expect(byId('temp').smooth).toBe(0.4)
  })

  it('stacks the bars of the new snow apart from the precipitation\'s, and in the grid of the snow plot', () => {
    const { option } = build()
    const byId = (id: string) => option.series.find((s: any) => s.id === id)
    expect(byId('snowNew')).toMatchObject({ type: 'bar', stack: 'snow', xAxisIndex: 3, yAxisIndex: 3 })
    expect(byId('rain')).toMatchObject({ type: 'custom', xAxisIndex: 2 })
    expect(byId('snowDepth')).toMatchObject({ type: 'line', xAxisIndex: 4 })
    expect(byId('snowChance')).toMatchObject({ type: 'line', xAxisIndex: 5 })
    // each stamp of the bars has a point, so that a bar is as wide as the steps are apart (three hours)
    // each bar over the 3 hours it covers, which end at the step: centred on T - 1.5 h
    expect(byId('snowNew').data.map((p: number[]) => p[0]).slice(0, 3)).toEqual([t0 - 1.5 * HOUR_MS, t0 + 1.5 * HOUR_MS, t0 + 4.5 * HOUR_MS])
  })

  // WCAG 1.4.11: the bars and the lines are graphics that carry the information, 3:1 on the paper (the card)
  describe.each([['light', false, '#ffffff'], ['dark', true, '#12233f']] as const)('in the %s scheme', (_name, dark, paper) => {
    const luminance = (hex: string) => {
      const [r, g, b] = [1, 3, 5].map(i => Number.parseInt(hex.slice(i, i + 2), 16) / 255).map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
      return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
    }
    const contrast = (a: string, b: string) => {
      const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
      return (hi! + 0.05) / (lo! + 0.05)
    }

    it.each(['snowNew', 'snowDepth', 'snowChance'] as const)('draws %s at 3:1 or more on the paper', (tone) => {
      expect(contrast(toneColor(tone, dark), paper)).toBeGreaterThanOrEqual(3)
    })

    it.each(['indigo', 'teal', 'gold'] as const)('writes the labels of %s at 4.5:1 or more on the paper', (name) => {
      expect(contrast(SERIES_LABEL[name][dark ? 'dark' : 'light'], paper)).toBeGreaterThanOrEqual(4.5)
    })

    it('draws the bars in the colour of the scheme, where the SVG has them', () => {
      const svg = draw(build(dark ? DARK : LIGHT))
      expect(svg).toContain(`fill="${toneColor('snowNew', dark)}"`)
    })
  })

  it('titles the plots in their colour, the unit on a line of its own', () => {
    const svg = draw(build())
    const turned = [...svg.matchAll(/<text[^>]*transform="matrix\(0,-1,1,0,([\d.-]+),([\d.-]+)\)"[^>]*fill="([^"]*)"[^>]*>([^<]*)<\/text>/g)].map(match => ({ colour: match[3], text: match[4]!.replaceAll('&gt;', '>') }))
    expect(turned).toEqual(expect.arrayContaining([
      { colour: SERIES_LABEL.indigo.light, text: 'meteogram.chart.axisSnowNew' },
      { colour: SERIES_LABEL.teal.light, text: 'meteogram.chart.axisSnowDepth' },
      { colour: SERIES_LABEL.gold.light, text: `>10${NB}cm new` },
    ]))
  })
})

describe('the list of the stations with a snow forecast', () => {
  const answer = (...ids: string[]) => ({ stations: ids.map(station_id => ({ station_id })) })

  it('is asked for once and kept, whatever the station shown', async () => {
    forgetSnowStations()
    const load = vi.fn(async () => answer('Z901', 'Z914'))
    const first = await snowStationIds(load)
    const second = await snowStationIds(load)
    expect([...first]).toEqual(['Z901', 'Z914'])
    expect(second).toBe(first)
    expect(load).toHaveBeenCalledTimes(1)
  })

  it('is asked for once where two forecasts are asked for at once', async () => {
    forgetSnowStations()
    const load = vi.fn(async () => answer('Z914'))
    await Promise.all([snowStationIds(load), snowStationIds(load)])
    expect(load).toHaveBeenCalledTimes(1)
  })

  it('is asked for again after a failure, which is no list', async () => {
    forgetSnowStations()
    const load = vi.fn<() => Promise<ReturnType<typeof answer>>>().mockRejectedValueOnce(new Error('down')).mockResolvedValue(answer('Z914'))
    await expect(snowStationIds(load)).rejects.toThrow('down')
    expect([...await snowStationIds(load)]).toEqual(['Z914'])
    expect(load).toHaveBeenCalledTimes(2)
  })

  it('is asked for again after an answer with no station, which says nothing of the stations', async () => {
    forgetSnowStations()
    const load = vi.fn<() => Promise<ReturnType<typeof answer>>>().mockResolvedValueOnce(answer()).mockResolvedValue(answer('Z914'))
    expect((await snowStationIds(load)).size).toBe(0)
    expect([...await snowStationIds(load)]).toEqual(['Z914'])
  })

  it('is asked for again after an hour, as DWD adds stations to the product', async () => {
    forgetSnowStations()
    const load = vi.fn(async () => answer('Z914'))
    await snowStationIds(load, 1000)
    await snowStationIds(load, 1000 + SNOW_STATIONS_TTL_MS - 1)
    expect(load).toHaveBeenCalledTimes(1)
    await snowStationIds(load, 1000 + SNOW_STATIONS_TTL_MS)
    expect(load).toHaveBeenCalledTimes(2)
  })
})
