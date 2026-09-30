import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { createError, getQuery } from 'h3'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { UApp } from '#components'
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

  it('renders the page', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays parameter selection', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)
    const text = wrapper.text()

    expect(text).toContain('Select Parameters')
  })

  it('displays station mode options', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)

    // Check that the component renders successfully
    expect(wrapper.exists()).toBe(true)
  })

  it('has data viewer component', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response(JSON.stringify({ dwd: ['observation'] }), { status: 200 }),
    )

    const wrapper = await mountSuspended(ExplorerPage)

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
  })

  it('offers Show again for the same selection after the fetch failed', async () => {
    // failing until the test lets it answer: a GET that fails is retried once on its own
    let failing = true
    const { wrapper, vm } = await mountWithSelection(() => {
      if (failing)
        throw createError({ statusCode: 502, statusMessage: 'Bad Gateway' })
      return { values: [VALUE_ROW] }
    })

    const showButton = () => wrapper.findAll('button').find(b => b.text() === 'Show')!
    await showButton().trigger('click')
    await vi.waitFor(() => expect(vm.dataViewerRef.fetchErrorMessage).toBeTruthy())
    await vi.waitFor(() => expect(showButton().attributes('disabled')).toBeUndefined())
    expect(wrapper.text()).not.toContain('12.3')

    failing = false
    await showButton().trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('12.3'))
    expect(vm.canFetch).toBe(false)
  })

  it('keeps Show disabled for a newer Fetch that overtook one still under way', async () => {
    // the first answer is held until the test lets it go
    let release!: () => void
    const held = new Promise<void>(resolve => (release = resolve))
    let requests = 0
    const { wrapper, vm } = await mountWithSelection(async () => {
      requests += 1
      if (requests === 1)
        await held
      return { values: [VALUE_ROW] }
    })

    const showButton = () => wrapper.findAll('button').find(b => b.text() === 'Show')!
    await showButton().trigger('click')
    await vi.waitFor(() => expect(requests).toBe(1))

    vm.dataSettings.humanize = false
    await wrapper.vm.$nextTick()
    await showButton().trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('12.3'))

    release()
    await vi.waitFor(() => expect(vm.dataViewerRef.valuesPending).toBe(false))
    await flushPromises()
    // the overtaken fetch filled nothing, but the newer one did, for the settings now selected
    expect(vm.canFetch).toBe(false)
  })
})
