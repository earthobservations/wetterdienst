import { describe, expect, it } from 'vitest'
import { classOf, recordOf, referenceOf, stripesAnswer } from '../helpers/stripes-answer'

/**
 * The test helper that writes the stripes of a record for the tests' fixtures (`tests/helpers/stripes-answer.ts`), which is made
 * by the app's own scale (`app/utils/stripes-scale.ts`, held to the backend's cases by `tests/unit/stripes-scale.test.ts`): a
 * window cuts the years and changes nothing of the classes, and a year without a value has no anomaly and no class.
 */
describe('the test helper that writes the stripes of a record', () => {
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

  it('classes by the reference of the years with a value', () => {
    const record = recordOf(1991, 2020, year => year / 100, [2000])
    const reference = referenceOf(record)
    expect(reference.centre.years).toBe(29)
    expect(classOf(reference.centre.value, reference)).toBe(8)
  })
})
