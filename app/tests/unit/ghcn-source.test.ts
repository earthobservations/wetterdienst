import { describe, expect, it } from 'vitest'
import { checkRunningYear, readFromMirror } from '../helpers/ghcn-source'

// What the GHCN stripes e2e decides from (GH-4387): whether the backend read a station from the AWS mirror while NCEI was down, and
// what that leaves of the check of the running year.

const warning = (code: string) => ({ code, message: '...' })
function years(last: number, value: number | null = null) {
  return [
    { timestamp: '1869-01-01T00:00:00+00:00', value: 11.2 },
    { timestamp: `${last - 1}-01-01T00:00:00+00:00`, value: 13.5 },
    { timestamp: `${last}-01-01T00:00:00+00:00`, value },
  ]
}

describe('readFromMirror', () => {
  it('is true for an answer with the source-fallback warning, among others', () => {
    expect(readFromMirror({ values: [], metadata: { warnings: [warning('parameter-without-rows'), warning('source-fallback')] } })).toBe(true)
  })

  it('is false for an answer without it, and for one that carries no warnings at all', () => {
    expect(readFromMirror({ metadata: { warnings: [warning('file-skipped')] } })).toBe(false)
    expect(readFromMirror({ metadata: { warnings: [] } })).toBe(false)
    expect(readFromMirror({ metadata: {} })).toBe(false)
    expect(readFromMirror({ metadata: { warnings: null } })).toBe(false)
    expect(readFromMirror({})).toBe(false)
    expect(readFromMirror(null)).toBe(false)
    expect(readFromMirror({ metadata: { warnings: [null, 'source-fallback'] } })).toBe(false)
  })
})

describe('checkRunningYear', () => {
  it('without the warning asks for the running year with no value, and checks it', () => {
    expect(checkRunningYear(years(2026), 2026, false)).toEqual({ checked: true, problem: null })
  })

  it('without the warning fails when the last year is 2025 in 2026 (NCEI answered without the running year)', () => {
    const { checked, problem } = checkRunningYear(years(2025), 2026, false)
    expect(checked).toBe(true)
    expect(problem).toContain('not the running 2026')
  })

  it('without the warning fails when the running year has a value', () => {
    expect(checkRunningYear(years(2026, 12.1), 2026, false).problem).toContain('not null')
  })

  it('with the warning accepts a last year before the running one, and says the running year was not checked', () => {
    expect(checkRunningYear(years(2025), 2026, true)).toEqual({ checked: false, problem: null })
    expect(checkRunningYear(years(2026), 2026, true)).toEqual({ checked: false, problem: null })
  })

  it('with the warning still fails for a last year with a value, and for no years', () => {
    expect(checkRunningYear(years(2025, 12.1), 2026, true).problem).toContain('not null')
    expect(checkRunningYear([], 2026, true).problem).toContain('no years')
  })
})
