import { mountSuspended } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ApiPage from '~/pages/api.vue'

describe('aPI Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  it('renders the page', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ApiPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays API endpoints', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ApiPage)
    const text = wrapper.text()

    expect(text).toContain('REST API')
    expect(text).toContain('Endpoints')
  })

  it('lists all API endpoints', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ApiPage)
    const text = wrapper.text()

    expect(text).toContain('coverage')
    expect(text).toContain('stations')
    expect(text).toContain('values')
    expect(text).toContain('interpolate')
    expect(text).toContain('summarize')
  })

  it('displays API examples', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    const wrapper = await mountSuspended(ApiPage)
    const text = wrapper.text()

    expect(text).toContain('Examples')
  })
})
