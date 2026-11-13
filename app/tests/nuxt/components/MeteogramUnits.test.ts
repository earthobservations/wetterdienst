import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useRouter } from '#imports'
import Meteogram from '~/components/Meteogram.vue'

// The forecast in the units the app settings choose (GH-3980): the numbers come in them, the labels say the unit the answer
// reports for each parameter, and what the code judges (rain or snow, the weather of a day, the wind barbs, the freezing
// point) is judged in canonical units, so the same weather is the same in every unit.

// ECharts draws in these tests as it does in a browser, to an SVG string, and every call is recorded
// (`tests/helpers/ssr-echarts.ts`)
const echarts = vi.hoisted(() => ({ ssr: null as any }))
vi.mock('~/utils/echarts-loader', async () => {
  const { createSsrEcharts } = await import('../../helpers/ssr-echarts')
  echarts.ssr = createSsrEcharts()
  return { loadEcharts: () => echarts.ssr }
})
const ssr = () => echarts.ssr as ReturnType<typeof import('../../helpers/ssr-echarts').createSsrEcharts>
const clearDrawn = () => echarts.ssr?.clear()
async function waitDrawn() {
  await vi.waitFor(() => expect(ssr().calls.setOption).toHaveBeenCalled(), { timeout: 5000 })
  await flushPromises()
}
/** The series of the last drawing by id */
const seriesOf = (id: string) => ssr().option().series.find((series: { id: string }) => series.id === id)
/** The sum of what the stacks of a kind of precipitation hold */
const total = (id: string) => seriesOf(id).data.reduce((sum: number, point: [number, number | null]) => sum + (point[1] ?? 0), 0)

// the units, as the metadata of an answer states them: the same weather in each
interface Units { temperature: string, speed: string, pressure: string, fraction: string, angle: string, precipitation: string }
const METRIC: Units = { temperature: '°C', speed: 'm/s', pressure: 'hPa', fraction: '%', angle: '°', precipitation: 'mm' }
const IMPERIAL: Units = { temperature: '°F', speed: 'km/h', pressure: 'kPa', fraction: '-', angle: 'rad', precipitation: 'l/m²' }
const ODD: Units = { temperature: 'K', speed: 'bft', pressure: 'Pa', fraction: '1/8', angle: 'grad', precipitation: 'mm' }

// written independently of app/utils/units.ts, from the backend's own conversions
const WRITE = {
  temperature: { '°C': (c: number) => c, '°F': (c: number) => c * 1.8 + 32, 'K': (c: number) => c + 273.15 },
  speed: { 'm/s': (v: number) => v, 'km/h': (v: number) => v * 3.6, 'bft': (v: number) => (v / 0.836) ** (2 / 3) },
  pressure: { hPa: (v: number) => v, kPa: (v: number) => v / 10, Pa: (v: number) => v * 100 },
  fraction: { '%': (v: number) => v, '-': (v: number) => v / 100, '1/8': (v: number) => v / 12.5 },
  angle: { '°': (v: number) => v, 'rad': (v: number) => v * Math.PI / 180, 'grad': (v: number) => v / 0.9 },
  precipitation: { 'mm': (v: number) => v, 'l/m²': (v: number) => v },
} as const

const PARAMETER = {
  temperature: 'temperature_air_2m',
  speed: 'wind_speed',
  pressure: 'pressure_air_sea_level',
  fraction: 'cloud_cover_total',
  angle: 'wind_direction',
  precipitation: 'precipitation_amount_significant_weather_last_1h',
} as const

/** Three days of hourly values of one weather, written in `units`: it rains a quarter of a millimetre an hour */
function forecast(units: Units, temperature: (hour: number) => number = hour => 10 + (hour % 24) / 4) {
  const canonical: Record<keyof Units, (hour: number) => number> = {
    temperature,
    speed: () => 6,
    pressure: () => 1013.25,
    fraction: () => 50,
    angle: () => 270,
    precipitation: () => 0.25,
  }
  return (Object.keys(PARAMETER) as (keyof Units)[]).flatMap(quantity => Array.from({ length: 72 }, (_, hour) => ({
    station_id: '10384',
    resolution: 'hourly',
    dataset: 'large',
    parameter: PARAMETER[quantity],
    timestamp: new Date(Date.UTC(2026, 9, 1 + Math.floor(hour / 24), hour % 24)).toISOString(),
    value: (WRITE[quantity] as Record<string, (v: number) => number>)[units[quantity]]!(canonical[quantity](hour)),
    quality_flags: null,
  })))
}
const unitsOf = (units: Units) => Object.fromEntries((Object.keys(PARAMETER) as (keyof Units)[]).map(quantity => [PARAMETER[quantity], units[quantity]]))

const mounted: Array<{ unmount: () => void }> = []
async function mountMeteogram(props: Record<string, unknown> & { values: unknown[] }) {
  const wrapper = await mountSuspended(Meteogram, {
    props: { stationName: 'Berlin', stationCoords: { latitude: 52.47, longitude: 13.4 }, ...props } as never,
    attachTo: document.body,
    route: '/',
  })
  mounted.push(wrapper)
  return wrapper
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-01T10:00:00Z') })
  clearDrawn()
})
afterEach(async () => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  vi.restoreAllMocks()
  vi.useRealTimers()
  document.body.innerHTML = ''
  await useRouter().replace({ query: {} })
})

describe('the day rows in each unit', () => {
  const rows = (wrapper: Awaited<ReturnType<typeof mountMeteogram>>) => wrapper.findAll('[data-testid="day-rows"] li')

  it.each([
    ['rain', (hour: number) => 10 + (hour % 24) / 4],
    // below freezing at the coldest hour and 6 mm of precipitation: snow, at -3 degrees Celsius, 26.6 Fahrenheit, 270.15 Kelvin
    ['snow', (hour: number) => -3 + (hour % 24) / 24],
  ])('give a day of %s the same weather in degrees Celsius, Fahrenheit and Kelvin, and the temperatures in the unit', async (kind, temperature) => {
    const seen: string[][] = []
    for (const units of [METRIC, IMPERIAL, ODD]) {
      const wrapper = await mountMeteogram({ values: forecast(units, temperature), units: unitsOf(units), widget: true, daysOnly: true })
      seen.push(rows(wrapper).map(row => row.find('[data-weather]').attributes('data-weather')!))
      const label = rows(wrapper)[0]!.find('.font-bold.tabular-nums').text()
      // the minimum and the maximum of the day, rounded, with the unit of the answer
      expect(label).toMatch(units.temperature === 'K' ? / K$/ : units.temperature === '°F' ? /°F$/ : /°C$/)
      // the 22 hours of the first day at the station, a quarter of a millimetre each, in the unit of the answer
      expect(rows(wrapper)[0]!.text()).toContain(`5.5 ${units.precipitation}`)
      wrapper.unmount()
      mounted.pop()
    }
    expect(seen[1]).toEqual(seen[0])
    expect(seen[2]).toEqual(seen[0])
    expect(seen[0]![0]).toBe(kind)
  })

  it('writes the temperatures of a day as the answer gives them', async () => {
    const wrapper = await mountMeteogram({ values: forecast(IMPERIAL), units: unitsOf(IMPERIAL), widget: true, daysOnly: true })
    // 10 to 15.25 degrees Celsius, the first day's hours at the station, is 50 to 59.45 Fahrenheit
    expect(rows(wrapper)[0]!.text()).toContain('50 / 59°F')
  })
})

describe('the chart in each unit', () => {
  async function draw(units: Units, temperature?: (hour: number) => number) {
    const wrapper = await mountMeteogram({ values: [], units: unitsOf(units) })
    await wrapper.setProps({ values: forecast(units, temperature) })
    await waitDrawn()
    return { wrapper, option: ssr().option() }
  }
  // the axes of the panels in the order of the chart: the days above, then the wind, the precipitation, the clouds, the temperature and the pressure
  const AXES = { wind: 1, precip: 2, cloud: 3, temp: 4, pressure: 5 }

  it('titles the axes with the unit the answer reports, and the readout of an hour writes the values in it', async () => {
    const { option } = await draw(IMPERIAL)
    // a title too long for its panel is broken in two lines
    const title = (panel: keyof typeof AXES) => option.yAxis[AXES[panel]].name.replace('\n', ' ')
    expect(title('temp')).toBe('Temp °F')
    expect(title('wind')).toBe('Wind km/h')
    expect(title('precip')).toBe('Precip l/m²')
    expect(title('pressure')).toBe('Pressure kPa')
    // a fraction as a decimal is named by what it ranges over
    expect(title('cloud')).toBe('Cloud 0–1')
    document.body.querySelector('[role="figure"]')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(document.body.querySelector('[data-testid="meteogram-readout"]')).not.toBeNull())
    const readout = document.body.querySelector('[data-testid="meteogram-readout"]')!.textContent!
    for (const unit of ['°F', 'km/h', 'kPa', 'rad'])
      expect(readout, unit).toContain(unit)
    expect(readout).not.toMatch(/°C|m\/s|hPa|\bmm\b/)
  })

  it('draws the cloud cover over the whole of its scale, whichever it is written in', async () => {
    expect((await draw(METRIC)).option.yAxis[AXES.cloud].max).toBe(100)
    clearDrawn()
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    expect((await draw(IMPERIAL)).option.yAxis[AXES.cloud].max).toBeCloseTo(1, 9)
    clearDrawn()
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    expect((await draw(ODD)).option.yAxis[AXES.cloud].max).toBeCloseTo(8, 9)
  })

  it('draws the freezing point as a line of its own in the unit of the answer, and the axis holds it', async () => {
    const freezing = () => seriesOf('backdrop-temp').data.filter((row: number[]) => row[0] === 3).map((row: number[]) => row[2])
    const celsius = (await draw(METRIC)).option
    expect(freezing()).toEqual([0])
    expect(celsius.yAxis[AXES.temp].min).toBeLessThan(0)
    clearDrawn()
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    const fahrenheit = (await draw(IMPERIAL)).option
    expect(freezing()).toEqual([32])
    // the axis holds the freezing point and reaches a degree below it: 1.8 Fahrenheit
    expect(fahrenheit.yAxis[AXES.temp].min).toBeCloseTo(32 - 1.8, 9)
    clearDrawn()
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    const kelvin = (await draw(ODD)).option
    expect(freezing()).toEqual([273.15])
    expect(kelvin.yAxis[AXES.temp].min).toBeCloseTo(273.15 - 1, 9)
  })

  it('draws a cold day under the freezing point as such in any unit, and the rain on it as snow', async () => {
    const cold = (hour: number) => -3 + (hour % 24) / 24
    const snow = async (units: Units) => {
      clearDrawn()
      mounted.splice(0).forEach(wrapper => wrapper.unmount())
      await draw(units, cold)
      return ['rain', 'mixed', 'snow'].map(total)
    }
    const metric = await snow(METRIC)
    expect(metric[2]).toBeGreaterThan(0)
    expect(metric.slice(0, 2)).toEqual([0, 0])
    expect(await snow(IMPERIAL)).toEqual(metric)
    expect(await snow(ODD)).toEqual(metric)
  })
})

describe('the table and the sentences in each unit', () => {
  it('say the unit of each series the answer reports', async () => {
    const wrapper = await mountMeteogram({ values: forecast(ODD), units: unitsOf(ODD) })
    await vi.waitFor(() => expect(wrapper.find('[role="radiogroup"]').exists()).toBe(true))
    await wrapper.findAll('[role="radio"]').find(radio => radio.text() === 'Table')!.trigger('click')
    await vi.waitFor(() => expect(wrapper.find('table').exists()).toBe(true))
    expect(wrapper.findAll('thead th').map(th => th.text())).toEqual([
      'Time (Europe/Berlin)',
      'Temperature K',
      'Wind bft',
      'Direction grad',
      'Precipitation mm',
      'Total Cloud Cover 1/8',
      'Pressure Pa',
    ])
  })

  it('say the temperatures of the sentence that describes the figure in the unit, from 10 to 15.75 degrees Celsius', async () => {
    const wrapper = await mountMeteogram({ values: forecast(ODD), units: unitsOf(ODD) })
    await vi.waitFor(() => expect(wrapper.find('[role="figure"]').exists()).toBe(true))
    const sentence = document.getElementById(wrapper.find('[role="figure"]').attributes('aria-describedby')!.split(' ')[0]!)!.textContent!
    const [, min, max] = /Temperature from ([\d.]+) to ([\d.]+) K\./.exec(sentence)!
    expect(Number(min)).toBeCloseTo(283.15, 0)
    expect(Number(max)).toBeCloseTo(288.9, 0)
    expect(sentence).not.toContain('°C')
  })

  it('write the summary of the chart in the units, with no unit that is not the answer\'s', async () => {
    const wrapper = await mountMeteogram({ values: forecast(IMPERIAL), units: unitsOf(IMPERIAL) })
    await vi.waitFor(() => expect(wrapper.text()).toContain('°F'))
    const text = wrapper.text()
    expect(text).toContain('50°')
    expect(text).toContain('km/h')
    expect(text).toContain('kPa')
    expect(text).not.toMatch(/°C|hPa|m\/s/)
  })

  it('write a cloud cover that is a decimal with nothing after it in the summary, as everywhere a number has its unit', async () => {
    const wrapper = await mountMeteogram({ values: forecast(IMPERIAL), units: unitsOf(IMPERIAL) })
    await vi.waitFor(() => expect(wrapper.find('[data-summary-icon="cloud"]').exists()).toBe(true))
    const share = wrapper.find('[data-summary-icon="cloud"]').element.parentElement!
    // 50 percent, as a decimal
    expect(share.textContent!.trim()).toBe('0.50')
  })

  it('read an answer that states no unit as the canonical units, as the app has always drawn it', async () => {
    const wrapper = await mountMeteogram({ values: forecast(METRIC) })
    await vi.waitFor(() => expect(wrapper.text()).toContain('°C'))
    expect(wrapper.text()).toContain('hPa')
  })
})

describe('the wind barbs in each unit', () => {
  // the barbs as the chart is given them: where the wind comes from in degrees, and the knots of its speed. A barb is a drawing
  // of the wind, so it is the same in every unit of speed and of direction
  async function barbsIn(units: Units) {
    clearDrawn()
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    const wrapper = await mountMeteogram({ values: [], units: unitsOf(units) })
    await wrapper.setProps({ values: forecast(units) })
    await waitDrawn()
    return seriesOf('barbs').data as [number, number, number, number][]
  }

  it('are from the west for a wind from 270 degrees, written in degrees, radians or gradians, and in any unit of speed', async () => {
    for (const units of [METRIC, IMPERIAL, ODD]) {
      const barbs = await barbsIn(units)
      expect(barbs.length, units.angle).toBeGreaterThan(0)
      // a direction taken for degrees would be 4.71 or 300
      for (const barb of barbs)
        expect(barb[2], units.angle).toBeCloseTo(270, 4)
    }
  })

  it('has the barb the force of the speed in knots, whatever unit it is in: 6 m/s is one full barb', async () => {
    const metric = await barbsIn(METRIC)
    expect(metric[0]![3]).toBeCloseTo(11.66, 2)
    for (const units of [IMPERIAL, ODD]) {
      const barbs = await barbsIn(units)
      expect(barbs[0]![3], units.speed).toBeCloseTo(metric[0]![3], 2)
    }
  })
})

// The dew point worked out from the humidity, where an answer has none of its own (a network that gives the humidity and not the
// dew point), and the wet bulb that tells rain from snow, are worked out in degrees Celsius and percent
describe('the dew point and the precipitation type from the humidity in each unit', () => {
  const HUMIDITY = { '%': (v: number) => v, '-': (v: number) => v / 100, '1/8': (v: number) => v / 12.5 } as const
  function humid(units: Units, celsius: (hour: number) => number) {
    return [
      ...forecast(units, celsius).filter(row => row.parameter !== PARAMETER.fraction),
      ...Array.from({ length: 72 }, (_, hour) => ({
        station_id: '10384',
        resolution: 'hourly',
        dataset: 'large',
        parameter: 'humidity_relative',
        timestamp: new Date(Date.UTC(2026, 9, 1 + Math.floor(hour / 24), hour % 24)).toISOString(),
        value: HUMIDITY[units.fraction as keyof typeof HUMIDITY](80),
        quality_flags: null,
      })),
    ]
  }
  async function draw(units: Units, celsius: (hour: number) => number) {
    clearDrawn()
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    const wrapper = await mountMeteogram({ values: [], units: { ...unitsOf(units), humidity_relative: units.fraction } })
    await wrapper.setProps({ values: humid(units, celsius) })
    await waitDrawn()
  }

  it('draws the same dew point, in the unit of the temperature, whichever the units of the temperature and the humidity', async () => {
    const warm = (hour: number) => 10 + (hour % 24) / 4
    const dew = async (units: Units) => {
      await draw(units, warm)
      return seriesOf('dew').data.map((point: [number, number]) => point[1])
    }
    const metric = await dew(METRIC)
    expect(metric.length).toBeGreaterThan(0)
    // 80 percent at 10 degrees Celsius: the dew point is a few degrees under the temperature
    expect(metric[0]!).toBeGreaterThan(5)
    expect(metric[0]!).toBeLessThan(10)
    const fahrenheit = await dew(IMPERIAL)
    const kelvin = await dew(ODD)
    metric.forEach((value: number, i: number) => {
      expect(fahrenheit[i]!).toBeCloseTo(value * 1.8 + 32, 5)
      expect(kelvin[i]!).toBeCloseTo(value + 273.15, 5)
    })
  })

  it('tells snow from rain by the wet bulb in any unit', async () => {
    const cold = (hour: number) => -3 + (hour % 24) / 24
    const amounts = async (units: Units) => {
      await draw(units, cold)
      return ['rain', 'mixed', 'snow'].map(total)
    }
    const metric = await amounts(METRIC)
    expect(metric[2]).toBeGreaterThan(0)
    expect(await amounts(IMPERIAL)).toEqual(metric)
    expect(await amounts(ODD)).toEqual(metric)
  })
})
