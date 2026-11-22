import type { DOMWrapper } from '@vue/test-utils'
import { mockNuxtImport, mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { setResponseStatus } from 'h3'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData } from '#app'
import AppCommandPalette from '~/components/AppCommandPalette.vue'
import { DEFAULT_PLACE } from '~/composables/usePlace'
import { providersAnswer } from '../fixtures/providers'

// The command palette of the search (GH-3518): the ARIA combobox with a listbox, its keys, and what it finds.

// where a choice of the palette goes: the router is not asked to load the page
const { navigateTo } = vi.hoisted(() => ({ navigateTo: vi.fn() }))
mockNuxtImport('navigateTo', () => navigateTo)

registerEndpoint('/api/providers', () => providersAnswer())
// the glossary, as the backend answers it, cut down to what the search reads; counted, since it is asked for when the search opens and not before
let glossaryRequests = 0
registerEndpoint('/api/glossary', () => {
  glossaryRequests++
  return [
    { name: 'temperature_dew_point_mean_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'The temperature at which the air is saturated with water vapour' },
    { name: 'temperature_air_mean_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Mean temperature of the air two metres above the ground' },
    { name: 'temperature_air_max_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Highest temperature of the air two metres above the ground' },
    { name: 'temperature_air_min_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Lowest temperature of the air two metres above the ground' },
    { name: 'temperature_soil_mean_0_05m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Mean temperature of the soil at five centimetres' },
    { name: 'temperature_wet_mean_2m', unit_type: 'temperature', unit: 'degree_celsius', unit_symbol: '°C', description: 'Wet-bulb temperature two metres above the ground' },
    { name: 'wind_speed', unit_type: 'speed', unit: 'meter_per_second', unit_symbol: 'm/s', description: 'Mean speed of the wind' },
  ]
})
const stationQueries: string[] = []
const stationNetworks: string[] = []
let failStations = false
registerEndpoint('/api/stations', (event) => {
  if (failStations) {
    setResponseStatus(event, 500)
    return { detail: 'down' }
  }
  const query = new URL(event.path, 'http://localhost').searchParams
  const name = query.get('name') ?? ''
  stationQueries.push(name)
  stationNetworks.push(`${query.get('provider')}/${query.get('network')}`)
  // the measuring stations, as the places of the questions are looked for: one that reports and one that stopped
  if (query.get('network') === 'observation') {
    return {
      stations: [
        { station_id: '00183', name: 'Arkona', region: 'Mecklenburg-Vorpommern', latitude: 54.68, longitude: 13.43, elevation: 42, start_timestamp: '1991-01-01T00:00:00+00:00', end_timestamp: null },
        { station_id: '00198', name: 'Artern', region: 'Thüringen', latitude: 51.37, longitude: 11.29, elevation: 164, start_timestamp: '1991-01-01T00:00:00+00:00', end_timestamp: '2018-12-31T00:00:00+00:00' },
      ],
    }
  }
  return { stations: [{ station_id: '10384', name: 'BERLIN-TEMPELHOF', region: null, latitude: 52.47, longitude: 13.4, elevation: 49, start_timestamp: null, end_timestamp: null }] }
})

const mounted: Array<{ unmount: () => void }> = []
async function mountPalette() {
  const wrapper = await mountSuspended(AppCommandPalette, { attachTo: document.body })
  mounted.push(wrapper)
  return wrapper
}

afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  clearNuxtData()
  stationQueries.length = 0
  stationNetworks.length = 0
  failStations = false
  navigateTo.mockClear()
})

describe('the command palette', () => {
  it('has a button that closes it, for a touch screen reader that cannot reach the overlay', async () => {
    const wrapper = await mountPalette()
    const close = wrapper.find('[data-testid="palette-close"]')
    expect(close.attributes('aria-label')).toBe('Close')
    await close.trigger('click')
    expect(wrapper.emitted('done')).toHaveLength(1)
  })

  it('is a combobox that controls a named listbox of grouped, named options', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    const list = wrapper.find('[role="listbox"]')
    expect(input.attributes('aria-label')).toBe('Search')
    expect(input.attributes('aria-expanded')).toBe('true')
    expect(input.attributes('aria-autocomplete')).toBe('list')
    expect(input.attributes('aria-controls')).toBe(list.attributes('id'))
    expect(list.attributes('aria-label')).toBe('Results')
    const groups = list.findAll('[role="group"]')
    expect(groups.length).toBeGreaterThan(3)
    for (const group of groups)
      expect(wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text()).not.toBe('')
    // the first option is the active one, and the field says so
    const options = list.findAll('[role="option"]')
    expect(options[0]!.attributes('aria-selected')).toBe('true')
    expect(input.attributes('aria-activedescendant')).toBe(options[0]!.attributes('id'))
    expect(options.filter(option => option.attributes('aria-selected') === 'true')).toHaveLength(1)
  })

  it('lists every page with the line that says what it is for', async () => {
    const wrapper = await mountPalette()
    const text = wrapper.find('[role="listbox"]').text()
    for (const label of ['Forecast', 'Explorer', 'Climate stripes', 'History', 'Providers', 'Glossary', 'API', 'Home', 'About', 'Support', 'Settings', 'Legal notice', 'Privacy'])
      expect(text, label).toContain(label)
    expect(text).toContain('See a multi-day forecast for your location.')
    expect(text).toContain('Who runs this site, and how to reach them')
  })

  it('lists the map among the tools, with the line that says what it is for, and opens it', async () => {
    const wrapper = await mountPalette()
    const tools = wrapper.findAll('[role="group"]').find(group => group.text().includes('Climate stripes'))!
    const map = tools.findAll('[role="option"]').find(option => option.text().startsWith('Map'))!
    expect(map.text()).toContain('Pick a station or any point on the map for its forecast, climate stripes and measurements.')
    await map.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/map')
  })

  it('finds a station by name and offers to open the map on it, beside its forecast', async () => {
    // real timers: Vue ignores a click whose time stamp is earlier than the moment its handler was attached, which a
    // clock that was faked and then restored makes of every click after it
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('berl')
    await vi.waitFor(() => expect(wrapper.text()).toContain('BERLIN-TEMPELHOF'))
    const groups = wrapper.findAll('[role="group"]')
    const onMap = groups.find(group => group.text().includes('Show station 10384 on the map'))!
    // a group of its own, named for what it does, right after the forecast of the station
    expect(wrapper.find(`[id="${onMap.attributes('aria-labelledby')}"]`).text()).toBe('Station on the map')
    expect(groups.indexOf(onMap)).toBe(groups.findIndex(group => group.text().includes('Forecast for station 10384')) + 1)
    await onMap.find('[role="option"]').trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/map?station=10384')
  })

  it('moves the active option with the arrow keys, round the ends', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    const options = () => wrapper.findAll('[role="option"]')
    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(input.attributes('aria-activedescendant')).toBe(options()[1]!.attributes('id'))
    await input.trigger('keydown', { key: 'ArrowUp' })
    await input.trigger('keydown', { key: 'ArrowUp' })
    expect(input.attributes('aria-activedescendant')).toBe(options().at(-1)!.attributes('id'))
  })

  it('filters as one types, says how many it found, and is done on Enter', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('glos')
    const options = wrapper.findAll('[role="option"]')
    expect(options[0]!.text()).toContain('Glossary')
    expect(wrapper.find('[role="status"]').text()).toMatch(/^\d+ results?/)
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('done')).toHaveLength(1)
  })

  it('changes the theme', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('dark')
    const option = wrapper.findAll('[role="option"]').find(candidate => candidate.text().includes('Dark'))!
    await option.trigger('click')
    expect(useColorMode().preference).toBe('dark')
    useColorMode().preference = 'system'
  })

  it('finds the forecast of a station by its name from three letters on, asking the backend once the typing stops', async () => {
    vi.useFakeTimers()
    try {
      const wrapper = await mountPalette()
      const input = wrapper.find('input[role="combobox"]')
      await input.setValue('be')
      await vi.advanceTimersByTimeAsync(400)
      expect(stationQueries).toEqual([])
      expect(wrapper.find('[role="status"]').text()).toContain('Type three letters or more')
      await input.setValue('ber')
      await input.setValue('berl')
      await vi.advanceTimersByTimeAsync(400)
      vi.useRealTimers()
      await vi.waitFor(() => expect(wrapper.text()).toContain('BERLIN-TEMPELHOF'))
      expect(stationQueries).toEqual(['berl'])
      expect(wrapper.text()).toContain('Forecast for station 10384')
    }
    finally {
      vi.useRealTimers()
    }
  })

  it('says so where nothing matches, and the field then controls no list', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('zzzqqq')
    expect(wrapper.text()).toContain('Nothing found')
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    expect(input.attributes('aria-expanded')).toBe('false')
    expect(input.attributes('aria-controls')).toBeUndefined()
  })
})

// The words of the app, a position and the questions (GH-3790)
describe('the command palette finding the words of the app', () => {
  const groupOf = (wrapper: Awaited<ReturnType<typeof mountPalette>>, label: string) =>
    wrapper.findAll('[role="group"]').find(group => wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text() === label)
  const headings = (wrapper: Awaited<ReturnType<typeof mountPalette>>) =>
    wrapper.findAll('[role="group"]').map(group => wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text())
  const optionsOf = (group: DOMWrapper<Element> | undefined) => group?.findAll('[role="option"]') ?? []
  // the index of the pages is a chunk that is loaded when the search opens: the results come once it is there
  const typed = async (wrapper: Awaited<ReturnType<typeof mountPalette>>, text: string, until: string) => {
    await wrapper.find('input[role="combobox"]').setValue(text)
    await vi.waitFor(() => expect(wrapper.text()).toContain(until), { timeout: 5000 })
  }

  it('asks for the glossary when the search is opened, and once for the visit', async () => {
    const wrapper = await mountPalette()
    await vi.waitFor(() => expect(glossaryRequests).toBeGreaterThan(0))
    const asked = glossaryRequests
    // the next opening has it already
    const again = await mountPalette()
    await again.find('input[role="combobox"]').setValue('dew point')
    await vi.waitFor(() => expect(again.text()).toContain('Dew point (2 m)'))
    expect(glossaryRequests).toBe(asked)
    // the first open lists the pages and the actions: the words are for a text that is typed
    expect(headings(wrapper)).not.toContain('Glossary')
    expect(headings(wrapper)).not.toContain('Ask the weather')
  })

  it('finds an entry of "How weather is measured" and leads to it at its anchor', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'dew point', 'Humidity and dew point')
    const group = groupOf(wrapper, 'How weather is measured')!
    const option = optionsOf(group)[0]!
    expect(option.text()).toContain('Humidity and dew point')
    await option.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/measurement#humidity')
  })

  it('finds the glossary by the label the reader sees, the name and the description, and leads to the entry', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'dew point', 'Dew point (2 m)')
    const option = optionsOf(groupOf(wrapper, 'Glossary'))[0]!
    expect(option.text()).toContain('Dew point (2 m)')
    await option.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/glossary#temperature_dew_point_mean_2m')
  })

  it('shows a few results of a group with a last option that opens the page that has them all', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'units', 'Convert units')
    const group = groupOf(wrapper, 'Settings')!
    const options = optionsOf(group)
    // three settings and the way on, not the eighteen rows of the page
    expect(options).toHaveLength(4)
    expect(options.at(-1)!.text()).toMatch(/^\d+ more in Settings/)
    await options.at(-1)!.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/settings')
  })

  it('leads a setting to its own anchor', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'plain-language', 'Plain-language labels')
    await optionsOf(groupOf(wrapper, 'Settings'))[0]!.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/settings#settings-friendly-labels')
  })

  it('leads the more of the glossary to the glossary with what was typed', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'temperature', 'more in Glossary')
    const options = optionsOf(groupOf(wrapper, 'Glossary'))
    await options.at(-1)!.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/glossary?q=temperature')
  })

  it('finds the cards of About and Support among the pages of the project', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'donations', 'Support the project')
    const project = groupOf(wrapper, 'Project')!
    const card = optionsOf(project).find(option => option.text().includes('Support the project') && option.text().includes('donations'))!
    await (card).trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/support#support-donate')
  })

  it('finds the questions of Ask the weather and opens the question on the home page', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'rain', 'Will it rain')
    const group = groupOf(wrapper, 'Ask the weather')!
    const option = (optionsOf(group))[0]!
    expect(option.text()).toContain('rain')
    await option.trigger('click')
    expect(navigateTo).toHaveBeenCalledWith('/?ask=rain')
  })

  it('shows a position that is typed as a place that leads to the map at that point, before everything else', async () => {
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('52.52, 13.40')
    await vi.waitFor(() => expect(headings(wrapper)).toContain('Place'))
    expect(headings(wrapper)[0]).toBe('Place')
    const option = optionsOf(groupOf(wrapper, 'Place'))
    expect(option).toHaveLength(1)
    expect(option[0]!.text()).toContain('52.5200, 13.4000')
    expect(option[0]!.text()).toContain('Show this point on the map')
    // it is the active one, so Enter takes it
    await wrapper.find('input[role="combobox"]').trigger('keydown', { key: 'Enter' })
    expect(navigateTo).toHaveBeenCalledWith('/map?lat=52.5200&lon=13.4000')
  })

  it('reads the hemisphere letters, and shows no place for a text that is no position', async () => {
    const wrapper = await mountPalette()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('52°31\'N 13°24\'E')
    await vi.waitFor(() => expect(headings(wrapper)).toContain('Place'))
    expect(wrapper.text()).toContain('52.5167, 13.4000')
    await input.setValue('glossary')
    await vi.waitFor(() => expect(headings(wrapper)).not.toContain('Place'))
  })

  it('puts a point first, then the stations, then the pages of the tools, then the words of the app', async () => {
    const wrapper = await mountPalette()
    // a text that is a position, a forecast and a glossary word at once would be odd: the order is the list of GROUP_ORDER, held here by what a query gives
    await typed(wrapper, 'forecast', 'BERLIN-TEMPELHOF')
    await vi.waitFor(() => expect(headings(wrapper)).toContain('How weather is measured'))
    const order = headings(wrapper)
    expect(order.indexOf('Forecast for a station')).toBeLessThan(order.indexOf('Station on the map'))
    expect(order.indexOf('Station on the map')).toBeLessThan(order.indexOf('Tools'))
    expect(order.indexOf('Tools')).toBeLessThan(order.indexOf('How weather is measured'))
  })

  it('puts a page that its name finds before the words of the app that mention it, whenever the index of the words arrives', async () => {
    const wrapper = await mountPalette()
    await wrapper.find('input[role="combobox"]').setValue('glossary')
    // the page is there at once; the entries that say the word come when the index is there, and after it
    const pageFirst = () => wrapper.findAll('[role="group"]').find(group => group.text().includes('What each parameter measures'))
    expect(pageFirst()).toBeDefined()
    await vi.waitFor(() => expect(headings(wrapper)).toContain('How weather is measured'), { timeout: 5000 })
    const order = headings(wrapper)
    expect(order.indexOf('Reference')).toBeGreaterThan(-1)
    expect(order.indexOf('Reference')).toBeLessThan(order.indexOf('How weather is measured'))
  })

  it('says how many results each group has, in the live region', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'dew point', 'Humidity and dew point')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Dew point (2 m)'))
    const status = wrapper.find('[role="status"]').text()
    expect(status).toMatch(/^\d+ results?\. /)
    expect(status).toMatch(/How weather is measured: \d+/)
    expect(status).toMatch(/Glossary: \d+/)
  })

  it('names every group, so that a screen reader announces its heading', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'temperature', 'Glossary')
    for (const group of wrapper.findAll('[role="group"]'))
      expect(wrapper.find(`[id="${group.attributes('aria-labelledby')}"]`).text(), group.html()).not.toBe('')
  })

  it('keeps the combobox pattern: one active option, which the field names, across the new groups', async () => {
    const wrapper = await mountPalette()
    await typed(wrapper, 'temperature', 'Glossary')
    const input = wrapper.find('input[role="combobox"]')
    const options = wrapper.findAll('[role="option"]')
    expect(options.filter(option => option.attributes('aria-selected') === 'true')).toHaveLength(1)
    expect(input.attributes('aria-activedescendant')).toBe(options[0]!.attributes('id'))
    await input.trigger('keydown', { key: 'ArrowUp' })
    expect(input.attributes('aria-activedescendant')).toBe(options.at(-1)!.attributes('id'))
  })
})

// In its place mode the palette is the search of the place the home page's questions are about (GH-3518)
describe('the command palette as the search of a place', () => {
  async function mountPlaces() {
    const wrapper = await mountSuspended(AppCommandPalette, { attachTo: document.body, props: { mode: 'place' } })
    mounted.push(wrapper)
    return wrapper
  }

  it('is a combobox named for the place, with nothing to choose until a name is typed', async () => {
    const wrapper = await mountPlaces()
    const input = wrapper.find('input[role="combobox"]')
    expect(input.attributes('aria-label')).toBe('Choose a place')
    expect(input.attributes('placeholder')).toBe('The name of a town or weather station …')
    expect(input.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Type the name of a town or weather station.')
    // none of the pages and settings of the search
    expect(wrapper.text()).not.toContain('Glossary')
  })

  it('finds the measuring stations by name from two letters on, leaves out one that stopped reporting, and makes the one chosen the place', async () => {
    vi.useFakeTimers()
    try {
      usePlace().place.value = DEFAULT_PLACE
      const wrapper = await mountPlaces()
      const input = wrapper.find('input[role="combobox"]')
      await input.setValue('a')
      await vi.advanceTimersByTimeAsync(400)
      expect(stationQueries).toEqual([])
      await input.setValue('ar')
      await vi.advanceTimersByTimeAsync(400)
      vi.useRealTimers()
      await vi.waitFor(() => expect(wrapper.findAll('[role="option"]')).toHaveLength(1))
      expect(stationNetworks).toEqual(['dwd/observation'])
      const option = wrapper.find('[role="option"]')
      expect(option.text()).toContain('Arkona')
      expect(option.text()).toContain('Mecklenburg-Vorpommern')
      expect(wrapper.text()).not.toContain('Artern')
      expect(wrapper.find('[role="group"]').text()).toContain('Weather stations')

      await input.trigger('keydown', { key: 'Enter' })
      expect(usePlace().place.value).toMatchObject({ id: '00183', name: 'Arkona', latitude: 54.68, longitude: 13.43 })
      expect(wrapper.emitted('place')![0]![0]).toMatchObject({ id: '00183' })
      expect(wrapper.emitted('done')).toHaveLength(1)
    }
    finally {
      vi.useRealTimers()
      usePlace().place.value = DEFAULT_PLACE
    }
  })

  it('announces the hint, not the failure of the text before, once the text is too short again', async () => {
    failStations = true
    const wrapper = await mountPlaces()
    const input = wrapper.find('input[role="combobox"]')
    await input.setValue('ar')
    await vi.waitFor(() => expect(wrapper.find('[role="status"]').text()).toContain('could not'), { timeout: 5000 })
    await input.setValue('a')
    await vi.waitFor(() => expect(wrapper.find('[role="status"]').text()).toBe('Type the name of a town or weather station.'), { timeout: 5000 })
  })
})
