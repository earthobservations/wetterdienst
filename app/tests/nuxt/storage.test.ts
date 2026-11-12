import { describe, expect, it } from 'vitest'

// The setup file of every project gives each test an empty `localStorage` and `sessionStorage` (GH-3990). The pairs
// below write in one test and read in the next, which is what leaked in CI, where Node's storage works, and not on a
// machine where it does not. Run them with `NODE_OPTIONS=--localstorage-file=<a file>` to see Node's storage work.

describe.each(['localStorage', 'sessionStorage'] as const)('the %s of a test', (name) => {
  const storage = () => globalThis[name]

  it('is there, and takes a write', () => {
    expect(storage().length).toBe(0)
    storage().setItem('wd-storage-test', 'written')
    expect(storage().getItem('wd-storage-test')).toBe('written')
    expect(storage().length).toBe(1)
  })

  it('is empty again in the next test', () => {
    expect(storage().getItem('wd-storage-test')).toBeNull()
    expect(storage().length).toBe(0)
  })

  it('is the one the window has', () => {
    expect(window[name]).toBe(storage())
  })
})
