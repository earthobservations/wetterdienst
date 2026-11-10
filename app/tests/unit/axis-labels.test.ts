import { describe, expect, it } from 'vitest'
import { chooseLabels, estimateLabelWidth, PLOT_HEIGHT_REM, VALUE_LABEL_REM, valueLabels, yearSteps } from '../../app/utils/axis-labels'

// The labels of the answers' bar charts (GH-3893): which bars carry one, by year and by what the width allows, and
// where the values beside the plot go.

const FONT = 11

/** The 74 summers of 1943 to 2026: ten of the 84 years are missing */
const MISSING = new Set([1945, 1946, 1947, 1948, 1949, 1950, 1951, 1960, 1971, 1984])
const years = Array.from({ length: 2026 - 1943 + 1 }, (_, index) => 1943 + index).filter(year => !MISSING.has(year))

function chosen(width: number, list = years) {
  const labels = list.map(String)
  const widths = labels.map(label => estimateLabelWidth(label, FONT))
  const highlights = [list.length - 1]
  const picked = chooseLabels({ positions: list, widths, width, steps: yearSteps(list), highlights })
  // the same box as the component's: centred on its bar, kept inside the plot
  const boxes = picked.map((index) => {
    const start = Math.min(Math.max(((index + 0.5) / list.length) * width - widths[index]! / 2, 0), width - widths[index]!)
    return { year: list[index]!, start, end: start + widths[index]! }
  })
  return { picked, boxes }
}

describe('the labels under a chart of years', () => {
  it('has 74 summers', () => {
    expect(years).toHaveLength(74)
  })

  for (const width of [240, 300, 800]) {
    it(`are round years, the one asked about too, and none touch at ${width} px`, () => {
      const { boxes } = chosen(width)
      const regular = boxes.filter(box => box.year !== 2026)
      expect(regular.length).toBeGreaterThan(1)
      expect(boxes.at(-1)!.year).toBe(2026)
      // round years, all at the same step (a year the series lacks is a gap, not a shift)
      const step = regular.every(box => box.year % 20 === 0) ? 20 : 10
      expect(regular.every(box => box.year % step === 0)).toBe(true)
      for (let at = 1; at < boxes.length; at += 1)
        expect(boxes[at]!.start, `${boxes[at - 1]!.year} and ${boxes[at]!.year}`).toBeGreaterThanOrEqual(boxes[at - 1]!.end)
    })
  }

  it('are every 10 years where the width allows and every 20 where it does not (1950 and 1960 are in the gaps)', () => {
    const decades = chosen(800).boxes.map(box => box.year).filter(year => year !== 2026)
    expect(decades).toEqual([1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020].filter(year => !MISSING.has(year)))
    // a phone's plot (320 px less the value labels and the page's margins)
    const narrow = chosen(240).boxes.map(box => box.year).filter(year => year !== 2026)
    // step 20 in the phase that labels more (1970, 1990, 2010: 1960 is in a gap), 1943 to 1969 stay without
    expect(narrow).toEqual([1970, 1990, 2010])
    expect(chosen(300).boxes.map(box => box.year)).toEqual([1970, 1980, 1990, 2000, 2010, 2026])
  })

  it('leave out the regular label that would touch the one asked about', () => {
    // 2020 is six years before 2026: at 300 px (about 3.5 px a bar) the two would be over each other
    expect(chosen(300).boxes.map(box => box.year)).not.toContain(2020)
    expect(chosen(300).boxes.map(box => box.year)).toContain(2026)
  })

  it('keep the label of a bar at the edge inside the plot', () => {
    for (const box of chosen(300).boxes) {
      expect(box.start).toBeGreaterThanOrEqual(0)
      expect(box.end).toBeLessThanOrEqual(300)
    }
  })

  it('take the earlier phase of a step where two label as many bars', () => {
    const list = [1960, 1970, 1980, 1990]
    // four bars of 25 px, labels of 30 px: every 10 years touches, every 20 does not, in either phase
    const input = { positions: list, widths: list.map(() => 30), width: 100, steps: [10, 20], highlights: [] }
    expect(chooseLabels(input)).toEqual([0, 2])
    // and the phase that labels more wins: 1970, 1990 and 2010 against 1960 alone
    const gapped = [1960, 1970, 1975, 1990, 1995, 2010]
    expect(chooseLabels({ ...input, positions: gapped, widths: gapped.map(() => 30), width: 150 })).toEqual([1, 3, 5])
  })

  it('write a single label where not even the widest step fits and nothing is asked about', () => {
    const list = [1943, 1950, 1960, 1970, 1980, 1990, 2000]
    const widths = list.map(() => 40)
    expect(chooseLabels({ positions: list, widths, width: 30, steps: [10, 20, 50, 100], highlights: [] })).toEqual([2])
    // where one is asked about, it is the one written
    expect(chooseLabels({ positions: list, widths, width: 30, steps: [10, 20, 50, 100], highlights: [6] })).toEqual([6])
  })

  it('write only the one asked about where the plot has no width yet', () => {
    expect(chosen(0).picked).toEqual([years.length - 1])
  })

  it('are years of a short series by the year', () => {
    const list = [2019, 2020, 2021, 2022, 2023]
    expect(yearSteps(list)).toEqual([1, 2, 5, 10])
    expect(chosen(300, list).boxes.map(box => box.year)).toEqual([2019, 2020, 2021, 2022, 2023])
  })
})

describe('the labels under a chart of the hours of a day', () => {
  const hours = Array.from({ length: 24 }, (_, hour) => hour)
  const labels = hours.map(hour => String(hour).padStart(2, '0'))
  const widths = labels.map(label => estimateLabelWidth(label, FONT))
  const steps = Array.from({ length: 24 }, (_, at) => 3 * (at + 1))

  it('are every third at the width of a phone and of a desktop, from midnight', () => {
    for (const width of [240, 300, 800])
      expect(chooseLabels({ positions: hours, widths, width, steps, highlights: [] })).toEqual([0, 3, 6, 9, 12, 15, 18, 21])
  })

  it('go on to every sixth where every third is too many', () => {
    expect(chooseLabels({ positions: hours, widths, width: 120, steps, highlights: [] })).toEqual([0, 6, 12, 18])
  })

  it('always write the hour asked about, and drop its neighbours', () => {
    const picked = chooseLabels({ positions: hours, widths, width: 240, steps, highlights: [13] })
    expect(picked).toContain(13)
    expect(picked).not.toContain(12)
    expect(picked).toContain(9)
  })
})

describe('the values beside a plot', () => {
  it('are the highest at the top and 0 at the bottom, for bars that stand on the bottom', () => {
    expect(valueLabels(3.2, 0, false)).toEqual([
      { kind: 'top', value: 3.2, rem: 0 },
      { kind: 'bottom', value: 0, rem: PLOT_HEIGHT_REM - VALUE_LABEL_REM },
    ])
  })

  it('are the lowest inside the plot too, and a 0 at the line, for bars that hang from it', () => {
    const labels = valueLabels(1.7, -3.4, true)
    expect(labels.map(label => label.kind)).toEqual(['top', 'zero', 'bottom'])
    expect(labels.at(-1)!.rem + VALUE_LABEL_REM).toBe(PLOT_HEIGHT_REM)
    // the line is at 1.7 / 5.1 of the height, the label's middle on it
    expect(labels[1]!.rem + VALUE_LABEL_REM / 2).toBeCloseTo((1.7 / 5.1) * PLOT_HEIGHT_REM, 10)
  })

  it('leave the 0 out where the line is within a label of the highest or the lowest', () => {
    expect(valueLabels(0.1, -5, true).map(label => label.kind)).toEqual(['top', 'bottom'])
    expect(valueLabels(5, -0.1, true).map(label => label.kind)).toEqual(['top', 'bottom'])
  })

  it('write the line as the 0 where the extreme is itself 0', () => {
    expect(valueLabels(0, -2, true)).toEqual([
      { kind: 'zero', value: 0, rem: 0 },
      { kind: 'bottom', value: -2, rem: PLOT_HEIGHT_REM - VALUE_LABEL_REM },
    ])
    expect(valueLabels(2, 0, true).map(label => label.kind)).toEqual(['top', 'zero'])
    expect(valueLabels(2, 0, true).at(-1)!.rem).toBe(PLOT_HEIGHT_REM - VALUE_LABEL_REM)
  })
})
