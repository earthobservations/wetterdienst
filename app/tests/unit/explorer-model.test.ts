import type { ExplorerSeries } from '../../app/utils/explorer-model'
import { describe, expect, it } from 'vitest'
import {
  boundsOf,
  buildTimeline,
  clampExplorerWindow,
  drawnPoints,
  minSpanOf,
  nearestIndex,
  niceScale,
  panExplorerWindow,
  pointCount,
  POINTS_PER_PX,
  readoutRows,
  revealMoment,
  sameExplorerWindow,
  SERIES_COLOURS,
  seriesColour,
  shownSeries,
  trendOf,
  typicalStep,
  valueAt,
  zoomExplorerWindow,
} from '../../app/utils/explorer-model'

const HOUR = 3_600_000
const DAY = 24 * HOUR
const START = Date.UTC(2026, 8, 1)

function series(id: string, y: (number | null)[], over: Partial<ExplorerSeries> = {}, step = DAY): ExplorerSeries {
  return { id, name: id, colorIndex: 0, kind: 'values', x: y.map((_, i) => START + i * step), y, ...over }
}

// WCAG 2.x relative luminance and contrast ratio
function luminance(hex: string) {
  const [r, g, b] = [1, 3, 5].map(i => Number.parseInt(hex.slice(i, i + 2), 16) / 255).map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
}
function contrast(a: string, b: string) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi! + 0.05) / (lo! + 0.05)
}

describe('series colours', () => {
  it('are on the white paper at 3:1 or more, which a mark that carries meaning needs (WCAG 1.4.11)', () => {
    for (const colour of SERIES_COLOURS)
      expect(contrast(colour.light, '#ffffff'), colour.light).toBeGreaterThanOrEqual(3)
  })

  it('are on the dark paper (`--ui-bg`, #12233f) at 3.5:1 or more, which the 3:1 of a mark has to spare', () => {
    for (const colour of SERIES_COLOURS)
      expect(contrast(colour.dark, '#12233f'), colour.dark).toBeGreaterThanOrEqual(3.5)
  })

  it('keep the hue of the stations: the light colour is the dark one where that reaches 3:1, else the same hue a step darker', () => {
    const changed = SERIES_COLOURS.filter(colour => colour.light !== colour.dark)
    // the five hues whose own colour is under 3:1 on white
    expect(changed.map(colour => colour.dark)).toEqual(['#22c55e', '#f59e0b', '#06b6d4', '#84cc16', '#f97316'])
    for (const colour of SERIES_COLOURS.filter(colour => colour.light === colour.dark))
      expect(contrast(colour.dark, '#ffffff')).toBeGreaterThanOrEqual(3)
  })

  it('are given out in turn, and start again after the last', () => {
    expect(seriesColour(0, true)).toBe('#3b82f6')
    expect(seriesColour(1, true)).toBe('#22c55e')
    expect(seriesColour(1, false)).toBe('#16a34a')
    expect(seriesColour(SERIES_COLOURS.length, true)).toBe(seriesColour(0, true))
  })
})

describe('points and trends', () => {
  it('counts the points that have a value, not the gaps', () => {
    expect(pointCount(series('a', [1, null, 3, null]))).toBe(2)
  })

  it('draws the least-squares line from the first moment to the last', () => {
    const line = trendOf(series('a', [1, 2, 3, 4]))!
    expect(line.x).toEqual([START, START + 3 * DAY])
    expect(line.y[0]).toBeCloseTo(1)
    expect(line.y[1]).toBeCloseTo(4)
  })

  it('leaves the gaps out of the line it fits', () => {
    const line = trendOf(series('a', [1, null, 3]))!
    expect(line.y[0]).toBeCloseTo(1)
    expect(line.y[1]).toBeCloseTo(3)
  })

  it('has no line through fewer than two points', () => {
    expect(trendOf(series('a', [1]))).toBeNull()
    expect(trendOf(series('a', [null, 5, null]))).toBeNull()
  })

  it('takes a series of more points than a call takes arguments, where Math.min(...x) threw', () => {
    const big = series('big', Array.from({ length: 200_000 }, (_, i) => i % 7), {}, 60_000)
    expect(trendOf(big)!.x).toEqual([big.x[0], big.x[199_999]])
  })

  it('shows the series the legend has not turned off', () => {
    const all = [series('a', [1]), series('b', [2])]
    expect(shownSeries(all, new Set(['a'])).map(item => item.id)).toEqual(['b'])
  })
})

describe('the window', () => {
  const bounds = { start: 0, end: 1000 }

  it('is from the first moment of any series to the last, a day wide round a lone one', () => {
    expect(boundsOf([series('a', [1, 2, 3]), series('b', [1, 2], {}, 2 * DAY)])).toEqual({ start: START, end: START + 2 * DAY })
    expect(boundsOf([series('a', [1])])).toEqual({ start: START - 12 * HOUR, end: START + 12 * HOUR })
    expect(boundsOf([])).toBeNull()
  })

  it('zooms in to no fewer than a few points of the finest series, and never to under ten minutes', () => {
    expect(typicalStep([series('a', [1, 2, 3, 4]), series('b', [1, 2], {}, HOUR)])).toBe(HOUR)
    expect(minSpanOf([series('a', [1, 2, 3, 4])])).toBe(3 * DAY)
    expect(minSpanOf([series('a', [1, 2, 3], {}, 60_000)])).toBe(600_000)
    // no two points: six hours
    expect(minSpanOf([series('a', [1])])).toBe(6 * HOUR)
  })

  it('keeps a window inside the bounds and no narrower than the least span', () => {
    expect(clampExplorerWindow({ start: -50, end: 100 }, bounds, 100)).toEqual({ start: 0, end: 150 })
    expect(clampExplorerWindow({ start: 950, end: 1100 }, bounds, 100)).toEqual({ start: 850, end: 1000 })
    expect(clampExplorerWindow({ start: 400, end: 410 }, bounds, 100)).toEqual({ start: 400, end: 500 })
    expect(clampExplorerWindow({ start: -100, end: 5000 }, bounds, 100)).toEqual(bounds)
  })

  it('zooms round an anchor that keeps its place in the window', () => {
    const zoomed = zoomExplorerWindow({ start: 0, end: 1000 }, 0.5, 250, bounds, 10)
    expect(zoomed).toEqual({ start: 125, end: 625 })
    expect((250 - zoomed.start) / (zoomed.end - zoomed.start)).toBeCloseTo(0.25)
  })

  it('moves by a distance and stops at the bounds', () => {
    expect(panExplorerWindow({ start: 100, end: 300 }, 100, bounds, 10)).toEqual({ start: 200, end: 400 })
    expect(panExplorerWindow({ start: 700, end: 900 }, 500, bounds, 10)).toEqual({ start: 800, end: 1000 })
  })

  it('moves the least that brings a moment in, with a margin', () => {
    const window = { start: 400, end: 600 }
    expect(revealMoment(window, 500, bounds, 10)).toBe(window)
    expect(revealMoment(window, 700, bounds, 10)).toEqual({ start: 510, end: 710 })
    expect(revealMoment(window, 100, bounds, 10)).toEqual({ start: 90, end: 290 })
  })

  it('tells a window that came back from the library from the one it was given', () => {
    expect(sameExplorerWindow({ start: 0, end: 1000 }, { start: 0.4, end: 1000.4 })).toBe(true)
    expect(sameExplorerWindow({ start: 0, end: 1000 }, { start: 5, end: 1000 })).toBe(false)
  })
})

describe('the moments a key steps through', () => {
  it('are those that have a value in a series, each once, in order, with no trendline among them', () => {
    const a = series('a', [1, null, 3])
    const b = series('b', [1, 2, 3, 4], {}, DAY / 2)
    const trend = series('t', [1, 2], { kind: 'trend', x: [START - DAY, START + 9 * DAY] })
    expect(buildTimeline([a, b, trend])).toEqual([START, START + DAY / 2, START + DAY, START + 1.5 * DAY, START + 2 * DAY])
  })

  it('finds the nearest moment to a time, the earlier of two that are as near', () => {
    const list = [0, 10, 20, 100]
    expect(nearestIndex(list, 4)).toBe(0)
    expect(nearestIndex(list, 6)).toBe(1)
    expect(nearestIndex(list, 15)).toBe(1)
    expect(nearestIndex(list, 70)).toBe(3)
    expect(nearestIndex(list, -50)).toBe(0)
    expect(nearestIndex(list, 500)).toBe(3)
    expect(nearestIndex([], 1)).toBe(-1)
  })

  it('reads a series at a moment it has, and not at one it has not', () => {
    const a = series('a', [5, null, 7])
    expect(valueAt(a, START)).toBe(5)
    expect(valueAt(a, START + DAY)).toBeNull()
    expect(valueAt(a, START + 2 * DAY)).toBe(7)
    expect(valueAt(a, START + HOUR)).toBeNull()
  })

  it('lists the values of the series that have one at the moment, as a hover label of the chart did', () => {
    const a = series('a', [5, 6], { name: 'Station A' })
    const b = series('b', [9], { name: 'Station B', colorIndex: 1 })
    expect(readoutRows([a, b], START + DAY)).toEqual([{ id: 'a', name: 'Station A', colorIndex: 0, value: 6 }])
    expect(readoutRows([a, b], START).map(row => row.value)).toEqual([5, 9])
  })
})

describe('what is drawn of a long series', () => {
  // a decade of hourly readings: 87,600 points
  const N = 87_600
  const long = (): ExplorerSeries => ({
    id: 'long',
    name: 'long',
    colorIndex: 0,
    kind: 'values',
    x: Array.from({ length: N }, (_, i) => START + i * HOUR),
    y: Array.from({ length: N }, (_, i) => 10 + 8 * Math.sin(i / 24 * 2 * Math.PI / 365 * 24) + (i % 97) / 50),
  })
  const whole = { start: START, end: START + (N - 1) * HOUR }

  it('is a few thousand points where it was 87,600, so the draw is cheap', () => {
    const drawn = drawnPoints(long(), whole, 700)
    expect(drawn.x.length).toBeLessThanOrEqual(700 * POINTS_PER_PX)
    expect(drawn.x.length).toBeGreaterThan(700)
  })

  it('keeps the lowest and the highest value of every column, so a peak or a trough a reader looks for is there', () => {
    const data = long()
    // one spike and one dip, each in the middle of a column's worth of ordinary readings
    data.y[40_001] = 99
    data.y[60_003] = -77
    const drawn = drawnPoints(data, whole, 700)
    expect(Math.max(...(drawn.y as number[]))).toBe(99)
    expect(Math.min(...(drawn.y as number[]))).toBe(-77)
    // and the overall extremes of the data are the extremes of what is drawn
    const real = data.y as number[]
    expect(Math.max(...(drawn.y as number[]))).toBe(Math.max(...real))
    expect(Math.min(...(drawn.y as number[]))).toBe(Math.min(...real))
  })

  it('keeps the first and the last point, and the points in order', () => {
    const drawn = drawnPoints(long(), whole, 700)
    expect(drawn.x[0]).toBe(START)
    expect(drawn.x.at(-1)).toBe(START + (N - 1) * HOUR)
    for (let i = 1; i < drawn.x.length; i++)
      expect(drawn.x[i]!).toBeGreaterThanOrEqual(drawn.x[i - 1]!)
  })

  it('keeps a gap as a gap: a point without a value is still in the list, between the points it parts', () => {
    const data = long()
    for (let i = 30_000; i < 30_500; i++)
      data.y[i] = null
    const drawn = drawnPoints(data, whole, 700)
    const gaps = drawn.y.map((value, i) => value === null ? i : -1).filter(i => i >= 0)
    expect(gaps.length).toBeGreaterThan(0)
    // the points on either side of a gap are real values, so the line breaks there
    for (const at of gaps) {
      expect(drawn.y[at - 1]).not.toBeNull()
      expect(drawn.x[at]!).toBeGreaterThanOrEqual(START + 30_000 * HOUR)
      expect(drawn.x[at]!).toBeLessThan(START + 30_500 * HOUR)
    }
  })

  it('draws a series that fits as it is, gaps included', () => {
    const small = series('s', [1, null, 3, 4])
    const drawn = drawnPoints(small, boundsOf([small])!, 700)
    expect(drawn.y).toEqual([1, null, 3, 4])
  })

  it('draws the window and one point beyond each edge, so that the line runs to the edge', () => {
    const data = series('d', [1, 2, 3, 4, 5, 6, 7, 8])
    const drawn = drawnPoints(data, { start: START + 2.5 * DAY, end: START + 4.5 * DAY }, 700)
    expect(drawn.y).toEqual([3, 4, 5, 6])
  })

  it('draws nothing where the window holds nothing of a series that ends before it', () => {
    const data = series('d', [1, 2])
    expect(drawnPoints(data, { start: START + 50 * DAY, end: START + 60 * DAY }, 700).y).toEqual([2])
    expect(drawnPoints({ x: [], y: [] }, { start: 0, end: 1 }, 700)).toEqual({ x: [], y: [] })
  })

  it('does the 87,600 points of a decade in a few milliseconds', () => {
    const data = long()
    const began = performance.now()
    for (let i = 0; i < 10; i++)
      drawnPoints(data, whole, 700)
    expect((performance.now() - began) / 10).toBeLessThan(50)
  })
})

describe('niceScale', () => {
  it('takes the step nearest to the raw one, so that an axis has its five or so ticks and not three', () => {
    // a range of 26.4 over five steps is 5.3 each: a step of 5, not of 10
    expect(niceScale(1.4, 27.8)).toMatchObject({ min: 0, max: 30, interval: 5 })
    expect(niceScale(0, 100)).toMatchObject({ interval: 20 })
    expect(niceScale(0, 7)).toMatchObject({ interval: 1 })
    expect(niceScale(0, 1000)).toMatchObject({ interval: 200 })
  })

  it('rounds the ends to a round step', () => {
    expect(niceScale(3.2, 27.8)).toEqual({ min: 0, max: 30, interval: 5, decimals: 0 })
    expect(niceScale(-4.3, 18.9)).toMatchObject({ min: -5, max: 20, interval: 5 })
  })

  it('writes a step below one with the fraction digits it needs', () => {
    const scale = niceScale(0.02, 0.37)
    expect(scale).toMatchObject({ min: 0, max: 0.4, interval: 0.05, decimals: 2 })
    expect(niceScale(0.001, 0.0034).decimals).toBe(4)
  })

  it('gives one value a range round it, and none a unit one', () => {
    const one = niceScale(5, 5)
    expect(one.min).toBeLessThan(5)
    expect(one.max).toBeGreaterThan(5)
    expect(niceScale(0, 0).max).toBeGreaterThan(0)
    expect(niceScale(Number.NaN, 3)).toMatchObject({ min: 0, max: 1 })
  })

  it('has ends that are ticks', () => {
    for (const [lo, hi] of [[0.3, 7.7], [-120, 40], [1013, 1042], [0, 1], [12.25, 12.75]] as const) {
      const scale = niceScale(lo, hi)
      expect(scale.min).toBeLessThanOrEqual(lo)
      expect(scale.max).toBeGreaterThanOrEqual(hi)
      expect(Math.abs(((scale.max - scale.min) / scale.interval) % 1) < 1e-6 || Math.abs((((scale.max - scale.min) / scale.interval) % 1) - 1) < 1e-6).toBe(true)
    }
  })
})
