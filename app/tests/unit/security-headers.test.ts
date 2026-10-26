import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// nuxt.config.ts relies on the `defineNuxtConfig` auto-import (an identity
// helper at runtime) and imports the tailwind vite plugin. Stub both so the
// raw config object can be imported in a plain node environment.
vi.mock('@tailwindcss/vite', () => ({ default: () => ({ name: 'tailwindcss-stub' }) }))

async function loadConfig() {
  vi.resetModules()
  return (await import('../../nuxt.config')).default as any
}

function policyOf(config: any): Record<string, string[]> {
  return config.security.headers.contentSecurityPolicy
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

  it('leaves who may frame a page to the widget plugin: no route rule and no default of the config relaxes it', async () => {
    const config = await loadConfig()
    const rules = config.routeRules as Record<string, any>

    // a route rule is matched on the decoded path, which `/%77idget` is the widget to, and the app's router is not
    // (`server/utils/widgetFrame.ts`): no rule may touch who frames a page
    for (const [path, rule] of Object.entries(rules))
      expect(JSON.stringify(rule), path).not.toMatch(/frame-ancestors|xFrameOptions|X-Frame-Options/i)
    expect(policyOf(config)['frame-ancestors']).toEqual(['\'self\''])
    expect(config.security.headers.xFrameOptions).toBeUndefined()
  })

  it('allows no CDN: the DuckDB-wasm and Swagger UI files are the app\'s own (GH-3094)', async () => {
    const config = await loadConfig()
    const policy = policyOf(config)

    const everything = Object.values(policy).flat().join(' ')
    expect(everything).not.toContain('jsdelivr')
    expect(policy['worker-src']).toEqual(['\'self\''])
    expect(policy['script-src']).not.toContain('blob:')
  })

  it('allows no evaluation of strings, and WebAssembly only for DuckDB\'s module', async () => {
    const config = await loadConfig()
    const scripts = policyOf(config)['script-src']!

    expect(scripts).not.toContain('\'unsafe-eval\'')
    expect(scripts).toContain('\'wasm-unsafe-eval\'')
  })

  it('lets the browser call its own origin, not the backend whose address is read when the server starts', async () => {
    // the variable and its deprecated name alike: neither one changes what the page may call
    vi.stubEnv('NUXT_API_BASE', 'http://backend.internal:7890/api')
    vi.stubEnv('NUXT_PUBLIC_API_BASE', 'http://old-backend.internal:7890/api')
    const config = await loadConfig()
    const connect = policyOf(config)['connect-src']!

    expect(connect).toContain('\'self\'')
    expect(connect.join(' ')).not.toContain('backend.internal')
    vi.unstubAllEnvs()
  })

  it('keeps the backend URL out of the public runtime config, which every page carries (GH-3096)', async () => {
    vi.stubEnv('NUXT_PUBLIC_API_BASE', 'http://old-backend.internal:7890/api')
    const config = await loadConfig()

    expect(config.runtimeConfig.public?.apiBase).toBeUndefined()
    expect(JSON.stringify(config.runtimeConfig.public ?? {})).not.toContain('backend')
    expect(config.runtimeConfig.apiBase).toBe('')
    vi.unstubAllEnvs()
  })

  it('leaves the rate limit and CORS to the app\'s own middleware, not to nuxt-security\'s fixed, wildcard defaults (GH-3093, GH-3095)', async () => {
    const config = await loadConfig()

    expect(config.security?.rateLimiter).toBe(false)
    expect(config.security?.corsHandler).toBe(false)
    expect(config.runtimeConfig.corsAllowedOrigins).toBe('')
  })
})

describe('the development server', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('names no host, so `nuxt dev` (with Nuxt DevTools) listens on localhost unless HOST says otherwise (GH-3096)', async () => {
    vi.stubGlobal('defineNuxtConfig', (config: any) => config)
    const config = await loadConfig()

    expect(config.devServer.host).toBeUndefined()
    expect(config.devServer.port).toBe(4000)
  })
})

describe('the assets under a page with a COEP', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('say it too: a browser refuses a worker script without it, and DuckDB\'s is one (GH-3094)', async () => {
    vi.stubGlobal('defineNuxtConfig', (config: any) => config)
    const config = await loadConfig()

    expect(config.routeRules['/_nuxt/**'].headers['Cross-Origin-Embedder-Policy']).toBe('credentialless')
  })
})

describe('the rate limit in the runtime config', () => {
  beforeEach(() => {
    vi.stubGlobal('defineNuxtConfig', (config: any) => config)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('is on, at 300 requests in 300 seconds, counting the address of the connection', async () => {
    vi.stubEnv('WD_E2E', '')
    const { rateLimit } = (await loadConfig()).runtimeConfig

    expect(rateLimit).toEqual({ enabled: true, tokens: 300, windowSeconds: 300, clientIpHeader: '' })
  })

  it('is off in the e2e suite\'s own build, and nowhere else', async () => {
    vi.stubEnv('WD_E2E', '1')
    expect((await loadConfig()).runtimeConfig.rateLimit.enabled).toBe(false)
  })
})

describe('the loggers of the production bundle', () => {
  beforeEach(() => {
    vi.stubGlobal('defineNuxtConfig', (config: any) => config)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  // nuxt-security's `removeLoggers: true` sets `vite.esbuild.drop`, which Vite 8 ignores with a warning on every
  // build (GH-3366): the option did nothing. The app keeps its `console.error` reports of a failed chart, map or
  // query, so the option is off. This fails when it is switched on again (whatever its form) and when someone
  // adds `vite.esbuild` by hand; the module's own write to `nuxt.options` at setup is not seen here.
  it('are not removed through an esbuild option that Vite 8 ignores', async () => {
    const config = await loadConfig()

    expect(config.security.removeLoggers).toBe(false)
    expect(config.vite.esbuild).toBeUndefined()
  })
})
