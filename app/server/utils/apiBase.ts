import * as process from 'node:process'

// Where the app's proxies (`/api`, `/mcp`, `/docs`, `/openapi.json`) find the backend: its `/api` (or `/api/v1`) URL.
//
// It is the private runtime config key `apiBase`, set at run time by `NUXT_API_BASE` (GH-3096). It used to be a
// public key, `NUXT_PUBLIC_API_BASE`, which put the backend's address into every page although no code in the
// browser reads it. Nuxt applies an environment variable only to a key the config has, so the old name does
// nothing by itself: it is read here, as a fallback, for a few releases, and the server says so when it starts.

/** What the proxies use when neither variable is set: a backend on this machine. */
export const DEFAULT_API_BASE = 'http://localhost:7890/api'

export const API_BASE_ENV = 'NUXT_API_BASE'
export const LEGACY_API_BASE_ENV = 'NUXT_PUBLIC_API_BASE'

type Env = Record<string, string | undefined>

/**
 * The backend URL: `NUXT_API_BASE` (the config's `apiBase`, empty when it is not set), else the old
 * `NUXT_PUBLIC_API_BASE`, else the default. An empty variable counts as not set, as it does for Nuxt.
 */
export function resolveApiBase(configured: string | undefined, env: Env = process.env): string {
  return configured || env[LEGACY_API_BASE_ENV] || DEFAULT_API_BASE
}

/**
 * The one line to log at server start if the old variable is set, otherwise `undefined`. It names variables and
 * never their values: a backend URL can carry credentials.
 */
export function apiBaseDeprecation(configured: string | undefined, env: Env = process.env): string | undefined {
  if (!env[LEGACY_API_BASE_ENV])
    return undefined
  return configured
    ? `${LEGACY_API_BASE_ENV} is deprecated and ignored, because ${API_BASE_ENV} is set; remove it.`
    : `${LEGACY_API_BASE_ENV} is deprecated and will be removed in a future release; set ${API_BASE_ENV} instead, to the same value.`
}

/** The backend URL for this request, from the runtime config. */
export function useApiBase(): string {
  return resolveApiBase(useRuntimeConfig().apiBase as string | undefined)
}
