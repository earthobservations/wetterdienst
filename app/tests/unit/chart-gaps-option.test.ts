import type { ExplorerSeries } from '../../app/utils/explorer-model'
import { describe, expect, it } from 'vitest'
import { EMPTY_CHART_THEME } from '../../app/utils/chart-theme'
import { boundsOf } from '../../app/utils/explorer-model'
import { buildExplorerOption, explorerFrame } from '../../app/utils/explorer-option'
import { breakAtGaps, LINE_GAP_MS, readoutValue } from '../../app/utils/meteogram-model'

// What the Explorer's option and the meteogram's lines make of the rows that are missing (GH-4100)

const HOUR = 3_600_000
const START = Date.UTC(2026, 8, 1)

describe('the option of a chart with a gap', () => {
  const build = (all: ExplorerSeries[], large = false) => {
    const bounds = boundsOf(all)!
    const input = { series: all, hidden: new Set<string>(), theme: EMPTY_CHART_THEME, window: bounds, bounds, width: 704, height: 400, large, locale: 'en', measure: (text: string) => text.length * 7 }
    return buildExplorerOption(input, explorerFrame(input)) as any
  }
  const lines = (option: any) => option.series.filter((line: any) => line.type === 'line' && line.id !== 'zero')
  const empty = (line: any) => line.data.filter((point: [number, number | null]) => point[1] === null)
  // ten hours, three missing, and ten more
  const offsets = [...Array.from({ length: 10 }, (_, i) => i), ...Array.from({ length: 10 }, (_, i) => 13 + i)]
  const gappy = (over: Partial<ExplorerSeries> = {}): ExplorerSeries => ({ id: 'g', name: 'g', colorIndex: 0, kind: 'values', resolution: 'hourly', x: offsets.map(o => START + o * HOUR), y: offsets.map(o => o), ...over })

  it('has a point of no value in the data of the line where hours are missing, which the line is not joined across', () => {
    const [line] = lines(build([gappy()]))
    expect(line.connectNulls).toBe(false)
    expect(empty(line)).toHaveLength(1)
    expect(line.data[10][1]).toBeNull()
  })

  it('has it by the series\' own steps where the answer names no resolution', () => {
    // ten days of hours, three of the fifth day missing
    const hoursOf = Array.from({ length: 240 }, (_, i) => i).filter(i => i < 100 || i > 102)
    const long = gappy({ resolution: undefined, x: hoursOf.map(o => START + o * HOUR), y: hoursOf.map(o => o) })
    expect(empty(lines(build([long]))[0])).toHaveLength(1)
  })

  it('has it for a short series of 20 hours with three missing, where the answer names no resolution', () => {
    expect(empty(lines(build([gappy({ resolution: undefined })]))[0])).toHaveLength(1)
  })

  it('does not break a series that is whole, nor a trendline', () => {
    const whole = gappy({ x: Array.from({ length: 20 }, (_, i) => START + i * HOUR), y: Array.from({ length: 20 }, (_, i) => i) })
    const trend: ExplorerSeries = { id: 'g:trend', name: 't', colorIndex: 0, kind: 'trend', x: [START, START + 40 * HOUR], y: [1, 2] }
    for (const line of lines(build([whole, trend])))
      expect(empty(line)).toHaveLength(0)
  })

  it('gives a point between two gaps a dot of its own in a chart of many points, which has no markers', () => {
    const x = [0, 1, 2, 3, 4, 8, 12, 13, 14, 15, 16].map(o => START + o * HOUR)
    const [line, dots] = lines(build([gappy({ x, y: x.map(() => 1) })], true))
    expect(line.showSymbol).toBe(false)
    expect(dots.id).toBe('g:isolated')
    expect(dots.data.filter((point: [number, number | null]) => point[1] !== null)).toEqual([[START + 8 * HOUR, 1]])
    // a chart of many points with no gap has no such series
    expect(lines(build([gappy({ x: Array.from({ length: 20 }, (_, i) => START + i * HOUR), y: Array.from({ length: 20 }).fill(1) })], true))).toHaveLength(1)
  })
})

describe('the forecast\'s lines', () => {
  const stamps = (...offsets: number[]): [number, number][] => offsets.map(o => [START + o * HOUR, o])

  it('are broken where a step is longer than the 3 hours, and not between the steps of an element given every 3 hours', () => {
    expect(breakAtGaps(stamps(0, 3, 6, 9, 12)).map(point => point[1])).toEqual([0, 3, 6, 9, 12])
    expect(breakAtGaps(stamps(0, 1, 2, 3, 4, 5)).map(point => point[1])).toEqual([0, 1, 2, 3, 4, 5])
    const broken = breakAtGaps(stamps(0, 1, 2, 3, 8, 9))
    expect(broken.map(point => point[1])).toEqual([0, 1, 2, 3, null, 8, 9])
    expect(broken[4]![0]).toBe(START + 5.5 * HOUR)
    // an element of 3 hours that misses a step: 6 hours between two stamps
    expect(breakAtGaps(stamps(0, 3, 9, 12)).map(point => point[1])).toEqual([0, 3, null, 9, 12])
  })

  it('are broken where the readout says there is no value', () => {
    const series = { id: 'x', panel: 'temp' as const, tone: 'temp' as const, hover: '', digits: 0, unit: '', mode: 'line' as const, x: [0, 3, 9].map(h => START + h * HOUR), y: [0, 3, 9] }
    expect(readoutValue(series, START + 2 * HOUR)).not.toBeNull()
    expect(readoutValue(series, START + 6 * HOUR)).toBeNull()
    expect(LINE_GAP_MS).toBe(3 * HOUR)
  })
})
