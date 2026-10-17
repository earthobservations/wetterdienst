import type { Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { clientKey, createRateLimiter, isLimited, positiveInteger, RATE_LIMIT_DEFAULTS } from '../../server/utils/rateLimit'
import { requestIdOf } from '../../server/utils/requestId'

// The rate limit of the server (GH-3093): the table of what is counted, the clients told apart, and the
// middleware run for real, on an h3 server with the limit lowered through its runtime config, which is
// where `NUXT_RATE_LIMIT_*` puts it.

describe('what is counted', () => {
  it.each([
    '/api/values',
    '/api/v1/values?provider=dwd',
    '/api/stations',
    '/api/interpolate',
    '/api/summarize',
    '/api/stripes/values',
    '/api/stripes/image',
    '/api/history',
    '/api/issues',
    '/mcp',
    '/mcp/v1',
    '/mcp/v1/anything',
  ])('counts %s', (path) => {
    expect(isLimited(path)).toBe(true)
  })

  it.each([
    '/api/version',
    '/api/v1/version',
    '/api/settings',
    '/api/providers',
    '/api/coverage?provider=dwd',
    '/api/glossary',
    '/api/auth',
    '/api/health',
    '/api/version/',
  ])('leaves the catalogue route %s out', (path) => {
    expect(isLimited(path)).toBe(false)
  })

  it.each([
    '/',
    '/explorer',
    '/explorer?provider=dwd&network=observation',
    '/providers/dwd',
    '/docs',
    '/openapi.json',
    '/_nuxt/entry.js',
    '/_swagger-ui/swagger-ui-bundle.js',
    '/.well-known/oauth-protected-resource',
    '/apix',
    '/mcpx',
  ])('leaves the page or asset %s out', (path) => {
    expect(isLimited(path)).toBe(false)
  })

  it.each([
    // a route the backend gains later is counted until someone says it is cheap
    '/api/something-new',
    '/api/v2/version',
    // a catalogue route is exactly that route: nothing under it, nothing in front of it, nothing that reaches another
    '/api/version/extra',
    '/api/version/../values',
    '/api/%2e%2e/values',
    '/api/v1/../values',
    '/api//values',
    '/api/Version',
    '/api/vers%69on',
    '/api/..%2fversion',
    '/api',
    '/api/',
    '/api/v1',
    // not a path the server can place
    'api/version',
    '*',
  ])('counts %s, which is not a catalogue route spelled plainly', (path) => {
    expect(isLimited(path)).toBe(true)
  })
})

describe('whose requests they are', () => {
  it('is the address of the connection unless a header is named', () => {
    expect(clientKey('203.0.113.7', '', '198.51.100.1')).toBe('203.0.113.7')
    expect(clientKey('203.0.113.7', '', undefined)).toBe('203.0.113.7')
  })

  it('reads the named header from its end, the address the nearest proxy saw', () => {
    expect(clientKey('10.0.0.1', 'x-forwarded-for', '198.51.100.1')).toBe('198.51.100.1')
    expect(clientKey('10.0.0.1', 'x-forwarded-for', '1.1.1.1, 2.2.2.2,  198.51.100.9')).toBe('198.51.100.9')
  })

  it('falls back to the connection for a header that is not there, or says nothing', () => {
    expect(clientKey('10.0.0.1', 'x-forwarded-for', undefined)).toBe('10.0.0.1')
    expect(clientKey('10.0.0.1', 'x-forwarded-for', '')).toBe('10.0.0.1')
    expect(clientKey('10.0.0.1', 'x-forwarded-for', ' , ')).toBe('10.0.0.1')
    expect(clientKey(undefined, '', undefined)).toBe('unknown')
  })

  it('counts an IPv6 client by its /64, which is what one client holds, and an IPv4-mapped address as IPv4', () => {
    const key = clientKey('2001:db8:1:2:aaaa:bbbb:cccc:dddd', '', undefined)
    expect(key).toBe('2001:db8:1:2::/64')
    expect(clientKey('2001:0db8:0001:0002::1', '', undefined)).toBe(key)
    expect(clientKey('2001:db8:1:3::1', '', undefined)).not.toBe(key)
    expect(clientKey('::ffff:203.0.113.7', '', undefined)).toBe('203.0.113.7')
    expect(clientKey('::1', '', undefined)).toBe('0:0:0:0::/64')
    expect(clientKey('fe80::1%en0', '', undefined)).toBe('fe80:0:0:0::/64')
  })
})

describe('the count', () => {
  it('lets a key have its tokens in a window, then refuses until the window is over', () => {
    const limiter = createRateLimiter()
    const results = [0, 1, 2, 3].map(i => limiter.take('a', 3, 1000, 100 + i))
    expect(results.map(r => r.allowed)).toEqual([true, true, true, false])
    expect(results.map(r => r.remaining)).toEqual([2, 1, 0, 0])
    expect(results[3]!.resetAt).toBe(1100)
    expect(limiter.take('a', 3, 1000, 1099).allowed).toBe(false)
    expect(limiter.take('a', 3, 1000, 1100)).toMatchObject({ allowed: true, remaining: 2, resetAt: 2100 })
  })

  it('counts a key by itself', () => {
    const limiter = createRateLimiter()
    limiter.take('a', 1, 1000, 0)
    expect(limiter.take('a', 1, 1000, 1).allowed).toBe(false)
    expect(limiter.take('b', 1, 1000, 1).allowed).toBe(true)
  })

  it('forgets a client whose window is over, so the table does not grow with the clients it has seen', () => {
    const limiter = createRateLimiter()
    for (let i = 0; i < 50; i++)
      limiter.take(`client-${i}`, 5, 1000, 0)
    expect(limiter.size).toBe(50)
    limiter.take('late', 5, 1000, 5000)
    expect(limiter.size).toBe(1)
  })

  it.each([
    ['300', 7, 300],
    [300, 7, 300],
    ['5', 7, 5],
    ['0', 7, 7],
    ['-1', 7, 7],
    ['1.5', 7, 7],
    ['many', 7, 7],
    [undefined, 7, 7],
    [Number.NaN, 7, 7],
  ])('reads %j from the config as a whole number of at least one, else the default', (value, fallback, expected) => {
    expect(positiveInteger(value, fallback)).toBe(expected)
  })

  it('is 300 requests in 300 seconds unless set', () => {
    expect(RATE_LIMIT_DEFAULTS).toEqual({ tokens: 300, windowSeconds: 300 })
  })
})

// The middleware as Nitro runs it: h3's own functions are its auto-imports, and so are the utilities.
const nuxtRequire = createRequire(createRequire(import.meta.url).resolve('nuxt/package.json'))
const h3 = nuxtRequire('h3') as typeof import('h3')

const config = {
  rateLimit: { enabled: true, tokens: 3, windowSeconds: 300, clientIpHeader: '' as string },
}
const servers: Server[] = []
let app: string

function raw(path: string, headers: Record<string, string> = {}) {
  return fetch(`${app}${path}`, { headers })
}

beforeAll(async () => {
  for (const [name, value] of Object.entries({
    defineEventHandler: h3.defineEventHandler,
    getRequestIP: h3.getRequestIP,
    getRequestHeader: h3.getRequestHeader,
    setResponseHeader: h3.setResponseHeader,
    setResponseStatus: h3.setResponseStatus,
    useRuntimeConfig: () => config,
    createRateLimiter,
    isLimited,
    clientKey,
    positiveInteger,
    RATE_LIMIT_DEFAULTS,
    requestIdOf,
  }))
    vi.stubGlobal(name, value)
  const { default: middleware } = await import('../../server/middleware/rate-limit')
  const router = h3.createApp()
  router.use(middleware)
  router.use(h3.defineEventHandler(() => ({ ok: true })))
  const server = createServer(h3.toNodeListener(router))
  servers.push(server)
  app = await new Promise<string>(resolve => server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${(server.address() as AddressInfo).port}`)))
})

afterAll(async () => {
  vi.unstubAllGlobals()
  await Promise.all(servers.map(server => new Promise(resolve => server.close(resolve))))
})

// each test is a client of its own, by the header the middleware is told to read
let clients = 0
function newClient() {
  config.rateLimit.clientIpHeader = 'x-test-client'
  return { 'x-test-client': `198.51.100.${++clients}` }
}

describe('the middleware', () => {
  it('lets a catalogue route and a page through however often they are asked for, while a values route is refused past the limit', async () => {
    const client = newClient()
    for (let i = 0; i < 10; i++) {
      expect((await raw('/api/version', client)).status).toBe(200)
      expect((await raw('/api/coverage', client)).status).toBe(200)
      expect((await raw('/explorer', client)).status).toBe(200)
    }
    const statuses = []
    for (let i = 0; i < 5; i++)
      statuses.push((await raw('/api/values?provider=dwd', client)).status)

    expect(statuses).toEqual([200, 200, 200, 429, 429])
  })

  it('counts the values, stations and MCP routes of a client together, and answers the first one refused with a problem and when to retry', async () => {
    const client = newClient()
    expect((await raw('/api/values', client)).status).toBe(200)
    expect((await raw('/api/stations', client)).status).toBe(200)
    expect((await raw('/mcp/v1', client)).status).toBe(200)
    const refused = await raw('/api/interpolate', { ...client, 'x-request-id': 'client-id.1' })

    expect(refused.status).toBe(429)
    expect(refused.headers.get('content-type')).toBe('application/problem+json')
    expect(Number(refused.headers.get('retry-after'))).toBeGreaterThan(0)
    expect(Number(refused.headers.get('retry-after'))).toBeLessThanOrEqual(300)
    expect(refused.headers.get('x-request-id')).toBe('client-id.1')
    expect(await refused.json()).toMatchObject({
      type: 'urn:wetterdienst:problem:rate-limited',
      title: 'Too Many Requests',
      status: 429,
      instance: 'urn:wetterdienst:request:client-id.1',
      request_id: 'client-id.1',
    })
  })

  it('sends the rate-limit headers with every counted answer, and none with an uncounted one', async () => {
    const client = newClient()
    const first = await raw('/api/values', client)
    const second = await raw('/api/values', client)

    expect(first.headers.get('x-ratelimit-limit')).toBe('3')
    expect(first.headers.get('x-ratelimit-remaining')).toBe('2')
    expect(second.headers.get('x-ratelimit-remaining')).toBe('1')
    expect(Number(first.headers.get('x-ratelimit-reset'))).toBeGreaterThan(Date.now() / 1000)
    const uncounted = await raw('/api/version', client)
    expect(uncounted.headers.get('x-ratelimit-limit')).toBeNull()
    expect(uncounted.headers.get('x-ratelimit-remaining')).toBeNull()
  })

  it('keeps one client\'s count from another\'s', async () => {
    const one = newClient()
    const other = newClient()
    for (let i = 0; i < 3; i++)
      await raw('/api/values', one)

    expect((await raw('/api/values', one)).status).toBe(429)
    expect((await raw('/api/values', other)).status).toBe(200)
  })

  it('ignores a header nobody was told to trust: a client cannot start a count of its own by writing one', async () => {
    config.rateLimit.clientIpHeader = ''
    const statuses = []
    for (let i = 0; i < 5; i++)
      statuses.push((await raw('/api/values', { 'x-forwarded-for': `203.0.113.${i + 1}`, 'x-test-client': `203.0.113.${i + 1}` })).status)

    // the connection is one address, whoever the headers say it is
    expect(statuses).toEqual([200, 200, 200, 429, 429])
  })

  it('reads the header the operator names, from its end', async () => {
    config.rateLimit.clientIpHeader = 'X-Forwarded-For'
    // the proxy appends the address it saw to what the client wrote: the client's own entries are not its count
    const behind = (spoofed: string) => ({ 'x-forwarded-for': `${spoofed}, 198.51.100.200` })
    for (let i = 0; i < 3; i++)
      expect((await raw('/api/values', behind(`10.0.0.${i}`))).status).toBe(200)

    expect((await raw('/api/values', behind('10.9.9.9'))).status).toBe(429)
    expect((await raw('/api/values', { 'x-forwarded-for': '198.51.100.201' })).status).toBe(200)
  })

  it('does nothing when the limit is switched off, as in the e2e suite\'s own build', async () => {
    const client = newClient()
    config.rateLimit.enabled = false
    try {
      for (let i = 0; i < 6; i++)
        expect((await raw('/api/values', client)).status).toBe(200)
      expect((await raw('/api/values', client)).headers.get('x-ratelimit-limit')).toBeNull()
    }
    finally {
      config.rateLimit.enabled = true
    }
  })

  it('takes the limit and the window from the config, falling back to the defaults for a value that is none', async () => {
    const client = newClient()
    config.rateLimit.tokens = 'not a number' as unknown as number
    try {
      const answer = await raw('/api/values', client)
      expect(answer.headers.get('x-ratelimit-limit')).toBe(String(RATE_LIMIT_DEFAULTS.tokens))
    }
    finally {
      config.rateLimit.tokens = 3
    }
  })

  it('does not count the preflight request of a browser', async () => {
    const client = newClient()
    for (let i = 0; i < 6; i++)
      expect((await fetch(`${app}/api/values`, { method: 'OPTIONS', headers: client })).headers.get('x-ratelimit-limit')).toBeNull()
  })
})
