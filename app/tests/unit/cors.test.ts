import type { Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { corsHeaders, parseAllowedOrigins } from '../../server/utils/cors'

// Same origin unless named (GH-3095): the app answers no `access-control-allow-origin` to a page of another
// origin, `*` least, unless `NUXT_CORS_ALLOWED_ORIGINS` lists it.

describe('the origins an operator names', () => {
  it('reads a list separated by commas, without spaces or trailing slashes', () => {
    expect(parseAllowedOrigins('https://a.example, https://b.example/ ,')).toEqual(['https://a.example', 'https://b.example'])
  })

  it.each([undefined, null, '', ' , '])('reads %j as none', (value) => {
    expect(parseAllowedOrigins(value)).toEqual([])
  })
})

describe('what a response says', () => {
  it('says nothing when no origin is named, to a page of another origin or to no page at all', () => {
    expect(corsHeaders('https://evil.example', [])).toEqual({})
    expect(corsHeaders(undefined, [])).toEqual({})
  })

  it('allows the origins named, by name, and no other', () => {
    const allowed = ['https://a.example']
    expect(corsHeaders('https://a.example', allowed)).toEqual({ 'access-control-allow-origin': 'https://a.example', 'vary': 'Origin' })
    expect(corsHeaders('https://evil.example', allowed)).toEqual({ vary: 'Origin' })
    expect(corsHeaders('https://a.example.evil.example', allowed)).toEqual({ vary: 'Origin' })
    expect(corsHeaders('http://a.example', allowed)).toEqual({ vary: 'Origin' })
  })

  it('does not answer a request without an Origin header with a wildcard, as h3 does', () => {
    expect(corsHeaders(undefined, ['https://a.example'])).toEqual({ vary: 'Origin' })
  })

  it('allows every origin only where the operator wrote `*`', () => {
    expect(corsHeaders('https://evil.example', ['*'])).toEqual({ 'access-control-allow-origin': '*', 'vary': 'Origin' })
  })
})

// the middleware as Nitro runs it
const nuxtRequire = createRequire(createRequire(import.meta.url).resolve('nuxt/package.json'))
const h3 = nuxtRequire('h3') as typeof import('h3')

const config = { corsAllowedOrigins: '' }
const servers: Server[] = []
let app: string

beforeAll(async () => {
  for (const [name, value] of Object.entries({
    defineEventHandler: h3.defineEventHandler,
    getRequestHeader: h3.getRequestHeader,
    appendResponseHeader: h3.appendResponseHeader,
    setResponseHeader: h3.setResponseHeader,
    setResponseStatus: h3.setResponseStatus,
    useRuntimeConfig: () => config,
    parseAllowedOrigins,
    corsHeaders,
  }))
    vi.stubGlobal(name, value)
  const { default: middleware } = await import('../../server/middleware/cors')
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

describe('the middleware', () => {
  it('sets no CORS header by default, and no wildcard, whoever asks', async () => {
    config.corsAllowedOrigins = ''
    for (const headers of [{}, { origin: 'https://evil.example' }] as Record<string, string>[]) {
      const response = await fetch(`${app}/api/values`, { headers })
      expect(response.status).toBe(200)
      expect([...response.headers.keys()].filter(name => name.startsWith('access-control'))).toEqual([])
    }
  })

  it('refuses a preflight of an origin that is not named: it is not answered with permission', async () => {
    config.corsAllowedOrigins = 'https://a.example'
    const response = await fetch(`${app}/api/values`, { method: 'OPTIONS', headers: { 'origin': 'https://evil.example', 'access-control-request-method': 'GET' } })

    expect(response.headers.get('access-control-allow-origin')).toBeNull()
    expect(response.headers.get('access-control-allow-methods')).toBeNull()
  })

  it('answers the origin named, and its preflight, and tells caches the answer depends on the origin', async () => {
    config.corsAllowedOrigins = 'https://a.example, https://b.example'
    const answer = await fetch(`${app}/api/values`, { headers: { origin: 'https://b.example' } })
    expect(answer.headers.get('access-control-allow-origin')).toBe('https://b.example')
    expect(answer.headers.get('vary')).toBe('Origin')
    expect(answer.headers.get('access-control-expose-headers')).toContain('x-request-id')

    const preflight = await fetch(`${app}/mcp/v1`, { method: 'OPTIONS', headers: { 'origin': 'https://a.example', 'access-control-request-method': 'POST', 'access-control-request-headers': 'content-type, mcp-session-id' } })
    expect(preflight.status).toBe(204)
    expect(preflight.headers.get('access-control-allow-origin')).toBe('https://a.example')
    expect(preflight.headers.get('access-control-allow-methods')).toContain('POST')
    expect(preflight.headers.get('access-control-allow-headers')).toBe('content-type, mcp-session-id')
  })

  it('keeps allowing every origin possible, for an operator that wants what the app did before', async () => {
    config.corsAllowedOrigins = '*'
    const response = await fetch(`${app}/api/values`, { headers: { origin: 'https://anyone.example' } })

    expect(response.headers.get('access-control-allow-origin')).toBe('*')
  })
})
