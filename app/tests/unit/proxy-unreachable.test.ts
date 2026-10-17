import { afterEach, describe, expect, it, vi } from 'vitest'

// The catch-all at `server/api/[...].get.ts` uses Nitro's auto-imports, which a plain node project
// does not have: stub the ones it calls, and import it afterwards.
const BACKEND = 'http://wetterdienst-backend.internal:3000/api'

async function proxyOutcome(failure: unknown, requestId?: string) {
  const setResponseStatus = vi.fn()
  const setResponseHeader = vi.fn()
  const sendProxy = vi.fn().mockRejectedValue(failure)
  vi.stubGlobal('defineEventHandler', (handler: unknown) => handler)
  vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBase: BACKEND } }))
  vi.stubGlobal('getQuery', () => ({}))
  vi.stubGlobal('getRequestHeader', (_event: unknown, name: string) => name === 'x-request-id' ? requestId : undefined)
  vi.stubGlobal('sendProxy', sendProxy)
  vi.stubGlobal('setResponseStatus', setResponseStatus)
  vi.stubGlobal('setResponseHeader', setResponseHeader)
  const { default: handler } = await import('../../server/api/[...].get')
  const event = { path: '/api/stations', handled: false, node: { res: {} } }
  const body = await (handler as unknown as (event: unknown) => Promise<unknown>)(event)
  return { body, setResponseStatus, setResponseHeader, sendProxy }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('the /api proxy with an unreachable backend', () => {
  it('answers a fixed text and logs the cause, which names the backend, on the server', async () => {
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    // what h3 throws for a refused connection: a constant message, the diagnostic on `cause`
    const cause = new Error('connect ECONNREFUSED 10.0.3.7:3000')
    const refused = Object.assign(new Error('Bad Gateway'), { statusCode: 502, cause })

    const { body, setResponseStatus, setResponseHeader } = await proxyOutcome(refused, 'req-1.a')

    expect(setResponseStatus).toHaveBeenCalledWith(expect.anything(), 502)
    expect(setResponseHeader).toHaveBeenCalledWith(expect.anything(), 'content-type', 'application/problem+json')
    expect(body).toEqual({
      type: 'urn:wetterdienst:problem:backend-unreachable',
      title: 'Bad Gateway',
      status: 502,
      detail: 'The backend could not be reached. The cause is in the server log.',
      instance: 'urn:wetterdienst:request:req-1.a',
      request_id: 'req-1.a',
    })
    expect(JSON.stringify(body)).not.toMatch(/ECONNREFUSED|10\.0\.3\.7|3000|internal/)
    expect(logged).toHaveBeenCalledOnce()
    expect(logged.mock.calls[0]).toContain(cause)
    // the log line names the request, so a client quoting the id finds it
    expect(String(logged.mock.calls[0]![0])).toContain('req-1.a')
  })

  it('tells the client the id and when to retry, as the backend does for its own 502, 503 and 504', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})

    const { setResponseHeader } = await proxyOutcome(new Error('Bad Gateway'), 'req-1.a')

    expect(setResponseHeader).toHaveBeenCalledWith(expect.anything(), 'x-request-id', 'req-1.a')
    expect(setResponseHeader).toHaveBeenCalledWith(expect.anything(), 'retry-after', 30)
  })

  it('sends the id of the client on to the backend, and makes one where it sent none or a bad one', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})

    const given = await proxyOutcome(new Error('x'), 'req-1.a')
    const none = await proxyOutcome(new Error('x'))
    const bad = await proxyOutcome(new Error('x'), 'has spaces\r\nSet-Cookie: x=1')

    expect(given.sendProxy.mock.calls[0]![2]).toMatchObject({ headers: { 'x-request-id': 'req-1.a' } })
    for (const made of [none, bad]) {
      const id = (made.body as { request_id: string }).request_id
      expect(id).toMatch(/^[0-9a-f]{32}$/)
      expect(made.sendProxy.mock.calls[0]![2]).toMatchObject({ headers: { 'x-request-id': id } })
    }
  })

  it('answers 502 and the same text for a failure that carries neither a status nor a cause', async () => {
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    const odd = new Error(`fetch failed for ${BACKEND}`)

    const { body, setResponseStatus } = await proxyOutcome(odd)

    expect(setResponseStatus).toHaveBeenCalledWith(expect.anything(), 502)
    expect(body).toMatchObject({
      type: 'urn:wetterdienst:problem:backend-unreachable',
      title: 'Bad Gateway',
      status: 502,
      detail: 'The backend could not be reached. The cause is in the server log.',
    })
    expect(logged.mock.calls[0]).toContain(odd)
  })
})
