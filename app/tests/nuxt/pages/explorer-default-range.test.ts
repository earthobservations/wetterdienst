import type { H3Event } from 'h3'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { getQuery, setResponseStatus } from 'h3'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { UApp } from '#components'
import { clearNuxtState, useRouter, useToast } from '#imports'
import ParameterSelection from '~/components/ParameterSelection.vue'
import ExplorerPage from '~/pages/explorer.vue'
import { dailyClimateSummaryCoverage } from '../fixtures/coverage'

// The date range the explorer starts for a selection whose whole record is more than the server sends as one
// answer (GH-3457), and who the range belongs to once the user has touched it

const ExplorerWithApp = defineComponent({
  setup() {
    return () => h(UApp, null, { default: () => h(ExplorerPage) })
  },
})

// today, which a record that is still going on ends at: the window ends there
const TODAY = new Date().toISOString().slice(0, 10)

// n stations of the daily record since 1891: 49,000 rows each, so that a few of them are over the limit
function stations(count: number, start = '1891-01-01T00:00:00+00:00') {
  return Array.from({ length: count }, (_, index) => ({
    station_id: String(index + 1).padStart(5, '0'),
    name: `Station ${index + 1}`,
    latitude: 52.5,
    longitude: 13.4,
    start_timestamp: start,
    end_timestamp: null,
  }))
}

const mounted: { unmount: () => void }[] = []
const endpoints: (() => void)[] = []

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  endpoints.splice(0).forEach(remove => remove())
  clearNuxtState()
  useToast().clear()
})

const query = () => useRouter().currentRoute.value.query

// The page, with the station list the test gives and the values the test answers. `route` is the link it is
// opened at; without stations in it the selection is made by the test
async function open(options: { route?: string, list?: ReturnType<typeof stations>, values?: (event: H3Event) => unknown, version?: unknown } = {}) {
  const list = options.list ?? stations(30)
  endpoints.push(registerEndpoint('/api/coverage', (event) => {
    if (getQuery(event).provider)
      return dailyClimateSummaryCoverage()
    return { dwd: { observation: {} } }
  }))
  endpoints.push(registerEndpoint('/api/stations', () => ({ stations: list })))
  endpoints.push(registerEndpoint('/api/values', options.values ?? (() => ({ values: [] }))))
  if (options.version)
    endpoints.push(registerEndpoint('/api/version', () => options.version))
  const wrapper = await mountSuspended(ExplorerWithApp, { attachTo: document.body, route: options.route ?? '/explorer' })
  mounted.push(wrapper)
  const vm = wrapper.findComponent(ExplorerPage).vm as any
  await vi.waitFor(
    () => expect((wrapper.findComponent(ParameterSelection).vm as any).isInitializing).toBe(false),
    { timeout: 5000 },
  )
  return { wrapper, vm, list }
}

// the selection the test makes: the dataset first, as it clears the stations, then the rest
async function select(wrapper: Awaited<ReturnType<typeof open>>['wrapper'], vm: any, chosen: ReturnType<typeof stations>) {
  vm.parameterSelectionState.selection.resolution = 'daily'
  vm.parameterSelectionState.selection.dataset = 'climate_summary'
  await wrapper.vm.$nextTick()
  await new Promise(resolve => setTimeout(resolve, 50))
  vm.parameterSelectionState.selection.parameters = ['temperature_air_max_2m']
  vm.stationSelectionState.selection.stations = chosen
  await wrapper.vm.$nextTick()
}

const dates = (vm: any) => ({ startDate: vm.stationSelectionState.dateRange.startDate, endDate: vm.stationSelectionState.dateRange.endDate })
const note = (wrapper: Awaited<ReturnType<typeof open>>['wrapper']) => wrapper.find('[data-testid="default-range-note"]').text()

async function typeDate(wrapper: Awaited<ReturnType<typeof open>>['wrapper'], index: number, value: string) {
  const input = wrapper.findAll('input[type="date"]')[index]!
  await input.setValue(value)
}

describe('explorer default date range', () => {
  it('starts the newest window that fits where the whole record of the selection is more than one answer', async () => {
    const { wrapper, vm, list } = await open()
    await select(wrapper, vm, list.slice(0, 30))
    // 30 stations of 135 years of daily readings: 1.5 million rows against 450,000 (90 % of 500,000)
    await vi.waitFor(() => expect(dates(vm).endDate).toBe(TODAY))
    const { startDate } = dates(vm)
    expect(startDate! > '1980-01-01' && startDate! < '1995-01-01').toBe(true)
    // said under the fields, as a status the fields are described by
    await vi.waitFor(() => expect(note(wrapper)).toContain('Default range: the newest data ('))
    expect(note(wrapper)).toMatch(/about 4\d\d,000 rows/)
    expect(note(wrapper)).toContain('Clear the date range to ask for everything')
    const status = wrapper.find('[data-testid="default-range-note"]')
    expect(status.attributes('role')).toBe('status')
    for (const input of wrapper.findAll('input[type="date"]'))
      expect(input.attributes('aria-describedby')).toBe(status.attributes('id'))
    // and in the link, as a user's edit would be
    await vi.waitFor(() => expect(query()).toMatchObject({ startDate, endDate: TODAY }))
    expect(query().range).toBeUndefined()
  })

  it('takes the note away when the selection becomes a point, whose range is the whole span of the records', async () => {
    const { wrapper, vm, list } = await open()
    await select(wrapper, vm, list.slice(0, 30))
    await vi.waitFor(() => expect(note(wrapper)).toContain('Default range: the newest data ('))
    vm.stationSelectionState.mode = 'interpolation'
    await vi.waitFor(() => expect(vm.defaultWindow).toBeNull())
    // the whole span, as a required range always was
    expect(dates(vm).startDate! < '1900-01-01').toBe(true)
  })

  it('takes the note away when the stations are removed before the selection becomes a point', async () => {
    const { wrapper, vm, list } = await open()
    await select(wrapper, vm, list.slice(0, 30))
    await vi.waitFor(() => expect(vm.defaultWindow).not.toBeNull())
    vm.stationSelectionState.selection.stations = []
    await vi.waitFor(() => expect(vm.defaultWindow).toBeNull())
  })

  it('fills a required range again at the next change, after it was emptied by hand', async () => {
    const { wrapper, vm, list } = await open()
    await select(wrapper, vm, list.slice(0, 3))
    vm.stationSelectionState.mode = 'interpolation'
    await vi.waitFor(() => expect(dates(vm).startDate).toBeDefined())
    vm.stationSelectionState.dateRange.startDate = undefined
    vm.stationSelectionState.dateRange.endDate = undefined
    vm.onRangeEdited()
    vm.stationSelectionState.selection.stations = list.slice(0, 4)
    await vi.waitFor(() => expect(dates(vm).startDate).toBeDefined())
  })

  it('keeps a range the user cleared cleared through a point, which has to have one', async () => {
    const { wrapper, vm, list } = await open()
    await select(wrapper, vm, list.slice(0, 30))
    await vi.waitFor(() => expect(dates(vm).endDate).toBe(TODAY))
    await wrapper.find('[data-testid="clear-date-range"]').trigger('click')
    expect(dates(vm)).toEqual({ startDate: undefined, endDate: undefined })
    vm.stationSelectionState.mode = 'interpolation'
    await vi.waitFor(() => expect(dates(vm).startDate).toBeDefined())
    vm.stationSelectionState.mode = 'station'
    await vi.waitFor(() => expect(dates(vm)).toEqual({ startDate: undefined, endDate: undefined }))
    expect(vm.defaultWindow).toBeNull()
  })

  it('leaves the range empty where the whole record fits', async () => {
    const { wrapper, vm, list } = await open()
    await select(wrapper, vm, list.slice(0, 2))
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(dates(vm)).toEqual({ startDate: undefined, endDate: undefined })
    // the note is there, empty, as a live region has to be before it speaks
    expect(note(wrapper)).toBe('')
    expect(wrapper.find('[data-testid="clear-date-range"]').exists()).toBe(false)
    expect(query().startDate).toBeUndefined()
  })

  it('takes the limit of the server over the documented one', async () => {
    const { wrapper, vm, list } = await open({ version: { version: '0', limits: { max_rows: 0, max_stations: 100, max_stream_rows: 0 } } })
    await vi.waitFor(() => expect(dates(vm)).toBeDefined())
    await select(wrapper, vm, list.slice(0, 30))
    await new Promise(resolve => setTimeout(resolve, 150))
    // a server that sets no limit sends it all at once
    expect(dates(vm)).toEqual({ startDate: undefined, endDate: undefined })
  })

  it('works the window out again as the selection changes, while the dates are the page\'s', async () => {
    const { wrapper, vm, list } = await open()
    await select(wrapper, vm, list.slice(0, 30))
    await vi.waitFor(() => expect(dates(vm).endDate).toBe(TODAY))
    const first = dates(vm).startDate!
    // twice the stations: half the window
    vm.stationSelectionState.selection.stations = list.slice(0, 30).concat(stations(30).map(s => ({ ...s, station_id: `9${s.station_id}` })))
    await vi.waitFor(() => expect(dates(vm).startDate! > first).toBe(true))
    // fewer, to where the whole record fits: nothing is asked of the stations beyond what they hold
    vm.stationSelectionState.selection.stations = list.slice(0, 2)
    await vi.waitFor(() => expect(dates(vm)).toEqual({ startDate: undefined, endDate: undefined }))
    expect(note(wrapper)).toBe('')
  })

  it('never writes over dates the user typed', async () => {
    const { wrapper, vm, list } = await open()
    await select(wrapper, vm, list.slice(0, 30))
    await vi.waitFor(() => expect(dates(vm).endDate).toBe(TODAY))
    await typeDate(wrapper, 0, '2001-05-01')
    expect(dates(vm).startDate).toBe('2001-05-01')
    expect(note(wrapper)).toBe('')
    // another selection, which would move the page's window
    vm.stationSelectionState.selection.stations = list.slice(0, 10)
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 150))
    expect(dates(vm)).toEqual({ startDate: '2001-05-01', endDate: TODAY })
    await vi.waitFor(() => expect(query().startDate).toBe('2001-05-01'))
  })

  it('keeps a range the user cleared cleared, in the link and through another selection', async () => {
    const { wrapper, vm, list } = await open()
    await select(wrapper, vm, list.slice(0, 30))
    await vi.waitFor(() => expect(dates(vm).endDate).toBe(TODAY))
    await wrapper.find('[data-testid="clear-date-range"]').trigger('click')
    expect(dates(vm)).toEqual({ startDate: undefined, endDate: undefined })
    expect(note(wrapper)).toBe('')
    await vi.waitFor(() => expect(query().range).toBe('all'))
    expect(query().startDate).toBeUndefined()
    vm.stationSelectionState.selection.stations = list.slice(0, 20)
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 150))
    expect(dates(vm)).toEqual({ startDate: undefined, endDate: undefined })
    // the clear button is of a range that is there to clear
    expect(wrapper.find('[data-testid="clear-date-range"]').exists()).toBe(false)
  })

  it('reads a range emptied by hand as cleared, too', async () => {
    const { wrapper, vm, list } = await open()
    await select(wrapper, vm, list.slice(0, 30))
    await vi.waitFor(() => expect(dates(vm).endDate).toBe(TODAY))
    await typeDate(wrapper, 0, '')
    await typeDate(wrapper, 1, '')
    await vi.waitFor(() => expect(query().range).toBe('all'))
    vm.stationSelectionState.selection.stations = list.slice(0, 20)
    await new Promise(resolve => setTimeout(resolve, 150))
    expect(dates(vm)).toEqual({ startDate: undefined, endDate: undefined })
  })

  it('starts over with another dataset: the choice was for the old one', async () => {
    const { wrapper, vm, list } = await open()
    await select(wrapper, vm, list.slice(0, 30))
    await vi.waitFor(() => expect(dates(vm).endDate).toBe(TODAY))
    await wrapper.find('[data-testid="clear-date-range"]').trigger('click')
    vm.parameterSelectionState.selection.resolution = 'hourly'
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(vm.rangeCleared).toBe(false)
    expect(vm.rangeEdited).toBe(false)
  })

  describe('in a link', () => {
    const LINK = 'provider=dwd&network=observation&resolution=daily&dataset=climate_summary&parameters=temperature_air_max_2m&mode=station'
    const IDS = (count: number) => stations(count).map(s => s.station_id).join(',')

    it('takes the page\'s window for a link that names none', async () => {
      const { vm } = await open({ route: `/explorer?${LINK}&stations=${IDS(30)}` })
      await vi.waitFor(() => expect(dates(vm).endDate).toBe(TODAY), { timeout: 5000 })
    })

    it('keeps the dates a link names, whatever the stations hold', async () => {
      const { vm, wrapper } = await open({ route: `/explorer?${LINK}&stations=${IDS(30)}&startDate=2010-01-01&endDate=2010-12-31` })
      await vi.waitFor(() => expect(vm.stationSelectionState.selection.stations.length).toBe(30), { timeout: 5000 })
      await new Promise(resolve => setTimeout(resolve, 150))
      expect(dates(vm)).toEqual({ startDate: '2010-01-01', endDate: '2010-12-31' })
      expect(note(wrapper)).toBe('')
    })

    it('asks for everything for a link that says range=all', async () => {
      const { vm } = await open({ route: `/explorer?${LINK}&stations=${IDS(30)}&range=all` })
      await vi.waitFor(() => expect(vm.stationSelectionState.selection.stations.length).toBe(30), { timeout: 5000 })
      await new Promise(resolve => setTimeout(resolve, 150))
      expect(dates(vm)).toEqual({ startDate: undefined, endDate: undefined })
      expect(query().range).toBe('all')
    })
  })

  describe('where the server refuses the request anyway', () => {
    const REFUSAL = {
      type: 'urn:wetterdienst:problem:limit-exceeded',
      title: 'Bad Request',
      status: 400,
      detail: 'English',
      limit: 'rows',
      maximum: 500_000,
      requested: 1_500_000,
    }

    it('shows the notice, applies its window as an edit of the user and asks again with it', async () => {
      const asked: (string | undefined)[] = []
      const { wrapper, vm, list } = await open({
        values: (event) => {
          const timestamp = getQuery(event).timestamp as string | undefined
          asked.push(timestamp)
          if (timestamp) {
            return { values: [{ station_id: '00001', resolution: 'daily', dataset: 'climate_summary', parameter: 'temperature_air_max_2m', timestamp: '2020-01-01T00:00:00Z', value: 1.5, quality_flags: null }] }
          }
          setResponseStatus(event, 400)
          return REFUSAL
        },
      })
      await select(wrapper, vm, list.slice(0, 30))
      await vi.waitFor(() => expect(dates(vm).endDate).toBe(TODAY))
      // asking for everything is the user's choice, and is then refused
      await wrapper.find('[data-testid="clear-date-range"]').trigger('click')
      await vi.waitFor(() => expect(vm.canFetch).toBe(true))
      await wrapper.findAll('button').find(b => b.text() === 'Show')!.trigger('click')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="limit-notice"]').exists()).toBe(true))
      expect(asked).toEqual([undefined])
      await wrapper.find('[data-testid="limit-apply"]').trigger('click')
      // the fields and the link hold the window, and the values are asked for with it
      await vi.waitFor(() => expect(dates(vm).endDate).toBe(TODAY))
      expect(vm.rangeEdited).toBe(true)
      await vi.waitFor(() => expect(asked).toHaveLength(2))
      expect(asked[1]).toBe(`${dates(vm).startDate}/${TODAY}`)
      await vi.waitFor(() => expect(wrapper.find('[data-testid="limit-notice"]').exists()).toBe(false))
      await vi.waitFor(() => expect(query().startDate).toBe(dates(vm).startDate))
      expect(query().range).toBeUndefined()
      // theirs now: no note, and another selection does not move it
      expect(note(wrapper)).toBe('')
    })
  })
})
