import type { H3Event } from 'h3'
import type { IncomingMessage, Server, ServerResponse } from 'node:http'
import type { AddressInfo } from 'node:net'
import type { SecurityStack } from '../helpers/nuxt-security-stack'
import { Buffer } from 'node:buffer'
import { createServer } from 'node:http'
import { join } from 'node:path'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { h3, loadSecurityStack, RAW_BODY } from '../helpers/nuxt-security-stack'

// No request body is read whole before a route runs (GH-4364). nuxt-security's `xssValidator` calls h3's `readBody`
// for every POST, on any path, which reads the whole body into memory before a route is picked, and its
// `requestSizeLimiter` looks at a declared `Content-Length` only: a chunked body of 16 MiB was read whole. The
// app has no `xssValidator` now (`security` of `nuxt.config.ts`), and the one route that reads a body, `/mcp`,
// caps what it reads (`tests/unit/mcp-proxy.test.ts`).
//
// Here the real middleware of nuxt-security (both of them) runs in front of the app's `/api` proxy and a path
// that is no route, with the rules it resolves from the app's config. A body that was read whole is h3's mark on
// the request (`RAW_BODY`), which `readBody` and `readRawBody` set when the reading starts.
vi.mock('@tailwindcss/vite', () => ({ default: () => ({ name: 'tailwindcss-stub' }) }))
// the `#imports` of the module's `requestSizeLimiter` (a Nuxt alias, which this project does not have)
vi.mock('#imports', () => ({ useRuntimeConfig: () => ({}) }))

const MIB = 1024 * 1024
const CHUNK = Buffer.alloc(64 * 1024, 'a')

const servers: Server[] = []
// what the backend of this test was asked for
const asked: string[] = []
// the requests the app's server met, in order
const met: IncomingMessage[] = []
const config = { apiBase: '' }
let stack: SecurityStack
let app: string

function backend(request: IncomingMessage, response: ServerResponse): void {
  asked.push(`${request.method} ${request.url}`)
  response.writeHead(200, { 'content-type': 'application/json' })
  response.end(JSON.stringify({ url: request.url }))
}

function listen(server: Server): Promise<string> {
  return new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${(server.address() as AddressInfo).port}`)))
}

beforeAll(async () => {
  stack = await loadSecurityStack()
  for (const [name, value] of Object.entries({
    defineEventHandler: h3.defineEventHandler,
    getQuery: h3.getQuery,
    getRequestHeader: h3.getRequestHeader,
    sendProxy: h3.sendProxy,
    setResponseHeader: h3.setResponseHeader,
    setResponseStatus: h3.setResponseStatus,
    useRuntimeConfig: () => config,
  }))
    vi.stubGlobal(name, value)
  const { default: requestSizeLimiter } = await import(/* @vite-ignore */ join(__dirname, '..', '..', 'node_modules', 'nuxt-security', 'dist', 'runtime', 'server', 'middleware', 'requestSizeLimiter.js'))
  const { default: apiHandler } = await import('../../server/api/[...].get')
  // nitro's order: nuxt-security's two middleware, then the route that matches the method and the path. The file
  // `server/api/[...].get.ts` is the `/api` proxy for a GET only, and no other file of the server is for a POST
  // to any other path, so a router of h3 (404 for a path, 405 for a method) stands for the rest.
  const router = h3.createRouter()
  router.get('/api/**', apiHandler)
  const handlers = h3.createApp()
  handlers.use(h3.defineEventHandler((event: H3Event) => {
    met.push(event.node.req)
  }))
  handlers.use(requestSizeLimiter)
  handlers.use(stack.xssValidator)
  handlers.use(router)
  const server = createServer(h3.toNodeListener(handlers))
  const stub = createServer(backend)
  servers.push(server, stub)
  app = await listen(server)
  config.apiBase = `${await listen(stub)}/api`
})

beforeEach(() => {
  asked.length = 0
  met.length = 0
  stack.setRules('app')
})

afterEach(() => stack.setRules('app'))

afterAll(async () => {
  vi.unstubAllGlobals()
  await Promise.all(servers.map(server => new Promise(resolve => server.close(resolve))))
})

/** A body of `mebibytes` MiB that is sent chunked: a stream has no length to declare */
function chunkedBody(mebibytes: number): ReadableStream<Uint8Array> {
  let sent = 0
  return new ReadableStream({
    pull(controller) {
      if (sent >= mebibytes * MIB) {
        controller.close()
        return
      }
      sent += CHUNK.length
      controller.enqueue(CHUNK)
    },
  })
}

async function sendChunked(method: string, path: string, mebibytes = 16): Promise<Response> {
  return fetch(`${app}${path}`, {
    method,
    body: chunkedBody(mebibytes),
    headers: { 'content-type': 'application/json' },
    duplex: 'half',
  } as RequestInit)
}

function bodyWasRead(request: IncomingMessage): boolean {
  return RAW_BODY in request
}

describe('the rules of the app', () => {
  it.each(['/', '/does-not-exist', '/api/values', '/mcp/v1', '/openapi.json'])('have no xssValidator for %s', (path) => {
    expect(stack.context.resolveSecurityRules({ path, context: {} }).xssValidator).toBe(false)
  })

  it('keep the requestSizeLimiter, which reads no body', () => {
    expect(stack.context.resolveSecurityRules({ path: '/api/values', context: {} }).requestSizeLimiter).toBeTruthy()
  })
})

describe('a chunked body of 16 MiB', () => {
  it.each(['POST', 'PUT', 'PATCH', 'DELETE'])('%s to a path that is no route is answered and not read', async (method) => {
    const response = await sendChunked(method, '/does-not-exist')

    expect(response.status).toBe(404)
    expect(met).toHaveLength(1)
    expect(bodyWasRead(met[0]!)).toBe(false)
    expect(asked).toEqual([])
  })

  it.each(['POST', 'PATCH'])('%s to /api/values is answered, not read, and not sent to the backend', async (method) => {
    const response = await sendChunked(method, '/api/values')

    // the proxy is for a GET only: a method of another kind is no route of it
    expect([404, 405]).toContain(response.status)
    expect(bodyWasRead(met[0]!)).toBe(false)
    expect(asked).toEqual([])
  })

  it('is read whole by nuxt-security as it is installed, which is what the app turned off', async () => {
    stack.setRules('module-defaults')
    const response = await sendChunked('POST', '/does-not-exist')

    // 400, as the validator finds no JSON in it, after it has read all of it
    expect(response.status).toBe(400)
    expect(bodyWasRead(met[0]!)).toBe(true)
  })
})

describe('the /api proxy behind the middleware of nuxt-security', () => {
  it('answers a GET with what the backend answered', async () => {
    const response = await fetch(`${app}/api/values?provider=dwd`)

    expect(response.status).toBe(200)
    expect(await response.json()).toEqual({ url: '/api/values?provider=dwd' })
    expect(asked).toEqual(['GET /api/values?provider=dwd'])
  })

  it('answers a small POST, which no route of the app takes, without reading it', async () => {
    const response = await fetch(`${app}/api/values`, { method: 'POST', body: JSON.stringify({ a: 1 }), headers: { 'content-type': 'application/json' } })

    expect([404, 405]).toContain(response.status)
    expect(bodyWasRead(met[0]!)).toBe(false)
    expect(asked).toEqual([])
  })

  it('refuses a declared 3 MB body with a 413 (the requestSizeLimiter, 2,000,000 bytes), before any of it is read', async () => {
    const response = await fetch(`${app}/api/values`, { method: 'POST', body: Buffer.alloc(3 * MIB, 'a'), headers: { 'content-type': 'application/json' } })

    expect(response.status).toBe(413)
    expect(bodyWasRead(met[0]!)).toBe(false)
    expect(asked).toEqual([])
  })
})
