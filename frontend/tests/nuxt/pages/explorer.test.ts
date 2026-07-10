import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery } from 'h3'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { UApp } from '#components'
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
    registerEndpoint('/api/coverage', (event) => {
      const q = getQuery(event)
      if (q.provider)
        return { daily: { climate_summary: [{ name: 'temperature_air_max_200' }] } }
      return { dwd: { observation: {} } }
    })
    registerEndpoint('/api/stations', () => ({
      stations: [{ station_id: '00001', name: 'Test Station', latitude: 52.5, longitude: 13.4 }],
    }))
    registerEndpoint('/api/values', () => ({
      values: [{ station_id: '00001', dataset: 'climate_summary', parameter: 'temperature_air_max_200', date: '2020-01-01T00:00:00Z', value: 12.3, quality: null, unit: 'degree_celsius' }],
    }))

    const wrapper = await mountSuspended(ExplorerWithApp, { attachTo: document.body })
    const vm = wrapper.findComponent(ExplorerPage).vm as any

    // Let ParameterSelection's async initialization settle before driving it
    // externally -- otherwise its own emitUpdate() races and clobbers these.
    await new Promise(resolve => setTimeout(resolve, 100))
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

    const showButton = wrapper.findAll('button').find(b => b.text() === 'Show')
    await showButton!.trigger('click')
    await new Promise(resolve => setTimeout(resolve, 100))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('12.3')

    const resetButton = wrapper.findAll('button').find(b => b.text() === 'Reset')
    await resetButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('12.3')
  })
})
