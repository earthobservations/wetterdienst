import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { setResponseStatus } from 'h3'
import { beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest'
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

  it('tells a failed forecast by the backend\'s detail', async () => {
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }],
    }))
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      new Response(JSON.stringify({ detail: 'No forecast for station 00001' }), { status: 404, statusText: 'Not Found' }),
    )

    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.error).toBe('Backend error 404: No forecast for station 00001'))
    expect(wrapper.text()).toContain('Backend error 404: No forecast for station 00001')
  })

  it('tells a failed forecast by its status when the body gives no detail', async () => {
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }],
    }))
    // a proxy's error page: its status text is told, its body left out
    vi.mocked(globalThis.fetch).mockImplementation(async () =>
      new Response('<html>proxy page</html>', { status: 502, statusText: 'Bad Gateway' }),
    )

    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.error).toBe('Backend error 502 Bad Gateway'))
    expect(wrapper.text()).not.toContain('proxy page')
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

describe('widget Page station lookup answered with a 500', () => {
  it('asks /api/stations once', async () => {
    // counted at the endpoint, which a request reaches however it is made
    let asked = 0
    onTestFinished(registerEndpoint('/api/stations', (event) => {
      asked++
      setResponseStatus(event, 500)
      return { detail: 'Upstream failed' }
    }))
    globalThis.fetch = vi.fn()
    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    onTestFinished(() => wrapper.unmount())
    // set once the lookup has failed, which a request asked again does after its second answer
    await vi.waitFor(() => expect((wrapper.vm as any).error).not.toBeNull())
    expect(asked).toBe(1)
  })
})

describe('widget Page station lookup answered with a 503 once', () => {
  it('asks /api/stations once more, and shows the station that answer brings', async () => {
    // a 503 the first time only, as a proxy gives while the backend restarts
    let asked = 0
    onTestFinished(registerEndpoint('/api/stations', (event) => {
      asked++
      if (asked === 1) {
        setResponseStatus(event, 503)
        return { detail: 'Service Unavailable' }
      }
      return { stations: [{ station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }] }
    }))
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({ values: [] }), { status: 200 }))
    const wrapper = await mountSuspended(WidgetPage, { route: '/widget?station=00001' })
    onTestFinished(() => wrapper.unmount())
    const vm = wrapper.vm as any
    await vi.waitFor(() => expect(vm.station?.station_id).toBe('00001'))
    expect(asked).toBe(2)
    expect(vm.error).toBeNull()
  })
})
