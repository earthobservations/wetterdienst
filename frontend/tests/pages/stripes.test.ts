import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'

describe('stripes page', () => {
  it('should render the page with correct title', async () => {
    const page = await mountSuspended(await import('~/pages/stripes.vue').then(m => m.default))
    expect(page.text()).toContain('Climate Stripes')
    expect(page.text()).toContain('Visualize long-term climate trends')
  })

  it('should display settings panel', async () => {
    const page = await mountSuspended(await import('~/pages/stripes.vue').then(m => m.default))
    expect(page.text()).toContain('Settings')
    expect(page.text()).toContain('Type')
    expect(page.text()).toContain('Station')
  })

  it('should display visualization panel', async () => {
    const page = await mountSuspended(await import('~/pages/stripes.vue').then(m => m.default))
    expect(page.text()).toContain('Visualization')
    expect(page.text()).toContain('Select a station to generate climate stripes')
  })

  it('should display about section', async () => {
    const page = await mountSuspended(await import('~/pages/stripes.vue').then(m => m.default))
    expect(page.text()).toContain('About Climate Stripes')
    expect(page.text()).toContain('Ed Hawkins')
  })

  it('should have format options', async () => {
    const page = await mountSuspended(await import('~/pages/stripes.vue').then(m => m.default))
    expect(page.text()).toContain('Format')
  })

  it('should have display options', async () => {
    const page = await mountSuspended(await import('~/pages/stripes.vue').then(m => m.default))
    expect(page.text()).toContain('Show title')
    expect(page.text()).toContain('Show years')
    expect(page.text()).toContain('Show data availability')
  })
})
