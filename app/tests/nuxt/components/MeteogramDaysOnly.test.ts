import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useRouter } from '#imports'
import Meteogram from '~/components/Meteogram.vue'

// The day rows of the map's panel (GH-3650): the meteogram with no chart, no controls, and nothing remembered or
// written to the address.

// the chart's code, which these rows never ask for: its loader is a spy
const echarts = vi.hoisted(() => ({ loadEcharts: vi.fn(() => ({ init: vi.fn() })) }))
vi.mock('~/utils/echarts-loader', () => echarts)

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

beforeEach(() => {
  // the first of October, as the values start on it: the rows start at today, which is a day of the run
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-01T10:00:00Z') })
  echarts.loadEcharts.mockClear()
})
afterEach(async () => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  vi.useRealTimers()
  await useRouter().replace({ query: {} })
})

describe('the meteogram as day rows (days-only)', () => {
  it('is a list of days, each with its temperatures, and no chart, no view choice and no chart code', async () => {
    const wrapper = await mountRows()
    const rows = wrapper.findAll('[data-testid="day-rows"] li')
    expect(rows.length).toBeGreaterThanOrEqual(3)
    expect(rows[0]!.text()).toMatch(/\d+ \/ \d+/)
    expect(wrapper.find('[role="figure"]').exists()).toBe(false)
    expect(wrapper.find('[role="radiogroup"]').exists()).toBe(false)
    await vi.waitFor(() => expect(echarts.loadEcharts).not.toHaveBeenCalled())
  })

  // the weather of a row is Yr's symbol, as the chart draws an hour's, hidden from a screen reader, with its words beside it (GH-4193)
  it('draws the weather of each row as a symbol that is hidden, and says it in words', async () => {
    const wrapper = await mountRows()
    const rows = wrapper.findAll('[data-testid="day-rows"] li')
    for (const row of rows) {
      const symbol = row.find('img[data-weather]')
      expect(symbol.exists()).toBe(true)
      expect(symbol.attributes('aria-hidden')).toBe('true')
      expect(symbol.attributes('alt')).toBe('')
      expect(symbol.attributes('src')).toMatch(/^\/yr-symbols\/lightmode\/[0-9a-z]+\.svg$/)
      expect(row.find('.sr-only').text()).not.toBe('')
      expect(row.text()).not.toMatch(/\p{Extended_Pictographic}/u)
    }
  })

  // the chart that carries Yr's credit (CC BY 4.0) is not here: the rows do (GH-4193)
  it('credits Yr under the rows, once, where there is no chart to carry it', async () => {
    const wrapper = await mountRows()
    const credit = wrapper.findAll('[data-testid="day-symbols-credit"]')
    expect(credit).toHaveLength(1)
    expect(credit[0]!.text()).toBe('Weather symbols © 2015 Yr/NRK, CC BY 4.0.')
    expect(credit[0]!.findAll('a').map(a => a.attributes('href'))).toEqual([
      'https://github.com/nrkno/yr-weather-symbols',
      'https://creativecommons.org/licenses/by/4.0/',
    ])
    expect(wrapper.find('[data-testid="meteogram-credit"]').exists()).toBe(false)
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

  it('marks the last day, which the run ends in, as partial with the hours it has, and not the first, of which it has 22 hours (GH-4175)', async () => {
    // at Berlin the run starts at 02:00 on the 1st, the first 22 hours of the day being all it has of it (the first hour after the
    // run's issue is the run's first): a day of 20 hours or more is not marked. It ends at 01:00 on the 4th: the hours 00:00 and 01:00
    // of a day of their own
    const wrapper = await mountRows()
    const rows = wrapper.findAll('[data-testid="day-rows"] li')
    expect(rows[0]!.text()).toContain('01/10')
    expect(rows[0]!.find('[data-testid="partial-day"]').exists()).toBe(false)
    const last = rows[rows.length - 1]!
    expect(last.text()).toContain('04/10')
    expect(last.find('[data-testid="partial-day"]').text()).toBe('partial, 2 h')
    expect(wrapper.findAll('[data-testid="partial-day"]')).toHaveLength(1)
  })

  it('marks a first day the run has fewer than 20 hours of, with them', async () => {
    // from 10:00 UTC, 12:00 at Berlin: 12 hours of the day
    const late = values.filter(value => new Date(value.timestamp).getUTCHours() >= 10 || new Date(value.timestamp).getUTCDate() > 1)
    const wrapper = await mountRows({ values: late })
    const first = wrapper.findAll('[data-testid="day-rows"] li')[0]!
    expect(first.find('[data-testid="partial-day"]').text()).toBe('partial, 12 h')
  })

  it('marks a last day of six hours as partial for six hours, and a day of its own that ends at 23:00 as whole', async () => {
    const six = values.slice(0, 48 + 6)
    const partial = await mountRows({ values: six, stationCoords: null })
    expect(partial.find('[data-testid="partial-day"]').text()).toBe('partial, 6 h')
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    const whole = await mountRows({ values: values.slice(0, 48), stationCoords: null })
    expect(whole.find('[data-testid="partial-day"]').exists()).toBe(false)
  })

  it('lists every day of a long run, with no cap (GH-4127)', async () => {
    // ten whole days of hourly values, the length of a MOSMIX-L run: ten rows, none partial
    const long = Array.from({ length: 10 * 24 }, (_, hour) => ({ ...values[0]!, timestamp: new Date(Date.UTC(2026, 9, 1, hour)).toISOString() }))
    const wrapper = await mountRows({ values: long, stationCoords: null })
    expect(wrapper.findAll('[data-testid="day-rows"] li')).toHaveLength(10)
    expect(wrapper.findAll('[data-testid="partial-day"]')).toHaveLength(0)
  })

  it('lists an eleventh day that the run only starts, and marks it as partial', async () => {
    const long = Array.from({ length: 10 * 24 + 6 }, (_, hour) => ({ ...values[0]!, timestamp: new Date(Date.UTC(2026, 9, 1, hour)).toISOString() }))
    const wrapper = await mountRows({ values: long, stationCoords: null })
    expect(wrapper.findAll('[data-testid="day-rows"] li')).toHaveLength(11)
    expect(wrapper.findAll('[data-testid="partial-day"]')).toHaveLength(1)
  })

  // hourly values from the 1st of October 00:00 UTC for `hours` hours: MOSMIX-L is hourly to its last step, there is no coarser end to a run
  const run = (hours: number) => Array.from({ length: hours }, (_, hour) => Date.UTC(2026, 9, 1, hour))
    .map(time => ({ ...values[0]!, timestamp: new Date(time).toISOString() }))

  it('counts the hours of the last day by the hourly steps of the run, in a run of more than 120 hours', async () => {
    // hourly to the 6th 05:00: six hours of the last day (GH-4176: it was counted by a 3-hourly step that no run has)
    const wrapper = await mountRows({ values: run(5 * 24 + 6), stationCoords: null })
    expect(wrapper.findAll('[data-testid="day-rows"] li')).toHaveLength(6)
    expect(wrapper.find('[data-testid="partial-day"]').text()).toBe('partial, 6 h')
  })

  it('marks a last day that an hourly run of more than 120 hours ends at 18:00, which has fewer than 20 hours', async () => {
    const wrapper = await mountRows({ values: run(5 * 24 + 19), stationCoords: null })
    expect(wrapper.find('[data-testid="partial-day"]').text()).toBe('partial, 19 h')
    // and one of 22 hours, which is 20 or more, is not marked
    mounted.splice(0).forEach(w => w.unmount())
    const nearly = await mountRows({ values: run(5 * 24 + 22), stationCoords: null })
    expect(nearly.find('[data-testid="partial-day"]').exists()).toBe(false)
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
