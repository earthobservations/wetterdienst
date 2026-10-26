import type { IncomingMessage, Server, ServerResponse } from 'node:http'
import type { AddressInfo } from 'node:net'
import { Buffer } from 'node:buffer'
import { createServer, request as httpRequest } from 'node:http'
import { createRequire } from 'node:module'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'

// The `/mcp` proxy (`server/utils/mcpProxy.ts`) run for real against a backend of this test, which answers with
// what it was sent. The client's credentials are none of the backend's business (GH-3095), and the headers
// the transport itself uses have to get through.
const nuxtRequire = createRequire(createRequire(import.meta.url).resolve('nuxt/package.json'))
const h3 = nuxtRequire('h3') as typeof import('h3')

const servers: Server[] = []
// the paths the backend was asked for
const asked: string[] = []
const config = { apiBase: '' }
let app: string

function backend(request: IncomingMessage, response: ServerResponse): void {
  asked.push(request.url ?? '')
  const chunks: Buffer[] = []
  request.on('data', chunk => chunks.push(chunk))
  request.on('end', () => {
    response.writeHead(200, {
      'content-type': 'application/json',
      'mcp-session-id': 'backend-session',
      'server': 'uvicorn',
      'set-cookie': 'session=1',
      'alt-svc': 'h3=":443"',
    })
    response.end(JSON.stringify({ method: request.method, url: request.url, headers: request.headers, body: Buffer.concat(chunks).toString() }))
  })
}

function listen(server: Server): Promise<string> {
  return new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${(server.address() as AddressInfo).port}`)))
}

beforeAll(async () => {
  for (const [name, value] of Object.entries({
    defineEventHandler: h3.defineEventHandler,
    getRequestHeader: h3.getRequestHeader,
    readRawBody: h3.readRawBody,
    sendProxy: h3.sendProxy,
    setResponseHeader: h3.setResponseHeader,
    setResponseStatus: h3.setResponseStatus,
    useRuntimeConfig: () => config,
  }))
    vi.stubGlobal(name, value)
  const { mcpProxyHandler } = await import('../../server/utils/mcpProxy')
  const router = h3.createApp()
  router.use(mcpProxyHandler())
  const proxy = createServer(h3.toNodeListener(router))
  const stub = createServer(backend)
  servers.push(proxy, stub)
  app = await listen(proxy)
  config.apiBase = `${await listen(stub)}/api`
})

afterAll(async () => {
  vi.unstubAllGlobals()
  await Promise.all(servers.map(server => new Promise(resolve => server.close(resolve))))
})

async function sent(init: RequestInit & { headers?: Record<string, string> }, path = '/mcp/v1') {
  const response = await fetch(`${app}${path}`, init)
  return { response, ...(await response.json() as { method: string, url: string, headers: Record<string, string>, body: string }) }
}

describe('the /mcp proxy and the client\'s request', () => {
  it('sends on neither the cookie nor the authorization of the client, nor anything else that is not the transport\'s', async () => {
    const { headers } = await sent({
      method: 'POST',
      body: '{}',
      headers: {
        'content-type': 'application/json',
        'cookie': 'session=secret',
        'authorization': 'Bearer secret',
        'proxy-authorization': 'Basic secret',
        'origin': 'https://some-page.example',
        'referer': 'https://some-page.example/x',
        'x-forwarded-for': '203.0.113.9',
        'x-api-key': 'secret',
      },
    })

    for (const name of ['cookie', 'authorization', 'proxy-authorization', 'origin', 'referer', 'x-forwarded-for', 'x-api-key'])
      expect(headers[name], name).toBeUndefined()
  })

  it('sends on what the transport uses: the session, the protocol version, the resumption point, the body\'s type and the request id', async () => {
    const { headers } = await sent({
      method: 'POST',
      body: '{}',
      headers: {
        'content-type': 'application/json',
        'mcp-session-id': 'abc',
        'mcp-protocol-version': '2025-06-18',
        'last-event-id': '7',
        'x-request-id': 'client-id.1',
      },
    })

    expect(headers).toMatchObject({
      'content-type': 'application/json',
      'mcp-session-id': 'abc',
      'mcp-protocol-version': '2025-06-18',
      'last-event-id': '7',
      'x-request-id': 'client-id.1',
    })
  })

  it('sends the method, the path with its query and the body as the client wrote them', async () => {
    const posted = await sent({ method: 'POST', body: '{"jsonrpc":"2.0"}', headers: { 'content-type': 'application/json' } }, '/mcp/v1?x=1')
    expect(posted).toMatchObject({ method: 'POST', url: '/mcp/v1?x=1', body: '{"jsonrpc":"2.0"}' })

    const deleted = await sent({ method: 'DELETE', headers: { 'mcp-session-id': 'abc' } })
    expect(deleted).toMatchObject({ method: 'DELETE', body: '' })

    expect((await sent({ method: 'GET' }, '/mcp')).method).toBe('GET')
  })

  it('gives the transport the Accept pair it needs where the client sends none, and keeps one that asks for the event stream', async () => {
    expect((await sent({ method: 'POST', body: '{}', headers: { accept: '*/*' } })).headers.accept).toBe('application/json, text/event-stream')
    expect((await sent({ method: 'GET', headers: { accept: 'text/event-stream' } })).headers.accept).toBe('text/event-stream')
  })
})

describe('the /mcp proxy and the answer of the backend', () => {
  it('passes on the session, and does not republish what describes the backend', async () => {
    const { response } = await sent({ method: 'POST', body: '{}' })

    expect(response.headers.get('mcp-session-id')).toBe('backend-session')
    expect(response.headers.get('server')).toBeNull()
    expect(response.headers.get('set-cookie')).toBeNull()
    expect(response.headers.get('alt-svc')).toBeNull()
  })
})

// A request with the path as the client wrote it: `fetch` normalises `..` before it sends anything
function rawRequest(path: string, method = 'GET', headers: Record<string, string> = {}, body?: string): Promise<{ status: number, body: string }> {
  return new Promise((resolve, reject) => {
    const { port } = new URL(app)
    const request = httpRequest({ host: '127.0.0.1', port, path, method, headers }, (response) => {
      let text = ''
      response.on('data', (chunk) => {
        text += chunk
      })
      response.on('end', () => resolve({ status: response.statusCode ?? 0, body: text }))
    })
    request.on('error', reject)
    request.end(body)
  })
}

describe('the /mcp proxy and the path of the client', () => {
  it.each([
    '/mcp/../health',
    '/mcp/%2e%2e/health',
    '/mcp/%2E%2E/api/values',
    '/mcp/v1/../../openapi.json',
    '/mcp/./../docs',
  ])('does not leave /mcp for %s, and answers it a 404 problem without asking the backend', async (path) => {
    asked.length = 0
    const { status, body } = await rawRequest(path)

    expect(status).toBe(404)
    expect(JSON.parse(body).type).toBe('urn:wetterdienst:problem:not-found')
    expect(asked).toEqual([])
  })

  it('answers a POST outside /mcp the same, whatever its body', async () => {
    asked.length = 0
    const { status } = await rawRequest('/mcp/../health', 'POST', { 'content-type': 'application/json' }, '{}')

    expect(status).toBe(404)
    expect(asked).toEqual([])
  })

  it('keeps a path that stays under /mcp, however it gets there', async () => {
    asked.length = 0
    const { status, body } = await rawRequest('/mcp/v2/../v1?x=1')

    expect(status).toBe(200)
    expect(JSON.parse(body).url).toBe('/mcp/v1?x=1')
  })

  it('takes an encoded slash as a character of a segment, not as one that could leave /mcp', async () => {
    const { status, body } = await rawRequest('/mcp/..%2fhealth')

    expect(status).toBe(200)
    expect(JSON.parse(body).url).toMatch(/^\/mcp\/\.\.%2fhealth/i)
  })
})
