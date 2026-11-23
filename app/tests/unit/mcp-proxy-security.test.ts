import type { IncomingMessage, Server, ServerResponse } from 'node:http'
import type { AddressInfo } from 'node:net'
import { Buffer } from 'node:buffer'
import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import { join } from 'node:path'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

// The `/mcp` proxy behind nuxt-security's own middleware (GH-4362). The proxy's tests run it on a bare h3 app,
// where nothing reads the body before it: in the built app nuxt-security's `xssValidator` does (it calls h3's
// `readBody` on every POST, which reads the whole stream and caches it), so a proxy that read the stream itself
// forwarded an empty body. Here the real `xssValidator` middleware runs in front of the proxy, with the rules that
// nuxt-security resolves for a path from the `routeRules` of `nuxt.config.ts`.
vi.mock('@tailwindcss/vite', () => ({ default: () => ({ name: 'tailwindcss-stub' }) }))

const APP = join(__dirname, '..', '..')
const SECURITY = join(APP, 'node_modules', 'nuxt-security', 'dist', 'runtime')
const nuxtRequire = createRequire(createRequire(import.meta.url).resolve('nuxt/package.json'))
const h3 = nuxtRequire('h3') as typeof import('h3')

interface Context {
  getAppSecurityOptions: () => Record<string, unknown>
  resolveSecurityRules: (event: unknown) => Record<string, unknown>
}

const servers: Server[] = []
const asked: { url: string, body: string }[] = []
const config = { apiBase: '' }
let context: Context
let routeRules: Record<string, { security?: Record<string, unknown> }>
let app: string

// What nuxt-security's defaults give every route (`defaultConfig.js`), before a rule of a route changes it
const GLOBAL_RULES = {
  enabled: true,
  xssValidator: { whiteList: {}, stripIgnoreTag: true, stripIgnoreTagBody: ['script'], methods: ['GET', 'POST'], throwError: true },
  requestSizeLimiter: { maxRequestSizeInBytes: 2e6, maxUploadFileRequestInBytes: 8e6, throwError: true },
}

// The plugin `00-routeRules` of nuxt-security: the rules of each route of the config beside the global ones
function setRules(withRouteRules: boolean): void {
  const rules = context.getAppSecurityOptions()
  for (const key of Object.keys(rules))
    delete rules[key]
  rules['/**'] = structuredClone(GLOBAL_RULES)
  if (withRouteRules) {
    for (const [route, rule] of Object.entries(routeRules)) {
      if (rule.security)
        rules[route] = structuredClone(rule.security)
    }
  }
}

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
  vi.stubGlobal('defineNuxtConfig', (value: unknown) => value)
  routeRules = ((await import('../../nuxt.config')).default as unknown as { routeRules: typeof routeRules }).routeRules
  context = await import(/* @vite-ignore */ join(SECURITY, 'nitro', 'context', 'index.js')) as Context
  const { default: xssValidator } = await import(/* @vite-ignore */ join(SECURITY, 'server', 'middleware', 'xssValidator.js'))
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
  router.use(xssValidator)
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

afterEach(() => setRules(true))

afterAll(async () => {
  vi.unstubAllGlobals()
  await Promise.all(servers.map(server => new Promise(resolve => server.close(resolve))))
})

const INITIALIZE = JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'client', version: '1' } } })

async function post(body: string, path = '/mcp/v1'): Promise<Response> {
  return fetch(`${app}${path}`, { method: 'POST', body, headers: { 'content-type': 'application/json' } })
}

describe('the security rules of /mcp (routeRules of nuxt.config.ts)', () => {
  it.each(['/mcp', '/mcp/', '/mcp/v1', '/mcp/v1/', '/mcp/v1?x=1', '/mcp/v2/anything'])('switch off, for %s, the xssValidator and the requestSizeLimiter', (path) => {
    setRules(true)
    const rules = context.resolveSecurityRules({ path, context: {} })

    expect(rules.xssValidator, 'xssValidator').toBe(false)
    expect(rules.requestSizeLimiter, 'requestSizeLimiter').toBe(false)
  })

  it('leave both on for the rest of the app', () => {
    setRules(true)
    for (const path of ['/api/values', '/mcpx', '/', '/openapi.json']) {
      const rules = context.resolveSecurityRules({ path, context: {} })
      expect(rules.xssValidator, path).toBeTruthy()
      expect(rules.requestSizeLimiter, path).toBeTruthy()
    }
  })
})

describe('the /mcp proxy behind the xssValidator of nuxt-security', () => {
  it('forwards an initialize with its body intact', async () => {
    setRules(true)
    const response = await post(INITIALIZE)

    expect(response.status).toBe(200)
    expect(response.headers.get('mcp-session-id')).toBe('backend-session')
    expect(asked).toEqual([{ url: '/mcp/v1', body: INITIALIZE }])
  })

  it('refuses with a 500 problem, and asks no backend, where a middleware has read the body (the rules do not switch it off)', async () => {
    setRules(false)
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const response = await post(INITIALIZE)

    expect(response.status).toBe(500)
    expect((await response.json() as { type: string }).type).toBe('urn:wetterdienst:problem:internal-error')
    expect(asked).toEqual([])
    expect(spy.mock.calls.flat().join(' ')).toContain('read the body before the /mcp proxy')
    spy.mockRestore()
  })
})
