import type { VueWrapper } from '@vue/test-utils'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { setResponseStatus } from 'h3'
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { clearNuxtState } from '#app'
import StationPicker from '~/components/StationPicker.vue'
import { LOCATION_STORAGE_KEY } from '~/utils/geolocation'

// "Use my location" in the station picker (GH-3651): the button under the toggle, the nearest station that the ranked
// `stations` request answers (or the list in hand, for the stripes), picked as the search would pick it, its distance
// told in a live region, and a refusal told in another. The browser's APIs are mocks, the backend is an endpoint.

vi.mock('~/components/MapStations.vue', async () => {
  const { defineComponent: define, h: render } = await import('vue')
  return { __esModule: true, default: define({ name: 'MapStationsStub', render: () => render('div', { class: 'leaflet-container' }) }) }
})

const berlin = { station_id: '00433', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4 }
const potsdam = { station_id: '03987', name: 'Potsdam', region: 'Brandenburg', latitude: 52.38, longitude: 13.06 }
const hamburg = { station_id: '01975', name: 'Hamburg-Fuhlsbüttel', region: 'Hamburg', latitude: 53.63, longitude: 10.0 }
const stations = [berlin, potsdam, hamburg]

const requests: URLSearchParams[] = []
let answer: unknown = { stations: [berlin] }
let failing = false
/** An answer that is held back until the test lets it go: a lookup that is on its way */
let hold: Promise<void> | null = null
registerEndpoint('/api/stations', async (event) => {
  requests.push(new URL(event.path, 'http://localhost').searchParams)
  if (hold)
    await hold
  if (failing) {
    setResponseStatus(event, 404)
    return { type: 'urn:wetterdienst:problem:not-found', title: 'Not Found', status: 404, detail: 'Not Found' }
  }
  return answer
})

type Props = Record<string, any>

function mockBrowser(options: { fix?: { latitude: number, longitude: number }, code?: number, permission?: PermissionState }) {
  const getCurrentPosition = vi.fn((success: (position: unknown) => void, failure: (error: unknown) => void) => {
    if (options.code)
      failure({ code: options.code })
    else
      success({ coords: options.fix ?? { latitude: 52.5234, longitude: 13.4111 } })
  })
  Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition } })
  Object.defineProperty(navigator, 'permissions', { configurable: true, value: { query: vi.fn(async () => ({ state: options.permission ?? 'prompt' })) } })
  return getCurrentPosition
}

beforeEach(() => {
  clearNuxtState()
  requests.length = 0
  answer = { stations: [berlin] }
  failing = false
  hold = null
})
afterEach(() => {
  delete (navigator as any).geolocation
  delete (navigator as any).permissions
  vi.unstubAllGlobals()
  clearNuxtState()
})

async function mountPage(props: Props = {}) {
  const picked = ref<typeof stations>(props.selected ?? [])
  const Host = defineComponent({
    setup: () => () => h(StationPicker as any, {
      'tool': 'explorer',
      stations,
      'multiple': true,
      ...props,
      'selected': picked.value,
      'onUpdate:selected': (value: typeof stations) => {
        picked.value = value
      },
    }),
  })
  const wrapper = await mountSuspended(Host, { attachTo: document.body })
  onTestFinished(() => wrapper.unmount())
  return { wrapper, picked }
}

const button = (wrapper: VueWrapper) => wrapper.find('[data-testid="use-my-location-button"]')
const status = (wrapper: VueWrapper) => wrapper.find('[data-testid="use-my-location-status"]')
const problem = (wrapper: VueWrapper) => wrapper.find('[data-testid="use-my-location-problem"]')
// the search that the toggle controls: the one place of the choice, in list mode
const search = (wrapper: VueWrapper) => wrapper.find(`[id="${wrapper.find('[role="radio"]').attributes('aria-controls')}"] button`)
const remember = (wrapper: VueWrapper) => wrapper.find('[data-testid="use-my-location-remember"] button[role="checkbox"], button[role="checkbox"]')
const chips = (wrapper: VueWrapper) => wrapper.findAll('[data-station-chip]').map(chip => chip.text())
const query = { provider: 'dwd', network: 'observation', parameters: 'daily/climate_summary' }

describe('the button', () => {
  it('is not there without `locate`: a picker that has no way to rank by position offers none', async () => {
    const { wrapper } = await mountPage()
    expect(wrapper.find('[data-testid="use-my-location"]').exists()).toBe(false)
  })

  it('is a real button with a text label, in the picker\'s own place under the toggle, hidden in print', async () => {
    mockBrowser({})
    const { wrapper } = await mountPage({ locate: query })
    const element = button(wrapper).element
    expect(element.tagName).toBe('BUTTON')
    expect(element.getAttribute('type')).toBe('button')
    expect(button(wrapper).text()).toBe('Use my location')
    expect(element.closest('[data-print="hide"]')).not.toBeNull()
  })

  it('asks the browser for nothing until it is pressed, and nothing of the backend', async () => {
    const getCurrentPosition = mockBrowser({})
    await mountPage({ locate: query })
    expect(getCurrentPosition).not.toHaveBeenCalled()
    expect(requests).toEqual([])
  })

  it('says in a note what is done with the position, and has a box for keeping it that is not ticked', async () => {
    mockBrowser({})
    const { wrapper } = await mountPage({ locate: query })
    expect(wrapper.find('[data-testid="use-my-location"]').text()).toContain('Rounded to about 1 km')
    expect(remember(wrapper).attributes('aria-checked')).toBe('false')
  })
})

describe('a press, with a ranked request', () => {
  it('sends the rounded position as the coordinates of the `stations` request, ranked by one, and picks the station', async () => {
    mockBrowser({ fix: { latitude: 52.523401, longitude: 13.411199 } })
    const { wrapper, picked } = await mountPage({ locate: query })

    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(picked.value).toEqual([berlin]))

    expect(requests).toHaveLength(1)
    expect(Object.fromEntries(requests[0]!)).toEqual({ ...query, latitude: '52.52', longitude: '13.41', rank: '1' })
    expect(chips(wrapper)).toEqual(['Berlin-Tempelhof (00433) ×'])
  })

  it('tells the distance of the station in a polite live region', async () => {
    mockBrowser({ fix: { latitude: 52.47, longitude: 13.5 } })
    const { wrapper } = await mountPage({ locate: query })
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(status(wrapper).text()).not.toBe(''))
    // 0.1 degree of longitude at 52.5 N is 6.8 km
    expect(status(wrapper).text()).toBe('Nearest station: Berlin-Tempelhof (00433), 6.8 km from your position.')
    expect(status(wrapper).attributes('role')).toBe('status')
    expect(status(wrapper).attributes('aria-live')).toBe('polite')
    expect(problem(wrapper).exists()).toBe(false)
  })

  it('adds the station to those picked for several, and replaces the one before for one', async () => {
    mockBrowser({})
    const several = await mountPage({ locate: query, selected: [hamburg] })
    await button(several.wrapper).trigger('click')
    await vi.waitFor(() => expect(several.picked.value.map(station => station.station_id)).toEqual(['01975', '00433']))

    const one = await mountPage({ locate: query, multiple: false, selected: [hamburg] })
    await button(one.wrapper).trigger('click')
    await vi.waitFor(() => expect(one.picked.value.map(station => station.station_id)).toEqual(['00433']))
  })

  it('leaves the other picks as they are where the nearest station is picked already, for several', async () => {
    mockBrowser({})
    const { wrapper, picked } = await mountPage({ locate: query, selected: [hamburg, berlin] })
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(status(wrapper).text()).toContain('Berlin-Tempelhof'))
    expect(picked.value.map(station => station.station_id)).toEqual(['01975', '00433'])
  })

  it('drops the answer of a lookup that was made for another dataset or network: it is not a station of this one', async () => {
    mockBrowser({})
    let release!: () => void
    hold = new Promise((resolve) => {
      release = resolve
    })
    const locate = ref<Record<string, string>>(query)
    const picked = ref<typeof stations>([])
    const Host = defineComponent({
      setup: () => () => h(StationPicker as any, {
        'tool': 'explorer',
        stations,
        'multiple': true,
        'locate': locate.value,
        'selected': picked.value,
        'onUpdate:selected': (value: typeof stations) => {
          picked.value = value
        },
      }),
    })
    const wrapper = await mountSuspended(Host, { attachTo: document.body })
    onTestFinished(() => wrapper.unmount())

    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(requests).toHaveLength(1))
    // the reader chooses another dataset while the answer is on its way
    locate.value = { ...query, parameters: 'hourly/temperature_air' }
    await vi.waitFor(() => expect(button(wrapper).attributes('aria-busy')).toBe('false'))
    release()
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(picked.value).toEqual([])
    expect(status(wrapper).text()).toBe('')
  })

  it('keeps the status region in the tree while it is empty, so that what fills it is announced', async () => {
    mockBrowser({})
    const { wrapper } = await mountPage({ locate: query })
    const classes = status(wrapper).classes()
    expect(classes).toContain('empty:sr-only')
    expect(classes).not.toContain('empty:hidden')
    expect(classes).not.toContain('hidden')
  })

  it('has a link to the section of the privacy policy beside its note', async () => {
    mockBrowser({})
    const { wrapper } = await mountPage({ locate: query })
    const link = wrapper.find('[data-testid="use-my-location-privacy"]')
    expect(link.text()).toBe('More in the privacy policy')
    expect(link.attributes('href')).toBe('/datenschutz#location')
    // the note that describes the button holds the link
    expect(wrapper.find(`[id="${button(wrapper).attributes('aria-describedby')}"]`).element.contains(link.element)).toBe(true)
  })

  it('does not pick a station twice', async () => {
    mockBrowser({})
    const { wrapper, picked } = await mountPage({ locate: query, selected: [berlin] })
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(status(wrapper).text()).not.toBe(''))
    expect(picked.value).toEqual([berlin])
  })

  it('tells where no station is near, in the alert region', async () => {
    mockBrowser({})
    answer = { stations: [] }
    const { wrapper, picked } = await mountPage({ locate: query })
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(problem(wrapper).text()).toBe('No station was found near your position.'))
    expect(problem(wrapper).attributes('role')).toBe('alert')
    expect(picked.value).toEqual([])
  })

  it('tells a lookup that fails, and leaves the search as it was', async () => {
    mockBrowser({})
    failing = true
    onTestFinished(() => {
      failing = false
    })
    const { wrapper, picked } = await mountPage({ locate: query })
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(problem(wrapper).text()).toBe('The nearest station could not be looked up. Try again, or use the search.'))
    expect(picked.value).toEqual([])
    expect(search(wrapper).exists()).toBe(true)
  })
})

describe('a press, with the list in hand', () => {
  it('picks the nearest of the stations the picker holds and sends nothing', async () => {
    mockBrowser({ fix: { latitude: 53.6, longitude: 10.05 } })
    const { wrapper, picked } = await mountPage({ locate: 'list' })
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(picked.value).toEqual([hamburg]))
    expect(requests).toEqual([])
    expect(status(wrapper).text()).toMatch(/^Nearest station: Hamburg-Fuhlsbüttel \(01975\), \d/)
  })

  it('tells where the list has no station with a position', async () => {
    mockBrowser({})
    const { wrapper } = await mountPage({ locate: 'list', stations: [{ station_id: '1', name: 'No place', region: null, latitude: null, longitude: null }] })
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(problem(wrapper).text()).toBe('No station was found near your position.'))
  })
})

describe('a refusal', () => {
  it('is announced in the alert region, with the way to allow it, and the search is still there', async () => {
    const getCurrentPosition = mockBrowser({ code: 1 })
    const { wrapper, picked } = await mountPage({ locate: query })
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(problem(wrapper).text()).toContain('Your browser blocks location for this site'))
    expect(getCurrentPosition).toHaveBeenCalledTimes(1)
    expect(problem(wrapper).attributes('role')).toBe('alert')
    expect(problem(wrapper).text()).toContain('set Location to Allow')
    expect(requests).toEqual([])
    expect(picked.value).toEqual([])
    expect(search(wrapper).exists()).toBe(true)
  })

  it('that the browser reports as denied already is not asked for again, and is told the same', async () => {
    const getCurrentPosition = mockBrowser({ permission: 'denied' })
    const { wrapper } = await mountPage({ locate: query })
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(problem(wrapper).text()).toContain('set Location to Allow'))
    expect(getCurrentPosition).not.toHaveBeenCalled()
    expect(requests).toEqual([])
  })

  it.each([
    [3, 'Finding your position took too long. Press the button to try again, or use the search.'],
    [2, 'Your position could not be found. Use the search instead.'],
  ])('with the browser\'s code %i is told as the text says', async (code, text) => {
    mockBrowser({ code })
    const { wrapper } = await mountPage({ locate: query })
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(problem(wrapper).text()).toBe(text))
  })

  it('is told for a browser without geolocation, which the button does not hide', async () => {
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: undefined })
    const { wrapper } = await mountPage({ locate: query })
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(problem(wrapper).text()).toBe('This browser cannot tell your position. Use the search instead.'))
  })
})

describe('"remember"', () => {
  it('keeps the rounded position in the browser when ticked, and shows it with a way to forget it', async () => {
    mockBrowser({ fix: { latitude: 52.523401, longitude: 13.411199 } })
    const { wrapper } = await mountPage({ locate: query })

    await remember(wrapper).trigger('click')
    expect(remember(wrapper).attributes('aria-checked')).toBe('true')
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(localStorage.getItem(LOCATION_STORAGE_KEY)).toBe('{"latitude":52.52,"longitude":13.41}'))
    await vi.waitFor(() => expect(wrapper.find('[data-testid="use-my-location-remembered"]').text()).toContain('52.52, 13.41'))

    await wrapper.find('[data-testid="use-my-location-forget"]').trigger('click')
    expect(localStorage.getItem(LOCATION_STORAGE_KEY)).toBeNull()
    expect(wrapper.find('[data-testid="use-my-location-remembered"]').exists()).toBe(false)
  })

  it('keeps nothing in the browser when it is not ticked', async () => {
    mockBrowser({})
    const { wrapper, picked } = await mountPage({ locate: query })
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(picked.value).toEqual([berlin]))
    expect(localStorage.getItem(LOCATION_STORAGE_KEY)).toBeNull()
  })
})
