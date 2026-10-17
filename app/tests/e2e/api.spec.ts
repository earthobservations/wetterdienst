import type { CoverageNetworkInfo } from '../../shared/types/api'
import { expect, test } from '@playwright/test'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:7890'

test.describe('API Coverage Endpoint', () => {
  test('should fetch coverage data', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/coverage`)
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data).toBeDefined()
    expect(typeof data).toBe('object')
  })

  test('should include DWD provider', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/coverage`)
    const data = await response.json()

    expect(data).toHaveProperty('dwd')
    expect(typeof data.dwd).toBe('object')
    expect(Array.isArray(data.dwd)).toBeFalsy()
    const networks = Object.keys(data.dwd)
    expect(networks).toContain('observation')
    for (const info of Object.values(data.dwd) as CoverageNetworkInfo[]) {
      expect(typeof info.auth).toBe('boolean')
      expect(typeof info.configured).toBe('boolean')
      // whether a provider accepts the credentials is `/api/auth`'s to tell, not the list's (GH-2641)
      expect(info).not.toHaveProperty('valid')
      expect(info.name_short).toBe('DWD')
      expect(info.country).toBe('Germany')
      expect(info.url).toMatch(/^https:\/\//)
    }
    // `radar` and `alerts` are standalone networks, every other one has stations and values
    expect(data.dwd.radar.kind).toBe('radar')
    expect(data.dwd.alerts.kind).toBe('alerts')
    expect(data.dwd.observation.kind).toBe('observation')
  })

  test('should fetch provider-network coverage', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/coverage?provider=dwd&network=observation`)
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data).toBeDefined()
    expect(typeof data).toBe('object')
  })
})

test.describe('API Stations Endpoint', () => {
  test('should fetch stations with parameters', async ({ request }) => {
    const response = await request.get(
      `${BACKEND_URL}/api/stations?provider=dwd&network=observation&parameters=daily/kl&all=true`,
    )
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data).toHaveProperty('stations')
    expect(Array.isArray(data.stations)).toBeTruthy()
  })

  test('stations should have required fields', async ({ request }) => {
    const response = await request.get(
      `${BACKEND_URL}/api/stations?provider=dwd&network=observation&parameters=daily/kl&all=true`,
    )
    const data = await response.json()

    if (data.stations.length > 0) {
      const station = data.stations[0]
      expect(station).toHaveProperty('station_id')
      expect(station).toHaveProperty('name')
      expect(station).toHaveProperty('latitude')
      expect(station).toHaveProperty('longitude')
    }
  })
})

test.describe('API Values Endpoint', () => {
  test('should fetch values for a station', async ({ request }) => {
    const response = await request.get(
      `${BACKEND_URL}/api/values?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&stations=00001`,
    )

    // May return 404 if station doesn't exist, or 200 with data
    expect([200, 400, 404]).toContain(response.status())

    if (response.status() === 200) {
      const data = await response.json()
      expect(data).toHaveProperty('values')
      expect(Array.isArray(data.values)).toBeTruthy()
    }
  })

  test('should return proper error for missing parameters', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/values`)

    // Should fail validation
    expect([400, 422]).toContain(response.status())
  })
})

test.describe('API Stripes Endpoints', () => {
  test('should fetch stripes stations', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/stripes/stations?kind=temperature`)
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data).toHaveProperty('stations')
    expect(Array.isArray(data.stations)).toBeTruthy()
  })

  test('should fetch stripes values', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/stripes/values?kind=temperature&station=1048`)

    // May return 400 (bad request), 404 (not found), 500 (DWD could not be read), or 200 with data
    expect([200, 400, 404, 500]).toContain(response.status())

    if (response.status() === 200) {
      const data = await response.json()
      expect(data).toHaveProperty('metadata')
      // what the values are of is its own member, `metadata` being the block every answer has
      expect(data.series).toMatchObject({ resolution: 'annual', dataset: 'climate_summary', parameter: 'temperature_air_mean_2m' })
      expect(data.series.station.station_id).toBe('01048')
      expect(typeof data.series.unit).toBe('string')
      expect(data.metadata).not.toHaveProperty('station')
      expect(data).toHaveProperty('values')
    }
  })

  test('should fetch stripes image', async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/api/stripes/image?kind=temperature&station=1048`)

    // May return 400 (bad request), 404 (not found), 500 (DWD could not be read), 501 (the backend
    // has no plotly, as in this job's restapi-only install), or 200 with data
    expect([200, 400, 404, 500, 501]).toContain(response.status())
  })
})
