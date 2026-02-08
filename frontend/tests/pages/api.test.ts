import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'

describe('api page', () => {
  it('should render the page with correct title', async () => {
    const page = await mountSuspended(await import('~/pages/api.vue').then(m => m.default))
    expect(page.text()).toContain('REST API')
    expect(page.text()).toContain('Access weather data programmatically')
  })

  it('should display all endpoints', async () => {
    const page = await mountSuspended(await import('~/pages/api.vue').then(m => m.default))
    expect(page.text()).toContain('coverage')
    expect(page.text()).toContain('stations')
    expect(page.text()).toContain('values')
    expect(page.text()).toContain('interpolate')
    expect(page.text()).toContain('summarize')
    expect(page.text()).toContain('stripes/stations')
    expect(page.text()).toContain('stripes/values')
    expect(page.text()).toContain('stripes/image')
  })

  it('should display response formats', async () => {
    const page = await mountSuspended(await import('~/pages/api.vue').then(m => m.default))
    expect(page.text()).toContain('Response Formats')
    expect(page.text()).toContain('json')
    expect(page.text()).toContain('csv')
    expect(page.text()).toContain('geojson')
    expect(page.text()).toContain('html')
  })

  it('should display common parameters documentation', async () => {
    const page = await mountSuspended(await import('~/pages/api.vue').then(m => m.default))
    expect(page.text()).toContain('Common Parameters')
    expect(page.text()).toContain('provider')
    expect(page.text()).toContain('network')
    expect(page.text()).toContain('parameters')
    expect(page.text()).toContain('station')
    expect(page.text()).toContain('date')
    expect(page.text()).toContain('format')
  })
})
