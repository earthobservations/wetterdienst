import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useRouter } from '#imports'
import Meteogram from '~/components/Meteogram.vue'

// The day rows of the map's panel (GH-3650): the meteogram with no chart, no controls, and nothing remembered or
// written to the address.

const plotly = vi.hoisted(() => ({
  newPlot: vi.fn(async () => {}),
  relayout: vi.fn(async () => {}),
  purge: vi.fn(),
}))
vi.mock('plotly.js-basic-dist-min', () => plotly)

// three days of hourly temperatures
const values = Array.from({ length: 72 }, (_, hour) => ({
  station_id: '10384',
  resolution: 'hourly',
  dataset: 'large',
  parameter: 'temperature_air_2m',
  timestamp: new Date(Date.UTC(2026, 9, 1 + Math.floor(hour / 24), hour % 24)).toISOString(),
  value: 10 + (hour % 24) / 4,
  quality_flags: null,
}))

const mounted: Array<{ unmount: () => void }> = []
async function mountRows(props: Record<string, unknown> = {}, route = '/') {
  const wrapper = await mountSuspended(Meteogram, {
    props: { values, stationName: 'Berlin', stationCoords: { latitude: 52.47, longitude: 13.4 }, widget: true, daysOnly: true, ...props },
    attachTo: document.body,
    route,
  })
  mounted.push(wrapper)
  return wrapper
}

// Node's own `localStorage` global stands in the test document's way and holds nothing: one that does
beforeEach(() => {
  plotly.newPlot.mockClear()
  const store = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, String(value)),
    removeItem: (key: string) => void store.delete(key),
    clear: () => store.clear(),
  })
})
afterEach(async () => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  vi.unstubAllGlobals()
  await useRouter().replace({ query: {} })
})

describe('the meteogram as day rows (days-only)', () => {
  it('is a list of days, each with its temperatures, and no chart, no view choice and no Plotly', async () => {
    const wrapper = await mountRows()
    const rows = wrapper.findAll('[data-testid="day-rows"] li')
    expect(rows.length).toBeGreaterThanOrEqual(3)
    expect(rows[0]!.text()).toMatch(/\d+ \/ \d+/)
    expect(wrapper.find('[role="figure"]').exists()).toBe(false)
    expect(wrapper.find('[role="radiogroup"]').exists()).toBe(false)
    await vi.waitFor(() => expect(plotly.newPlot).not.toHaveBeenCalled())
  })

  it('is not taken to the chart by the view the reader chose on the forecast page, which is kept in the browser', async () => {
    localStorage.setItem('meteogram.view', 'chart')
    const wrapper = await mountRows()
    await vi.waitFor(() => expect(wrapper.find('[data-testid="day-rows"]').exists()).toBe(true))
    // let a restore that would run on mount have run
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(wrapper.find('[data-testid="day-rows"]').exists()).toBe(true)
    expect(wrapper.find('[role="figure"]').exists()).toBe(false)
  })

  it('is not taken to another view by the address of the page it is in, and does not write its own to it', async () => {
    const wrapper = await mountRows({ widget: false }, '/meteogram?view=table&horizon=24&panels=wind')
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(wrapper.find('[data-testid="day-rows"]').exists()).toBe(true)
    // the address is the page's: nothing is added to it or taken from it
    expect(useRouter().currentRoute.value.query).toEqual({ view: 'table', horizon: '24', panels: 'wind' })
    await wrapper.setProps({ values: values.slice(0, 48) })
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(useRouter().currentRoute.value.query).toEqual({ view: 'table', horizon: '24', panels: 'wind' })
  })

  it('remembers nothing in the browser: the view the forecast page keeps is left as it was', async () => {
    localStorage.setItem('meteogram.view', 'table')
    const wrapper = await mountRows()
    await wrapper.setProps({ values: values.slice(0, 48) })
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(localStorage.getItem('meteogram.view')).toBe('table')
    expect(localStorage.getItem('meteogram.compact')).toBeNull()
  })
})
