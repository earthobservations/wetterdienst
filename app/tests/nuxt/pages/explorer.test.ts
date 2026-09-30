import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { createError, getQuery } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { UApp } from '#components'
import { useToast } from '#imports'
import ParameterSelection from '~/components/ParameterSelection.vue'
import ExplorerPage from '~/pages/explorer.vue'

// DataViewer's copy-to-clipboard buttons use UTooltip, which needs a
// TooltipProvider -- normally supplied by app.vue's root <UApp>. Mounting the
// bare page works for most tests, but any test that drives it far enough to
// render DataViewer (i.e. picks a station) needs this wrapper too.
const ExplorerWithApp = defineComponent({
  setup() {
    return () => h(UApp, null, { default: () => h(ExplorerPage) })
  },
})

const VALUE_ROW = { station_id: '00001', dataset: 'climate_summary', parameter: 'temperature_air_max_200', timestamp: '2020-01-01T00:00:00Z', value: 12.3, quality: null, unit: 'degree_celsius' }

// pages mounted with a selection, unmounted after each test
const mounted: { unmount: () => void }[] = []

// Mount the page with a station and a parameter selected, ready to fetch; `values` answers /api/values
async function mountWithSelection(values: () => unknown) {
  registerEndpoint('/api/coverage', (event) => {
    const q = getQuery(event)
    if (q.provider)
      return { daily: { description: null, datasets: { climate_summary: { description: null, parameters: [{ name: 'temperature_air_max_200' }] } } } }
    return { dwd: { observation: {} } }
  })
  registerEndpoint('/api/stations', () => ({
    stations: [{ station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }],
  }))
  registerEndpoint('/api/values', values)

  const wrapper = await mountSuspended(ExplorerWithApp, { attachTo: document.body })
  mounted.push(wrapper)
  const vm = wrapper.findComponent(ExplorerPage).vm as any

  // Let ParameterSelection's initialization settle before driving it externally -- otherwise its
  // own emitUpdate() races and clobbers these. It no longer awaits /api/coverage in setup, so
  // that window now spans the whole round trip and is too long to sleep through blindly.
  await vi.waitFor(
    () => expect((wrapper.findComponent(ParameterSelection).vm as any).isInitializing).toBe(false),
    { timeout: 5000 },
  )
  await wrapper.vm.$nextTick()

  vm.parameterSelectionState.selection.resolution = 'daily'
  vm.parameterSelectionState.selection.dataset = 'climate_summary'
  await wrapper.vm.$nextTick()
  await new Promise(resolve => setTimeout(resolve, 50))
  await wrapper.vm.$nextTick()

  vm.parameterSelectionState.selection.parameters = ['temperature_air_max_200']
  vm.stationSelectionState.selection.stations = [{ station_id: '00001', name: 'Test Station' }]
  await wrapper.vm.$nextTick()
  await new Promise(resolve => setTimeout(resolve, 50))
  await wrapper.vm.$nextTick()

  expect(vm.canFetch).toBe(true)
  return { wrapper, vm }
}

describe('explorer Page', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    // toasts are app-wide, so a failed fetch's would be shown by the next test's page
    useToast().clear()
  })

  it('renders the page', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)
    mounted.push(wrapper)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays parameter selection', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)
    mounted.push(wrapper)
    const text = wrapper.text()

    expect(text).toContain('Select Parameters')
  })

  it('displays station mode options', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)
    mounted.push(wrapper)

    // Check that the component renders successfully
    expect(wrapper.exists()).toBe(true)
  })

  it('has data viewer component', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)
    mounted.push(wrapper)

    // Check if DataViewer component is present
    expect(wrapper.html()).toBeTruthy()
  })

  it('clicking Show fetches values into the table, and clicking Reset clears them', async () => {
    const { wrapper, vm } = await mountWithSelection(() => ({ values: [VALUE_ROW] }))

    const showButton = wrapper.findAll('button').find(b => b.text() === 'Show')
    await showButton!.trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('12.3'))
    // nothing has changed since, so there is nothing new to fetch
    expect(vm.canFetch).toBe(false)

    const resetButton = wrapper.findAll('button').find(b => b.text() === 'Reset')
    await resetButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('12.3')
    expect(vm.canFetch).toBe(true)
  })

  it('offers Show again for the same selection after the fetch failed', async () => {
    // failing until the test lets it answer: a GET that fails is retried once on its own. The answer is
    // then held until the test lets it go
    let failing = true
    let release!: () => void
    const held = new Promise<void>(resolve => (release = resolve))
    const { wrapper, vm } = await mountWithSelection(async () => {
      if (failing)
        throw createError({ statusCode: 502, statusMessage: 'Bad Gateway' })
      await held
      return { values: [VALUE_ROW] }
    })

    const showButton = () => wrapper.findAll('button').find(b => b.text() === 'Show')!
    await showButton().trigger('click')
    await vi.waitFor(() => expect(vm.dataViewerRef.fetchErrorMessage).toBeTruthy())
    await vi.waitFor(() => expect(showButton().attributes('disabled')).toBeUndefined())
    expect(wrapper.text()).not.toContain('12.3')

    failing = false
    await showButton().trigger('click')
    // the failed fetch's error stays until the retry answers, but the retry is under way
    await vi.waitFor(() => expect(vm.dataViewerRef.valuesPending).toBe(true))
    expect(vm.canFetch).toBe(false)
    release()
    await vi.waitFor(() => expect(wrapper.text()).toContain('12.3'))
    expect(vm.canFetch).toBe(false)
  })

  it('keeps Show disabled while a fetch is under way, and for a newer Fetch that cancelled it', async () => {
    // the first request's answer is held until the test lets it go, and differs from the second's
    let release!: () => void
    const held = new Promise<void>(resolve => (release = resolve))
    let requests = 0
    let firstAnswered = false
    const { wrapper, vm } = await mountWithSelection(async () => {
      requests += 1
      if (requests === 1) {
        await held
        firstAnswered = true
        return { values: [VALUE_ROW] }
      }
      return { values: [{ ...VALUE_ROW, value: 45.6 }] }
    })

    const showButton = () => wrapper.findAll('button').find(b => b.text() === 'Show')!
    await showButton().trigger('click')
    await vi.waitFor(() => expect(requests).toBe(1))
    expect(vm.canFetch).toBe(false)

    vm.dataSettings.humanize = false
    await wrapper.vm.$nextTick()
    expect(vm.canFetch).toBe(true)
    await showButton().trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('45.6'))
    expect(vm.canFetch).toBe(false)
    expect(wrapper.text()).not.toContain('12.3')

    // let the held handler finish, within this test. Its answer cannot reach the table whenever it
    // comes: useAsyncData rejects a cancelled fetch as it is aborted, not when its answer arrives
    release()
    await vi.waitFor(() => expect(firstAnswered).toBe(true))
  })

  it('offers Show again when the station is removed and chosen again', async () => {
    const { wrapper, vm } = await mountWithSelection(() => ({ values: [VALUE_ROW] }))

    await wrapper.findAll('button').find(b => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('12.3'))
    expect(vm.canFetch).toBe(false)

    // with no station the viewer is gone, and it comes back empty
    vm.stationSelectionState.selection.stations = []
    await wrapper.vm.$nextTick()
    expect(vm.dataViewerRef).toBeNull()
    vm.stationSelectionState.selection.stations = [{ station_id: '00001', name: 'Test Station' }]
    await vi.waitFor(() => expect(vm.canFetch).toBe(true))
    expect(wrapper.text()).not.toContain('12.3')
  })

  it('keeps Show disabled when a setting the request does not carry changes', async () => {
    const { wrapper, vm } = await mountWithSelection(() => ({ values: [VALUE_ROW] }))

    await wrapper.findAll('button').find(b => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('12.3'))
    expect(vm.canFetch).toBe(false)

    // an interpolation point is sent only in interpolation mode; this is station mode
    vm.stationSelectionState.interpolation.latitude = 50.1
    await wrapper.vm.$nextTick()
    expect(vm.canFetch).toBe(false)

    // the shape is sent in station mode, so changing it asks for something new
    vm.dataSettings.shape = 'wide'
    await wrapper.vm.$nextTick()
    expect(vm.canFetch).toBe(true)
  })

  it('offers Show again when a setting sent empty becomes NaN', async () => {
    const { wrapper, vm } = await mountWithSelection(() => ({ values: [VALUE_ROW] }))
    // a cleared number input is null
    vm.dataSettings.skipThreshold = null
    await wrapper.vm.$nextTick()

    await wrapper.findAll('button').find(b => b.text() === 'Show')!.trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('12.3'))
    expect(vm.canFetch).toBe(false)

    // sent as "NaN" where null is sent empty, so another request, though JSON writes both as null
    vm.dataSettings.skipThreshold = Number.NaN
    await wrapper.vm.$nextTick()
    expect(vm.canFetch).toBe(true)
  })
})
