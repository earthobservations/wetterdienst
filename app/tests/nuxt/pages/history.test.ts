import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { createError, getQuery } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ParameterSelection from '~/components/ParameterSelection.vue'
import HistoryPage from '~/pages/history.vue'

// pages mounted by a test, unmounted after it: a page left mounted can share its fetch with the next
// test's, useFetch keying a fetch by where it is called and what it asks for
const mounted: Array<{ unmount: () => void }> = []

// ParameterSelection fires its /api/coverage request without awaiting it in setup, so mounting no
// longer implies it has restored provider/network. Driving `paramSel` before that has settled
// would be clobbered by the component's own initial emit. The page's own `paramSel.provider` is
// no signal here -- it starts out as 'dwd' -- so this waits on the child's initialization flag.
async function mountHistory(options?: Record<string, unknown>) {
  const wrapper = await mountSuspended(HistoryPage, options)
  mounted.push(wrapper)
  await vi.waitFor(
    () => expect((wrapper.findComponent(ParameterSelection).vm as any).isInitializing).toBe(false),
    { timeout: 5000 },
  )
  return wrapper
}

const HISTORY = {
  histories: [
    { parameter: [{ station_id: '00001', station_name: 'Foo Station', start_date: '2000-01-01', end_date: null, parameter: 'temperature_air_mean_2m', description: 'Air temp', unit: '°C' }] },
  ],
}

// disposers of the /api/history endpoints the tests below register, so none answers the next test
const endpoints: Array<() => void> = []

// the page with a dataset and a station chosen, and /api/history answered by `history`
async function mountWithSelection(history: Parameters<typeof registerEndpoint>[1]) {
  endpoints.push(registerEndpoint('/api/history', history))
  const wrapper = await mountHistory({ attachTo: document.body })
  const vm = wrapper.vm as any
  // Resolution and dataset get a tick of their own: each has a watcher that clears the station selection
  vm.paramSel.resolution = 'daily'
  vm.paramSel.dataset = 'climate_summary'
  await wrapper.vm.$nextTick()
  vm.stationSelectionState.selection.stations = [{ station_id: '00001', name: 'Test' }]
  await wrapper.vm.$nextTick()
  const showButton = () => wrapper.findAll('button').find(b => b.text() === 'Show')!
  return { wrapper, vm, showButton }
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

  afterEach(() => {
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    endpoints.splice(0).forEach(dispose => dispose())
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
    endpoints.push(registerEndpoint('/api/history', () => ({
      histories: [
        {
          parameter: [{ station_id: '00001', station_name: 'Foo Station', start_date: '2000-01-01', end_date: null, parameter: 'temperature_air_mean_2m', description: 'Air temp', unit: '°C' }],
          name: { station: [{ start_date: '2000-01-01', end_date: null, station_name: 'Foo Station' }] },
        },
      ],
    })))

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
    expect(vm.canFetch).toBe(true)
  })

  it('offers Show again for the same selection after the fetch failed', async () => {
    // failing until the test lets it answer: a GET that fails is retried once on its own;
    // then held until the test lets it go
    let failing = true
    let release!: () => void
    const held = new Promise<void>(resolve => (release = resolve))
    const { wrapper, vm, showButton } = await mountWithSelection(async () => {
      if (failing)
        throw createError({ statusCode: 502, statusMessage: 'Bad Gateway' })
      await held
      return HISTORY
    })

    await showButton().trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Error:'), { timeout: 5000 })
    await vi.waitFor(() => expect(showButton().attributes('disabled')).toBeUndefined(), { timeout: 5000 })

    failing = false
    await showButton().trigger('click')
    // the failed fetch's error goes once the retry is under way, not when it answers
    await vi.waitFor(() => expect(wrapper.text()).toContain('Loading'), { timeout: 5000 })
    expect(wrapper.text()).not.toContain('Error:')
    release()
    await vi.waitFor(() => expect(wrapper.text()).toContain('Station ID: 00001'), { timeout: 5000 })
    expect(vm.canFetch).toBe(false)
  })

  it('keeps Show disabled for the selection fetched, while under way and once answered', async () => {
    // the answer is held until the test lets it go
    let release!: () => void
    const held = new Promise<void>(resolve => (release = resolve))
    const sent: unknown[] = []
    const { wrapper, vm, showButton } = await mountWithSelection(async (event) => {
      sent.push(getQuery(event).sections)
      await held
      return HISTORY
    })
    vm.selectedSections = ['parameter', 'name']
    await wrapper.vm.$nextTick()

    await showButton().trigger('click')
    expect(vm.canFetch).toBe(false)
    release()
    await vi.waitFor(() => expect(wrapper.text()).toContain('Station ID: 00001'), { timeout: 5000 })
    expect(vm.canFetch).toBe(false)

    // the sections are sent sorted, and the user's own order is left alone
    expect(sent).toEqual([['name', 'parameter']])
    expect(vm.selectedSections).toEqual(['parameter', 'name'])
    // so picking the same sections in another order is nothing new to fetch
    vm.selectedSections = ['name', 'parameter']
    await wrapper.vm.$nextTick()
    expect(vm.canFetch).toBe(false)

    vm.selectedSections = ['name', 'parameter', 'device']
    await wrapper.vm.$nextTick()
    expect(vm.canFetch).toBe(true)
    // and back to the sections the table shows
    vm.selectedSections = ['parameter', 'name']
    await wrapper.vm.$nextTick()
    expect(vm.canFetch).toBe(false)
  })

  it('shows the answer to a fetch under way when the selection changes before it answers', async () => {
    // the answer is held until the test lets it go
    let release!: () => void
    const held = new Promise<void>(resolve => (release = resolve))
    const { wrapper, vm, showButton } = await mountWithSelection(async () => {
      await held
      return HISTORY
    })

    await showButton().trigger('click')
    vm.selectedSections = ['device']
    await wrapper.vm.$nextTick()
    release()
    await vi.waitFor(() => expect(wrapper.text()).toContain('Station ID: 00001'), { timeout: 5000 })
    // what the table shows isn't the selection, so Show is offered for it
    expect(vm.canFetch).toBe(true)
  })
})
