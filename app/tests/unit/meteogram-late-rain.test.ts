import type { ModelInput } from '../../app/utils/meteogram-model'
import type { OptionInput } from '../../app/utils/meteogram-option'
import * as SunCalc from 'suncalc'
import { describe, expect, it } from 'vitest'
import { EMPTY_CHART_THEME } from '../../app/utils/chart-theme'
import { loadEcharts } from '../../app/utils/echarts-loader'
import { hourFormatter } from '../../app/utils/format'
import { chartLayout, GUTTER_RIGHT, plotWidthFor } from '../../app/utils/meteogram-geometry'
import { buildMeteogramModel, readoutHours, readoutValue } from '../../app/utils/meteogram-model'
import { buildMeteogramOption, gutterLeftFor, toneColor } from '../../app/utils/meteogram-option'
import { buildSeries } from '../../app/utils/meteogram-series'
import { meteogramSummary, meteogramTable } from '../../app/utils/meteogram-summary'
import { meteogramUnits } from '../../app/utils/meteogram-units'
import { FORECAST_UNITS } from '../helpers/meteogram-forecast'
import { PRECIPITATION, precipitationRunValues, run10382Values } from '../helpers/mosmix-run'

// The precipitation panel, the readout, the table and the summary of a run whose hourly amount is 0.0 late in it: blocks of 1, 6 and 12
// hours (GH-4175). The run is MOSMIX-L at 10382 (Berlin-Tegel) of 2026-11-17 03 UTC.

const HOUR = 3_600_000
const T = (hours: number) => Date.UTC(2026, 10, 17, 0) + hours * HOUR
const t = (key: string, named?: Record<string, unknown>) => key + (named?.hours ? ` ${named.hours}` : '') + (named?.unit ? ` ${named.unit}` : '')

function input(values: unknown[], rest: Partial<ModelInput> = {}): ModelInput {
  return {
    series: buildSeries(values as any),
    panels: { temp: true, wind: true, precip: true, snow: true, cloud: true, pressure: true },
    horizonHours: null,
    zone: 'Europe/Berlin',
    language: 'en-GB',
    coords: { latitude: 52.5, longitude: 13.4 },
    sun: SunCalc as any,
    units: meteogramUnits(FORECAST_UNITS, t),
    t,
    ...rest,
  }
}
const model = (values: unknown[] = run10382Values(), rest: Partial<ModelInput> = {}) => buildMeteogramModel(input(values, rest))!
const series = (m: ReturnType<typeof model>, id: string) => m.series.find(s => s.id === id)!

describe('the precipitation panel of a run with a dry hourly tail', () => {
  const m = model()

  it('draws a block for each hour, 6 hours and 12 hours of the plan, each over the hours it covers', () => {
    const rain = series(m, 'rain')
    expect(rain.windows).toBeDefined()
    expect(rain.data).toHaveLength(rain.windows!.length)
    expect(new Set(rain.windows)).toEqual(new Set([1, 6, 12]))
    // each point is at the middle of the hours its block covers: the block that ends at 06:00 UTC on the 26th and covers 12 hours is at 00:00
    const i = rain.windows!.findIndex((hours, k) => hours === 12 && rain.data[k]![0] === T(222) - 6 * HOUR)
    expect(i).toBeGreaterThanOrEqual(0)
    // and the three kinds share the blocks: one of them has a value, the others none
    for (const k of [0, 50, 90]) {
      const values = ['rain', 'mixed', 'snow'].map(id => series(m, id).data[k]![1])
      expect(values.filter(v => v !== null).length).toBeLessThanOrEqual(1)
    }
  })

  it('goes from hours to 6 hour and to 12 hour blocks, and has the label of each change for the panel', () => {
    expect(m.precipChanges).toEqual([
      { t: T(78), hours: 6, label: 'meteogram.chart.precipBlocks 6' },
      { t: T(174), hours: 12, label: 'meteogram.chart.precipBlocks 12' },
    ])
  })

  it('cuts the changes off at the horizon, with the blocks, and keeps a block that crosses it', () => {
    const short = model(run10382Values(), { horizonHours: 72 })
    expect(short.precipChanges).toEqual([])
    expect(series(short, 'rain').windows!.every(hours => hours === 1)).toBe(true)
    // a horizon of 100 hours: the 6 hour blocks that begin by then, and the change into them
    const mid = model(run10382Values(), { horizonHours: 100 })
    expect(mid.precipChanges.map(change => change.hours)).toEqual([6])
    expect(series(mid, 'rain').windows!.at(-1)).toBe(6)
  })

  // 10147 at 03 UTC: the 12 hour block of +159 to +171 h after the issue crosses the 7 day horizon (168 h from the run's first hour),
  // which the chart cut off, leaving 10 hours of the panel blank (GH-4175 review)
  it.each([24, 72, 168])('has no gap in the blocks up to a horizon of %i hours, and keeps the block that crosses it', (horizon) => {
    const values = precipitationRunValues('10147@2026-11-17 03 UTC')
    const m = model(values, { horizonHours: horizon })
    const blocks = ['rain', 'mixed', 'snow'].map(id => series(m, id)).flatMap(s => s.data.map((point, i) => ({ end: point[0] + (s.windows![i]! * HOUR) / 2, start: point[0] - (s.windows![i]! * HOUR) / 2 })))
    const readout = ['rain', 'mixed', 'snow'].map(id => m.readout.find(r => r.id === id)!)
    // the readout has every hour to the horizon in a block of the plan (the amounts of nothing are in it as 0)
    for (let time = m.minTime; time <= m.maxTime; time += HOUR)
      expect(readout.some(r => readoutValue(r, time) !== null), `${horizon} h, hour ${(time - m.minTime) / HOUR}`).toBe(true)
    const last = Math.max(...blocks.map(block => block.end))
    expect(last).toBeGreaterThanOrEqual(m.maxTime)
    // and a change of cadence has the blocks after it
    for (const change of m.precipChanges)
      expect(blocks.some(block => block.start >= change.t - 1 && block.start < m.maxTime)).toBe(true)
    if (horizon === 168) {
      expect(m.maxTime).toBe(m.minTime + 168 * HOUR)
      expect(last).toBeGreaterThan(m.maxTime)
    }
    // the table has the block that crosses it as a row
    const table = meteogramTable(buildSeries(values as any), { panels: { temp: false, wind: false, precip: true, snow: false, cloud: false, pressure: false }, horizonHours: horizon, zone: 'Europe/Berlin', formatLanguage: 'en-GB', locale: 'en', units: meteogramUnits(FORECAST_UNITS, t), t, widget: false })!
    expect(table.rows.length).toBe(m.series.find(s => s.id === 'rain')!.data.length)
  })

  it('has the axis up to a seventh above the largest block, which is a total of more hours than an hour', () => {
    const plan = [...series(m, 'rain').data, ...series(m, 'mixed').data, ...series(m, 'snow').data]
    const largest = Math.max(...plan.map(p => p[1] ?? 0))
    expect(largest).toBeGreaterThan(1)
    expect(m.axes.precip!.range[1]).toBeCloseTo(Math.max(1, largest * 1.15), 6)
  })

  it('reads a 6 or 12 hour block at every hour it covers, with its hours, and an hour at its stamp alone', () => {
    const rain = [series(m, 'rain'), series(m, 'mixed'), series(m, 'snow')].map(s => m.readout.find(r => r.id === s.id)!)
    const at = (hour: number) => {
      for (const r of rain) {
        const value = readoutValue(r, T(hour))
        if (value !== null)
          return { value, hours: readoutHours(r, T(hour)) }
      }
      return null
    }
    // 2026-11-26 00:00 to 12:00 UTC, the 12 hour block of +222 h less 12: 0.6 mm (the totals are 1.2 mm, 0.6 mm each of two blocks)
    const inside = at(210)
    expect(inside).not.toBeNull()
    expect(inside!.hours).toBe(12)
    // the same block at its first hour and at its stamp, and not at the stamp before it
    expect(at(199)).toEqual(inside)
    expect(at(210)).toEqual(inside)
    expect(at(198)!.hours).toBe(12)
    // an hourly block is read at its stamp: an hour of the first days
    const early = at(30)
    expect(early!.hours).toBe(1)
  })
})

describe('the kind of precipitation of a block, by the mean wet bulb of its hours', () => {
  // two days of hourly zeros under a 24 hour total of 2.4 mm of the second, which the 12 hour totals have, 1.2 mm in each half
  const stampIso = (hours: number) => new Date(T(hours)).toISOString()
  const base = (parameter: string, hours: number[], value: (h: number) => number) => hours.map(h => ({ station_id: 'X', resolution: 'hourly', dataset: 'large', parameter, timestamp: stampIso(h), value: value(h), quality_flags: null }))
  const range = (from: number, to: number) => Array.from({ length: to - from + 1 }, (_, i) => from + i)
  const values = (temperature: (h: number) => number) => [
    ...base(PRECIPITATION.hour, range(1, 48), () => 0),
    ...base(PRECIPITATION.twelve, [36, 48], () => 1.2),
    ...base(PRECIPITATION.day, [24, 48], h => h === 24 ? 0 : 2.4),
    ...base('temperature_air_2m', range(1, 48), temperature),
  ]
  const kindOf = (m: ReturnType<typeof model>, end: number) => ['rain', 'mixed', 'snow'].filter(id => series(m, id).data.some((p, i) => p[1] !== null && p[0] === T(end) - 6 * HOUR && series(m, id).windows![i] === 12))

  it('is rain for a block of mild hours and snow for one of cold hours', () => {
    expect(kindOf(model(values(h => h > 36 ? 8 : -4)), 36)).toEqual(['snow'])
    expect(kindOf(model(values(h => h > 36 ? 8 : -4)), 48)).toEqual(['rain'])
  })

  it('is mixed for a block that is warm for some of its hours and cold for others, whose mean is between: not rain for the one and snow for the other', () => {
    // the block of 24:00 to 36:00 is 4 degrees for its first 6 hours and -1 for the other 6: a mean of 1.5, which is mixed
    const m = model(values(h => h <= 30 ? 4 : h <= 36 ? -1 : 8))
    expect(kindOf(m, 36)).toEqual(['mixed'])
  })

  it('is rain where the forecast has no temperature to judge it by', () => {
    const none = values(() => 0).filter(v => v.parameter !== 'temperature_air_2m')
    const m = model(none)
    expect(kindOf(m, 36)).toEqual(['rain'])
  })
})

describe('the symbols of a forecast with an hour missing from the hourly amount', () => {
  it('has a symbol for the hour, with no amount, which is not a dry hour', () => {
    const values = run10382Values().filter(v => !(v.parameter === PRECIPITATION.hour && v.timestamp === new Date(T(30)).toISOString().replace('.000Z', '+00:00')))
    const m = model(values)
    const symbol = m.symbols.find(s => s.t === T(30))!
    expect(symbol).toBeDefined()
    expect(symbol.precipitationMm).toBeNull()
    // and its neighbours have theirs
    expect(m.symbols.find(s => s.t === T(31))!.precipitationMm).not.toBeNull()
  })

  it('draws a rain symbol for no hour of the coarse tail, where the amounts are of 6 and 12 hours', () => {
    const m = model()
    const late = m.symbols.filter(s => s.t > T(200))
    expect(late.length).toBeGreaterThan(40)
    expect(late.every(s => s.kind !== 'rain')).toBe(true)
  })
})

describe('the table and the summary of a run with blocks', () => {
  const m = meteogramUnits(FORECAST_UNITS, t)
  const values = run10382Values()

  it('has the rain as the blocks the chart draws, one value at the end of each, with the hours it covers', () => {
    const table = meteogramTable(buildSeries(values as any), { panels: { temp: false, wind: false, precip: true, snow: false, cloud: false, pressure: false }, horizonHours: null, zone: 'Europe/Berlin', formatLanguage: 'en-GB', locale: 'en', units: m, t, widget: false })!
    expect(table.columns.slice(1)).toEqual(['meteogram.chart.panelPrecipitation mm', 'meteogram.chart.tableBlockHours'])
    const rows = table.rows
    // an hourly row, a 6 hour one and a 12 hour one
    expect(rows.some(row => row[2] === '1')).toBe(true)
    expect(rows.some(row => row[2] === '6')).toBe(true)
    expect(rows.some(row => row[2] === '12')).toBe(true)
    // one row for each block: 79 hours of the first days, the 6 hour blocks to +174 h and the 12 hour blocks after it
    expect(rows).toHaveLength(97)
  })

  it('has no column of hours where every block is of an hour', () => {
    const hourlyOnly = values.filter(v => !v.parameter.endsWith('_6h') && !v.parameter.endsWith('_12h') && !v.parameter.endsWith('_24h'))
    const table = meteogramTable(buildSeries(hourlyOnly as any), { panels: { temp: false, wind: false, precip: true, snow: false, cloud: false, pressure: false }, horizonHours: null, zone: 'Europe/Berlin', formatLanguage: 'en-GB', locale: 'en', units: m, t, widget: false })!
    expect(table.columns).toHaveLength(2)
    expect(table.rows).toHaveLength(247)
  })

  it('sums the rain of the run over the blocks: the late days are in it', () => {
    const withTotals = meteogramSummary(buildSeries(values as any), m, 'en')!
    const hourlyOnly = meteogramSummary(buildSeries(values.filter(v => v.parameter === PRECIPITATION.hour || !v.parameter.startsWith('precipitation')) as any), m, 'en')!
    // the hourly amounts alone have 23.1 mm; the blocks add what the 6 and 12 hour totals have for days 5 to 10
    expect(Number(withTotals.precip.value)).toBeGreaterThan(Number(hourlyOnly.precip.value) + 3)
    // the totals end 4 hours before the run does, which the last day's `≥` says, and so the run's total is the least as well
    expect(withTotals.precip.atLeast).toBe(true)
    expect(hourlyOnly.precip.atLeast).toBe(false)
  })
})

describe('the precipitation blocks drawn', () => {
  const echarts = loadEcharts()
  const LIGHT = { ...EMPTY_CHART_THEME, text: 'rgb(15, 23, 43)', textStrong: 'rgb(0, 0, 0)', textMuted: 'rgb(90, 100, 120)', zeroline: 'rgb(90, 100, 120)' }
  const m = model()
  const layout = chartLayout(m.panels, m.symbols.length > 0)
  const gutterLeft = gutterLeftFor(m, 'en')
  const plotPx = plotWidthFor(1600, (m.maxTime - m.minTime) / HOUR, gutterLeft)
  const built: OptionInput = {
    model: m,
    theme: LIGHT,
    layout,
    outerPx: plotPx + gutterLeft + GUTTER_RIGHT,
    plotPx,
    gutterLeft,
    window: { start: m.minTime, end: m.maxTime },
    now: null,
    fontFamily: 'sans-serif',
    locale: 'en',
    hourLabel: hourFormatter('en-GB', 'Europe/Berlin'),
  }
  const option = buildMeteogramOption(built) as any
  const chart = echarts.init(null as any, null, { renderer: 'svg', ssr: true, width: built.outerPx, height: layout.height })
  chart.setOption(option)
  const svg = chart.renderToSVGString()
  chart.dispose()
  /** The boxes (left, width) of the rectangles painted in `colour` in the SVG: `M136.9 392l15.9 0l0 -16.1l-15.9 0Z` */
  const boxes = (colour: string) => [...svg.matchAll(new RegExp(`<path d="M([\\d.]+) [\\d.]+l([\\d.]+) 0[^"]*" fill="${colour}"`, 'g'))].map(match => ({ left: Number(match[1]), width: Number(match[2]) }))
  const pxPerHour = plotPx / ((m.maxTime - m.minTime) / HOUR)

  it('is custom series: the blocks are rectangles over their own hours, which the library\'s bars of one width cannot be', () => {
    for (const id of ['rain', 'mixed', 'snow'])
      expect(option.series.find((s: any) => s.id === id).type).toBe('custom')
    const rain = option.series.find((s: any) => s.id === 'rain')
    // [first moment, last moment, amount] of each block that has an amount
    expect(new Set(rain.data.map((d: number[]) => (d[1]! - d[0]!) / HOUR))).toEqual(new Set([1, 6, 12]))
    expect(rain.data.every((d: number[]) => d[2]! > 0)).toBe(true)
  })

  it('draws a 6 hour block six times as wide as an hour\'s, and a 12 hour block twelve times', () => {
    const widths = ['rain', 'mixed', 'snow'].flatMap(id => boxes(toneColor(id as any, false))).map(box => box.width / pxPerHour)
    const near = (target: number) => widths.filter(width => Math.abs(width - target * 0.9) < 0.05 * target)
    expect(near(1).length).toBeGreaterThan(20)
    expect(near(6).length).toBeGreaterThan(5)
    expect(near(12).length).toBeGreaterThan(3)
  })

  it('marks each change of the cadence in the precipitation panel, with the label of the new blocks, and in no other panel', () => {
    const backdrop = option.series.find((s: any) => s.id === 'backdrop-precip')
    // BACKDROP.cadence is 5: [kind, first, last, index of the change]
    const marks = backdrop.data.filter((d: number[]) => d[0] === 5)
    expect(marks.map((d: number[]) => d[1])).toEqual([T(78), T(174)])
    expect(marks.map((d: number[]) => d[3])).toEqual([0, 1])
    expect(option.series.find((s: any) => s.id === 'backdrop-wind').data.some((d: number[]) => d[0] === 5)).toBe(false)
    // drawn: a dashed line and its label
    expect(svg).toContain('meteogram.chart.precipBlocks 6')
    expect(svg).toContain('meteogram.chart.precipBlocks 12')
  })
})
