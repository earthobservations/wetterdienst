import type { IncomingMessage, Server, ServerResponse } from 'node:http'
import type { AddressInfo } from 'node:net'
import type { SecurityStack } from '../helpers/nuxt-security-stack'
import { Buffer } from 'node:buffer'
import { createServer } from 'node:http'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { h3, loadSecurityStack } from '../helpers/nuxt-security-stack'

// The `/mcp` proxy behind nuxt-security's own middleware (GH-4362). The proxy's tests run it on a bare h3 app,
// where nothing reads the body before it: in the built app nuxt-security's `xssValidator` does (it calls h3's
// `readBody` on every POST, which reads the whole stream and caches it), so a proxy that read the stream itself
// forwarded an empty body. The app has no `xssValidator` since GH-4364; here the real one runs in front of the proxy
// as it is installed (`module-defaults`) to show the proxy never forwards an empty body, and with the app's rules
// (`security` and `routeRules` of `nuxt.config.ts`) to show the proxy gets its body through.
vi.mock('@tailwindcss/vite', () => ({ default: () => ({ name: 'tailwindcss-stub' }) }))

const servers: Server[] = []
const asked: { url: string, body: string }[] = []
const config = { apiBase: '' }
let stack: SecurityStack
let app: string

function backend(request: IncomingMessage, response: ServerResponse): void {
  const chunks: Buffer[] = []
  request.on('data', chunk => chunks.push(chunk))
  request.on('end', () => {
    asked.push({ url: request.url ?? '', body: Buffer.concat(chunks).toString() })
    response.writeHead(200, { 'content-type': 'application/json', 'mcp-session-id': 'backend-session' })
    response.end('{}')
  })
}

function listen(server: Server): Promise<string> {
  return new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${(server.address() as AddressInfo).port}`)))
}

beforeAll(async () => {
  stack = await loadSecurityStack()
  for (const [name, value] of Object.entries({
    defineEventHandler: h3.defineEventHandler,
    getRequestHeader: h3.getRequestHeader,
    sendProxy: h3.sendProxy,
    setResponseHeader: h3.setResponseHeader,
    setResponseStatus: h3.setResponseStatus,
    useRuntimeConfig: () => config,
  }))
    vi.stubGlobal(name, value)
  const { mcpProxyHandler } = await import('../../server/utils/mcpProxy')
  const router = h3.createApp()
  router.use(stack.xssValidator)
  router.use(mcpProxyHandler())
  const proxy = createServer(h3.toNodeListener(router))
  const stub = createServer(backend)
  servers.push(proxy, stub)
  app = await listen(proxy)
  config.apiBase = `${await listen(stub)}/api`
})

beforeEach(() => {
  asked.length = 0
})

afterEach(() => stack.setRules('app'))

afterAll(async () => {
  vi.unstubAllGlobals()
  await Promise.all(servers.map(server => new Promise(resolve => server.close(resolve))))
})

const INITIALIZE = JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'client', version: '1' } } })

async function post(body: string, path = '/mcp/v1'): Promise<Response> {
  return fetch(`${app}${path}`, { method: 'POST', body, headers: { 'content-type': 'application/json' } })
}

describe('the security rules of /mcp (routeRules of nuxt.config.ts)', () => {
  it.each(['/mcp', '/mcp/', '/mcp/v1', '/mcp/v1/', '/mcp/v1?x=1', '/mcp/v2/anything'])('switch off, for %s, the requestSizeLimiter', (path) => {
    stack.setRules('app')
    const rules = stack.context.resolveSecurityRules({ path, context: {} })

    expect(rules.requestSizeLimiter, 'requestSizeLimiter').toBe(false)
  })

  it('leave the requestSizeLimiter on for the rest of the app', () => {
    stack.setRules('app')
    for (const path of ['/api/values', '/mcpx', '/', '/openapi.json'])
      expect(stack.context.resolveSecurityRules({ path, context: {} }).requestSizeLimiter, path).toBeTruthy()
  })
})

describe('the /mcp proxy behind the xssValidator of nuxt-security', () => {
  it('forwards an initialize with its body intact', async () => {
    stack.setRules('app')
    const response = await post(INITIALIZE)

    expect(response.status).toBe(200)
    expect(response.headers.get('mcp-session-id')).toBe('backend-session')
    expect(asked).toEqual([{ url: '/mcp/v1', body: INITIALIZE }])
  })

  it('refuses with a 500 problem, and asks no backend, where a middleware has read the body (the xssValidator of nuxt-security, as it is installed)', async () => {
    stack.setRules('module-defaults')
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const response = await post(INITIALIZE)

    expect(response.status).toBe(500)
    expect((await response.json() as { type: string }).type).toBe('urn:wetterdienst:problem:internal-error')
    expect(asked).toEqual([])
    expect(spy.mock.calls.flat().join(' ')).toContain('read the body before the /mcp proxy')
    spy.mockRestore()
  })
})
