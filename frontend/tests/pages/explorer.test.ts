import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'

describe('explorer page', () => {
  it('should render the page', async () => {
    const page = await mountSuspended(await import('~/pages/explorer.vue').then(m => m.default))
    expect(page.html()).toBeTruthy()
    page.unmount()
  })

  it('should display parameter selection', async () => {
    const page = await mountSuspended(await import('~/pages/explorer.vue').then(m => m.default))
    expect(page.text()).toContain('Select Parameters')
    page.unmount()
  })
})
