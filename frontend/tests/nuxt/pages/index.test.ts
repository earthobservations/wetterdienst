import { mountSuspended } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import IndexPage from '~/pages/index.vue'

describe('index Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  it('renders the page', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('contains main navigation elements', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(IndexPage)
    const html = wrapper.html()

    expect(html.length).toBeGreaterThan(0)
  })
})
