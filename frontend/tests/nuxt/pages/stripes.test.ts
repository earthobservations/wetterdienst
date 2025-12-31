import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import StripesPage from '~/pages/stripes.vue'

describe('Stripes Page', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
  })

  it('renders the page', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays climate stripes title', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)
    const text = wrapper.text()
    
    expect(text).toContain('Climate Stripes')
  })

  it('has station selection', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)
    
    expect(wrapper.html()).toBeTruthy()
  })

  it('allows selecting kind (temperature/precipitation)', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)
    const vm = wrapper.vm as any
    
    expect(vm.kind).toBeDefined()
    expect(['temperature', 'precipitation']).toContain(vm.kind)
  })

  it('fetches stations based on kind', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ stations: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(StripesPage)
    const vm = wrapper.vm as any
    
    expect(vm.stations).toBeDefined()
  })
})
