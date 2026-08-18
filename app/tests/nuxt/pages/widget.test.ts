import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WidgetPage from '~/pages/widget.vue'

describe('widget Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  it('renders the page', async () => {
    const wrapper = await mountSuspended(WidgetPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('shows a hint when no station query param is given', async () => {
    const wrapper = await mountSuspended(WidgetPage)
    expect(wrapper.text()).toContain('No station specified')
  })

  it('loads the station and forecast when ?station= is present', async () => {
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }],
    }))
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ values: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    const vm = wrapper.vm as any
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(vm.station?.station_id).toBe('00001')
  })

  it('shows an error when the station lookup fails', async () => {
    registerEndpoint('/api/stations', () => new Response('not found', { status: 404 }))

    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=99999' })
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Station not found')
  })

  it('applies the theme query param to color mode', async () => {
    registerEndpoint('/api/stations', () => ({ stations: [] }))

    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?theme=dark' })
    const vm = wrapper.vm as any
    await wrapper.vm.$nextTick()

    expect(vm.colorMode.preference).toBe('dark')
  })

  it('links back to the full meteogram page', async () => {
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }],
    }))
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ values: [] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    await new Promise(resolve => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('/meteogram?station=00001')
  })
})
