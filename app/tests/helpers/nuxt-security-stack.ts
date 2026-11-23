import { createRequire } from 'node:module'
import { join } from 'node:path'
import { vi } from 'vitest'

// nuxt-security's own server middleware, run as it is by the tests that put a proxy behind it (GH-4362, GH-4364),
// with the rules that the module resolves for a path from `nuxt.config.ts`: its `security` options are the rules of
// every route (`/**`), the `routeRules` with a `security` key are the rules of one route, and the module's defaults
// (`defaultConfig.mjs`) are what neither of them says. The plugin `00-routeRules` of nuxt-security does this in the
// built app, where the e2e check of GH-4364 reads what comes out.

const APP = join(__dirname, '..', '..')
const SECURITY = join(APP, 'node_modules', 'nuxt-security', 'dist', 'runtime')
const nuxtRequire = createRequire(createRequire(import.meta.url).resolve('nuxt/package.json'))

export const h3 = nuxtRequire('h3') as typeof import('h3')

// h3's mark on a request whose body `readBody` or `readRawBody` has read whole (and cached)
export const RAW_BODY = Symbol.for('h3RawBody')

// What nuxt-security's defaults give every route (`defaultConfig.mjs`), before the app or a route changes it
const MODULE_DEFAULTS: Rules = {
  enabled: true,
  xssValidator: { methods: ['GET', 'POST'], throwError: true },
  requestSizeLimiter: { maxRequestSizeInBytes: 2e6, maxUploadFileRequestInBytes: 8e6, throwError: true },
}

type Rules = Record<string, unknown>

interface Context {
  getAppSecurityOptions: () => Rules
  resolveSecurityRules: (event: unknown) => Rules
}

export type RulesMode = 'app' | 'module-defaults'

export interface SecurityStack {
  context: Context
  /** The `security` options of the app's `nuxt.config.ts` (the rules of `/**`) */
  appOptions: Rules
  /** The middleware `xssValidator`, as nuxt-security registers it */
  xssValidator: ReturnType<typeof h3.defineEventHandler>
  /**
   * Sets what the module resolves rules from.
   *
   * @param mode `app`: the app's options and `routeRules`; `module-defaults`: nuxt-security as it is installed,
   * with nothing of the app's
   */
  setRules: (mode: RulesMode) => void
}

/**
 * Loads nuxt-security's middleware and the app's config.
 *
 * The test file needs `vi.mock('@tailwindcss/vite')`, since the config imports it.
 *
 * @returns The middleware, the rules' context and a function that sets the rules
 */
export async function loadSecurityStack(): Promise<SecurityStack> {
  vi.stubGlobal('defineNuxtConfig', (value: unknown) => value)
  const config = (await import('../../nuxt.config')).default as unknown as {
    security: Rules
    routeRules: Record<string, { security?: Rules }>
  }
  const context = await import(/* @vite-ignore */ join(SECURITY, 'nitro', 'context', 'index.js')) as Context
  const { default: xssValidator } = await import(/* @vite-ignore */ join(SECURITY, 'server', 'middleware', 'xssValidator.js'))
  function setRules(mode: RulesMode): void {
    const rules = context.getAppSecurityOptions()
    for (const key of Object.keys(rules))
      delete rules[key]
    const global: Rules = structuredClone(MODULE_DEFAULTS)
    if (mode === 'app') {
      // a rule that the app gives (`xssValidator: false`) replaces the module's
      for (const name of ['xssValidator', 'requestSizeLimiter']) {
        if (name in config.security)
          global[name] = structuredClone(config.security[name])
      }
    }
    rules['/**'] = global
    if (mode === 'app') {
      for (const [route, rule] of Object.entries(config.routeRules)) {
        if (rule.security)
          rules[route] = structuredClone(rule.security)
      }
    }
  }
  return { context, appOptions: config.security, xssValidator, setRules }
}
