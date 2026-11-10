import { describe, expect, it } from 'vitest'
import { reachesPx, SUB_PIXEL_PX } from '../e2e/target-size'

// The e2e specs measure targets with one helper (GH-3968): sub-pixel rounding passes, a real shortfall does not
describe('the target size of the e2e specs', () => {
  it('accepts the size and what Firefox rounds it to', () => {
    expect(reachesPx(44, 44)).toBe(true)
    expect(reachesPx(43.99999237, 44)).toBe(true)
    expect(reachesPx(24, 24)).toBe(true)
    expect(reachesPx(60, 44)).toBe(true)
  })

  it('refuses a target that is really smaller', () => {
    expect(reachesPx(43, 44)).toBe(false)
    expect(reachesPx(43.9, 44)).toBe(false)
    expect(reachesPx(44 - 2 * SUB_PIXEL_PX, 44)).toBe(false)
    expect(reachesPx(23, 24)).toBe(false)
  })
})
