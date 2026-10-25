import { afterEach, describe, expect, it, vi } from 'vitest'

// The three proxies and the start-up plugin, with the runtime config's `apiBase` empty, which is what the app has
// when a deployment still sets only the old `NUXT_PUBLIC_API_BASE` (GH-3096). A proxy that reads the runtime
// config directly, and not through `useApiBase`, would send the request to nowhere, and the plugin that is
// dropped would leave the operator without the warning.
const OLD = 'http://old.internal:7890/api'
const NEW = 'http://new.internal:7890/api'

function stubNitro(apiBase: string) {
  const sendProxy = vi.fn().mockResolvedValue('proxied')
  vi.stubGlobal('defineEventHandler', (handler: unknown) => handler)
  vi.stubGlobal('defineNitroPlugin', (plugin: unknown) => plugin)
  vi.stubGlobal('useRuntimeConfig', () => ({ apiBase }))
  vi.stubGlobal('getQuery', () => ({}))
  vi.stubGlobal('getRequestHeader', () => undefined)
  vi.stubGlobal('readRawBody', () => Promise.resolve(undefined))
  vi.stubGlobal('setResponseStatus', vi.fn())
  vi.stubGlobal('setResponseHeader', vi.fn())
  vi.stubGlobal('sendProxy', sendProxy)
  return sendProxy
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
  vi.resetModules()
})

describe('the proxies with only NUXT_PUBLIC_API_BASE set', () => {
  it('sends the /api proxy to the URL of the old variable', async () => {
    vi.stubEnv('NUXT_PUBLIC_API_BASE', OLD)
    const sendProxy = stubNitro('')
    const { default: handler } = await import('../../server/api/[...].get')

    await (handler as unknown as (event: unknown) => Promise<unknown>)({ path: '/api/stations', node: { res: {} } })

    expect(String(sendProxy.mock.calls[0]![1])).toBe(`${OLD}/stations`)
  })

  it('sends the /mcp proxy to the origin of the old variable', async () => {
    vi.stubEnv('NUXT_PUBLIC_API_BASE', OLD)
    const sendProxy = stubNitro('')
    const { mcpProxyHandler } = await import('../../server/utils/mcpProxy')

    await (mcpProxyHandler() as unknown as (event: unknown) => Promise<unknown>)({ path: '/mcp/v1', method: 'GET', node: { res: {} } })

    expect(sendProxy.mock.calls[0]![1]).toBe('http://old.internal:7890/mcp/v1')
  })

  it('sends the /docs and /openapi.json proxy to the origin of the old variable', async () => {
    vi.stubEnv('NUXT_PUBLIC_API_BASE', OLD)
    const sendProxy = stubNitro('')
    const { backendDocsProxyHandler } = await import('../../server/utils/backendProxy')

    await (backendDocsProxyHandler() as unknown as (event: unknown) => Promise<unknown>)({ path: '/openapi.json', node: { res: {} } })

    expect(sendProxy.mock.calls[0]![1]).toBe('http://old.internal:7890/openapi.json')
  })
})

describe('the plugin that warns when the server starts', () => {
  async function start(apiBase: string) {
    stubNitro(apiBase)
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const { default: plugin } = await import('../../server/plugins/api-base')
    ;(plugin as unknown as () => void)()
    return warn
  }

  it('warns once, naming both variables and no value, when only the old one is set', async () => {
    vi.stubEnv('NUXT_PUBLIC_API_BASE', OLD)
    const warn = await start('')

    expect(warn).toHaveBeenCalledOnce()
    const line = String(warn.mock.calls[0]![0])
    expect(line).toContain('NUXT_PUBLIC_API_BASE is deprecated')
    expect(line).toContain('NUXT_API_BASE')
    expect(line).not.toContain('old.internal')
  })

  it('says the old variable is ignored when both are set', async () => {
    vi.stubEnv('NUXT_PUBLIC_API_BASE', OLD)
    const warn = await start(NEW)

    expect(warn).toHaveBeenCalledOnce()
    const line = String(warn.mock.calls[0]![0])
    expect(line).toContain('ignored')
    expect(line).not.toContain('internal')
  })

  it('is silent when the old variable is not set', async () => {
    vi.stubEnv('NUXT_PUBLIC_API_BASE', '')

    expect(await start(NEW)).not.toHaveBeenCalled()
    vi.resetModules()
    expect(await start('')).not.toHaveBeenCalled()
  })
})
