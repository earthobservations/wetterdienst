import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useRouter } from '#imports'
import Meteogram from '~/components/Meteogram.vue'

// The forecast in the units the app settings choose (GH-3980): the numbers come in them, the labels say the unit the answer
// reports for each parameter, and what the code judges (rain or snow, the weather of a day, the wind barbs, the freezing
// point) is judged in canonical units, so the same weather is the same in every unit.

const plotly = vi.hoisted(() => ({
  newPlot: vi.fn(async () => {}),
  relayout: vi.fn(async () => {}),
  purge: vi.fn(),
}))
vi.mock('plotly.js-basic-dist-min', () => plotly)

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
  plotly.newPlot.mockClear()
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
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce(), { timeout: 5000 })
    await flushPromises()
    const [, traces, layout] = plotly.newPlot.mock.calls[0] as unknown as [unknown, { name: string, hovertemplate?: string, y: number[] }[], any]
    return { wrapper, traces, layout }
  }

  it('titles the axes and the traces with the unit the answer reports, in the hover texts as well', async () => {
    const { traces, layout } = await draw(IMPERIAL)
    // a title too long for its panel is broken in two lines
    const title = (axis: string) => layout[axis].title.text.replace('<br>', ' ')
    expect(title('yaxis3')).toBe('Temp °F')
    expect(title('yaxis')).toBe('Wind km/h')
    expect(title('yaxis2')).toBe('Precip l/m²')
    expect(title('yaxis4')).toBe('Pressure kPa')
    // a fraction as a decimal is named by what it ranges over
    expect(title('yaxis5')).toBe('Cloud 0–1')
    const hover = (name: string) => traces.find(trace => trace.name === name)!.hovertemplate
    expect(hover('Temperature °F')).toBe('<b>Temperature</b>: %{y:.1f}°F<extra></extra>')
    expect(hover('Wind km/h')).toBe('<b>Wind</b> %{y:.1f} km/h → %{customdata:.2f}rad<extra></extra>'.replace('rad', ' rad'))
    expect(hover('Pressure kPa')).toBe('<b>Pressure</b><br>%{y:.2f} kPa<extra></extra>')
    expect(hover('Total Cloud Cover 0–1')).toBe('<b>Total Cloud Cover</b><br>%{y:.2f}<extra></extra>')
    expect(traces.map(trace => trace.name).join('|')).not.toMatch(/°C|m\/s|hPa|mm\b/)
  })

  it('draws the cloud cover over the whole of its scale, whichever it is written in', async () => {
    expect((await draw(METRIC)).layout.yaxis5.range).toEqual([0, 100])
    plotly.newPlot.mockClear()
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    expect((await draw(IMPERIAL)).layout.yaxis5.range[1]).toBeCloseTo(1, 9)
    plotly.newPlot.mockClear()
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    expect((await draw(ODD)).layout.yaxis5.range[1]).toBeCloseTo(8, 9)
  })

  it('keeps Plotly\'s zero line for degrees Celsius, and draws the freezing point of the other units as a line of its own', async () => {
    const celsius = (await draw(METRIC)).layout
    expect(celsius.yaxis3.zeroline).toBe(true)
    expect(celsius.shapes.some((shape: any) => shape.yref === 'y3')).toBe(false)
    plotly.newPlot.mockClear()
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    const fahrenheit = (await draw(IMPERIAL)).layout
    expect(fahrenheit.yaxis3.zeroline).toBe(false)
    expect(fahrenheit.shapes.filter((shape: any) => shape.yref === 'y3').map((shape: any) => [shape.y0, shape.y1])).toEqual([[32, 32]])
    // the axis holds the freezing point and reaches a degree below it: 1.8 Fahrenheit
    expect(fahrenheit.yaxis3.range[0]).toBeCloseTo(32 - 1.8, 9)
    plotly.newPlot.mockClear()
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    const kelvin = (await draw(ODD)).layout
    expect(kelvin.shapes.filter((shape: any) => shape.yref === 'y3').map((shape: any) => shape.y0)).toEqual([273.15])
    expect(kelvin.yaxis3.range[0]).toBeCloseTo(273.15 - 1, 9)
  })

  it('draws a cold day under the freezing point as such in any unit, and the rain on it as snow', async () => {
    const cold = (hour: number) => -3 + (hour % 24) / 24
    const snow = async (units: Units) => {
      plotly.newPlot.mockClear()
      mounted.splice(0).forEach(wrapper => wrapper.unmount())
      const { traces } = await draw(units, cold)
      const amount = (name: string) => traces.find(trace => trace.name === name)!.y.reduce((sum, value) => sum + value, 0)
      return [amount('Rain'), amount('Mixed'), amount('Snow')]
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
    const sentence = document.getElementById(wrapper.find('[role="figure"]').attributes('aria-describedby')!)!.textContent!
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

describe('the wind barbs and arrows in each unit', () => {
  // the first barb drawn, as the point it starts at and the point of its shaft's other end: a barb is a drawing of the wind,
  // so it has the same shaft in every unit of speed and of direction
  async function firstBarb(units: Units) {
    const calls: Array<[string, number[]]> = []
    const context = new Proxy({} as Record<string, unknown>, {
      get: (target, property: string) => property === 'moveTo' || property === 'lineTo' ? (...args: number[]) => { calls.push([property, args]) } : (property in target ? target[property] : vi.fn()),
      set: (target, property: string, value) => {
        target[property] = value
        return true
      },
    })
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation((() => context) as any)
    plotly.newPlot.mockClear()
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    const wrapper = await mountMeteogram({ values: [], units: unitsOf(units) })
    await wrapper.setProps({ values: forecast(units) })
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce(), { timeout: 5000 })
    await flushPromises()
    const start = calls.find(([name]) => name === 'moveTo')![1] as [number, number]
    const end = calls.find(([name]) => name === 'lineTo')![1] as [number, number]
    const traces = (plotly.newPlot.mock.calls[0] as unknown as [unknown, Array<{ name: string, text?: string[] }>])[1]
    return { dx: end[0] - start[0], dy: end[1] - start[1], arrows: traces.find(trace => trace.name.startsWith('Direction'))!.text! }
  }

  it('are drawn from the west for a wind from 270 degrees, written in degrees, radians or gradians, and in any unit of speed', async () => {
    for (const units of [METRIC, IMPERIAL, ODD]) {
      const { dx, dy } = await firstBarb(units)
      // the shaft is 20 px long and points west, whence the wind comes: a direction taken for degrees would point it north
      expect(dx, `${units.angle}`).toBeCloseTo(-20, 5)
      expect(dy, `${units.angle}`).toBeCloseTo(0, 5)
    }
  })

  it('has the arrows of the direction point the way a wind from 270 degrees does, whichever unit the direction is in', async () => {
    for (const units of [METRIC, IMPERIAL, ODD]) {
      const { arrows } = await firstBarb(units)
      expect(arrows.length, `${units.angle}`).toBeGreaterThan(0)
      expect(new Set(arrows), `${units.angle}`).toEqual(new Set(['→']))
    }
  })

  it('has the barb the force of the speed in knots, whatever unit it is in: 6 m/s is one full barb', async () => {
    const barbs = async (units: Units) => {
      const calls: string[] = []
      const context = new Proxy({} as Record<string, unknown>, {
        get: (target, property: string) => property === 'lineTo' ? () => { calls.push(property) } : (property in target ? target[property] : vi.fn()),
        set: (target, property: string, value) => {
          target[property] = value
          return true
        },
      })
      vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation((() => context) as any)
      plotly.newPlot.mockClear()
      mounted.splice(0).forEach(wrapper => wrapper.unmount())
      const wrapper = await mountMeteogram({ values: [], units: unitsOf(units) })
      await wrapper.setProps({ values: forecast(units) })
      await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce(), { timeout: 5000 })
      await flushPromises()
      return calls.length
    }
    const metric = await barbs(METRIC)
    expect(metric).toBeGreaterThan(0)
    expect(await barbs(IMPERIAL)).toBe(metric)
    expect(await barbs(ODD)).toBe(metric)
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
    plotly.newPlot.mockClear()
    mounted.splice(0).forEach(wrapper => wrapper.unmount())
    const wrapper = await mountMeteogram({ values: [], units: { ...unitsOf(units), humidity_relative: units.fraction } })
    await wrapper.setProps({ values: humid(units, celsius) })
    await vi.waitFor(() => expect(plotly.newPlot).toHaveBeenCalledOnce(), { timeout: 5000 })
    await flushPromises()
    return (plotly.newPlot.mock.calls[0] as unknown as [unknown, Array<{ name: string, y: number[] }>])[1]
  }

  it('draws the same dew point, in the unit of the temperature, whichever the units of the temperature and the humidity', async () => {
    const warm = (hour: number) => 10 + (hour % 24) / 4
    const dew = async (units: Units) => (await draw(units, warm)).find(trace => trace.name === 'Dew Point')!.y
    const metric = await dew(METRIC)
    expect(metric.length).toBeGreaterThan(0)
    // 80 percent at 10 degrees Celsius: the dew point is a few degrees under the temperature
    expect(metric[0]!).toBeGreaterThan(5)
    expect(metric[0]!).toBeLessThan(10)
    const fahrenheit = await dew(IMPERIAL)
    const kelvin = await dew(ODD)
    metric.forEach((value, i) => {
      expect(fahrenheit[i]!).toBeCloseTo(value * 1.8 + 32, 5)
      expect(kelvin[i]!).toBeCloseTo(value + 273.15, 5)
    })
  })

  it('tells snow from rain by the wet bulb in any unit', async () => {
    const cold = (hour: number) => -3 + (hour % 24) / 24
    const amounts = async (units: Units) => {
      const traces = await draw(units, cold)
      return ['Rain', 'Mixed', 'Snow'].map(name => traces.find(trace => trace.name === name)!.y.reduce((sum, value) => sum + value, 0))
    }
    const metric = await amounts(METRIC)
    expect(metric[2]).toBeGreaterThan(0)
    expect(await amounts(IMPERIAL)).toEqual(metric)
    expect(await amounts(ODD)).toEqual(metric)
  })
})
