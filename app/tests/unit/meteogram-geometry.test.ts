import { describe, expect, it } from 'vitest'
import {
  chartLayout,
  clampWindow,
  defaultWindow,
  every,
  GUTTER_LEFT,
  GUTTER_RIGHT,
  HOUR_MAX_PX,
  HOUR_MS,
  HOUR_PX,
  hourWidth,
  knotsOf,
  labelStepHours,
  MIN_SPAN_HOURS,
  PANEL_GAP,
  PANEL_HEIGHT,
  panWindow,
  plotWidthFor,
  revealInstant,
  scrollStrip,
  windBarb,
  windowFromScroll,
  zoomWindow,
} from '../../app/utils/meteogram-geometry'

const bounds = { start: 0, end: 240 * HOUR_MS }

describe('the fixed hour width', () => {
  it('is 10 px on every screen a forecast does not fit', () => {
    for (const available of [200, 300, 700, 1200, 2000])
      expect(hourWidth(available, 240)).toBe(HOUR_PX)
  })

  it('fills the plot up to a cap where the whole forecast fits at less', () => {
    // 24 h on a plot 400 px wide: 24 * 10 = 240 px, so the hours stretch to 16.7 px to fill it
    expect(hourWidth(400, 24)).toBeCloseTo(400 / 24, 6)
    // 24 h on 1200 px would want 50 px an hour: the cap holds it
    expect(hourWidth(1200, 24)).toBe(HOUR_MAX_PX)
  })

  it('is the fixed width for a plot of no width or a forecast of no hours, which never fail', () => {
    expect(hourWidth(0, 24)).toBe(HOUR_PX)
    expect(hourWidth(400, 0)).toBe(HOUR_PX)
  })

  it('makes the plot as wide as the forecast needs, never wider than the screen gives', () => {
    // a ten-day forecast on a phone: the screen minus the gutters; on a desktop too
    expect(plotWidthFor(320, 240)).toBe(320 - GUTTER_LEFT - GUTTER_RIGHT)
    expect(plotWidthFor(1400, 240)).toBe(1400 - GUTTER_LEFT - GUTTER_RIGHT)
    // a day on a desktop is 24 h at the widest spacing, not the screen
    expect(plotWidthFor(1400, 24)).toBe(24 * HOUR_MAX_PX)
    expect(plotWidthFor(30, 24)).toBe(0)
  })

  it('opens the window on the first hours, as many as the plot holds at that width', () => {
    const plot = 722
    const win = defaultWindow(bounds, plot)
    expect(win.start).toBe(0)
    expect((win.end - win.start) / HOUR_MS).toBeCloseTo(72.2, 6)
    // all of a short forecast
    expect(defaultWindow({ start: 0, end: 24 * HOUR_MS }, 722).end).toBe(24 * HOUR_MS)
  })
})

describe('the layout', () => {
  const all = ['wind', 'precip', 'cloud', 'temp', 'pressure'] as const

  it('gives each panel its fixed height and a gap, and the chart the sum, whatever the screen', () => {
    const layout = chartLayout(all, true)
    expect(layout.rows.map(row => row.height)).toEqual(all.map(id => PANEL_HEIGHT[id]))
    for (let i = 1; i < layout.rows.length; i++)
      expect(layout.rows[i]!.top).toBe(layout.rows[i - 1]!.top + layout.rows[i - 1]!.height + PANEL_GAP)
    const last = layout.rows.at(-1)!
    expect(layout.height).toBeGreaterThan(last.top + last.height)
  })

  it('keeps the panels in their order, leaves out those that are off, and moves the rest up', () => {
    const layout = chartLayout(['pressure', 'wind'], true)
    expect(layout.rows.map(row => row.id)).toEqual(['wind', 'pressure'])
    expect(layout.rows[0]!.top).toBe(layout.header.height)
  })

  it('takes the symbols\' row out of the header where there are none', () => {
    expect(chartLayout(all, false).header.height).toBeLessThan(chartLayout(all, true).header.height)
    expect(chartLayout(all, false).header.symbolsTop).toBeNull()
  })

  it('is no more than the header for no panel', () => {
    expect(chartLayout([], true).rows).toEqual([])
  })
})

describe('the window', () => {
  const hours = (n: number) => n * HOUR_MS

  it('is held inside the forecast, at the width it has', () => {
    expect(clampWindow({ start: -hours(5), end: hours(20) }, bounds)).toEqual({ start: 0, end: hours(25) })
    expect(clampWindow({ start: hours(230), end: hours(260) }, bounds)).toEqual({ start: hours(210), end: hours(240) })
  })

  it('is no narrower than six hours and no wider than the forecast', () => {
    const narrow = clampWindow({ start: hours(10), end: hours(11) }, bounds)
    expect((narrow.end - narrow.start) / HOUR_MS).toBe(MIN_SPAN_HOURS)
    const wide = clampWindow({ start: -hours(10), end: hours(400) }, bounds)
    expect(wide).toEqual(bounds)
  })

  it('zooms around an instant that stays where it is on the screen', () => {
    const win = { start: hours(24), end: hours(96) }
    const anchor = hours(48)
    const zoomed = zoomWindow(win, 0.5, anchor, bounds)
    expect(zoomed.end - zoomed.start).toBe(hours(36))
    // the anchor was a third of the way across and still is
    expect((anchor - zoomed.start) / (zoomed.end - zoomed.start)).toBeCloseTo((anchor - win.start) / (win.end - win.start), 9)
  })

  it('zooms out to the whole forecast and no further', () => {
    const out = zoomWindow({ start: hours(100), end: hours(200) }, 10, hours(150), bounds)
    expect(out).toEqual(bounds)
  })

  it('pans by a span of time, and stops at the ends', () => {
    expect(panWindow({ start: hours(10), end: hours(40) }, hours(5), bounds)).toEqual({ start: hours(15), end: hours(45) })
    expect(panWindow({ start: hours(10), end: hours(40) }, hours(500), bounds)).toEqual({ start: hours(210), end: hours(240) })
    expect(panWindow({ start: hours(10), end: hours(40) }, -hours(500), bounds)).toEqual({ start: 0, end: hours(30) })
  })

  it('moves the least that shows an instant, and not at all where it is in view', () => {
    const win = { start: hours(10), end: hours(40) }
    expect(revealInstant(win, hours(20), bounds)).toBe(win)
    expect(revealInstant(win, hours(60), bounds).end).toBe(hours(62))
    expect(revealInstant(win, hours(2), bounds).start).toBe(0)
  })
})

describe('the strip that scrolls under the chart', () => {
  it('is the forecast at the window\'s spacing wide, and scrolled by the pixels to the window', () => {
    const plot = 722
    const win = { start: 10 * HOUR_MS, end: 10 * HOUR_MS + 72.2 * HOUR_MS }
    const strip = scrollStrip(win, bounds, plot, 800)
    // 240 h at 10 px, and the 78 px of the gutters
    expect(strip.width).toBe(2400 + 78)
    expect(strip.left).toBe(100)
  })

  it('is what a scroll position is read back from', () => {
    const plot = 722
    const span = 72.2 * HOUR_MS
    for (const left of [0, 100, 777, 1678]) {
      const win = windowFromScroll(left, span, bounds, plot)
      expect(scrollStrip(win, bounds, plot, 800).left).toBe(left)
    }
  })

  it('has no scroll where the forecast fits', () => {
    const short = { start: 0, end: 24 * HOUR_MS }
    const plot = plotWidthFor(800, 24)
    const strip = scrollStrip(defaultWindow(short, plot), short, plot, plot + GUTTER_LEFT + GUTTER_RIGHT)
    expect(strip.left).toBe(0)
    expect(strip.width).toBe(plot + GUTTER_LEFT + GUTTER_RIGHT)
  })
})

describe('thinning a row to the room there is', () => {
  it('draws every item where they are further apart than the minimum, and every third where a third of that is', () => {
    expect(every(30, 1, 26)).toBe(1)
    expect(every(10, 1, 26)).toBe(3)
    expect(every(10, 3, 26)).toBe(1)
    expect(every(4, 1, 26)).toBe(7)
  })

  it('writes a label every 6 hours at 10 px an hour, and every hour at 50', () => {
    expect(labelStepHours(10, 46)).toBe(6)
    expect(labelStepHours(50, 46)).toBe(1)
    expect(labelStepHours(1, 46)).toBe(24)
  })
})

describe('the wind barb', () => {
  const near = (a: number, b: number) => expect(a).toBeCloseTo(b, 6)

  it('is a circle for a calm', () => {
    expect(windBarb(90, 2.4)).toMatchObject({ calm: 4, shaft: null, ticks: [], pennants: [] })
    expect(windBarb(90, 2.5).calm).toBeNull()
  })

  it('points its shaft to the direction the wind comes from, 20 px long, from the tip', () => {
    // a wind from the west: the shaft goes to the left of the tip; from the north, up; from the east, right; from the south, down
    const [, , wx, wy] = windBarb(270, 10).shaft!
    near(wx, -20)
    near(wy, 0)
    const [, , nx, ny] = windBarb(0, 10).shaft!
    near(nx, 0)
    near(ny, -20)
    const [, , ex, ey] = windBarb(90, 10).shaft!
    near(ex, 20)
    near(ey, 0)
    const [, , sx, sy] = windBarb(180, 10).shaft!
    near(sx, 0)
    near(sy, 20)
  })

  it('counts a pennant for 50 knots, a full barb for 10 and a half barb for 5', () => {
    const count = (knots: number) => {
      const barb = windBarb(270, knots)
      return { pennants: barb.pennants.length, full: barb.ticks.length - (knots % 10 >= 5 ? 1 : 0), half: knots % 10 >= 5 ? 1 : 0 }
    }
    expect(count(5)).toEqual({ pennants: 0, full: 0, half: 1 })
    expect(count(10)).toEqual({ pennants: 0, full: 1, half: 0 })
    expect(count(15)).toEqual({ pennants: 0, full: 1, half: 1 })
    expect(count(34)).toEqual({ pennants: 0, full: 3, half: 0 })
    expect(count(50)).toEqual({ pennants: 1, full: 0, half: 0 })
    expect(count(65)).toEqual({ pennants: 1, full: 1, half: 1 })
    expect(count(100)).toEqual({ pennants: 2, full: 0, half: 0 })
  })

  it('draws its barbs to the left of the wind: for a wind from the west, below the shaft', () => {
    const barb = windBarb(270, 10)
    const [, y1, , y2] = barb.ticks[0]!
    // a screen's y grows downwards
    expect(y2).toBeGreaterThan(y1)
    // a barb is 8 px long
    expect(Math.hypot(barb.ticks[0]![2] - barb.ticks[0]![0], y2 - y1)).toBeCloseTo(8, 6)
  })

  it('draws a half barb half as long, and one apart from the tail where it is the only one', () => {
    const half = windBarb(270, 5).ticks[0]!
    expect(Math.hypot(half[2] - half[0], half[3] - half[1])).toBeCloseTo(4, 6)
    // the shaft is 20 px and the lone half barb sits 5 px in from its tail
    near(half[0], -15)
  })

  it('is scaled by the factor it is given', () => {
    const small = windBarb(0, 10, 0.5)
    near(small.shaft![3], -10)
  })

  it('has the force of the speed in knots, whatever unit the speed is in: 6 m/s is one full barb', () => {
    expect(knotsOf(6)).toBeCloseTo(11.66, 2)
    expect(windBarb(270, knotsOf(6)).ticks).toHaveLength(1)
  })
})
