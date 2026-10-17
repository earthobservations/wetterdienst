import type { IncomingMessage, Server, ServerResponse } from 'node:http'
import type { AddressInfo } from 'node:net'
import { createServer, request as httpRequest } from 'node:http'
import { createRequire } from 'node:module'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'

// The catch-all at `server/api/[...].get.ts` run for real: Nitro's auto-imports are h3's own functions, taken
// from the h3 that Nuxt resolves, and the backend is a server of this test, which answers the way the backend's
// problems are written (docs/usage/restapi.md, "Errors"). What a client sees is read off a real response.
const nuxtRequire = createRequire(createRequire(import.meta.url).resolve('nuxt/package.json'))
const h3 = nuxtRequire('h3') as typeof import('h3')

function listen(server: Server): Promise<string> {
  return new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${(server.address() as AddressInfo).port}`)))
}

function backend(request: IncomingMessage, response: ServerResponse): void {
  // the backend answers with the id it was sent, as the real one does
  const requestId = String(request.headers['x-request-id'])
  const headers = {
    'x-request-id': requestId,
    'server': 'uvicorn',
    'set-cookie': 'session=1',
    'x-wetterdienst-license': 'CC-BY-4.0',
  }
  if (request.url?.startsWith('/api/timeout')) {
    // an id of its own, which is what the client has to read: the proxy relays the backend's, it does not replace it
    response.writeHead(504, { ...headers, 'x-request-id': 'backend-own-id', 'content-type': 'application/problem+json', 'retry-after': '30' })
    response.end(JSON.stringify({ type: 'urn:wetterdienst:problem:request-timeout', title: 'Gateway Timeout', status: 504, detail: 'Too slow.', request_id: 'backend-own-id' }))
    return
  }
  if (!request.url?.startsWith('/api')) {
    // beside the API, as the backend's own `/health` and `/docs` are
    response.writeHead(200, { ...headers, 'content-type': 'application/json' })
    response.end(JSON.stringify({ outside: request.url }))
    return
  }
  response.writeHead(200, { ...headers, 'content-type': 'application/json' })
  response.end(JSON.stringify({ received: request.headers, url: request.url }))
}

// A request with the path as the client wrote it: `fetch` normalises `..` before it sends anything
function rawGet(base: string, path: string): Promise<{ status: number, body: string }> {
  return new Promise((resolve, reject) => {
    const { port } = new URL(base)
    httpRequest({ host: '127.0.0.1', port, path, method: 'GET' }, (response) => {
      let body = ''
      response.on('data', (chunk) => {
        body += chunk
      })
      response.on('end', () => resolve({ status: response.statusCode ?? 0, body }))
    }).on('error', reject).end()
  })
}

const servers: Server[] = []
// where the app's proxy sends a request, which each test sets
const config = { apiBase: '' }

let app: string
let backendBase: string
let closedBase: string

beforeAll(async () => {
  vi.stubGlobal('defineEventHandler', h3.defineEventHandler)
  vi.stubGlobal('getQuery', h3.getQuery)
  vi.stubGlobal('getRequestHeader', h3.getRequestHeader)
  vi.stubGlobal('sendProxy', h3.sendProxy)
  vi.stubGlobal('setResponseStatus', h3.setResponseStatus)
  vi.stubGlobal('setResponseHeader', h3.setResponseHeader)
  vi.stubGlobal('useRuntimeConfig', () => ({ public: config }))
  const { default: handler } = await import('../../server/api/[...].get')
  const router = h3.createApp()
  router.use(handler)
  const proxy = createServer(h3.toNodeListener(router))
  const stub = createServer(backend)
  servers.push(proxy, stub)
  app = await listen(proxy)
  backendBase = `${await listen(stub)}/api`
  // a port nobody listens on: the connection is refused
  const closed = createServer()
  closedBase = `${await listen(closed)}/api`
  await new Promise(resolve => closed.close(resolve))
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterAll(async () => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  await Promise.all(servers.map(server => new Promise(resolve => server.close(resolve))))
})

describe('the /api proxy and the answer of the backend', () => {
  it('passes on the request id and the Retry-After of a problem the backend answered', async () => {
    config.apiBase = backendBase
    const response = await fetch(`${app}/api/timeout`)

    expect(response.status).toBe(504)
    expect(response.headers.get('content-type')).toBe('application/problem+json')
    expect(response.headers.get('retry-after')).toBe('30')
    expect(response.headers.get('x-request-id')).toBe('backend-own-id')
    expect((await response.json()).type).toBe('urn:wetterdienst:problem:request-timeout')
  })

  it('does not republish what describes the backend, and keeps the headers of the data', async () => {
    config.apiBase = backendBase
    const response = await fetch(`${app}/api/timeout`)

    expect(response.headers.get('server')).toBeNull()
    expect(response.headers.get('set-cookie')).toBeNull()
    expect(response.headers.get('x-wetterdienst-license')).toBe('CC-BY-4.0')
  })

  it('sends the request id of the client on to the backend, which answers with it, and nothing else of the client', async () => {
    config.apiBase = backendBase
    const response = await fetch(`${app}/api/anything`, { headers: { 'x-request-id': 'client-id.1', 'cookie': 'a=b', 'authorization': 'secret' } })

    expect(response.headers.get('x-request-id')).toBe('client-id.1')
    const { received } = await response.json() as { received: Record<string, string> }
    expect(received['x-request-id']).toBe('client-id.1')
    expect(received.cookie).toBeUndefined()
    expect(received.authorization).toBeUndefined()
  })

  it('makes an id for a request that has none, and the backend answers with it', async () => {
    config.apiBase = backendBase
    const response = await fetch(`${app}/api/anything`)

    expect(response.headers.get('x-request-id')).toMatch(/^[0-9a-f]{32}$/)
  })
})

describe('the /api proxy and the path of the client', () => {
  it.each([
    '/api/../health',
    '/api/%2e%2e/health',
    '/api/%2E%2E/health',
    '/api/./../health',
    '/api/stations/../../health',
  ])('does not leave apiBase for %s, and answers it a 404 problem without asking the backend', async (path) => {
    config.apiBase = backendBase
    const { status, body } = await rawGet(app, path)

    expect(status).toBe(404)
    expect(JSON.parse(body).type).toBe('urn:wetterdienst:problem:not-found')
    expect(body).not.toContain('outside')
  })

  it('keeps a path that stays under apiBase, however it gets there', async () => {
    config.apiBase = backendBase
    const { status, body } = await rawGet(app, '/api/stations/../values?parameters=daily%2Fkl')

    expect(status).toBe(200)
    expect(JSON.parse(body).url).toBe('/api/values?parameters=daily%2Fkl')
  })

  it('takes an encoded slash as a character of a segment, not as one that could leave apiBase', async () => {
    config.apiBase = backendBase
    const { status, body } = await rawGet(app, '/api/..%2fhealth')

    expect(status).toBe(200)
    expect(JSON.parse(body).url).toMatch(/^\/api\/\.\.%2fhealth/i)
  })
})

describe('the /api proxy and a backend that cannot be reached', () => {
  it('answers a problem of the documented type, with the id of the request and when to retry', async () => {
    config.apiBase = closedBase
    const response = await fetch(`${app}/api/stations`, { headers: { 'x-request-id': 'client-id.1' } })

    expect(response.status).toBe(502)
    expect(response.headers.get('content-type')).toBe('application/problem+json')
    expect(response.headers.get('x-request-id')).toBe('client-id.1')
    expect(response.headers.get('retry-after')).toBe('30')
    expect(await response.json()).toEqual({
      type: 'urn:wetterdienst:problem:backend-unreachable',
      title: 'Bad Gateway',
      status: 502,
      detail: 'The backend could not be reached. The cause is in the server log.',
      instance: 'urn:wetterdienst:request:client-id.1',
      request_id: 'client-id.1',
    })
  })
})
