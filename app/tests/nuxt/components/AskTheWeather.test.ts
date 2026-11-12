import type { H3Event } from 'h3'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData, clearNuxtState } from '#app'
import { useSettings } from '#imports'
import AskTheWeather from '~/components/AskTheWeather.vue'
import { DEFAULT_PLACE } from '~/composables/usePlace'
import { KIEL_MOSMIX, rainValues, summerValues, windValues } from '../../e2e/accessibility/ask-backend'
import { providersAnswer } from '../fixtures/providers'

// Ask the weather (GH-3518): the suggestions of the home page as buttons that are pressed or not, the answer under
// them with its live region, the chart and the way into the tool, and the place the questions are about. The
// backend is the accessibility spec's answers (tests/e2e/accessibility/ask-backend.ts); the rules that turn them
// into a verdict are held by tests/unit/answers.test.ts.

const requests: Array<{ path: string, query: URLSearchParams }> = []
let failValues = false
function record(event: H3Event, path: string) {
  const query = new URL(event.path, 'http://localhost').searchParams
  requests.push({ path, query })
  return query
}
// the first request for the providers fails (a 404 is not retried) where a test asks it to, so that the
// download question has to ask for them itself
let failFirstProviders = false
registerEndpoint('/api/providers', (event) => {
  record(event, 'providers')
  if (failFirstProviders) {
    failFirstProviders = false
    setResponseStatus(event, 404)
    return { type: 'urn:wetterdienst:problem:not-found', title: 'Not Found', status: 404, detail: 'Not Found' }
  }
  return providersAnswer()
})
// the station nearest to a position the reader gave (GH-3651): asked with `rank`, answered by the DWD observation list
const NEAREST = { station_id: '01975', name: 'Hamburg-Fuhlsbüttel', region: 'Hamburg', latitude: 53.63, longitude: 10, elevation: 11, start_timestamp: null, end_timestamp: null }
registerEndpoint('/api/stations', (event) => {
  const query = record(event, 'stations')
  if (query.get('rank') && query.get('network') === 'observation')
    return { stations: [NEAREST] }
  return { stations: query.get('network') === 'mosmix' ? [KIEL_MOSMIX] : [] }
})
// what the backend does with `unit_targets` (GH-3980): the values in the unit asked for, and each parameter's unit in the
// metadata. The fixtures are written in degrees Celsius, metres per second, millimetres and decimals
const FROM_CELSIUS: Record<string, [string, (value: number) => number]> = {
  degree_celsius: ['°C', value => value],
  degree_fahrenheit: ['°F', value => value * 1.8 + 32],
  degree_kelvin: ['K', value => value + 273.15],
}
const FROM_METERS_PER_SECOND: Record<string, [string, (value: number) => number]> = {
  meter_per_second: ['m/s', value => value],
  kilometer_per_hour: ['km/h', value => value * 3.6],
  knots: ['kn', value => value / (1852 / 3600)],
  beaufort: ['bft', value => (value / 0.836) ** (2 / 3)],
}
const FROM_MILLIMETERS: Record<string, [string, (value: number) => number]> = {
  millimeter: ['mm', value => value],
  liter_per_square_meter: ['l/m²', value => value],
}
const QUANTITIES: Record<string, [string, Record<string, [string, (value: number) => number]>]> = {
  temperature_air_mean_2m: ['temperature', FROM_CELSIUS],
  precipitation_amount_significant_weather_last_1h: ['precipitation', FROM_MILLIMETERS],
  wind_gust_max: ['speed', FROM_METERS_PER_SECOND],
  wind_speed_mean: ['speed', FROM_METERS_PER_SECOND],
}
function inUnits(values: Array<{ parameter: string, value: number | null }>, query: URLSearchParams) {
  const targets = JSON.parse(query.get('unit_targets') ?? '{}') as Record<string, string>
  const convert = query.get('convert_units') !== 'false'
  const conversion = (parameter: string) => {
    const [quantity, units] = QUANTITIES[parameter] ?? []
    return units && convert ? units[targets[quantity!] ?? Object.keys(units)[0]!]! : units ? Object.values(units)[0]! : undefined
  }
  const unitOf: Record<string, string> = {}
  const converted = values.map((row) => {
    const unit = conversion(row.parameter)
    if (unit)
      unitOf[row.parameter] = unit[0]
    return unit && row.value !== null ? { ...row, value: unit[1](row.value) } : row
  })
  const parameters = [...new Set(values.map(row => row.parameter))].map(name => ({ name, unit: unitOf[name] ?? ('-') }))
  return { values: converted, metadata: { parameters } }
}
// an answer of the values that waits for the test where it asks (a request to hold)
let holdValues: Promise<void> | null = null
// the speed unit of the only requests to hold, where the test holds those of one unit and lets the others through
let holdOnlySpeed: string | null = null
registerEndpoint('/api/values', async (event) => {
  const query = record(event, 'values')
  if (failValues) {
    setResponseStatus(event, 422)
    return { type: 'urn:wetterdienst:problem:invalid-request', title: 'Unprocessable', status: 422, detail: 'The request could not be processed.' }
  }
  if (!holdOnlySpeed || JSON.parse(query.get('unit_targets') ?? '{}').speed === holdOnlySpeed)
    await holdValues
  const station = query.get('stations') ?? ''
  const parameters = query.get('parameters') ?? ''
  if (query.get('network') === 'mosmix')
    return inUnits(rainValues(station), query)
  return inUnits(parameters.startsWith('monthly/') ? summerValues(station) : windValues(station, query.get('timestamp')), query)
})
function coverage() {
  return {
    hourly: { description: null, datasets: { temperature_air: { description: null, parameters: [{ name: 'temperature_air_mean_2m', name_original: 'tt_tu', unit_type: 'temperature', unit: 'degree_celsius', description: '' }] } } },
  }
}
// the networks that have no hourly resolution answer the 404 of a resolution the network lacks
let withoutHourly: string[] = []
registerEndpoint('/api/coverage', (event) => {
  const query = record(event, 'coverage')
  if (withoutHourly.includes(`${query.get('provider')}/${query.get('network')}`)) {
    setResponseStatus(event, 404)
    return { type: 'urn:wetterdienst:problem:not-found', title: 'Not Found', status: 404, detail: 'Resolution \'hourly\' not found.' }
  }
  return coverage()
})

const mounted: Array<{ unmount: () => void }> = []
async function mountAsk(route = '/') {
  const wrapper = await mountSuspended(AskTheWeather, { attachTo: document.body, route })
  mounted.push(wrapper)
  return wrapper
}
const chip = (wrapper: Awaited<ReturnType<typeof mountAsk>>, id: string) => wrapper.find(`[data-testid="question-${id}"]`)
const verdict = (wrapper: Awaited<ReturnType<typeof mountAsk>>) => wrapper.find('[data-testid="answer-verdict"]')
const asked = (path: string) => requests.filter(request => request.path === path)

beforeEach(() => {
  failValues = false
  failFirstProviders = false
  withoutHourly = []
  usePlace().place.value = DEFAULT_PLACE
})
afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  clearNuxtData()
  // the services found for the visit are kept, and the next test is another visit
  clearNuxtState('download-sources')
  requests.length = 0
  holdValues = null
  holdOnlySpeed = null
  Object.assign(useSettings().settings.value, { convertUnits: true })
  Object.assign(useSettings().settings.value.units, { temperature: 'degree_celsius', speed: 'meter_per_second', precipitation: 'millimeter' })
})

describe('the suggestions', () => {
  it('are a list of buttons that are none of them pressed, and nothing is asked of the backend until one is', async () => {
    const wrapper = await mountAsk()
    const list = wrapper.find('[data-testid="questions"]')
    expect(list.element.tagName).toBe('UL')
    expect(list.attributes('aria-label')).toBe('Questions')
    const buttons = list.findAll('li > button')
    expect(buttons).toHaveLength(4)
    expect(buttons.map(button => button.attributes('aria-pressed'))).toEqual(['false', 'false', 'false', 'false'])
    expect(buttons.map(button => button.attributes('type'))).toEqual(['button', 'button', 'button', 'button'])
    expect(buttons[0]!.text()).toBe('Will it rain in Kiel-Holtenau tomorrow?')
    expect(buttons[1]!.text()).toBe('Was last summer hotter than usual here?')
    expect(buttons[3]!.text()).toBe('Where can I download hourly temperatures?')
    expect(wrapper.find('[data-testid="ask-idle"]').text()).toBe('Pick a question and it is answered here, from live data.')
    expect(wrapper.find('[data-testid="answer"]').exists()).toBe(false)
    expect(requests).toEqual([])
  })

  it('carry no colour of a tile: the tiles are the tools\' marks, and only the links into the tools have one', async () => {
    const wrapper = await mountAsk()
    expect(wrapper.find('[data-testid="questions"] .tile').exists()).toBe(false)
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).exists()).toBe(true))
    // the monthly means open the Explorer (rain blue), the stripes the stripes (coral)
    const tiles = wrapper.findAll('[data-testid="answer-actions"] .tile').map(tile => tile.classes().find(name => name.startsWith('tile-') && name !== 'tile'))
    expect(tiles).toEqual(['tile-rain', 'tile-heat'])
  })

  it('answer the rain question from the forecast nearest the place, say it in a live region, and lead into the forecast', async () => {
    const wrapper = await mountAsk()
    await chip(wrapper, 'rain').trigger('click')
    await vi.waitFor(() => expect(chip(wrapper, 'rain').attributes('aria-pressed')).toBe('true'))
    await vi.waitFor(() => expect(verdict(wrapper).text()).toBe('Yes, rain is likely.'))
    const status = wrapper.find('[data-testid="answer-status"]')
    expect(status.attributes('role')).toBe('status')
    expect(status.text()).toBe('Yes, rain is likely.')
    const answer = wrapper.find('[data-testid="answer"]')
    expect(answer.find('h3').text()).toBe('Will it rain in Kiel-Holtenau tomorrow?')
    expect(answer.text()).toContain('Forecast for KIEL-HOLTENAU, the forecast point nearest to Kiel-Holtenau (0.6 km away).')
    expect(answer.find('figure figcaption').text()).toBe('Rain per hour tomorrow, in mm')
    expect(answer.findAll('figure tbody tr')).toHaveLength(24)
    expect(answer.findAll('a').map(link => link.attributes('href'))).toContain('/meteogram?station=10046')
    // the position of the place was asked, then the values of that point
    expect(asked('stations')[0]!.query.get('latitude')).toBe(String(DEFAULT_PLACE.latitude))
    expect(asked('values')[0]!.query.get('stations')).toBe('10046')
  })

  it('answer the summer, wind and download questions', async () => {
    const wrapper = await mountAsk()
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toContain('warmer than usual'))
    expect(asked('values').at(-1)!.query.get('stations')).toBe('02564')

    await chip(wrapper, 'wind').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('#answer-day').exists()).toBe(true))
    await vi.waitFor(() => expect(verdict(wrapper).exists()).toBe(true))
    await vi.waitFor(() => expect(chip(wrapper, 'wind').attributes('aria-pressed')).toBe('true'))
    expect(chip(wrapper, 'summer').attributes('aria-pressed')).toBe('false')

    await chip(wrapper, 'download').trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toMatch(/^Weather services that publish hourly air temperature: \d+\.$/))
    // one link for each service the verdict counts, the place's own (DWD) first
    const links = wrapper.findAll('[data-testid="answer-sources"] a').map(link => link.attributes('href'))
    expect(verdict(wrapper).text()).toContain(`: ${links.length}.`)
    expect(links.length).toBeGreaterThan(0)
    expect(links[0]).toContain('/explorer?')
    expect(links[0]).toContain('provider=dwd')
    expect(links[0]).toContain('resolution=hourly')
    expect(links[0]).toContain('stations=02564')
  })

  it('ask for the list of providers themselves where it did not come, as the app does', async () => {
    failFirstProviders = true
    const wrapper = await mountAsk()
    await chip(wrapper, 'download').trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toMatch(/^Weather services that publish hourly air temperature: [1-9]\d*\.$/))

    // the first request failed, the question asked again, and then the coverage of each measurement network
    expect(asked('providers').length).toBeGreaterThanOrEqual(2)
    expect(asked('coverage').length).toBeGreaterThan(0)
  })

  it('leave out the networks that have no hourly resolution, which answer a 404, and count the others', async () => {
    withoutHourly = ['aemet/observation']
    const wrapper = await mountAsk()
    await chip(wrapper, 'download').trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toBe('Weather services that publish hourly air temperature: 2.'))

    // each measurement network of the list of providers was asked for its hourly resolution, the one without it too
    const networks = asked('coverage').map(request => `${request.query.get('provider')}/${request.query.get('network')}`).toSorted()
    expect(networks).toEqual(['aemet/observation', 'dwd/observation', 'metno/frost'])
    expect(asked('coverage').map(request => request.query.get('resolutions'))).toEqual(['hourly', 'hourly', 'hourly'])
    expect(wrapper.findAll('[data-testid="answer-sources"] a')).toHaveLength(2)
    expect(wrapper.find('[data-testid="answer-sources"]').text()).not.toContain('AEMET')
  })

  it('look the services up once for the visit, not again for each place tried', async () => {
    const wrapper = await mountAsk()
    await chip(wrapper, 'download').trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toMatch(/: \d+\.$/))
    const first = asked('coverage').length
    expect(first).toBeGreaterThan(0)

    usePlace().setPlace({ id: '00183', name: 'Arkona', latitude: 54.68, longitude: 13.43, region: 'Mecklenburg-Vorpommern' })
    await vi.waitFor(() => expect(wrapper.find('[data-testid="place-button"]').text()).toContain('Arkona'))
    await vi.waitFor(() => expect(verdict(wrapper).text()).toMatch(/: \d+\.$/))

    expect(asked('coverage')).toHaveLength(first)
  })

  it('close when the one open is pressed again, and the link follows', async () => {
    const wrapper = await mountAsk()
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(chip(wrapper, 'summer').attributes('aria-pressed')).toBe('true'))
    await vi.waitFor(() => expect(verdict(wrapper).exists()).toBe(true))
    expect(useRoute().query.ask).toBe('summer')
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="answer"]').exists()).toBe(false))
    expect(chip(wrapper, 'summer').attributes('aria-pressed')).toBe('false')
    expect(useRoute().query.ask).toBeUndefined()
    expect(wrapper.find('[data-testid="ask-idle"]').exists()).toBe(true)
  })

  it('open from a link that names the question, and the day of the wind one', async () => {
    const wrapper = await mountAsk('/?ask=wind&day=2025-12-26')
    expect(chip(wrapper, 'wind').attributes('aria-pressed')).toBe('true')
    expect(chip(wrapper, 'wind').text()).toBe('How windy was it on 26 December?')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toBe('Stormy.'))
    expect(asked('values')[0]!.query.get('timestamp')).toBe('2025-12-19/2026-01-02')
  })

  it.each(['2025-13-45', '2025-02-30'])('keep the section, and the last Boxing Day, for a link whose day (%s) is no day', async (day) => {
    const wrapper = await mountAsk(`/?ask=wind&day=${day}`)
    expect(wrapper.find('[data-testid="ask"]').exists()).toBe(true)
    expect(chip(wrapper, 'wind').text()).toMatch(/^How windy was it on 26 December\?$/)
  })

  it('say that the answer could not be worked out, with a way to ask again', async () => {
    failValues = true
    const wrapper = await mountAsk()
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('The answer could not be worked out.'))
    expect(wrapper.text()).toContain('The request could not be processed.')
    expect(wrapper.find('[data-testid="answer-status"]').text()).toBe('')
    failValues = false
    await wrapper.findAll('button').find(button => button.text() === 'Retry')!.trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toContain('warmer than usual'))
  })

  it('hand the focus from the Retry that worked to the heading of the question', async () => {
    failValues = true
    const wrapper = await mountAsk()
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('The answer could not be worked out.'))
    const retry = wrapper.findAll('button').find(button => button.text() === 'Retry')!
    ;(retry.element as HTMLElement).focus()
    failValues = false
    await retry.trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toContain('warmer than usual'))
    expect(document.activeElement).toBe(wrapper.find('#answer-heading').element)
  })

  it('are about the place, which names them and which the answers are asked for', async () => {
    usePlace().setPlace({ id: '00183', name: 'Arkona', latitude: 54.68, longitude: 13.43, region: 'Mecklenburg-Vorpommern' })
    const wrapper = await mountAsk()
    expect(wrapper.find('[data-testid="place-button"]').text()).toContain('Arkona')
    expect(chip(wrapper, 'rain').text()).toBe('Will it rain in Arkona tomorrow?')
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).exists()).toBe(true))
    expect(asked('values')[0]!.query.get('stations')).toBe('00183')
  })
})

// "Here" (GH-3651): the reader's own position, given by "Use my location", takes the station nearest to it as the place
describe('the place from the reader\'s position', () => {
  function mockBrowser(options: { code?: number } = {}) {
    const getCurrentPosition = vi.fn((success: (position: unknown) => void, failure: (error: unknown) => void) => {
      if (options.code)
        failure({ code: options.code })
      else
        success({ coords: { latitude: 53.6012, longitude: 10.0499 } })
    })
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition } })
    Object.defineProperty(navigator, 'permissions', { configurable: true, value: { query: vi.fn(async () => ({ state: 'prompt' })) } })
    return getCurrentPosition
  }
  // the position's own state only: the place is the file's, which each test sets
  const clearLocation = () => clearNuxtState(['wd-location-position', 'wd-location-failure', 'wd-location-busy', 'wd-location-remember', 'wd-location-loaded'])
  beforeEach(() => {
    clearLocation()
  })
  afterEach(() => {
    delete (navigator as any).geolocation
    delete (navigator as any).permissions
    vi.unstubAllGlobals()
    clearLocation()
  })
  const locate = (wrapper: Awaited<ReturnType<typeof mountAsk>>) => wrapper.find('[data-testid="use-my-location-button"]')

  it('asks the browser for nothing until the button is pressed', async () => {
    const getCurrentPosition = mockBrowser()
    await mountAsk()
    expect(getCurrentPosition).not.toHaveBeenCalled()
    expect(requests).toEqual([])
  })

  it('makes the nearest DWD station the place that the questions are about, and tells how far it is', async () => {
    mockBrowser()
    const wrapper = await mountAsk()
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="place-button"]').text()).toContain('Hamburg-Fuhlsbüttel'))

    const request = asked('stations')[0]!.query
    // the rounded position, asked as the stations request of the questions' own network
    expect(Object.fromEntries(request)).toEqual({ provider: 'dwd', network: 'observation', parameters: 'daily/climate_summary', latitude: '53.6', longitude: '10.05', rank: '1' })
    expect(wrapper.find('[data-testid="use-my-location-status"]').text()).toMatch(/^Asking about Hamburg-Fuhlsbüttel, the station \d+(\.\d)? km from your position\.$/)
    expect(chip(wrapper, 'rain').text()).toBe('Will it rain in Hamburg-Fuhlsbüttel tomorrow?')

    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).exists()).toBe(true))
    expect(asked('values')[0]!.query.get('stations')).toBe('01975')
  })

  it('keeps the place for this visit only, unless the reader ticked remember', async () => {
    mockBrowser()
    const wrapper = await mountAsk()
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="place-button"]').text()).toContain('Hamburg-Fuhlsbüttel'))
    expect(localStorage.getItem('wd-place')).toBeNull()
    expect(localStorage.getItem('wd-location')).toBeNull()
  })

  it('keeps the place in the browser with the position when remember is ticked', async () => {
    mockBrowser()
    const wrapper = await mountAsk()
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('button[role="checkbox"]').exists()).toBe(true))
    await wrapper.find('button[role="checkbox"]').trigger('click')
    await vi.waitFor(() => expect(localStorage.getItem('wd-place')).not.toBeNull())
    expect(JSON.parse(localStorage.getItem('wd-place')!).id).toBe('01975')
    expect(JSON.parse(localStorage.getItem('wd-location')!)).toEqual({ latitude: 53.6, longitude: 10.05 })
  })

  it('takes the place of the link out of the address, and keeps the position out of it', async () => {
    mockBrowser()
    const wrapper = await mountAsk('/?place=02564&ask=rain')
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="place-button"]').text()).toContain('Hamburg-Fuhlsbüttel'))
    const address = useRoute().fullPath
    expect(address).not.toContain('place=')
    expect(address).not.toMatch(/lat|lon|53\.6|10\.05/)
  })

  it('takes the place back, in the browser and in the page, when the reader forgets the position', async () => {
    mockBrowser()
    const wrapper = await mountAsk()
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('button[role="checkbox"]').exists()).toBe(true))
    await wrapper.find('button[role="checkbox"]').trigger('click')
    await vi.waitFor(() => expect(localStorage.getItem('wd-place')).not.toBeNull())

    // "Stored" opens the position and the way to forget it; the popover is teleported to the body
    await wrapper.find('[data-testid="use-my-location-stored"]').trigger('click')
    await vi.waitFor(() => expect(document.body.querySelector('[data-testid="use-my-location-forget"]')).not.toBeNull())
    document.body.querySelector<HTMLElement>('[data-testid="use-my-location-forget"]')!.click()
    await vi.waitFor(() => expect(localStorage.getItem('wd-place')).toBeNull())
    expect(localStorage.getItem('wd-location')).toBeNull()
    await vi.waitFor(() => expect(wrapper.find('[data-testid="place-button"]').text()).toContain('Kiel-Holtenau'))
  })

  it('leaves the place as it was where the reader refuses, and says so in the alert region', async () => {
    const getCurrentPosition = mockBrowser({ code: 1 })
    const wrapper = await mountAsk()
    await locate(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="use-my-location-problem"]').text()).toContain('Your browser blocks location for this site'))
    expect(getCurrentPosition).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-testid="place-button"]').text()).toContain('Kiel-Holtenau')
    expect(asked('stations')).toEqual([])
    // the questions still work
    await chip(wrapper, 'summer').trigger('click')
    await vi.waitFor(() => expect(verdict(wrapper).exists()).toBe(true))
  })
})

// The answers follow the unit settings (GH-3980): the request carries the unit, the sentences, the chart and its table say the unit
// the answer reports, the verdict is the same in every unit, and a change of the unit refetches
describe('the answers in the unit of the settings', () => {
  const settings = () => useSettings().settings.value

  it('says the summer in degrees Fahrenheit, with the difference as degrees of it, and the same verdict', async () => {
    const celsius = await mountAsk('/?ask=summer')
    await vi.waitFor(() => expect(verdict(celsius).text()).toMatch(/^Yes, [\d.]+ °C warmer than usual\.$/))
    const inCelsius = Number(/([\d.]+) °C/.exec(verdict(celsius).text())![1])
    celsius.unmount()
    mounted.pop()

    settings().units.temperature = 'degree_fahrenheit'
    const wrapper = await mountAsk('/?ask=summer')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toMatch(/^Yes, [\d.]+ °F warmer than usual\.$/))
    expect(JSON.parse(asked('values').at(-1)!.query.get('unit_targets')!)).toEqual({ temperature: 'degree_fahrenheit' })
    // 1 degree Celsius is 1.8 degrees Fahrenheit
    expect(Number(/([\d.]+) °F/.exec(verdict(wrapper).text())![1])).toBeCloseTo(inCelsius * 1.8, 0)
    expect(wrapper.text()).toContain('averaged')
    expect(wrapper.text()).toMatch(/averaged [\d.]+ °F;/)
    expect(wrapper.find('figure figcaption').text()).toContain('in °F')
    expect(wrapper.find('figure table thead th:last-child').text()).toBe('°F')
    expect(wrapper.text()).not.toContain('°C')
  })

  it.each([
    ['kilometer_per_hour', 'km/h', 77.8],
    ['knots', 'kn', 42],
    ['beaufort', 'bft', 8.7],
  ])('says the wind in %s, with the same verdict and the same Beaufort force', async (unit, symbol, gust) => {
    settings().units.speed = unit
    const wrapper = await mountAsk('/?ask=wind&day=2025-12-26')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toBe('Stormy.'))
    expect(JSON.parse(asked('values')[0]!.query.get('unit_targets')!)).toEqual({ speed: unit })
    expect(wrapper.text()).toContain(`Strongest gust ${gust}`)
    expect(wrapper.text()).toMatch(new RegExp(`Strongest gust [\\d.]+ ${symbol.replace('/', '\\/')}, Beaufort 9\\.`))
    expect(wrapper.text()).toMatch(new RegExp(`Mean wind [\\d.]+ ${symbol.replace('/', '\\/')}, Beaufort 5\\.`))
    expect(wrapper.find('figure figcaption').text()).toBe(`Strongest gust per day, in ${symbol}`)
  })

  it('says the rain in litres per square metre, and asks the chance as a decimal whatever the settings', async () => {
    settings().units.precipitation = 'liter_per_square_meter'
    settings().units.fraction = 'one_eighth'
    const wrapper = await mountAsk('/?ask=rain')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toBe('Yes, rain is likely.'))
    expect(JSON.parse(asked('values')[0]!.query.get('unit_targets')!)).toEqual({ precipitation: 'liter_per_square_meter', fraction: 'decimal' })
    expect(wrapper.text()).toMatch(/[\d.]+ l\/m² forecast for the whole day\./)
    expect(wrapper.text()).toMatch(/Wettest hour: 15:00 to 16:00, [\d.]+ l\/m²\./)
    expect(wrapper.find('figure figcaption').text()).toBe('Rain per hour tomorrow, in l/m²')
    expect(wrapper.text()).toContain('Highest chance of rain in any hour: 85%.')
  })

  it('asks for the values as the source has them, and reads the unit the answer says, where the settings do not convert', async () => {
    settings().convertUnits = false
    const wrapper = await mountAsk('/?ask=wind&day=2025-12-26')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toBe('Stormy.'))
    expect(asked('values')[0]!.query.get('convert_units')).toBe('false')
    expect(wrapper.text()).toMatch(/Strongest gust 21\.6 m\/s, Beaufort 9\./)
  })

  it('asks again, in the new unit, where the settings change while the answer is shown', async () => {
    const wrapper = await mountAsk('/?ask=wind&day=2025-12-26')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toBe('Stormy.'))
    expect(asked('values')).toHaveLength(1)
    settings().units.speed = 'kilometer_per_hour'
    await vi.waitFor(() => expect(asked('values')).toHaveLength(2))
    await vi.waitFor(() => expect(wrapper.text()).toContain('km/h'))
    expect(JSON.parse(asked('values')[1]!.query.get('unit_targets')!)).toEqual({ speed: 'kilometer_per_hour' })
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(asked('values')).toHaveLength(2)
  })

  it('leaves the answer as it is where the unit of another quantity changes', async () => {
    const wrapper = await mountAsk('/?ask=wind&day=2025-12-26')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toBe('Stormy.'))
    settings().units.temperature = 'degree_fahrenheit'
    settings().units.precipitation = 'liter_per_square_meter'
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(asked('values')).toHaveLength(1)
  })

  it('shows the answer of the newest request where the unit changes while one is under way, followed by one more fetch', async () => {
    let release!: () => void
    holdValues = new Promise<void>((resolve) => {
      release = resolve
    })
    const wrapper = await mountAsk('/?ask=wind&day=2025-12-26')
    await vi.waitFor(() => expect(asked('values')).toHaveLength(1))
    settings().units.speed = 'knots'
    await vi.waitFor(() => expect(asked('values')).toHaveLength(2))
    release()
    await vi.waitFor(() => expect(verdict(wrapper).text()).toBe('Stormy.'))
    expect(wrapper.text()).toMatch(/Strongest gust [\d.]+ kn,/)
    expect(wrapper.text()).not.toContain('m/s')
    expect(asked('values')).toHaveLength(2)
  })

  it('keeps the answer of the newer request where the older one comes back last, as the first visit\'s seeding of the settings makes it', async () => {
    // the request in metres per second is held; the unit changes to knots, and that answer comes first
    let release!: () => void
    holdValues = new Promise<void>((resolve) => {
      release = resolve
    })
    holdOnlySpeed = 'meter_per_second'
    const wrapper = await mountAsk('/?ask=wind&day=2025-12-26')
    await vi.waitFor(() => expect(asked('values')).toHaveLength(1))
    settings().units.speed = 'knots'
    await vi.waitFor(() => expect(asked('values')).toHaveLength(2))
    await vi.waitFor(() => expect(wrapper.text()).toMatch(/Strongest gust [\d.]+ kn,/))
    // now the older one returns
    release()
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(wrapper.text()).toMatch(/Strongest gust [\d.]+ kn,/)
    expect(wrapper.text()).not.toContain('m/s')
    expect(wrapper.find('figure figcaption').text()).toBe('Strongest gust per day, in kn')
  })

  it('asks again for no unit where the values are not converted: the unit chosen changes nothing of them', async () => {
    settings().convertUnits = false
    const wrapper = await mountAsk('/?ask=wind&day=2025-12-26')
    await vi.waitFor(() => expect(verdict(wrapper).text()).toBe('Stormy.'))
    settings().units.speed = 'knots'
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(asked('values')).toHaveLength(1)
  })
})
