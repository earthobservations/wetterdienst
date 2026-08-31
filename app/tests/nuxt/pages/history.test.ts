import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery } from 'h3'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ParameterSelection from '~/components/ParameterSelection.vue'
import HistoryPage from '~/pages/history.vue'

// ParameterSelection fires its /api/coverage request without awaiting it in setup, so mounting no
// longer implies it has restored provider/network. Driving `paramSel` before that has settled
// would be clobbered by the component's own initial emit. The page's own `paramSel.provider` is
// no signal here -- it starts out as 'dwd' -- so this waits on the child's initialization flag.
async function mountHistory(options?: Record<string, unknown>) {
  const wrapper = await mountSuspended(HistoryPage, options)
  await vi.waitFor(
    () => expect((wrapper.findComponent(ParameterSelection).vm as any).isInitializing).toBe(false),
    { timeout: 5000 },
  )
  return wrapper
}

describe('history Page', () => {
  beforeEach(() => {
    // Same path serves two shapes: the plain provider/network listing, and --
    // once a provider+network is picked -- the resolution/dataset/parameter tree.
    registerEndpoint('/api/coverage', (event) => {
      const q = getQuery(event)
      if (q.provider)
        return { daily: { description: null, datasets: { climate_summary: { description: null, parameters: [{ name: 'temperature_air_max_200' }] } } } }
      return { dwd: { observation: {} } }
    })
  })

  it('renders the page', async () => {
    const wrapper = await mountHistory()
    expect(wrapper.exists()).toBe(true)
  })

  it('displays the station history heading', async () => {
    const wrapper = await mountHistory()
    expect(wrapper.text()).toContain('Station history')
  })

  it('restricts provider/network to dwd/observation', async () => {
    const wrapper = await mountHistory()
    const vm = wrapper.vm as any

    expect(vm.paramSel.provider).toBe('dwd')
    expect(vm.paramSel.network).toBe('observation')
  })

  it('prompts to select resolution/dataset before station selection', async () => {
    const wrapper = await mountHistory()
    expect(wrapper.text()).toContain('Please select resolution and dataset first')
  })

  it('shows the history sections selector', async () => {
    const wrapper = await mountHistory()
    expect(wrapper.text()).toContain('History sections')
  })

  it('disables fetching until resolution, dataset and a station are selected', async () => {
    const wrapper = await mountHistory()
    const vm = wrapper.vm as any

    expect(vm.canFetch).toBe(false)

    vm.paramSel.resolution = 'daily'
    vm.paramSel.dataset = 'climate_summary'
    await wrapper.vm.$nextTick()
    expect(vm.canFetch).toBe(false)

    vm.stationSelectionState.selection.stations = [{ station_id: '00001', name: 'Test' }]
    await wrapper.vm.$nextTick()
    expect(vm.canFetch).toBe(true)
  })

  it('shows an empty-results hint before any query has run', async () => {
    const wrapper = await mountHistory()
    expect(wrapper.text()).toContain('No histories loaded')
  })

  it('clear() resets fetched history data', async () => {
    const wrapper = await mountHistory()
    const vm = wrapper.vm as any

    vm.data = { histories: [{ name: { station: [{ station_name: 'Foo' }] } }] }
    await wrapper.vm.$nextTick()

    vm.clear()
    await wrapper.vm.$nextTick()

    expect(vm.data).toEqual({ histories: [] })
  })

  it('clicking the about toggle reveals the explanatory text', async () => {
    const wrapper = await mountHistory({ attachTo: document.body })
    expect(wrapper.text()).not.toContain('captures the administrative')

    const aboutButton = wrapper.findAll('button').find(b => b.text().includes('About station history'))
    await aboutButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('captures the administrative')
  })

  it('clicking Show fetches history, and clicking Reset clears it again', async () => {
    registerEndpoint('/api/history', () => ({
      histories: [
        {
          parameter: [{ station_id: '00001', station_name: 'Foo Station', start_date: '2000-01-01', end_date: null, parameter: 'temperature_air_mean_2m', description: 'Air temp', unit: '°C' }],
          name: { station: [{ start_date: '2000-01-01', end_date: null, station_name: 'Foo Station' }] },
        },
      ],
    }))

    const wrapper = await mountHistory({ attachTo: document.body })
    const vm = wrapper.vm as any

    // mountHistory() already waited for ParameterSelection's initialization, whose own emitUpdate()
    // would otherwise clobber what is set here. Resolution and dataset go first and get a tick of
    // their own: each has a watcher that clears the station selection, so a station set in the
    // same tick would be wiped again.
    vm.paramSel.resolution = 'daily'
    vm.paramSel.dataset = 'climate_summary'
    await wrapper.vm.$nextTick()

    vm.stationSelectionState.selection.stations = [{ station_id: '00001', name: 'Test' }]
    await wrapper.vm.$nextTick()
    expect(vm.canFetch).toBe(true)

    const runButton = wrapper.findAll('button').find(b => b.text() === 'Show')
    await runButton!.trigger('click')
    // Waiting on the rendered result rather than on a fixed sleep: under a parallel test run no
    // sleep short enough to be worth having is reliably long enough.
    await vi.waitFor(() => expect(wrapper.text()).toContain('Station ID: 00001'), { timeout: 5000 })

    const nameHistoryButton = wrapper.findAll('button').find(b => b.text().includes('Name history'))
    await nameHistoryButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Foo Station')

    const resetButton = wrapper.findAll('button').find(b => b.text() === 'Reset')
    await resetButton!.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('Foo Station')
    expect(wrapper.text()).toContain('No histories loaded')
  })
})
