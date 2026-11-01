import { scaleLinear } from 'd3-scale'
import { DateTime } from 'luxon'
import { describe, expect, it } from 'vitest'
import { demoForecast } from '../../app/utils/meteogram-demo'
import {
  areaPath,
  barbIndices,
  buildSeries,
  cloudScaleFactor,
  daySpan,
  hourTicks,
  interpAt,
  layoutPanels,
  linePath,
  localDays,
  nearestTimeIndex,
  panDomain,
  panelDomain,
  revealInDomain,
  stepIndex,
  tooltipLeft,
  valueTicks,
  windBarb,
  zoomDomain,
} from '../../app/utils/meteogram-svg'

const HOUR = 3_600_000
const KT = 1852 / 3600 // m/s in one knot

describe('windBarb', () => {
  it('draws a circle for a calm', () => {
    const barb = windBarb(90, 2 * KT)
    expect(barb.calm).toBe(true)
    expect(barb.radius).toBe(4)
    expect(barb.shaft).toBe('')
  })

  it('puts the tail towards where the wind comes from', () => {
    // from the north: the tail is above the tip (negative y in SVG)
    expect(windBarb(0, 12 * KT).shaft).toBe('M0,0L0,-20')
    // from the east: the tail is to the right
    expect(windBarb(90, 12 * KT).shaft).toBe('M0,0L20,0')
    // from the south: below
    expect(windBarb(180, 12 * KT).shaft).toBe('M0,0L0,20')
    // from the west: to the left
    expect(windBarb(270, 12 * KT).shaft).toBe('M0,0L-20,0')
  })

  it('counts pennants (50 kt), full barbs (10 kt) and half barbs (5 kt), flooring the rest', () => {
    const counts = (kt: number) => {
      const b = windBarb(0, kt * KT)
      return { pennants: b.pennants.length, strokes: (b.barbs.match(/M/g) ?? []).length }
    }
    expect(counts(4.9)).toEqual({ pennants: 0, strokes: 0 })
    expect(counts(5.1)).toEqual({ pennants: 0, strokes: 1 })
    expect(counts(10.1)).toEqual({ pennants: 0, strokes: 1 })
    expect(counts(15.1)).toEqual({ pennants: 0, strokes: 2 })
    expect(counts(50.1)).toEqual({ pennants: 1, strokes: 0 })
    // 65 kt: a pennant, a full barb and a half barb
    expect(counts(65.1)).toEqual({ pennants: 1, strokes: 2 })
    expect(counts(120)).toEqual({ pennants: 2, strokes: 2 })
  })

  it('draws the barbs on the left of the wind and a lone half barb set in from the tail', () => {
    // from the north, tail at (0,-20): the barb goes to -x (left of the shaft seen from the tip)
    const full = windBarb(0, 10.5 * KT)
    expect(full.barbs).toBe('M0,-20L-8,-20')
    // a lone half barb starts one spacing in from the tail, half as long
    const half = windBarb(0, 5.5 * KT)
    expect(half.barbs).toBe('M0,-15L-4,-15')
  })

  it('shrinks with the scale', () => {
    expect(windBarb(0, 12 * KT, 0.78).shaft).toBe('M0,0L0,-16')
  })

  it('uses the knot of 1852 m per hour exactly: 5.14444 m/s is 10 kt, one full barb, not a half', () => {
    expect(windBarb(0, 10 * KT).barbs).not.toBe('')
    expect((windBarb(0, 10 * KT).barbs.match(/M/g) ?? []).length).toBe(1)
  })
})

describe('barbIndices', () => {
  const times = Array.from({ length: 240 }, (_, i) => i * HOUR)
  it('thins the barbs to the room there is, and spreads them from the first', () => {
    const idx = barbIndices(times, [0, 239 * HOUR], 700)
    // 700 px for 239 hours: 2.9 px an hour, 24 px needs every 9th
    expect(idx.slice(0, 3)).toEqual([0, 9, 18])
  })
  it('gives a zoomed-in chart a barb for every hour it has room for', () => {
    const idx = barbIndices(times, [0, 24 * HOUR], 700)
    // 29 px an hour: every hour
    expect(idx.length).toBe(25)
  })
  it('keeps barbs of the window only', () => {
    const idx = barbIndices(times, [48 * HOUR, 72 * HOUR], 700)
    expect(Math.min(...idx)).toBeGreaterThanOrEqual(48)
    expect(Math.max(...idx)).toBeLessThanOrEqual(72)
  })
  it('is empty without points in the window', () => {
    expect(barbIndices(times, [1000 * HOUR, 1100 * HOUR], 700)).toEqual([])
  })
})

describe('scales and panels', () => {
  it('maps time to pixels and back with a linear scale', () => {
    const x = scaleLinear().domain([0, 10 * HOUR]).range([0, 500])
    expect(x(5 * HOUR)).toBe(250)
    expect(x.invert(125)).toBe(2.5 * HOUR)
  })

  it('gives each panel the range of Meteogram.vue', () => {
    expect(panelDomain('wind', [3, 8])).toEqual([0, 8 * 1.6])
    // never under 5 m/s of headroom
    expect(panelDomain('wind', [1, 2])).toEqual([0, 8])
    expect(panelDomain('precip', [0, 0.5])).toEqual([0, 1])
    expect(panelDomain('precip', [0, 4])[1]).toBeCloseTo(4.6)
    expect(panelDomain('cloud', [])).toEqual([0, 100])
    // the temperature panel always includes 0 and has room above
    expect(panelDomain('temp', [4, 12])).toEqual([-1, 15])
    expect(panelDomain('temp', [-5, 2])).toEqual([-6, 5])
    expect(panelDomain('pressure', [1008, 1020])).toEqual([1006, 1022])
  })

  it('ticks a range with nice values inside it', () => {
    const ticks = valueTicks([-1, 15], 4)
    expect(ticks).toEqual([0, 5, 10, 15])
    expect(valueTicks([0, 100], 3).every(v => v >= 0 && v <= 100)).toBe(true)
  })

  it('stacks the panels with the gaps between them', () => {
    const boxes = layoutPanels(['wind', 'precip', 'temp'], 436, 8)
    expect(boxes.map(b => b.id)).toEqual(['wind', 'precip', 'temp'])
    expect(boxes[0]).toMatchObject({ top: 0, bottom: 140, height: 140 })
    expect(boxes[1]!.top).toBe(148)
    expect(boxes[2]!.bottom).toBeCloseTo(436)
    expect(layoutPanels([], 400, 8)).toEqual([])
  })
})

describe('line and area paths', () => {
  const xs = [0, 1, 2, 3, 4]
  const px = (v: number) => v * 10
  const py = (v: number) => 100 - v

  it('draws one stroke over continuous data', () => {
    const d = linePath(xs, [1, 2, 3, 2, 1], px, py)
    expect((d.match(/M/g) ?? []).length).toBe(1)
    expect(d.startsWith('M0,99')).toBe(true)
  })

  it('breaks at a null, as the maximum and minimum of Meteogram.vue do between windows', () => {
    const d = linePath(xs, [1, 2, null, 2, 1], px, py)
    expect((d.match(/M/g) ?? []).length).toBe(2)
  })

  it('draws steps for the held extremes', () => {
    const d = linePath([0, 1, 2], [5, 7, 7], px, py, true)
    // step-before: vertical first, then horizontal
    expect(d).toBe('M0,95L0,93L10,93L10,93L20,93')
  })

  it('closes an area down to the baseline', () => {
    const d = areaPath(xs, [1, 2, 3, 2, 1], px, py, 100)
    expect(d.endsWith('Z')).toBe(true)
    expect(d).toContain('100')
  })
})

describe('time axis', () => {
  const zone = 'Europe/Berlin'
  const from = Date.UTC(2026, 9, 21, 22, 0) // 00:00 local on the 22nd (CEST, UTC+2)

  it('puts the ticks on whole local hours that divide the day', () => {
    const ticks = hourTicks(from, from + 48 * HOUR, 560, zone)
    expect(ticks.length).toBeGreaterThan(3)
    for (const tick of ticks) {
      const dt = DateTime.fromMillis(tick.ms, { zone })
      expect(dt.minute).toBe(0)
      expect(dt.hour % 6 === 0 || dt.hour % 3 === 0).toBe(true)
      expect(tick.label).toBe(dt.toFormat('HH:mm'))
    }
  })

  it('is hourly up to a day and coarser the more it has to fit', () => {
    expect(hourTicks(from, from + 12 * HOUR, 1000, zone).length).toBe(13)
    const wide = hourTicks(from, from + 240 * HOUR, 700, zone)
    // 700 px has room for 19 labels: a day apart
    expect(wide.every(t => t.label === '00:00')).toBe(true)
    expect(wide.length).toBe(10)
  })

  it('writes the station time, not UTC', () => {
    const ticks = hourTicks(from, from + 6 * HOUR, 1000, zone)
    expect(ticks[0]!.label).toBe('00:00')
    expect(ticks[0]!.ms).toBe(from)
  })

  it('splits the calendar days of the station, with a 25-hour day where the clocks go back', () => {
    // 25 October 2026: CEST ends
    const start = DateTime.fromISO('2026-10-24T00:00', { zone }).toMillis()
    const days = localDays(start, start + 4 * 24 * HOUR, zone)
    expect(days.length).toBe(4)
    expect((days[1]!.endMs - days[1]!.startMs) / HOUR).toBe(25)
    expect(days[0]!.dt.toFormat('yyyy-MM-dd')).toBe('2026-10-24')
  })
})

describe('daySpan', () => {
  const day = localDays(Date.UTC(2026, 9, 21, 12), Date.UTC(2026, 9, 21, 12), 'UTC')[0]!
  const coords = { latitude: 70.9, longitude: -8.7 }
  const sun = (rise: Date | null, set: Date | null, altitude: number) => ({
    getTimes: () => ({ sunrise: rise, sunset: set }),
    getPosition: () => ({ altitude }),
  })

  it('is the span from sunrise to sunset', () => {
    const rise = new Date(Date.UTC(2026, 9, 21, 7))
    const set = new Date(Date.UTC(2026, 9, 21, 17))
    expect(daySpan(day, coords, sun(rise, set, 0.2))).toEqual({ fromMs: rise.getTime(), toMs: set.getTime(), sunriseMs: rise.getTime(), sunsetMs: set.getTime() })
  })

  it('covers the whole day where the sun does not set, and none where it does not rise', () => {
    // suncalc answers an invalid date inside the polar circle
    const invalid = new Date(Number.NaN)
    expect(daySpan(day, coords, sun(invalid, invalid, 0.3))).toMatchObject({ fromMs: day.startMs, toMs: day.endMs, sunriseMs: null })
    expect(daySpan(day, coords, sun(invalid, invalid, -0.3))).toEqual({ fromMs: null, toMs: null, sunriseMs: null, sunsetMs: null })
  })

  it('falls back to 04:00 to 20:00 without coordinates', () => {
    const span = daySpan(day, null, null)
    expect((span.toMs! - span.fromMs!) / HOUR).toBe(16)
    expect(span.fromMs).toBe(day.startMs + 4 * HOUR)
  })
})

describe('zoom and pan', () => {
  const full: [number, number] = [0, 240 * HOUR]

  it('zooms around an anchor and keeps the anchor where it was', () => {
    const next = zoomDomain(full, full, 2, 60 * HOUR)
    expect(next[1] - next[0]).toBe(120 * HOUR)
    // the anchor was at 25 % of the window and still is
    expect((60 * HOUR - next[0]) / (next[1] - next[0])).toBeCloseTo(0.25)
  })

  it('stays inside the data and within the minimum span', () => {
    expect(zoomDomain(full, full, 0.5, 0)).toEqual(full)
    const tight = zoomDomain([0, 8 * HOUR], full, 100, 4 * HOUR)
    expect(tight[1] - tight[0]).toBe(6 * HOUR)
    const nearEnd = zoomDomain(full, full, 4, 240 * HOUR)
    expect(nearEnd[1]).toBe(240 * HOUR)
  })

  it('pans without leaving the data or changing the width', () => {
    expect(panDomain([10 * HOUR, 20 * HOUR], full, -50 * HOUR)).toEqual([0, 10 * HOUR])
    expect(panDomain([230 * HOUR, 240 * HOUR], full, 5 * HOUR)).toEqual([230 * HOUR, 240 * HOUR])
    expect(panDomain([10 * HOUR, 20 * HOUR], full, 5 * HOUR)).toEqual([15 * HOUR, 25 * HOUR])
  })

  it('reveals a stamp outside the window by the least move', () => {
    expect(revealInDomain([10 * HOUR, 20 * HOUR], full, 15 * HOUR)).toEqual([10 * HOUR, 20 * HOUR])
    expect(revealInDomain([10 * HOUR, 20 * HOUR], full, 25 * HOUR)).toEqual([15 * HOUR, 25 * HOUR])
    expect(revealInDomain([10 * HOUR, 20 * HOUR], full, 4 * HOUR)).toEqual([4 * HOUR, 14 * HOUR])
  })
})

describe('keyboard stepping', () => {
  it('steps by one with the arrows, by six with Shift, by a day with the page keys', () => {
    expect(stepIndex(10, 'ArrowRight', false, 240)).toBe(11)
    expect(stepIndex(10, 'ArrowLeft', false, 240)).toBe(9)
    expect(stepIndex(10, 'ArrowRight', true, 240)).toBe(16)
    expect(stepIndex(10, 'PageDown', false, 240)).toBe(34)
    expect(stepIndex(30, 'PageUp', false, 240)).toBe(6)
  })
  it('stops at the ends, and Home and End go to them', () => {
    expect(stepIndex(0, 'ArrowLeft', false, 240)).toBe(0)
    expect(stepIndex(239, 'ArrowRight', false, 240)).toBe(239)
    expect(stepIndex(100, 'Home', false, 240)).toBe(0)
    expect(stepIndex(100, 'End', false, 240)).toBe(239)
  })
  it('starts at the given index when nothing is selected', () => {
    expect(stepIndex(null, 'ArrowRight', false, 240, 24, 7)).toBe(7)
    expect(stepIndex(null, 'ArrowLeft', false, 240, 24, 7)).toBe(7)
  })
  it('ignores other keys and an empty chart', () => {
    expect(stepIndex(3, 'a', false, 240)).toBeNull()
    expect(stepIndex(3, 'ArrowRight', false, 0)).toBeNull()
  })
})

describe('lookups', () => {
  const times = [0, HOUR, 2 * HOUR, 3 * HOUR]
  it('finds the nearest stamp', () => {
    expect(nearestTimeIndex(times, 0.4 * HOUR)).toBe(0)
    expect(nearestTimeIndex(times, 0.6 * HOUR)).toBe(1)
    expect(nearestTimeIndex(times, 99 * HOUR)).toBe(3)
    expect(nearestTimeIndex([], 5)).toBe(-1)
  })
  it('puts the readout on the side of the crosshair that has room', () => {
    expect(tooltipLeft(100, 190, 800)).toBe(112)
    expect(tooltipLeft(700, 190, 800)).toBe(498)
    expect(tooltipLeft(50, 190, 100)).toBe(0)
  })
})

describe('series from the long rows', () => {
  it('sorts by time, drops nulls and groups by parameter', () => {
    const series = buildSeries([
      { parameter: 'a', timestamp: '2026-10-01T02:00:00+00:00', value: 3 },
      { parameter: 'a', timestamp: '2026-10-01T01:00:00+00:00', value: 2 },
      { parameter: 'a', timestamp: '2026-10-01T03:00:00+00:00', value: null },
      { parameter: 'b', timestamp: '2026-10-01T01:00:00+00:00', value: 9 },
    ])
    expect(series.get('a')).toEqual({ x: [Date.UTC(2026, 9, 1, 1), Date.UTC(2026, 9, 1, 2)], y: [2, 3] })
    expect(series.get('b')!.y).toEqual([9])
  })
  it('reads a cloud cover as a fraction, oktas or percent', () => {
    expect(cloudScaleFactor([0, 0.5, 1])).toBe(100)
    expect(cloudScaleFactor([0, 4, 8])).toBe(12.5)
    expect(cloudScaleFactor([0, 40, 100])).toBe(1)
  })
})

describe('interpAt', () => {
  const s = { x: [0, 10, 20], y: [0, 10, 40] }
  it('is linear between stamps and flat beyond them', () => {
    expect(interpAt(s, 5)).toBe(5)
    expect(interpAt(s, 15)).toBe(25)
    expect(interpAt(s, 10)).toBe(10)
    expect(interpAt(s, -5)).toBe(0)
    expect(interpAt(s, 99)).toBe(40)
    expect(interpAt({ x: [], y: [] }, 1)).toBeNull()
  })
})

describe('demoForecast', () => {
  const rows = demoForecast(Date.UTC(2026, 9, 21, 0), 240)
  it('has ten days of hourly stamps for each series the meteogram draws', () => {
    const count = (parameter: string) => rows.filter(r => r.parameter === parameter).length
    expect(count('temperature_air_2m')).toBe(240)
    expect(count('wind_speed')).toBe(240)
    expect(count('pressure_air_sea_level')).toBe(240)
    expect(count('temperature_air_max_2m_last_12h')).toBe(20)
  })
  it('is deterministic', () => {
    expect(demoForecast(0, 24)).toEqual(demoForecast(0, 24))
  })
})
