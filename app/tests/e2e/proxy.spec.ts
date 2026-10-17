import process from 'node:process'
import { expect, test } from '@playwright/test'

// Every request here goes through the app's own catch-all at `server/api/[...].get.ts`
// (relative URLs resolve against `baseURL`, port 4000), unlike `api.spec.ts` which talks to the
// backend directly on port 7890. That handler streams the upstream response straight through, so
// what needs guarding is fidelity: status codes, bodies and query parameters must survive the hop.
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:7890'

// Playwright defaults to 30s for both a test and a single API request, which is tight for a backend
// that may still be downloading from DWD opendata on a cold cache.
const REQUEST_TIMEOUT = 90_000
const LARGE_PAYLOAD_TIMEOUT = 240_000

// Every answer of the data routes says when it was made (`metadata.retrieved_at`, GH-2561), so two requests
// for the same data never give the same bytes. The proxy has to pass the body on as it is; the time is
// taken out of both sides before they are compared.
function withoutRetrievalTime(text: string): string {
  return text.replace(/"retrieved_at":\s*"[^"]*"/g, '"retrieved_at": ""')
}

test.describe('API proxy', () => {
  test('forwards a JSON response unchanged', async ({ request }) => {
    const viaProxy = await request.get('/api/coverage', { timeout: REQUEST_TIMEOUT })
    expect(viaProxy.ok()).toBeTruthy()
    expect(viaProxy.headers()['content-type']).toContain('application/json')

    const direct = await request.get(`${BACKEND_URL}/api/coverage`, { timeout: REQUEST_TIMEOUT })
    expect(direct.ok()).toBeTruthy()
    expect(await viaProxy.json()).toEqual(await direct.json())
  })

  test('does not republish the backend\'s own response headers', async ({ request }) => {
    // Streaming relays upstream response headers, which buffering never did. uvicorn sends
    // `server: uvicorn` on every response, so this asserts against something the backend really
    // emits rather than passing vacuously.
    const viaProxy = await request.get('/api/coverage', { timeout: REQUEST_TIMEOUT })
    expect(viaProxy.ok()).toBeTruthy()

    const headers = viaProxy.headers()
    expect(headers.server).not.toBe('uvicorn')
    expect(headers['alt-svc']).toBeUndefined()
    // The backend sets no cookies today; this guards the boundary if that ever changes.
    expect(headers['set-cookie']).toBeUndefined()
  })

  test('preserves the backend error status and problem shape', async ({ request }) => {
    // `/api/values` without parameters is a validation error. The proxy must not turn it into a
    // 500 or swallow `detail`, because the UI renders that field verbatim.
    const response = await request.get('/api/values', { timeout: REQUEST_TIMEOUT })
    expect([400, 422]).toContain(response.status())

    const body = await response.json()
    expect(body).toHaveProperty('detail')
  })

  test('carries the request id of the client to the backend and its problem back', async ({ request }) => {
    // The backend names the request in the `X-Request-ID` header of every answer and in the `request_id` of
    // a problem, the client's own id where it sends a plain one. The proxy passes that id on, and the
    // backend's answer is what the client reads (the `Retry-After` of a 502, 503 or 504 travels the same
    // way, see tests/unit/proxy-forwards.test.ts: no backend of an e2e run fails on demand).
    const response = await request.get('/api/values', { headers: { 'x-request-id': 'e2e-proxy-1' }, timeout: REQUEST_TIMEOUT })
    expect([400, 422]).toContain(response.status())

    expect(response.headers()['x-request-id']).toBe('e2e-proxy-1')
    expect((await response.json()).request_id).toBe('e2e-proxy-1')
  })

  test('forwards repeated query parameters', async ({ request }) => {
    const query = 'provider=dwd&network=observation&parameters=daily/kl&stations=00011&stations=00003'

    const viaProxy = await request.get(`/api/stations?${query}`, { timeout: REQUEST_TIMEOUT })
    // Assert success rather than branching on it: if the backend fails, both sides fail the same
    // way and a `viaProxy.ok()` guard would let the test pass while comparing nothing.
    expect(viaProxy.ok()).toBeTruthy()

    const direct = await request.get(`${BACKEND_URL}/api/stations?${query}`, { timeout: REQUEST_TIMEOUT })
    expect(direct.ok()).toBeTruthy()

    // A dropped repeat would silently return one station instead of two, so compare the payloads
    // rather than just the status.
    expect(withoutRetrievalTime(await viaProxy.text())).toBe(withoutRetrievalTime(await direct.text()))
  })

  test('streams a large payload without truncating it', async ({ request }) => {
    // Decades of daily data for one station is a few MB (~3.2 MB at the time of writing) -- enough
    // that a body which is buffered, re-encoded or cut short shows up as a length mismatch against
    // the direct response. CI runs this against a cold cache, so the backend has to pull from DWD
    // opendata first; both the test and each request get their own generous budget.
    test.setTimeout(LARGE_PAYLOAD_TIMEOUT)
    const query = 'provider=dwd&network=observation&parameters=daily/kl&stations=00011&timestamp=1990-01-01/2024-12-31'

    const viaProxy = await request.get(`/api/values?${query}`, { timeout: REQUEST_TIMEOUT })
    expect(viaProxy.ok()).toBeTruthy()

    const direct = await request.get(`${BACKEND_URL}/api/values?${query}`, { timeout: REQUEST_TIMEOUT })
    expect(direct.ok()).toBeTruthy()

    const proxied = await viaProxy.body()
    const expected = await direct.body()
    expect(proxied.byteLength).toBe(expected.byteLength)
    expect(withoutRetrievalTime(proxied.toString('utf8'))).toBe(withoutRetrievalTime(expected.toString('utf8')))
  })
})

test.describe('OpenAPI proxy', () => {
  test('serves the backend Swagger UI on this origin', async ({ request }) => {
    const response = await request.get('/docs')

    expect(response.status()).toBe(200)
    // the app's own shell answers with a Nuxt document, so assert on what only Swagger sends
    expect(await response.text()).toContain('swagger-ui')
  })

  test('serves the schema Swagger UI fetches', async ({ request }) => {
    const response = await request.get('/openapi.json')

    expect(response.status()).toBe(200)
    const schema = await response.json()
    expect(schema.openapi).toBeTruthy()
    expect(schema.paths['/api/v1/coverage']).toBeTruthy()
  })
})
