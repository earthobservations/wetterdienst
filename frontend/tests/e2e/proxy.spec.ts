import process from 'node:process'
import { expect, test } from '@playwright/test'

// Every request here goes through the frontend's own catch-all at `server/api/[...].get.ts`
// (relative URLs resolve against `baseURL`, port 4000), unlike `api.spec.ts` which talks to the
// backend directly on port 3000. That handler streams the upstream response straight through, so
// what needs guarding is fidelity: status codes, bodies and query parameters must survive the hop.
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:3000'

test.describe('API proxy', () => {
  test('forwards a JSON response unchanged', async ({ request }) => {
    const viaProxy = await request.get('/api/coverage')
    expect(viaProxy.ok()).toBeTruthy()
    expect(viaProxy.headers()['content-type']).toContain('application/json')

    const direct = await request.get(`${BACKEND_URL}/api/coverage`)
    expect(await viaProxy.json()).toEqual(await direct.json())
  })

  test('preserves the backend error status and FastAPI error shape', async ({ request }) => {
    // `/api/values` without parameters is a validation error. The proxy must not turn it into a
    // 500 or swallow `detail`, because the UI renders that field verbatim.
    const response = await request.get('/api/values')
    expect([400, 422]).toContain(response.status())

    const body = await response.json()
    expect(body).toHaveProperty('detail')
  })

  test('forwards repeated query parameters', async ({ request }) => {
    const query = 'provider=dwd&network=observation&parameters=daily/kl&station=00011&station=00003'

    const viaProxy = await request.get(`/api/stations?${query}`)
    const direct = await request.get(`${BACKEND_URL}/api/stations?${query}`)
    expect(viaProxy.status()).toBe(direct.status())

    // A dropped repeat would silently return one station instead of two, so compare the payloads
    // rather than just the status.
    if (viaProxy.ok()) {
      expect(await viaProxy.json()).toEqual(await direct.json())
    }
  })

  test('streams a large payload without truncating it', async ({ request }) => {
    // Decades of daily data for one station is a few MB -- enough that a body which is buffered,
    // re-encoded or cut short shows up as a length mismatch against the direct response.
    const query = 'provider=dwd&network=observation&parameters=daily/kl&station=00011&date=1990-01-01/2024-12-31'

    const viaProxy = await request.get(`/api/values?${query}`)
    const direct = await request.get(`${BACKEND_URL}/api/values?${query}`)
    expect(viaProxy.status()).toBe(direct.status())

    if (viaProxy.ok()) {
      const proxied = await viaProxy.body()
      const expected = await direct.body()
      expect(proxied.byteLength).toBe(expected.byteLength)
      expect(proxied.equals(expected)).toBe(true)
    }
  })
})
