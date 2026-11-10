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
  // the first of October, as the values start on it: the rows start at today, which is a day of the run
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-01T10:00:00Z') })
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
  vi.useRealTimers()
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

// The day rows start at today and mark a last day the run does not reach the end of (GH-3840). The values are those
// above: hourly from the 1st of October 00:00 UTC to the 3rd 23:00 UTC, at Berlin (UTC+2 in October)
describe('the days the rows list', () => {
  const rowsOf = (wrapper: Awaited<ReturnType<typeof mountRows>>) => wrapper.findAll('[data-testid="day-rows"] li').map(row => row.text())

  it('starts at today, and lists no day before it', async () => {
    vi.setSystemTime(new Date('2026-10-02T09:00:00Z'))
    const rows = rowsOf(await mountRows())
    expect(rows[0]).toContain('TODAY')
    expect(rows[0]).toContain('02/10')
    expect(rows.some(row => row.includes('01/10'))).toBe(false)
    expect(rows).toHaveLength(3)
  })

  it('takes today in the time zone of the station, where it is already the next day by the clock of UTC', async () => {
    // 22:30 UTC on the 1st is 00:30 on the 2nd at Berlin: the 1st is yesterday there, and a stub of it must not be listed
    vi.setSystemTime(new Date('2026-10-01T22:30:00Z'))
    const rows = rowsOf(await mountRows())
    expect(rows[0]).toContain('TODAY')
    expect(rows[0]).toContain('02/10')
    expect(rows.some(row => row.includes('01/10'))).toBe(false)
  })

  it('takes today in the time zone of the station, where it is still the day before by the clock of UTC', async () => {
    // 23:30 UTC on the 1st is 01:30 on the 2nd at Berlin, and at a station in the west (Reykjavik, UTC) still the 1st
    vi.setSystemTime(new Date('2026-10-01T23:30:00Z'))
    const berlin = rowsOf(await mountRows())
    expect(berlin[0]).toContain('02/10')
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    const reykjavik = rowsOf(await mountRows({ stationCoords: { latitude: 64.13, longitude: -21.9 } }))
    expect(reykjavik[0]).toContain('TODAY')
    expect(reykjavik[0]).toContain('01/10')
  })

  it('lists the first day of the run where it is today, whole', async () => {
    const rows = rowsOf(await mountRows({ stationCoords: null }))
    expect(rows).toHaveLength(3)
    expect(rows[0]).toContain('TODAY')
    expect(rows.some(row => /partial/.test(row))).toBe(false)
  })

  it('marks the last day, which the run ends in, as partial with the hours it has', async () => {
    // at Berlin the run ends at 01:00 on the 4th: the hours 00:00 and 01:00 of a day of their own
    const wrapper = await mountRows()
    const rows = wrapper.findAll('[data-testid="day-rows"] li')
    const last = rows[rows.length - 1]!
    expect(last.text()).toContain('04/10')
    expect(last.find('[data-testid="partial-day"]').text()).toBe('partial, 2 h')
    // and only it: the days before are whole
    expect(wrapper.findAll('[data-testid="partial-day"]')).toHaveLength(1)
  })

  it('marks a last day of six hours as partial for six hours, and a day of its own that ends at 23:00 as whole', async () => {
    const six = values.slice(0, 48 + 6)
    const partial = await mountRows({ values: six, stationCoords: null })
    expect(partial.find('[data-testid="partial-day"]').text()).toBe('partial, 6 h')
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    const whole = await mountRows({ values: values.slice(0, 48), stationCoords: null })
    expect(whole.find('[data-testid="partial-day"]').exists()).toBe(false)
  })

  it('does not mark a day that is the last one it lists but not the last of the run', async () => {
    // eight days of hourly values: the rows are cut at seven, and the eighth day, which the run has, is not listed
    const long = Array.from({ length: 8 * 24 - 5 }, (_, hour) => ({ ...values[0]!, timestamp: new Date(Date.UTC(2026, 9, 1, hour)).toISOString() }))
    const wrapper = await mountRows({ values: long, stationCoords: null })
    expect(wrapper.findAll('[data-testid="day-rows"] li')).toHaveLength(7)
    expect(wrapper.findAll('[data-testid="partial-day"]')).toHaveLength(0)
  })

  // hourly values from the 1st of October 00:00 UTC for `hours` hours, then 3-hourly ones for `coarse` more
  const run = (hours: number, coarse = 0) => [
    ...Array.from({ length: hours }, (_, hour) => Date.UTC(2026, 9, 1, hour)),
    ...Array.from({ length: coarse }, (_, step) => Date.UTC(2026, 9, 1, hours + 3 * (step + 1) - 3)),
  ].map(time => ({ ...values[0]!, timestamp: new Date(time).toISOString() }))

  it('counts the hours of the last day by the step of the run, in a run of more than 120 hours', async () => {
    // hourly to the 6th 05:00: six hours of the last day, where a 3-hourly step would count eight
    const wrapper = await mountRows({ values: run(5 * 24 + 6), stationCoords: null })
    expect(wrapper.findAll('[data-testid="day-rows"] li')).toHaveLength(6)
    expect(wrapper.find('[data-testid="partial-day"]').text()).toBe('partial, 6 h')
  })

  it('marks a last day that an hourly run of more than 120 hours ends at 21:00, which is not whole', async () => {
    const wrapper = await mountRows({ values: run(5 * 24 + 22), stationCoords: null })
    expect(wrapper.find('[data-testid="partial-day"]').text()).toBe('partial, 22 h')
  })

  it('counts the hours of the last day by the 3-hourly step where an hourly run goes on in 3 hours', async () => {
    // hourly for five days, then 3-hourly from the 6th 00:00 to the 7th 09:00: the 7th has 00, 03, 06 and 09
    const wrapper = await mountRows({ values: run(5 * 24, 0).concat(Array.from({ length: 12 }, (_, step) => ({ ...values[0]!, timestamp: new Date(Date.UTC(2026, 9, 6, 3 * step)).toISOString() }))), stationCoords: null })
    expect(wrapper.findAll('[data-testid="day-rows"] li')).toHaveLength(7)
    expect(wrapper.find('[data-testid="partial-day"]').text()).toBe('partial, 12 h')
    // and the same run with its last sample at 21:00 is whole
    mounted.splice(0).forEach(w => w.unmount())
    const whole = await mountRows({ values: run(5 * 24, 0).concat(Array.from({ length: 16 }, (_, step) => ({ ...values[0]!, timestamp: new Date(Date.UTC(2026, 9, 6, 3 * step)).toISOString() }))), stationCoords: null })
    expect(whole.find('[data-testid="partial-day"]').exists()).toBe(false)
  })

  it('says there is no data where every day of the run is before today', async () => {
    vi.setSystemTime(new Date('2026-10-05T09:00:00Z'))
    const wrapper = await mountRows()
    expect(wrapper.findAll('[data-testid="day-rows"] li')).toHaveLength(0)
    expect(wrapper.find('[data-testid="day-rows-empty"]').text()).toBe('No forecast data available.')
  })

  it('moves Today on at the midnight of the station, while the page stays open', async () => {
    // 23:59:30 at Berlin on the 1st
    vi.useRealTimers()
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'], now: new Date('2026-10-01T21:59:30Z') })
    const wrapper = await mountRows()
    const first = () => wrapper.find('[data-testid="day-rows"] li').text()
    expect(first()).toContain('01/10')
    expect(first()).toContain('TODAY')
    // a minute on: it is the 2nd, and the 1st is yesterday
    await vi.advanceTimersByTimeAsync(60_000)
    await wrapper.vm.$nextTick()
    expect(first()).toContain('02/10')
    expect(first()).toContain('TODAY')
    expect(wrapper.text()).not.toContain('01/10')
  })
})
