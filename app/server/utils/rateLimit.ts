// The rate limit of the app's server (GH-3093): what it counts, how it counts, and whose requests they are.
// The pure parts live here so a test can read them without a server; `server/middleware/rate-limit.ts`
// is the part that talks to h3.

/**
 * The default limit, the one place it is written: 300 requests in 300 seconds for each client, that is
 * 60 a minute. An operator changes it at run time with `NUXT_RATE_LIMIT_TOKENS` and
 * `NUXT_RATE_LIMIT_WINDOW_SECONDS` (`runtimeConfig.rateLimit` in `nuxt.config.ts` reads these).
 */
export const RATE_LIMIT_DEFAULTS = { tokens: 300, windowSeconds: 300 } as const

/**
 * What the app serves from the catalogue of the backend: small, the same for every caller, and asked for
 * by every page it shows. They are not counted. Everything else under `/api` and `/mcp` is, which makes a
 * route the backend gains later limited until someone decides it is cheap.
 */
const CATALOGUE_ROUTES: ReadonlySet<string> = new Set(['version', 'settings', 'providers', 'coverage', 'glossary', 'auth', 'health'])

/**
 * Whether a request is counted against the limit of its client.
 *
 * The pages, the assets and the proxied `/docs` and `/openapi.json` are not. Under `/api` (and its pinned
 * `/api/v1`) and `/mcp` every route is, but the catalogue ones. The path is read as the router reads it, as
 * written: only a catalogue route spelled exactly, with nothing in front of it or behind it (a single trailing
 * slash aside), is left out. `/api/version/../values` is not `version`: the proxy resolves it to a route of
 * its own, which this does not know, and what is not known is counted.
 *
 * @param path The request's path and query, as `event.path`
 * @returns True if the request counts against the limit
 */
export function isLimited(path: string): boolean {
  if (!path.startsWith('/'))
    return true
  const pathname = path.split('?')[0]!.replace(/(?<=.)\/$/, '')
  const [, first, ...rest] = pathname.split('/')
  if (first === 'mcp')
    return true
  if (first !== 'api')
    return false
  const route = rest[0] === 'v1' ? rest.slice(1) : rest
  return !(route.length === 1 && CATALOGUE_ROUTES.has(route[0]!))
}

/** IPv6 addresses are limited by their /64: a client holds that many, and the limit is for the client */
function ipv6Prefix(address: string): string | undefined {
  const bare = address.split('%')[0]!.toLowerCase()
  const mapped = bare.match(/^(?:::ffff:|::)(\d{1,3}(?:\.\d{1,3}){3})$/)
  if (mapped)
    return mapped[1]
  if (!bare.includes(':'))
    return undefined
  const [head, tail, ...more] = bare.split('::')
  if (more.length > 0)
    return undefined
  const groups = head ? head.split(':') : []
  const rest = tail === undefined ? [] : tail ? tail.split(':') : []
  const missing = 8 - groups.length - rest.length
  if (tail === undefined ? groups.length !== 8 : missing < 0)
    return undefined
  const all = [...groups, ...Array.from<string>({ length: tail === undefined ? 0 : missing }).fill('0'), ...rest]
  return `${all.slice(0, 4).map(group => group.replace(/^0+(?=.)/, '')).join(':')}::/64`
}

/**
 * The key a request is counted under: the address of its client.
 *
 * By default that is the address of the connection. A header is read only when the operator names one
 * (`trustedHeader`, `NUXT_RATE_LIMIT_CLIENT_IP_HEADER`), because any client can write any header: a proxy
 * that overwrites it makes the header the truth, and one that does not makes it the client's choice. A
 * list (`x-forwarded-for`) is read from its end, the address the nearest proxy saw. A header that is not
 * there or says nothing falls back to the connection.
 *
 * @param socketAddress The address of the connection, as the server sees it
 * @param trustedHeader The name of the header the deployment's proxy sets, or empty
 * @param headerValue That header's value in the request
 * @returns The key to count the request under
 */
export function clientKey(socketAddress: string | undefined, trustedHeader: string, headerValue: string | undefined): string {
  const named = trustedHeader ? headerValue?.split(',').at(-1)?.trim() : undefined
  const address = named || socketAddress || 'unknown'
  return ipv6Prefix(address) ?? address
}

export interface RateLimitResult {
  allowed: boolean
  /** Requests left in this window, after this one */
  remaining: number
  /** When the window ends, in milliseconds since the epoch */
  resetAt: number
}

interface Bucket { used: number, resetAt: number }

/** What the table of clients may hold: a client that is not seen again is dropped when its window is over */
const MAX_CLIENTS = 100_000

/**
 * Counts requests per key in fixed windows, in memory: one process, which is how the app runs.
 *
 * @returns A limiter whose `take` counts one request
 */
export function createRateLimiter() {
  const buckets = new Map<string, Bucket>()
  let nextSweep = 0
  return {
    take(key: string, tokens: number, windowMs: number, now = Date.now()): RateLimitResult {
      if (now >= nextSweep || buckets.size > MAX_CLIENTS) {
        for (const [other, bucket] of buckets) {
          if (bucket.resetAt <= now)
            buckets.delete(other)
        }
        // still over the cap with every window open: the oldest clients go first
        for (const other of buckets.keys()) {
          if (buckets.size <= MAX_CLIENTS)
            break
          buckets.delete(other)
        }
        nextSweep = now + windowMs
      }
      let bucket = buckets.get(key)
      if (!bucket || bucket.resetAt <= now) {
        bucket = { used: 0, resetAt: now + windowMs }
        buckets.set(key, bucket)
      }
      if (bucket.used >= tokens)
        return { allowed: false, remaining: 0, resetAt: bucket.resetAt }
      bucket.used += 1
      return { allowed: true, remaining: tokens - bucket.used, resetAt: bucket.resetAt }
    },
    get size() {
      return buckets.size
    },
  }
}

/** A positive whole number from the runtime config (an environment variable arrives as text), else the default */
export function positiveInteger(value: unknown, fallback: number): number {
  const number = Number(value)
  return Number.isInteger(number) && number >= 1 ? number : fallback
}
