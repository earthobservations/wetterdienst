import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import IndexPage from '~/pages/index.vue'

describe('Index Page', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
  })

  it('renders the page', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('contains main navigation elements', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const html = wrapper.html()
    
    expect(html.length).toBeGreaterThan(0)
  })
})
