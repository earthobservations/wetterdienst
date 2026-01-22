import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'

describe('index page', () => {
  it('should render the page with correct title', async () => {
    const page = await mountSuspended(await import('~/pages/index.vue').then(m => m.default))
    expect(page.text()).toContain('Wetterdienst')
    expect(page.text()).toContain('Open weather data for humans')
  })

  it('should display features section', async () => {
    const page = await mountSuspended(await import('~/pages/index.vue').then(m => m.default))
    expect(page.text()).toContain('Multiple Data Sources')
    expect(page.text()).toContain('Geospatial Queries')
    expect(page.text()).toContain('Flexible Export')
    expect(page.text()).toContain('Data Analysis')
  })

  it('should display authors section', async () => {
    const page = await mountSuspended(await import('~/pages/index.vue').then(m => m.default))
    expect(page.text()).toContain('Benjamin Gutzmann')
    expect(page.text()).toContain('Andreas Motl')
  })

  it('should have links to external resources', async () => {
    const page = await mountSuspended(await import('~/pages/index.vue').then(m => m.default))
    expect(page.text()).toContain('GitHub')
    expect(page.text()).toContain('Documentation')
    expect(page.text()).toContain('PyPI')
  })
})
