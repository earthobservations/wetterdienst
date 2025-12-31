import { test, expect } from '@playwright/test'

test.describe('API Coverage Endpoint', () => {
  test('should fetch coverage data', async ({ page }) => {
    const response = await page.request.get('/api/coverage')
    expect(response.ok()).toBeTruthy()
    
    const data = await response.json()
    expect(data).toBeDefined()
    expect(typeof data).toBe('object')
  })

  test('should include DWD provider', async ({ page }) => {
    const response = await page.request.get('/api/coverage')
    const data = await response.json()
    
    expect(data).toHaveProperty('dwd')
    expect(Array.isArray(data.dwd)).toBeTruthy()
  })

  test('should fetch provider-network coverage', async ({ page }) => {
    const response = await page.request.get('/api/coverage?provider=dwd&network=observation')
    expect(response.ok()).toBeTruthy()
    
    const data = await response.json()
    expect(data).toBeDefined()
    expect(typeof data).toBe('object')
  })
})

test.describe('API Stations Endpoint', () => {
  test('should fetch stations with parameters', async ({ page }) => {
    const response = await page.request.get(
      '/api/stations?provider=dwd&network=observation&parameters=daily/kl&all=true'
    )
    expect(response.ok()).toBeTruthy()
    
    const data = await response.json()
    expect(data).toHaveProperty('stations')
    expect(Array.isArray(data.stations)).toBeTruthy()
  })

  test('stations should have required fields', async ({ page }) => {
    const response = await page.request.get(
      '/api/stations?provider=dwd&network=observation&parameters=daily/kl&all=true'
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
  test('should fetch values for a station', async ({ page }) => {
    const response = await page.request.get(
      '/api/values?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00001'
    )
    
    // May return 404 if station doesn't exist, or 200 with data
    expect([200, 404]).toContain(response.status())
    
    if (response.status() === 200) {
      const data = await response.json()
      expect(data).toHaveProperty('values')
      expect(Array.isArray(data.values)).toBeTruthy()
    }
  })

  test('should return proper error for missing parameters', async ({ page }) => {
    const response = await page.request.get('/api/values')
    
    // Should fail validation
    expect([400, 422]).toContain(response.status())
  })
})

test.describe('API Stripes Endpoints', () => {
  test('should fetch stripes stations', async ({ page }) => {
    const response = await page.request.get('/api/stripes/stations?kind=temperature')
    expect(response.ok()).toBeTruthy()
    
    const data = await response.json()
    expect(data).toHaveProperty('stations')
    expect(Array.isArray(data.stations)).toBeTruthy()
  })

  test('should fetch stripes values', async ({ page }) => {
    const response = await page.request.get('/api/stripes/values?kind=temperature&station=1048')
    
    // May return 404 if station doesn't exist, or 200 with data
    expect([200, 404]).toContain(response.status())
  })
})
