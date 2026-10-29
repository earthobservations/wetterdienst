import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearNuxtData } from '#app'
import AppCommandPalette from '~/components/AppCommandPalette.vue'
import { providersResponse } from '../fixtures/providers'

// The command palette of the search (GH-3518): the ARIA combobox with a listbox, its keys, and what it finds.

registerEndpoint('/api/providers', () => providersResponse())
const stationQueries: string[] = []
registerEndpoint('/api/stations', (event) => {
  const name = new URL(event.path, 'http://localhost').searchParams.get('name') ?? ''
  stationQueries.push(name)
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
})

describe('the command palette', () => {
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
