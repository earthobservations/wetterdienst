import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useRouter } from '#imports'
import Meteogram from '~/components/Meteogram.vue'
import { FORECAST_UNITS } from '../../helpers/meteogram-forecast'
import { PRECIPITATION, run10382Values } from '../../helpers/mosmix-run'

// The days of a MOSMIX-L run whose hourly amount (`RR1c`) is 0.0 from +112 h, which the 6 and 12 hour totals still have rain for: the
// compact view and the map's day rows show it (GH-4175). The run is 10382 (Berlin-Tegel) of 2026-11-17 03 UTC, real.

// the chart's code, which these views never ask for
vi.mock('~/utils/echarts-loader', () => ({ loadEcharts: vi.fn(() => ({ init: vi.fn() })) }))

const BERLIN = { latitude: 52.47, longitude: 13.4 }
const mounted: Array<{ unmount: () => void }> = []

async function mountForecast(props: Record<string, unknown> = {}, values: unknown[] = run10382Values()) {
  const wrapper = await mountSuspended(Meteogram, {
    props: { values, stationName: 'Berlin', stationCoords: BERLIN, units: FORECAST_UNITS, ...props } as never,
    attachTo: document.body,
    route: '/',
  })
  mounted.push(wrapper)
  return wrapper
}

beforeEach(() => {
  // 05:30 at Berlin on the 17th: the run was issued at 03 UTC, and the rows start at today
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-11-17T04:30:00Z') })
})
afterEach(async () => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  vi.useRealTimers()
  document.body.innerHTML = ''
  await useRouter().replace({ query: {} })
})

describe('the compact view of a run with a dry hourly tail', () => {
  async function compact(values?: unknown[]) {
    const wrapper = await mountForecast({}, values)
    ;(wrapper.vm as any).view = 'compact'
    await vi.waitFor(() => expect(useRouter().currentRoute.value.query.view).toBe('compact'))
    await wrapper.vm.$nextTick()
    return wrapper
  }
  const cards = (wrapper: Awaited<ReturnType<typeof compact>>) => wrapper.findAll('[data-testid="compact-days"] > div')
  const rain = (card: ReturnType<ReturnType<typeof cards>['at']>) => card!.find('[data-testid="day-precip"]')

  it('shows rain on days 6 to 10, which the hourly amounts alone showed dry', async () => {
    const hourlyOnly = await compact(run10382Values({ without: [PRECIPITATION.six, PRECIPITATION.twelve, PRECIPITATION.day] }))
    const dryHourly = cards(hourlyOnly)
    // 18th to 27th at Berlin: the cards of the 24th to the 26th have no rain line from the hourly amounts
    expect(dryHourly).toHaveLength(11)
    for (const index of [7, 8, 9])
      expect(rain(dryHourly[index]).text(), `card ${index} from the hourly amounts`).toBe('')
    hourlyOnly.unmount()
    mounted.pop()

    const wrapper = await compact()
    const all = cards(wrapper)
    expect(all).toHaveLength(11)
    // 2026-11-24, 25 and 26: DWD's 12 hour totals of 0.5, 1.2 and 1.1 mm, `≈`, which says the figure is made of totals of more hours than one
    expect([7, 8, 9].map(index => rain(all[index]).text())).toEqual(['Precipitation: ≈0.5 mm, approximately, from 12 h totals', 'Precipitation: ≈1.2 mm, approximately, from 12 h totals', 'Precipitation: ≈1.1 mm, approximately, from 12 h totals'])
    expect(rain(all[7]).attributes('title')).toBe('approximately, from 12 h totals')
    // the first days are the hourly amounts' own, as they were, with no mark
    expect(rain(all[1]).text()).toBe('Precipitation: 6.8 mm')
    expect(rain(all[1]).attributes('title')).toBeUndefined()
    // a day without rain in the totals has none, as before
    expect(rain(all[6]).text()).toBe('')
  })

  it('draws the icon of rain on a late day whose rain is the totals\' (GH-4175)', async () => {
    const wrapper = await compact()
    const icon = (index: number) => cards(wrapper)[index]!.find('[data-weather]').attributes('data-weather')
    // 2026-11-25 and 26 (1.2 and 1.1 mm), where the weather codes say cloudy; the 23rd has none
    expect([icon(8), icon(9), icon(6)]).toEqual(['rain', 'rain', 'cloudy'])
  })

  it('says of the first day, which the run starts in after its midnight, and of the last, which it ends in, how many hours they have', async () => {
    const wrapper = await compact()
    const all = cards(wrapper)
    expect(all[0]!.find('[data-testid="partial-day"]').text()).toBe('partial, 19 h')
    expect(all.at(-1)!.find('[data-testid="partial-day"]').text()).toBe('partial, 12 h')
    expect(wrapper.findAll('[data-testid="partial-day"]')).toHaveLength(2)
  })

  it('is the total of the run in the summary, with the late days in it', async () => {
    const wrapper = await mountForecast()
    // the hourly amounts of the run add up to 23.1 mm; the 6 and 12 hour totals of the days after the fourth have 5.5 mm more
    const summary = wrapper.find('[data-summary-icon="precip"]').element.parentElement!.textContent!
    // the totals end before the run does: the least the forecast says, `≥`
    expect(summary.startsWith('≥')).toBe(true)
    expect(Number.parseFloat(summary.slice(1))).toBeGreaterThan(26)
  })
})

describe('the map\'s day rows of the same run', () => {
  it('has the rain of the late days in the rows, marked as approximate, and the hours of the first and the last day', async () => {
    const wrapper = await mountForecast({ widget: true, daysOnly: true })
    const rows = wrapper.findAll('[data-testid="day-rows"] li')
    expect(rows).toHaveLength(11)
    const late = rows[8]!
    expect(late.text()).toContain('Wed')
    expect(late.find('[data-testid="row-precip"]').text()).toContain('≈1.2 mm')
    expect(late.find('[data-testid="row-precip"]').text()).toContain('approximately, from 12 h totals')
    expect(rows[0]!.find('[data-testid="partial-day"]').text()).toBe('partial, 19 h')
    expect(rows.at(-1)!.find('[data-testid="partial-day"]').text()).toBe('partial, 12 h')
  })
})
