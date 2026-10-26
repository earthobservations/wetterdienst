import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiBaseDeprecation, DEFAULT_API_BASE, resolveApiBase, useApiBase } from '../../server/utils/apiBase'

// Where the proxies find the backend (GH-3096): `NUXT_API_BASE` (the private runtime config `apiBase`), the old
// `NUXT_PUBLIC_API_BASE` for a few releases more, then the default. Nuxt applies the first by itself and the
// second is read from the environment here.
const NEW = 'http://new.internal:7890/api'
const OLD = 'http://old.internal:7890/api'

describe('the backend URL', () => {
  it('is NUXT_API_BASE when it is set, even if the old name is set too', () => {
    expect(resolveApiBase(NEW, { NUXT_PUBLIC_API_BASE: OLD })).toBe(NEW)
    expect(resolveApiBase(NEW, {})).toBe(NEW)
  })

  it('is NUXT_PUBLIC_API_BASE when only the old name is set', () => {
    expect(resolveApiBase('', { NUXT_PUBLIC_API_BASE: OLD })).toBe(OLD)
    expect(resolveApiBase(undefined, { NUXT_PUBLIC_API_BASE: OLD })).toBe(OLD)
  })

  it('is the local backend when neither is set, an empty value counting as not set', () => {
    expect(DEFAULT_API_BASE).toBe('http://localhost:7890/api')
    expect(resolveApiBase('', {})).toBe(DEFAULT_API_BASE)
    expect(resolveApiBase('', { NUXT_PUBLIC_API_BASE: '' })).toBe(DEFAULT_API_BASE)
  })
})

describe('useApiBase', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
  })

  it('reads the private runtime config, then the old variable, then the default', () => {
    vi.stubGlobal('useRuntimeConfig', () => ({ apiBase: NEW }))
    vi.stubEnv('NUXT_PUBLIC_API_BASE', OLD)
    expect(useApiBase()).toBe(NEW)

    vi.stubGlobal('useRuntimeConfig', () => ({ apiBase: '' }))
    expect(useApiBase()).toBe(OLD)

    vi.stubEnv('NUXT_PUBLIC_API_BASE', '')
    expect(useApiBase()).toBe(DEFAULT_API_BASE)
  })
})

describe('the deprecation of NUXT_PUBLIC_API_BASE', () => {
  it('warns, in one line that names the new variable and no value, when only the old one is set', () => {
    const message = apiBaseDeprecation('', { NUXT_PUBLIC_API_BASE: OLD })

    expect(message).toContain('NUXT_PUBLIC_API_BASE is deprecated')
    expect(message).toContain('NUXT_API_BASE')
    expect(message).not.toContain('\n')
    expect(message).not.toContain('old.internal')
  })

  it('says the old one is ignored when both are set, again without a value', () => {
    const message = apiBaseDeprecation(NEW, { NUXT_PUBLIC_API_BASE: OLD })

    expect(message).toContain('ignored')
    expect(message).not.toContain('internal')
  })

  it('stays silent when the old one is not set', () => {
    expect(apiBaseDeprecation(NEW, {})).toBeUndefined()
    expect(apiBaseDeprecation('', {})).toBeUndefined()
    expect(apiBaseDeprecation('', { NUXT_PUBLIC_API_BASE: '' })).toBeUndefined()
  })
})
