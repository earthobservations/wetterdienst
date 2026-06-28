import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// nuxt.config.ts relies on the `defineNuxtConfig` auto-import (an identity
// helper at runtime) and imports the tailwind vite plugin. Stub both so the
// raw config object can be imported in a plain node environment.
vi.mock('@tailwindcss/vite', () => ({ default: () => ({ name: 'tailwindcss-stub' }) }))

async function loadConfig() {
  vi.resetModules()
  return (await import('../../nuxt.config')).default as any
}

describe('security headers', () => {
  beforeEach(() => {
    vi.stubGlobal('defineNuxtConfig', (config: any) => config)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('does not strip the Referer header (OpenStreetMap tiles need it)', async () => {
    const config = await loadConfig()
    const referrerPolicy = config.security?.headers?.referrerPolicy

    // OSM tile servers reject refererless requests ("Access denied, referer
    // required"). nuxt-security defaults this to 'no-referrer', which would
    // strip it; we must send at least the origin cross-origin.
    expect(referrerPolicy).toBeDefined()
    expect(referrerPolicy).not.toBe('no-referrer')
    expect(referrerPolicy).toBe('strict-origin-when-cross-origin')
  })

  it('allows OpenStreetMap tile images in the CSP', async () => {
    const config = await loadConfig()
    const imgSrc = config.security?.headers?.contentSecurityPolicy?.['img-src'] ?? []

    expect(imgSrc).toContain('https://*.tile.openstreetmap.org')
  })
})
