import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { classOf, recordOf, referenceOf, stripesAnswer } from '../helpers/stripes-answer'

/**
 * The records and what the backend gives them (`tests/ui/stripes_scale.golden.json`, which `tests/ui/test_stripes_scale.py`
 * holds to `wetterdienst/ui/stripes_scale.py`): the app's fixtures are written with a port of the scale, held to it here.
 */
interface Stat { value: number, first_year: number, last_year: number, years: number, fallback: boolean }
interface GoldenCase { name: string, years: number[], values: number[], reference: { centre: Stat, spread: Stat }, classes: number[] }
const GOLDEN: GoldenCase[] = JSON.parse(readFileSync(new URL('../../../tests/ui/stripes_scale.golden.json', import.meta.url), 'utf8'))

describe('the test helper that writes the backend\'s answer', () => {
  it('has the cases of the backend to be held to', () => {
    expect(GOLDEN.length).toBeGreaterThanOrEqual(4)
    // a case of each way a station is classed: the method itself, a mean of the whole record, a spread of it, and an outlier
    expect(GOLDEN.map(item => [item.reference.centre.fallback, item.reference.spread.fallback])).toEqual(expect.arrayContaining([[false, false], [true, true], [false, true]]))
  })

  it.each(GOLDEN.map(item => [item.name, item] as const))('gives %s the reference and the classes of the backend', (_name, golden) => {
    const record = golden.years.map((year, index) => ({ year, value: golden.values[index]! }))
    const reference = referenceOf(record)
    for (const part of ['centre', 'spread'] as const) {
      const { value, ...rest } = golden.reference[part]
      expect(reference[part]).toMatchObject(rest)
      expect(reference[part].value).toBeCloseTo(value, 9)
    }
    expect(golden.values.map(value => classOf(value, reference))).toEqual(golden.classes)
    expect(stripesAnswer(record).values.map(item => item.stripe_class)).toEqual(golden.classes)
  })

  it('classes a year of a window as the whole record does', () => {
    const record = recordOf(1901, 2020, year => 8 + (year - 1901) * 0.02 + (year % 2 ? 0.3 : -0.3))
    const whole = stripesAnswer(record)
    const window = stripesAnswer(record, { start: 1990, end: 2000 })
    expect(window.reference).toEqual(whole.reference)
    expect(window.values.map(item => item.stripe_class)).toEqual(whole.values.slice(1990 - 1901, 2001 - 1901).map(item => item.stripe_class))
  })

  it('leaves the class and the anomaly of a year without a value empty', () => {
    const { values } = stripesAnswer(recordOf(1991, 2020, year => year / 100, [2000]))
    const gap = values.find(item => item.timestamp?.startsWith('2000'))!
    expect([gap.value, gap.anomaly, gap.stripe_class]).toEqual([null, null, null])
  })
})
