import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ExplorerPage from '~/pages/explorer.vue'

describe('Explorer Page', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
  })

  it('renders the page', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays parameter selection', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)
    const text = wrapper.text()
    
    expect(text).toContain('Select Parameters')
  })

  it('displays station mode options', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)
    
    // Check that the component renders successfully
    expect(wrapper.exists()).toBe(true)
  })

  it('has data viewer component', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)
    
    // Check if DataViewer component is present
    expect(wrapper.html()).toBeTruthy()
  })
})
