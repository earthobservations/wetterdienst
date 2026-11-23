import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, onTestFinished, vi } from 'vitest'
import { nextTick } from 'vue'
import { clearNuxtState } from '#app'
import PlaceField from '~/components/PlaceField.vue'
import PlacesCredit from '~/components/PlacesCredit.vue'
import PlaceStations from '~/components/PlaceStations.vue'
import StationPicker from '~/components/StationPicker.vue'
import { stationsNear } from '~/utils/place-stations'

// The place picker (GH-3791): the places of the search (`usePlacesSearch`, the same rules everywhere), the field that finds one (`PlaceField`), the
// station search of a picker that also finds places (`StationPicker` with `places`), and the stations near the place that was chosen (`PlaceStations`).
// The menu of Nuxt UI is a popover that this document does not lay out: what the pickers hand it (its items and its model) is read, and the keys,
// the focus and the look of the open list are the end-to-end specs'.

// the map is Leaflet, which is no use in this document: a stand-in (the map's own drawing is the end-to-end tests')
vi.mock('~/components/MapStations.vue', async () => {
  const { defineComponent: define, h: render, onMounted } = await import('vue')
  return {
    __esModule: true,
    default: define({
      name: 'MapStationsStub',
      props: ['stations', 'selectedStations', 'multiple'],
      emits: ['update:selectedStations', 'ready'],
      setup(_props, { emit }) {
        onMounted(() => emit('ready'))
        return () => render('div', { class: 'leaflet-container', tabindex: 0 })
      },
    }),
  }
})

const placeQueries: Array<{ q: string, lang: string }> = []
let placesMode: 'answer' | 'off' | 'fail' = 'answer'
const place = (id: string, name: string, kind: string, region: string | null, latitude: number, longitude: number) => ({ id, name, kind, region, latitude, longitude })
registerEndpoint('/_search/places', (event) => {
  const query = new URL(event.path, 'http://localhost').searchParams
  const q = query.get('q') ?? ''
  placeQueries.push({ q, lang: query.get('lang') ?? '' })
  if (placesMode === 'off')
    return { query: q, state: 'off', places: [], attribution: '© OpenStreetMap contributors' }
  if (placesMode === 'fail')
    throw createError({ statusCode: 503, statusMessage: 'busy' })
  return {
    query: q,
    state: 'ok',
    places: q.toLowerCase().startsWith('bad t') ? [place('N240109189', 'Bad Tölz', 'town', 'Bayern, Germany', 47.7614, 11.5583), place('R1', 'Landkreis Bad Tölz-Wolfratshausen', 'county', 'Bayern, Germany', 47.78, 11.5)] : [],
    attribution: '© OpenStreetMap contributors',
  }
})

afterEach(() => {
  placeQueries.length = 0
  placesMode = 'answer'
  clearNuxtState('places-search-off')
})

const BAD_TOELZ = { latitude: 47.7614, longitude: 11.5583 }
const station = (station_id: string, name: string, latitude: number, longitude: number, elevation: number | null) => ({ station_id, name, region: null, latitude, longitude, elevation })
const STATIONS = [
  station('M0814', 'BAD TOELZ', 47.77, 11.55, 668),
  station('M0818', 'TEGERNSEE', 47.71, 11.76, 735),
  station('M0816', 'KOCHEL AM SEE', 47.65, 11.37, 614),
  station('10865', 'MUENCHEN-STADT', 48.16, 11.54, 515),
  station('10147', 'HAMBURG-FUHLSBUETTEL', 53.63, 10, 11),
]

describe('the stations near a place that was chosen', () => {
  async function mountStations(props: Record<string, unknown> = {}) {
    const wrapper = await mountSuspended(PlaceStations, {
      props: { place: { name: 'Bad Tölz', region: 'Bayern, Germany', ...BAD_TOELZ }, near: stationsNear(BAD_TOELZ, STATIONS), state: 'ready', selectedId: 'M0814', ...props },
      attachTo: document.body,
    })
    onTestFinished(() => wrapper.unmount())
    return wrapper
  }

  it('shows the place with its name and where it lies, and says which station it shows and how far it is', async () => {
    const wrapper = await mountStations()
    expect(wrapper.find('[data-testid="place-name"]').text()).toBe('Bad Tölz')
    expect(wrapper.find('[data-testid="place-region"]').text()).toBe('Bayern, Germany')
    expect(wrapper.find('[data-testid="place-summary"]').text()).toBe('Showing BAD TOELZ (BAD TOELZ), the closest forecast station to Bad Tölz, 1.1 km away.'.replace('BAD TOELZ (BAD TOELZ)', 'BAD TOELZ (M0814)'))
    // a polite status, so that a screen reader says it when it changes
    expect(wrapper.find('[data-testid="place-summary"]').attributes('role')).toBe('status')
  })

  it('lists the stations within reach, closest first, each with its distance and height, and the others\' height against the closest', async () => {
    const wrapper = await mountStations()
    const rows = wrapper.findAll('[data-testid="place-station-list"] li')
    // Munich is 44 km away and within reach; Hamburg is 600 km away and is no alternative to list
    expect(rows.map(row => row.text().replace(/\s+/g, ' '))).toEqual([
      expect.stringContaining('BAD TOELZ (M0814) closest 1.1 km Height 668 m Shown'),
      expect.stringContaining('TEGERNSEE (M0818)'),
      expect.stringContaining('KOCHEL AM SEE (M0816)'),
      expect.stringContaining('MUENCHEN-STADT (10865)'),
    ])
    expect(rows[1]!.text()).toContain('Height 735 m (+67 m)')
    expect(rows[2]!.text()).toContain('Height 614 m (−54 m)')
    expect(rows[3]!.text()).toContain('Height 515 m (−153 m)')
    // the one shown is marked for assistive technology and has no button; the others have one named for their station
    expect(rows[0]!.attributes('aria-current')).toBe('true')
    expect(rows[0]!.find('button').exists()).toBe(false)
    expect(rows[1]!.find('button').attributes('aria-label')).toBe('Show the forecast of TEGERNSEE (M0818)')
    expect(wrapper.text()).toContain('A place has no height of its own')
  })

  it('says a height that is not given, and tells no difference for it', async () => {
    const wrapper = await mountStations({ near: stationsNear(BAD_TOELZ, [station('A', 'A', 47.77, 11.55, 668), station('B', 'B', 47.7, 11.6, null)]) })
    expect(wrapper.findAll('li')[1]!.text()).toContain('Height not given')
    expect(wrapper.findAll('li')[1]!.text()).not.toMatch(/[+−]\d/)
  })

  it('hands over the station of a press, and leaves the place as it is', async () => {
    const wrapper = await mountStations()
    await wrapper.findAll('li')[1]!.find('button').trigger('click')
    expect(wrapper.emitted('pick')![0]![0]).toMatchObject({ station_id: 'M0818' })
  })

  it('says plainly that no station is within 50 km, names the nearest and its distance, and lists it as the station\'s, not the place\'s', async () => {
    const paris = { latitude: 48.8566, longitude: 2.3522 }
    const wrapper = await mountStations({ place: { name: 'Paris', region: 'Île-de-France, France', ...paris }, near: stationsNear(paris, STATIONS), selectedId: undefined })
    const summary = wrapper.find('[data-testid="place-summary"]').text()
    expect(summary).toContain('No forecast station is within 50 km of Paris.')
    // the nearest of the stations of this test, which are all in Bavaria, to Paris
    expect(summary).toMatch(/The nearest, [A-Z -]+ \([A-Z0-9]+\), is \d+ km away/)
    expect(summary).toContain('so its forecast is not the forecast of Paris and none is shown.')
    const rows = wrapper.findAll('[data-testid="place-station-list"] li')
    expect(rows).toHaveLength(1)
    expect(rows[0]!.text()).not.toContain('closest')
    const button = rows[0]!.find('button')
    expect(button.text()).toBe('Show anyway')
    expect(button.attributes('aria-label')).toMatch(/^Show the forecast of [A-Z -]+ \([A-Z0-9]+\) anyway: it is not the forecast of Paris$/)
    expect(wrapper.text()).not.toContain('A place has no height')
  })

  it('says so where there is no station at all, while it looks, and where it could not', async () => {
    const empty = await mountStations({ near: [] })
    expect(empty.find('[data-testid="place-summary"]').text()).toBe('No forecast station was found near Bad Tölz.')
    expect(empty.find('[data-testid="place-station-list"]').exists()).toBe(false)
    const loading = await mountStations({ state: 'loading', near: [] })
    expect(loading.find('[data-testid="place-summary"]').text()).toBe('Looking for stations near Bad Tölz …')
    const failed = await mountStations({ state: 'failed', near: [] })
    expect(failed.find('[data-testid="place-summary"]').text()).toContain('could not be looked up')
    expect(failed.find('[data-testid="place-station-list"]').exists()).toBe(false)
  })

  it('shows a place without a region (a country) by its name', async () => {
    const wrapper = await mountStations({ place: { name: 'France', region: null, latitude: 46.2, longitude: 2.2 } })
    expect(wrapper.find('[data-testid="place-region"]').exists()).toBe(false)
  })

  it('shows text as text: a name with markup is not read as markup', async () => {
    const wrapper = await mountStations({ place: { name: '<b id="x">Bad</b>', region: '<i>Bayern</i>', ...BAD_TOELZ } })
    expect(wrapper.find('[data-testid="place-name"]').text()).toBe('<b id="x">Bad</b>')
    expect(wrapper.find('#x').exists()).toBe(false)
  })
})

describe('the credit of the places', () => {
  it('names OpenStreetMap and its licence and Photon, as links that open in a place of their own', async () => {
    const wrapper = await mountSuspended(PlacesCredit)
    expect(wrapper.text()).toBe('© OpenStreetMap contributors (ODbL) · places via Photon')
    const links = wrapper.findAll('a')
    expect(links.map(link => link.attributes('href'))).toEqual(['https://www.openstreetmap.org/copyright', 'https://opendatacommons.org/licenses/odbl/1-0/', 'https://photon.komoot.io'])
    for (const link of links) {
      expect(link.attributes('target')).toBe('_blank')
      expect(link.attributes('rel')).toBe('noopener noreferrer')
    }
  })
})

describe('the field that finds a place', () => {
  async function mountField() {
    const wrapper = await mountSuspended(PlaceField, { props: { label: 'Find a place' }, attachTo: document.body })
    onTestFinished(() => wrapper.unmount())
    return wrapper
  }
  const vm = (wrapper: Awaited<ReturnType<typeof mountField>>) => wrapper.vm as any

  it('has a label that names the combobox', async () => {
    const wrapper = await mountField()
    expect(wrapper.find('label').text()).toBe('Find a place')
    expect(wrapper.find('[data-testid="place-field"]').exists()).toBe(true)
  })

  it('asks for the places of a text from three letters on, a moment after the last key, in the language of the page, and offers them with what they are and where they lie', async () => {
    const wrapper = await mountField()
    vm(wrapper).term = 'ba'
    await new Promise(resolve => setTimeout(resolve, 600))
    expect(placeQueries).toEqual([])
    vm(wrapper).term = 'bad tölz'
    await vi.waitFor(() => expect(placeQueries).toEqual([{ q: 'bad tölz', lang: 'en' }]))
    await vi.waitFor(() => expect(vm(wrapper).items).toHaveLength(2))
    expect(vm(wrapper).items[0]).toMatchObject({ label: 'Bad Tölz', description: 'Town · Bayern, Germany', value: 'N240109189' })
    expect(vm(wrapper).items[1]).toMatchObject({ label: 'Landkreis Bad Tölz-Wolfratshausen', description: 'County · Bayern, Germany' })
  })

  it('asks for no position and no text without three letters', async () => {
    const wrapper = await mountField()
    for (const text of ['47.76 N', 'N 47.7 E', '47°45′N', 'lat 47.7 lon 11.5', 'A12', '10381', 'ab']) {
      vm(wrapper).term = text
      await new Promise(resolve => setTimeout(resolve, 450))
    }
    expect(placeQueries).toEqual([])
  }, 20_000)

  it('hands over the place chosen and keeps no choice of its own', async () => {
    const wrapper = await mountField()
    vm(wrapper).term = 'bad tölz'
    await vi.waitFor(() => expect(vm(wrapper).items).toHaveLength(2))
    vm(wrapper).model = vm(wrapper).items[0]
    expect(wrapper.emitted('pick')![0]![0]).toMatchObject({ id: 'N240109189', name: 'Bad Tölz', latitude: 47.7614, longitude: 11.5583 })
    // the field shows nothing chosen: the tool shows the place
    expect(vm(wrapper).model).toBeUndefined()
  })

  it('says why the list is empty: a hint before three letters, that it is looking, that there is none, that it failed, that it is switched off', async () => {
    const wrapper = await mountField()
    expect(vm(wrapper).emptyText).toBe('Type at least three letters of a name.')
    vm(wrapper).term = 'zzz nothing'
    await vi.waitFor(() => expect(placeQueries).toHaveLength(1))
    await vi.waitFor(() => expect(vm(wrapper).emptyText).toBe('Nothing found'))
    placesMode = 'fail'
    vm(wrapper).term = 'bad t'
    await vi.waitFor(() => expect(vm(wrapper).emptyText).toBe('Places could not be searched just now. Keep typing to try again.'))
    placesMode = 'off'
    vm(wrapper).term = 'paris'
    await vi.waitFor(() => expect(vm(wrapper).emptyText).toBe('The search of places is switched off on this server.'))
    // and asks no more
    vm(wrapper).term = 'berlin'
    await new Promise(resolve => setTimeout(resolve, 700))
    expect(placeQueries.filter(query => query.q === 'berlin')).toEqual([])
  })

  it('says how many places there are in a polite live region, a moment after the last key', async () => {
    const wrapper = await mountField()
    const status = wrapper.find('[data-testid="place-field-results"]')
    expect(status.attributes('role')).toBe('status')
    expect(status.attributes('aria-live')).toBe('polite')
    vm(wrapper).term = 'bad tölz'
    await vi.waitFor(() => expect(status.text()).toBe('2 results'), { timeout: 4000 })
  })
})

describe('the station search that also finds places', () => {
  async function mountPicker(props: Record<string, unknown> = {}) {
    const wrapper = await mountSuspended(StationPicker as any, {
      props: { tool: 'forecast', stations: STATIONS, selected: [], places: true, ...props },
      attachTo: document.body,
    })
    onTestFinished(() => wrapper.unmount())
    return wrapper
  }
  const vm = (wrapper: Awaited<ReturnType<typeof mountPicker>>) => wrapper.vm as any
  const labels = (items: Array<{ label: string, type?: string }>) => items.map(item => item.type ? `[${item.label}]` : item.label)

  it('lists the stations only, as before, until a text of three letters has places', async () => {
    const wrapper = await mountPicker()
    expect(vm(wrapper).items.map((item: { value: string }) => item.value)).toEqual(['M0814', 'M0818', 'M0816', '10865', '10147'])
    vm(wrapper).searchTerm = 'te'
    await new Promise(resolve => setTimeout(resolve, 600))
    expect(placeQueries).toEqual([])
    // the menu's own filter is off, so the stations the text keeps are kept here (accents and case apart)
    expect(labels(vm(wrapper).items)).toEqual(['TEGERNSEE (ID: M0818)', 'HAMBURG-FUHLSBUETTEL (ID: 10147)'])
  })

  it('puts the places before the stations, under headings, once the text has places', async () => {
    const wrapper = await mountPicker()
    vm(wrapper).searchTerm = 'bad tölz'
    await vi.waitFor(() => expect(placeQueries).toEqual([{ q: 'bad tölz', lang: 'en' }]))
    await vi.waitFor(() => expect(labels(vm(wrapper).items)[0]).toBe('[Places]'))
    // no station is named "Tölz" (the one of the list spells it "TOELZ"), and a heading with nothing under it is left out
    expect(labels(vm(wrapper).items)).toEqual(['[Places]', 'Bad Tölz', 'Landkreis Bad Tölz-Wolfratshausen'])
    expect(vm(wrapper).items[1]).toMatchObject({ description: 'Town · Bayern, Germany', value: 'place:N240109189' })
    // the credit that OpenStreetMap's licence asks for is under the list, and the count is said
    expect(vm(wrapper).resultCount).toBe(2)
  })

  it('hands the place chosen to the caller and picks no station by it', async () => {
    const wrapper = await mountPicker()
    vm(wrapper).searchTerm = 'bad tölz'
    await vi.waitFor(() => expect(vm(wrapper).placeItems).toHaveLength(2))
    vm(wrapper).selectedItems = vm(wrapper).items[1]
    expect(wrapper.emitted('update:place')![0]![0]).toMatchObject({ id: 'N240109189', name: 'Bad Tölz', latitude: 47.7614, longitude: 11.5583 })
    expect(wrapper.emitted('update:selected')).toBeUndefined()
  })

  it('still picks a station of the list', async () => {
    const wrapper = await mountPicker()
    vm(wrapper).selectedItems = { label: 'TEGERNSEE', value: 'M0818' }
    expect(wrapper.emitted('update:selected')![0]![0]).toEqual([STATIONS[1]])
    expect(wrapper.emitted('update:place')).toBeUndefined()
  })

  it('offers no places where the picker is not asked to, and asks for none', async () => {
    const wrapper = await mountPicker({ places: false })
    vm(wrapper).searchTerm = 'bad tölz'
    await new Promise(resolve => setTimeout(resolve, 700))
    expect(placeQueries).toEqual([])
    expect(vm(wrapper).placeItems).toEqual([])
  })

  it('asks for no places on the map, where there is no search', async () => {
    const wrapper = await mountPicker()
    await wrapper.findAll('[role="radio"]').find(radio => radio.text() === 'Map')!.trigger('click')
    await nextTick()
    vm(wrapper).searchTerm = 'bad tölz'
    await new Promise(resolve => setTimeout(resolve, 700))
    expect(placeQueries).toEqual([])
  })

  it('leaves the stations as they are where the places could not be searched, and says so', async () => {
    placesMode = 'fail'
    const wrapper = await mountPicker()
    vm(wrapper).searchTerm = 'tegernsee'
    await vi.waitFor(() => expect(placeQueries).toHaveLength(1))
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(labels(vm(wrapper).items)).toEqual(['TEGERNSEE (ID: M0818)'])
    expect(vm(wrapper).placesFailed).toBe(true)
  })

  it('shows no places and asks no more where the operator has switched the search off', async () => {
    placesMode = 'off'
    const wrapper = await mountPicker()
    vm(wrapper).searchTerm = 'bad tölz'
    await vi.waitFor(() => expect(placeQueries).toHaveLength(1))
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(vm(wrapper).placeItems).toEqual([])
    vm(wrapper).searchTerm = 'paris'
    await new Promise(resolve => setTimeout(resolve, 700))
    expect(placeQueries).toHaveLength(1)
  })

  it('has a live region for how many results the text has, for the picker that finds places', async () => {
    const wrapper = await mountPicker()
    const region = wrapper.find('[data-testid="station-picker-results"]')
    expect(region.attributes('role')).toBe('status')
    expect(region.attributes('aria-live')).toBe('polite')
    const without = await mountPicker({ places: false })
    expect(without.find('[data-testid="station-picker-results"]').exists()).toBe(false)
  })
})
