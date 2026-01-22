import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'

describe('impressum page', () => {
  it('should render the page', async () => {
    const page = await mountSuspended(await import('~/pages/impressum.vue').then(m => m.default))
    expect(page.html()).toBeTruthy()
  })
})
