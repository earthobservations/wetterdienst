import { afterEach, describe, expect, it, vi } from 'vitest'

// The catch-all at `server/api/[...].get.ts` uses Nitro's auto-imports, which a plain node project
// does not have: stub the ones it calls, and import it afterwards.
const BACKEND = 'http://wetterdienst-backend.internal:3000/api'

async function proxyOutcome(failure: unknown) {
  const setResponseStatus = vi.fn()
  const setResponseHeader = vi.fn()
  vi.stubGlobal('defineEventHandler', (handler: unknown) => handler)
  vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBase: BACKEND } }))
  vi.stubGlobal('getQuery', () => ({}))
  vi.stubGlobal('sendProxy', vi.fn().mockRejectedValue(failure))
  vi.stubGlobal('setResponseStatus', setResponseStatus)
  vi.stubGlobal('setResponseHeader', setResponseHeader)
  const { default: handler } = await import('../../server/api/[...].get')
  const event = { path: '/api/stations', handled: false, node: { res: {} } }
  const body = await (handler as unknown as (event: unknown) => Promise<unknown>)(event)
  return { body, setResponseStatus, setResponseHeader }
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

    const { body, setResponseStatus, setResponseHeader } = await proxyOutcome(refused)

    expect(setResponseStatus).toHaveBeenCalledWith(expect.anything(), 502)
    expect(setResponseHeader).toHaveBeenCalledWith(expect.anything(), 'content-type', 'application/problem+json')
    expect(body).toEqual({
      type: 'about:blank',
      title: 'Bad Gateway',
      status: 502,
      detail: 'The backend could not be reached. The cause is in the server log.',
    })
    expect(JSON.stringify(body)).not.toMatch(/ECONNREFUSED|10\.0\.3\.7|3000|internal/)
    expect(logged).toHaveBeenCalledOnce()
    expect(logged.mock.calls[0]).toContain(cause)
  })

  it('answers 502 and the same text for a failure that carries neither a status nor a cause', async () => {
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    const odd = new Error(`fetch failed for ${BACKEND}`)

    const { body, setResponseStatus } = await proxyOutcome(odd)

    expect(setResponseStatus).toHaveBeenCalledWith(expect.anything(), 502)
    expect(body).toEqual({
      type: 'about:blank',
      title: 'Bad Gateway',
      status: 502,
      detail: 'The backend could not be reached. The cause is in the server log.',
    })
    expect(logged.mock.calls[0]).toContain(odd)
  })
})
