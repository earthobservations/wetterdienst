import { mountSuspended } from '@nuxt/test-utils/runtime'

describe('history page', () => {
  it('renders', async () => {
    const page = await mountSuspended(await import('~/pages/history.vue').then(m => m.default))
    expect(page.text()).toContain('Station History')
  })
})
