import { registerEndpoint } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtState } from '#imports'
import { limitsOf, useServerLimits } from '~/composables/useServerLimits'

const DEFAULTS = { max_rows: 500_000, max_stations: 100, max_stream_rows: 10_000_000 }

afterEach(() => clearNuxtState())

describe('limitsOf', () => {
  it('takes the limits the server reports, 0 being none', () => {
    expect(limitsOf({ version: '1', limits: { max_stations: 50, max_rows: 0, max_stream_rows: 2_000_000, timeout: 60 } }))
      .toEqual({ max_rows: 0, max_stations: 50, max_stream_rows: 2_000_000 })
  })

  it.each([
    ['a server that reports none', { version: '1' }],
    ['no answer', null],
    ['an answer that is no object', 'ok'],
    ['limits that are no numbers', { limits: { max_rows: '500', max_stations: null, max_stream_rows: -1 } }],
    ['limits that are no whole numbers', { limits: { max_rows: 1.5, max_stations: Number.NaN } }],
  ])('keeps the documented defaults for %s', (_name, answer) => {
    expect(limitsOf(answer)).toEqual(DEFAULTS)
  })
})

describe('useServerLimits', () => {
  it('starts at the documented defaults and takes the server\'s once it has answered', async () => {
    registerEndpoint('/api/version', () => ({ version: '1', limits: { max_rows: 1000, max_stations: 5, max_stream_rows: 0 } }))
    const limits = useServerLimits()
    expect(limits.value).toEqual(DEFAULTS)
    await vi.waitFor(() => expect(limits.value).toEqual({ max_rows: 1000, max_stations: 5, max_stream_rows: 0 }))
  })
})
