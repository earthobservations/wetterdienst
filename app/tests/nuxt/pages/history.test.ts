import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { createError, getQuery, setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ParameterSelection from '~/components/ParameterSelection.vue'
import HistoryPage from '~/pages/history.vue'
import { dailyClimateSummaryCoverage } from '../fixtures/coverage'

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
        return dailyClimateSummaryCoverage()
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

    expect(vm.data).toEqual({ histories: [], stations: [] })
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
    // told by its status, not by ofetch's message with the whole request in front
    await vi.waitFor(() => expect(wrapper.text()).toContain('Error: 502 Bad Gateway'), { timeout: 5000 })
    expect(wrapper.text()).not.toContain('/api/history')
    await vi.waitFor(() => expect(showButton().attributes('disabled')).toBeUndefined(), { timeout: 5000 })

    failing = false
    await showButton().trigger('click')
    // the failed fetch's error goes once Show is pressed again, not when that fetch answers
    await vi.waitFor(() => expect(wrapper.text()).toContain('Loading'), { timeout: 5000 })
    expect(wrapper.text()).not.toContain('Error:')
    release()
    await vi.waitFor(() => expect(wrapper.text()).toContain('Station ID: 00001'), { timeout: 5000 })
    expect(vm.canFetch).toBe(false)
  })

  it('tells a refused request by the backend\'s detail', async () => {
    // answered as FastAPI answers a lookup that failed: the reason under `detail`, nothing around it
    const { wrapper, showButton } = await mountWithSelection((event) => {
      setResponseStatus(event, 400)
      return { detail: 'No stations found for the given ids' }
    })

    await showButton().trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Error: No stations found for the given ids'), { timeout: 5000 })
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

  it('lists the stations the histories shown were fetched for, not the live selection', async () => {
    // each answer is for the station asked for, and held until the test lets it go
    const gates: Array<() => void> = []
    const { wrapper, vm, showButton } = await mountWithSelection(async (event) => {
      const station = String(getQuery(event).station)
      await new Promise<void>(resolve => gates.push(resolve))
      return { histories: [{ parameter: [{ ...HISTORY.histories[0]!.parameter[0], station_id: station }] }] }
    })
    // the id and name of each station in the Selected stations overview
    const overview = () => {
      const heading = wrapper.findAll('h3').find(h => h.text() === 'Selected stations')
      return heading
        ? [...heading.element.parentElement!.querySelectorAll('tbody tr')].map(tr =>
            [...tr.querySelectorAll('td')].slice(0, 2).map(td => td.textContent!.trim()).join(' '))
        : []
    }

    await showButton().trigger('click')
    await vi.waitFor(() => expect(gates).toHaveLength(1), { timeout: 5000 })
    gates[0]!()
    await vi.waitFor(() => expect(wrapper.text()).toContain('Station ID: 00001'), { timeout: 5000 })
    expect(overview()).toEqual(['00001 Test'])

    vm.stationSelectionState.selection.stations = [{ station_id: '00044', name: 'Other' }]
    await wrapper.vm.$nextTick()
    expect(overview()).toEqual(['00001 Test'])

    // nor while the next fetch is under way, beside the answer before it
    await showButton().trigger('click')
    await vi.waitFor(() => expect(gates).toHaveLength(2), { timeout: 5000 })
    expect(overview()).toEqual(['00001 Test'])
    // and the answer is for the stations sent, whatever is selected by the time it comes
    vm.stationSelectionState.selection.stations = [{ station_id: '00099', name: 'Third' }]
    await wrapper.vm.$nextTick()
    gates[1]!()
    await vi.waitFor(() => expect(wrapper.text()).toContain('Station ID: 00044'), { timeout: 5000 })
    expect(overview()).toEqual(['00044 Other'])
  })

  it('shows a station\'s position by the periods it held, as its geography gives them', async () => {
    // shaped as the backend answers the name and geography sections, with positions of 01048's: the
    // position is in `geography`, one record per period, and nowhere at the top of the history
    const { wrapper, vm, showButton } = await mountWithSelection(() => ({
      histories: [{
        name: {
          station: [{ station_id: '00001', station_name: 'Foo Station', start_date: '1926-05-01T00:00:00+00:00', end_date: null }],
          operator: [],
        },
        geography: [
          { station_id: '00001', station_name: 'Foo Station', latitude: 51.0883, longitude: 13.7601, station_elevation: 152, start_date: '1926-05-01T00:00:00+00:00', end_date: '1935-07-10T00:00:00+00:00' },
          { station_id: '00001', station_name: 'Foo Station', latitude: 51.1278, longitude: 13.7543, station_elevation: 227.57, start_date: '2019-08-14T00:00:00+00:00', end_date: '2026-09-30T00:00:00+00:00' },
        ],
      }],
    }))
    vm.selectedSections = ['name', 'geography']
    await wrapper.vm.$nextTick()

    await showButton().trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Station ID: 00001'), { timeout: 5000 })
    await wrapper.findAll('button').find(b => b.text().includes('Geography history'))!.trigger('click')

    // each period a row of its own: from, to, latitude, longitude, elevation
    const rows = () => {
      const table = wrapper.findAll('table').find(t => t.text().includes('1935-07-10'))
      return table
        ? [...table.element.querySelectorAll('tbody tr')].map(tr =>
            [...tr.querySelectorAll('td')].map(td => td.textContent!.trim()))
        : []
    }
    await vi.waitFor(() => expect(rows()).toEqual([
      ['1926-05-01T00:00:00+00:00', '1935-07-10T00:00:00+00:00', '51.0883', '13.7601', '152'],
      ['2019-08-14T00:00:00+00:00', '2026-09-30T00:00:00+00:00', '51.1278', '13.7543', '227.57'],
    ]), { timeout: 5000 })
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

describe('history Page results', () => {
  beforeEach(() => {
    registerEndpoint('/api/coverage', (event) => {
      const q = getQuery(event)
      if (q.provider)
        return dailyClimateSummaryCoverage()
      return { dwd: { observation: {} } }
    })
  })

  afterEach(() => {
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    endpoints.splice(0).forEach(dispose => dispose())
  })

  it('shows a number of 0 as 0, and one the backend has no value for as -', async () => {
    const period = { station_id: '00001', station_name: 'Foo Station', start_date: '2000-01-01T00:00:00+00:00', end_date: '2001-01-01T00:00:00+00:00' }
    // each table a row with its numbers at 0, and one with them null, as the backend sends a field it has no value for
    const { wrapper, showButton } = await mountWithSelection(() => ({
      histories: [{
        device: [
          { ...period, device_type: 'Thermometer', device_height: 0, latitude: 0, longitude: 0, station_elevation: 0, method: 'M' },
          { ...period, device_type: 'Thermometer', device_height: null, latitude: null, longitude: null, station_elevation: null, method: 'M' },
        ],
        geography: [
          { ...period, latitude: 0, longitude: 0, station_elevation: 0 },
          { ...period, latitude: null, longitude: null, station_elevation: null },
        ],
        missing_data: {
          summary: [
            { ...period, parameter: 'TMK', missing_count: 0, description: null },
            { ...period, parameter: 'TMK', missing_count: null, description: null },
          ],
          periods: [
            { ...period, parameter: 'TXK', missing_count: 0, description: null },
            { ...period, parameter: 'TXK', missing_count: null, description: null },
          ],
        },
      }],
    }))

    await showButton().trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Station ID: 00001'), { timeout: 5000 })
    for (const section of ['Device history', 'Geography history', 'Missing data history'])
      await wrapper.findAll('button').find(b => b.text().includes(section))!.trigger('click')

    // each row's cells after its start and end date, in the table headed by `column` that holds `text`
    const cells = (column: string, text = '') => {
      const table = wrapper.findAll('table').find(t =>
        t.find('thead').exists() && t.find('thead').text().includes(column) && t.text().includes(text))
      return table
        ? [...table.element.querySelectorAll('tbody tr')].map(tr =>
            [...tr.querySelectorAll('td')].slice(2).map(td => td.textContent!.trim()))
        : []
    }
    await vi.waitFor(() => expect(cells('Station elevation')).toEqual([['0', '0', '0'], ['-', '-', '-']]), { timeout: 5000 })
    expect(cells('Device height')).toEqual([['Thermometer', '0', 'M'], ['Thermometer', '-', 'M']])
    expect(cells('Missing count', 'TMK')).toEqual([['TMK', '0'], ['TMK', '-']])
    expect(cells('Missing count', 'TXK')).toEqual([['TXK', '0'], ['TXK', '-']])
  })

  // a station name record, as the backend's name section has them
  const named = (station_name: string, start_date: string, end_date: string | null) =>
    ({ station_id: '00001', station_name, start_date, end_date })
  // a geography record, with the station's name at the time
  const placed = (station_name: string, start_date: string, end_date: string) =>
    ({ station_id: '00001', station_name, latitude: 51.1, longitude: 13.8, station_elevation: 227, start_date, end_date })
  // a parameter record of `parameter`, with the station's name at the time
  const measured = (parameter: string, station_name: string, start_date: string, end_date: string) =>
    ({ station_id: '00001', station_name, parameter, start_date, end_date, description: null, unit: null, data_source: null, extra_info: null, special: null, literature: null })

  // the station card's header, after Show has answered with `history`
  async function cardHeader(history: Record<string, unknown>) {
    const { wrapper, showButton } = await mountWithSelection(() => ({ histories: [history] }))
    await showButton().trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Station ID: 00001'), { timeout: 5000 })
    return { wrapper, header: wrapper.findAll('h3').find(h => h.text().startsWith('Station ID'))!.text() }
  }

  it('names the card by the name the station holds now, as its name history gives it', async () => {
    // 01048's names: Dresden-Heller until 1935, Dresden-Klotzsche since; the other sections name it too
    const { wrapper, header } = await cardHeader({
      name: {
        station: [
          named('Dresden-Heller', '1926-05-01T00:00:00+00:00', '1935-07-10T00:00:00+00:00'),
          named('Dresden-Klotzsche', '1934-01-01T00:00:00+00:00', null),
        ],
        operator: [],
      },
      geography: [placed('Elsewhere', '1926-05-01T00:00:00+00:00', '2026-09-30T00:00:00+00:00')],
    })

    expect(header).toBe('Station ID: 00001 Dresden-Klotzsche')
    // told once, in the header: the card has no row of its own for it
    expect(wrapper.text().split('Dresden-Klotzsche')).toHaveLength(2)
    expect(wrapper.text()).not.toContain('Dresden-Heller')
  })

  it('takes the name still held over the one listed last', async () => {
    const { header } = await cardHeader({
      name: {
        station: [
          named('Dresden-Klotzsche', '1934-01-01T00:00:00+00:00', null),
          named('Dresden-Heller', '1926-05-01T00:00:00+00:00', '1935-07-10T00:00:00+00:00'),
        ],
        operator: [],
      },
      geography: [placed('Elsewhere', '1926-05-01T00:00:00+00:00', '2026-09-30T00:00:00+00:00')],
    })

    expect(header).toBe('Station ID: 00001 Dresden-Klotzsche')
  })

  it('takes the name begun last of two still held', async () => {
    const { header } = await cardHeader({
      name: {
        station: [
          named('Dresden-Klotzsche', '1934-01-01T00:00:00+00:00', null),
          named('Dresden-Heller', '1926-05-01T00:00:00+00:00', null),
        ],
        operator: [],
      },
      geography: [placed('Elsewhere', '1926-05-01T00:00:00+00:00', '2026-09-30T00:00:00+00:00')],
    })

    expect(header).toBe('Station ID: 00001 Dresden-Klotzsche')
  })

  it('takes the name that ended last where none is still held, wherever it is listed', async () => {
    const { header } = await cardHeader({
      name: {
        station: [
          named('Dresden-Klotzsche', '1934-01-01T00:00:00+00:00', '2020-01-01T00:00:00+00:00'),
          named('Dresden-Heller', '1926-05-01T00:00:00+00:00', '1935-07-10T00:00:00+00:00'),
        ],
        operator: [],
      },
      geography: [placed('Elsewhere', '1926-05-01T00:00:00+00:00', '2026-09-30T00:00:00+00:00')],
    })

    expect(header).toBe('Station ID: 00001 Dresden-Klotzsche')
  })

  it('names the card from the other sections where the name history has no name', async () => {
    const { header } = await cardHeader({
      name: { station: [], operator: [] },
      geography: [
        placed('Dresden-Heller', '1926-05-01T00:00:00+00:00', '1935-07-10T00:00:00+00:00'),
        placed('Dresden-Klotzsche', '1935-07-10T00:00:00+00:00', '2026-09-30T00:00:00+00:00'),
      ],
    })

    expect(header).toBe('Station ID: 00001 Dresden-Klotzsche')
  })

  it('names the card by the parameter record that ended last, listed per parameter as they are', async () => {
    // TMK's periods, then TXK's: the last record listed is an old one
    const { header } = await cardHeader({
      parameter: [
        measured('TMK', 'Dresden-Heller', '1926-05-01T00:00:00+00:00', '1935-07-10T00:00:00+00:00'),
        measured('TMK', 'Dresden-Klotzsche', '1935-07-10T00:00:00+00:00', '2026-09-30T00:00:00+00:00'),
        measured('TXK', 'Dresden-Heller', '1926-05-01T00:00:00+00:00', '1935-07-10T00:00:00+00:00'),
      ],
    })

    expect(header).toBe('Station ID: 00001 Dresden-Klotzsche')
  })

  it('names the card from the missing data section where no other section names it', async () => {
    const missing = (station_name: string, end_date: string) =>
      ({ station_id: '00001', station_name, parameter: 'TMK', start_date: '1926-05-01T00:00:00+00:00', end_date, missing_count: 3, description: null })
    const { header } = await cardHeader({
      // the id from a section with no name
      device: [{ ...placed('', '1926-05-01T00:00:00+00:00', '2026-09-30T00:00:00+00:00'), station_name: null, device_type: null, device_height: null, method: null }],
      missing_data: {
        summary: [missing('Dresden-Klotzsche', '2026-09-30T00:00:00+00:00'), missing('Dresden-Heller', '1935-07-10T00:00:00+00:00')],
        periods: [],
      },
    })

    expect(header).toBe('Station ID: 00001 Dresden-Klotzsche')
  })

  it('takes the station id from the next section where a record\'s is empty', async () => {
    const { header } = await cardHeader({
      parameter: [{ ...measured('TMK', 'Dresden-Klotzsche', '1935-07-10T00:00:00+00:00', '2026-09-30T00:00:00+00:00'), station_id: '' }],
      geography: [placed('Dresden-Klotzsche', '1935-07-10T00:00:00+00:00', '2026-09-30T00:00:00+00:00')],
    })

    expect(header).toBe('Station ID: 00001 Dresden-Klotzsche')
  })
})

describe('history Page station card id', () => {
  beforeEach(() => {
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

  // the station card's header, once Show has answered with `history`
  async function cardHeader(history: Record<string, unknown>) {
    const { wrapper, showButton } = await mountWithSelection(() => ({ histories: [history] }))
    await showButton().trigger('click')
    const header = () => wrapper.findAll('h3').find(h => h.text().startsWith('Station ID'))
    await vi.waitFor(() => expect(header()).toBeDefined(), { timeout: 5000 })
    return header()!.text()
  }

  const period = { station_id: '00001', start_date: '1934-01-01T00:00:00+00:00', end_date: null }
  const missing = { ...period, station_name: null, parameter: 'TMK', end_date: '2026-09-30T00:00:00+00:00', missing_count: 3, description: null }

  it('takes the id from the station names where only the name section is fetched', async () => {
    const header = await cardHeader({ name: { station: [{ ...period, station_name: 'Dresden-Klotzsche' }], operator: [] } })

    expect(header).toBe('Station ID: 00001 Dresden-Klotzsche')
  })

  it('takes the id from the operator names where the name section has no station name', async () => {
    const header = await cardHeader({ name: { station: [], operator: [{ ...period, operator_name: 'DWD' }] } })

    expect(header).toBe('Station ID: 00001')
  })

  it('takes the id from the missing data summary where only the missing data section is fetched', async () => {
    const header = await cardHeader({ missing_data: { summary: [missing], periods: [] } })

    expect(header).toBe('Station ID: 00001')
  })

  it('takes the id from the missing data periods where the missing data section has no summary', async () => {
    const header = await cardHeader({ missing_data: { summary: [], periods: [missing] } })

    expect(header).toBe('Station ID: 00001')
  })
})
