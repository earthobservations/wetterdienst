import { describe, expect, it } from 'vitest'
import { rowWidth, visibleTabCount } from '../../app/utils/header-fit'

// The fitting of the header's tool tabs (GH-4500): the tabs that do not fit go, from the end, into the "More" menu.

const WIDTHS = [100, 110, 120, 130, 140, 150, 160]
const BASE = { widths: WIDTHS, gap: 4, fixed: 150, more: 70 }
/** The width of all seven tabs in a row with no "More" button */
const ALL = 100 + 110 + 120 + 130 + 140 + 150 + 160 + 6 * 4 + 150

describe('rowWidth', () => {
  it('is the tabs, the gaps between them and the rest of the row', () => {
    expect(rowWidth(BASE, 7, false)).toBe(ALL)
    expect(rowWidth(BASE, 2, false)).toBe(100 + 110 + 4 + 150)
  })

  it('has the More button after the last tab, a gap from it', () => {
    expect(rowWidth(BASE, 2, true)).toBe(100 + 110 + 70 + 2 * 4 + 150)
    // and the button alone is the whole list
    expect(rowWidth(BASE, 0, true)).toBe(70 + 150)
  })
})

describe('visibleTabCount', () => {
  it('shows every tab where they all fit, and no More button', () => {
    expect(visibleTabCount({ ...BASE, available: ALL })).toBe(7)
    expect(visibleTabCount({ ...BASE, available: ALL + 300 })).toBe(7)
  })

  it('takes the last tab into the menu when it is one pixel short, and the button takes room of its own', () => {
    // seven tabs miss by a pixel: six are left with the button, which is 70 px and a gap in place of the 160 px tab and its gap
    expect(visibleTabCount({ ...BASE, available: ALL - 1 })).toBe(6)
  })

  it('takes tabs into the menu from the end until the rest and the button fit', () => {
    const six = 100 + 110 + 120 + 130 + 140 + 150 + 70 + 6 * 4 + 150
    expect(visibleTabCount({ ...BASE, available: six })).toBe(6)
    expect(visibleTabCount({ ...BASE, available: six - 1 })).toBe(5)
    const three = 100 + 110 + 120 + 70 + 3 * 4 + 150
    expect(visibleTabCount({ ...BASE, available: three })).toBe(3)
    expect(visibleTabCount({ ...BASE, available: three - 1 })).toBe(2)
  })

  it('never shows a tab that does not fit, and the menu holds the others: the row is never wider than the room', () => {
    for (let available = 0; available < ALL + 50; available++) {
      const count = visibleTabCount({ ...BASE, available })
      expect(count).toBeGreaterThanOrEqual(0)
      expect(count).toBeLessThanOrEqual(7)
      // a row that has the room is no wider than it, unless not even the button fits
      const needed = rowWidth(BASE, count, count < 7)
      if (rowWidth(BASE, 0, true) <= available + 0.5)
        expect(needed, `at ${available}px`).toBeLessThanOrEqual(available + 0.5)
      // and one tab more would not have fitted: the menu holds exactly the tabs that do not
      if (count < 7 && count > 0)
        expect(rowWidth(BASE, count + 1, count + 1 < 7), `at ${available}px`).toBeGreaterThan(available + 0.5)
    }
  })

  it('shows one tab where one and the button fit, and none a pixel short of it', () => {
    // the first tab, a gap and the button, and the rest of the row
    const one = 100 + 4 + 70 + 150
    expect(visibleTabCount({ ...BASE, available: one })).toBe(1)
    expect(visibleTabCount({ ...BASE, available: one - 1 })).toBe(0)
  })

  it('shows none where not even the button fits, and the button is still there', () => {
    expect(visibleTabCount({ ...BASE, available: 100 })).toBe(0)
    expect(visibleTabCount({ ...BASE, available: 0 })).toBe(0)
  })

  it('is monotonic: a wider row never shows fewer tabs', () => {
    let before = 0
    for (let available = 0; available < ALL + 50; available++) {
      const count = visibleTabCount({ ...BASE, available })
      expect(count, `at ${available}px`).toBeGreaterThanOrEqual(before)
      before = count
    }
  })

  it('lets half a pixel of the browser\'s rounding pass, and no more', () => {
    expect(visibleTabCount({ ...BASE, available: ALL - 0.5 })).toBe(7)
    expect(visibleTabCount({ ...BASE, available: ALL - 0.6 })).toBe(6)
  })

  it('shows every tab of a header with no width to measure (a test\'s document): all zero fits', () => {
    expect(visibleTabCount({ widths: [0, 0, 0], gap: 0, fixed: 0, more: 0, available: 0 })).toBe(3)
  })

  it('is the order of the header that goes first: a long tab at the end is the first to go, a short one before it stays', () => {
    const widths = [100, 100, 100, 400]
    expect(visibleTabCount({ widths, gap: 0, fixed: 0, more: 50, available: 650 })).toBe(3)
    expect(visibleTabCount({ widths, gap: 0, fixed: 0, more: 50, available: 700 })).toBe(4)
  })
})
