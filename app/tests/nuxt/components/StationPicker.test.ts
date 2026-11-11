import type { VueWrapper } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, onTestFinished, vi } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import StationPicker from '~/components/StationPicker.vue'
import { STATION_PICKER_STORAGE_KEY } from '~/utils/station-picker-mode'

// The one station picker of the explorer, the history, the forecast and the stripes (GH-3877): the toggle, its keys,
// the chips in both modes, a pick that shows in the other mode, the mode kept for each tool, and the storage that is
// refused. The map itself is Leaflet, which is no use in this document: a stand-in with its container and its `ready`;
// the map's own drawing is the e2e tests'.

vi.mock('~/components/MapStations.vue', async () => {
  const { defineComponent: define, h: render, onMounted } = await import('vue')
  return {
    // as a module Vue's async component takes the component from
    __esModule: true,
    default: define({
      name: 'MapStationsStub',
      props: ['stations', 'selectedStations', 'multiple'],
      emits: ['update:selectedStations', 'ready'],
      setup(props: { selectedStations: { station_id: string }[] }, { emit }) {
        onMounted(() => emit('ready'))
        return () => render('div', {
          'class': 'leaflet-container',
          'tabindex': 0,
          'data-selected': props.selectedStations.map(station => station.station_id).join(','),
        })
      },
    }),
  }
})

const berlin = { station_id: '00433', name: 'Berlin-Tempelhof', region: 'Berlin', latitude: 52.47, longitude: 13.4 }
const potsdam = { station_id: '03987', name: 'Potsdam', region: 'Brandenburg', latitude: 52.38, longitude: 13.06 }
const hamburg = { station_id: '01975', name: 'Hamburg-Fuhlsbüttel', region: 'Hamburg', latitude: 53.63, longitude: 10.0 }
const stations = [berlin, potsdam, hamburg]

// a generic component's props are not typed here: the stations are of the test's own kind
type Props = Record<string, any>

afterEach(() => {
  vi.unstubAllGlobals()
})

async function mountPicker(props: Partial<Props> = {}, options: Record<string, unknown> = {}) {
  const wrapper = await mountSuspended(StationPicker as any, {
    props: { tool: 'explorer', stations, selected: [], multiple: true, ...props } as Props,
    attachTo: document.body,
    ...options,
  })
  onTestFinished(() => wrapper.unmount())
  return wrapper
}

/**
 * The picker as a page holds it: the picked stations are the page's, handed back as `selected`.
 * Returns the wrapper and the stations the page holds.
 */
async function mountPage(props: { tool?: Props['tool'], multiple?: boolean, selected?: typeof stations } = {}) {
  const picked = ref(props.selected ?? [])
  const Host = defineComponent({
    setup: () => () => h(StationPicker as any, {
      'tool': props.tool ?? 'explorer',
      stations,
      'selected': picked.value,
      'multiple': props.multiple ?? true,
      'onUpdate:selected': (value: typeof stations) => {
        picked.value = value
      },
    }),
  })
  const wrapper = await mountSuspended(Host, { attachTo: document.body })
  onTestFinished(() => wrapper.unmount())
  return { wrapper, picked }
}

const radio = (wrapper: VueWrapper, name: 'List' | 'Map') => wrapper.findAll('[role="radio"]').find(r => r.text() === name)!
const checked = (wrapper: VueWrapper) => wrapper.find('[role="radio"][aria-checked="true"]').text()
const chips = (wrapper: VueWrapper) => wrapper.findAll('[data-station-chip]').map(chip => chip.text())
const mapStub = (wrapper: VueWrapper) => wrapper.findComponent({ name: 'MapStationsStub' })
const picker = (wrapper: VueWrapper) => wrapper.findComponent(StationPicker).vm as any

describe('the station picker\'s toggle', () => {
  it('is a radio group of the list and the map, on the list at first, that controls the one place of the choice', async () => {
    const wrapper = await mountPicker()

    const group = wrapper.find('[role="radiogroup"]')
    expect(group.attributes('aria-label')).toBe('Pick a station from a list or on a map')
    expect(wrapper.findAll('[role="radio"]').map(r => r.text())).toEqual(['List', 'Map'])
    expect(checked(wrapper)).toBe('List')
    // one stop in the tab order: the chosen option
    expect(wrapper.findAll('[role="radio"]').map(r => r.attributes('tabindex'))).toEqual(['0', '-1'])

    // the id every option controls is an element that is there in both modes, which holds the one that is shown
    const controls = new Set(wrapper.findAll('[role="radio"]').map(r => r.attributes('aria-controls')))
    expect(controls.size).toBe(1)
    const id = [...controls][0]!
    expect(document.getElementById(id)).not.toBeNull()
    await radio(wrapper, 'Map').trigger('click')
    expect(document.getElementById(id)).not.toBeNull()
  })

  it('is hidden in print, with the map', async () => {
    const wrapper = await mountPicker()
    expect(wrapper.find('[role="radiogroup"]').element.closest('[data-print="hide"]')).not.toBeNull()
    await radio(wrapper, 'Map').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('.leaflet-container').exists()).toBe(true))
    expect(wrapper.find('.leaflet-container').element.closest('[data-print="hide"]')).not.toBeNull()
  })

  it('has a place for an action beside it', async () => {
    const wrapper = await mountPicker({}, { slots: { actions: () => h('button', { 'data-testid': 'my-location' }, 'Use my location') } })
    const action = wrapper.find('[data-testid="my-location"]')
    expect(action.exists()).toBe(true)
    // in the row of the toggle, not under the choice
    expect(action.element.parentElement).toBe(wrapper.find('[role="radiogroup"]').element.parentElement)
  })
})

describe('the station picker\'s keys', () => {
  async function keys(wrapper: VueWrapper, from: 'List' | 'Map', key: string) {
    await radio(wrapper, from).trigger('keydown', { key })
    await nextTick()
    await nextTick()
  }

  it('moves from option to option with the arrow keys, round the ends, and keeps the focus on the toggle', async () => {
    const wrapper = await mountPicker()
    ;(radio(wrapper, 'List').element as HTMLElement).focus()

    await keys(wrapper, 'List', 'ArrowRight')
    expect(checked(wrapper)).toBe('Map')
    expect(document.activeElement).toBe(radio(wrapper, 'Map').element)
    // not into the map: the keys walk along the toggle, and a Tab goes on into the map
    await vi.waitFor(() => expect(wrapper.find('.leaflet-container').exists()).toBe(true))
    expect(document.activeElement).not.toBe(wrapper.find('.leaflet-container').element)

    await keys(wrapper, 'Map', 'ArrowRight')
    expect(checked(wrapper)).toBe('List')
    await keys(wrapper, 'List', 'ArrowLeft')
    expect(checked(wrapper)).toBe('Map')
    await keys(wrapper, 'Map', 'Home')
    expect(checked(wrapper)).toBe('List')
    await keys(wrapper, 'List', 'End')
    expect(checked(wrapper)).toBe('Map')
    expect(document.activeElement).toBe(radio(wrapper, 'Map').element)
  })

  it('moves the focus into the map where the map is chosen by a click, and into the search where the list is', async () => {
    const wrapper = await mountPicker()

    await radio(wrapper, 'Map').trigger('click')
    await vi.waitFor(() => expect(document.activeElement).toBe(wrapper.find('.leaflet-container').element))

    await radio(wrapper, 'List').trigger('click')
    // the search's own button, which is what Tab reaches first in it
    await vi.waitFor(() => {
      const search = wrapper.find(`[id="${wrapper.find('[role="radio"]').attributes('aria-controls')}"] button`)
      expect(search.exists()).toBe(true)
      expect(document.activeElement).toBe(search.element)
    })
  })

  it('takes the focus into a map that is not there yet as soon as it is', async () => {
    // the map's code and the stations are on their way: the focus waits for them
    const wrapper = await mountPicker({ stations: [], loading: true })
    await radio(wrapper, 'Map').trigger('click')
    expect(wrapper.find('.leaflet-container').exists()).toBe(false)
    expect(wrapper.text()).toContain('Loading stations')

    await wrapper.setProps({ stations, loading: false })
    await vi.waitFor(() => expect(document.activeElement).toBe(wrapper.find('.leaflet-container').element))
  })

  it('does not take the focus into a map that arrives after the reader has gone on to something else', async () => {
    const wrapper = await mountPicker({ stations: [], loading: true })
    const elsewhere = document.createElement('button')
    document.body.append(elsewhere)
    onTestFinished(() => elsewhere.remove())
    await radio(wrapper, 'Map').trigger('click')
    // the focus left the picker for the page while the map was on its way
    elsewhere.focus()
    await nextTick()

    await wrapper.setProps({ stations, loading: false })
    await vi.waitFor(() => expect(wrapper.find('.leaflet-container').exists()).toBe(true))
    await nextTick()
    expect(document.activeElement).toBe(elsewhere)
  })

  it('drops the ask for the map\'s focus where the focus leaves the picker, so that a later map does not take it', async () => {
    const wrapper = await mountPicker({ stations: [], loading: true })
    await radio(wrapper, 'Map').trigger('click')
    const elsewhere = document.createElement('button')
    document.body.append(elsewhere)
    onTestFinished(() => elsewhere.remove())
    // out of the picker, and back into it by the toggle, which is not a switch
    await wrapper.find('[data-testid="station-picker"]').trigger('focusout', { relatedTarget: elsewhere })
    ;(radio(wrapper, 'Map').element as HTMLElement).focus()

    await wrapper.setProps({ stations, loading: false })
    await vi.waitFor(() => expect(wrapper.find('.leaflet-container').exists()).toBe(true))
    await nextTick()
    expect(document.activeElement).toBe(radio(wrapper, 'Map').element)
  })

  it('does not scroll the page to what a click of the pointer focuses, as a key does', async () => {
    const focus = vi.spyOn(HTMLElement.prototype, 'focus')
    onTestFinished(() => focus.mockRestore())
    const wrapper = await mountPicker()
    await radio(wrapper, 'Map').trigger('click', { detail: 1 })
    await vi.waitFor(() => expect(focus.mock.contexts.some(el => (el as HTMLElement).classList?.contains('leaflet-container'))).toBe(true))
    const mapCall = focus.mock.calls[focus.mock.contexts.findIndex(el => (el as HTMLElement).classList?.contains('leaflet-container'))]!
    expect(mapCall[0]).toEqual({ preventScroll: true })

    focus.mockClear()
    await radio(wrapper, 'List').trigger('click', { detail: 0 })
    await vi.waitFor(() => expect(focus.mock.calls.some(call => call[0] && (call[0] as FocusOptions).preventScroll === false)).toBe(true))
  })

  it('tells a screen reader what the mode it was changed to does, and nothing before it is changed', async () => {
    const wrapper = await mountPicker({ multiple: true })
    const status = () => wrapper.find('[role="status"]').text()
    expect(status()).toBe('')

    await radio(wrapper, 'Map').trigger('click')
    expect(status()).toBe('Tap markers on the map to add or remove stations.')

    await radio(wrapper, 'List').trigger('click')
    expect(status()).toBe('Station search')
  })
})

describe('the station picker\'s modes', () => {
  it('loads the map only where it is shown, and says what a tap does: for several stations, or for one', async () => {
    const wrapper = await mountPicker({ multiple: true })
    expect(wrapper.find('.leaflet-container').exists()).toBe(false)
    expect(wrapper.find('[data-testid="station-picker-map-hint"]').exists()).toBe(false)

    await radio(wrapper, 'Map').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('.leaflet-container').exists()).toBe(true))
    expect(wrapper.find('[data-testid="station-picker-map-hint"]').text()).toBe('Tap markers on the map to add or remove stations.')
    // the search is not there beside it
    expect(wrapper.find('[role="combobox"]').exists()).toBe(false)

    await wrapper.setProps({ multiple: false })
    expect(wrapper.find('[data-testid="station-picker-map-hint"]').text()).toBe('Tap a marker on the map to pick that station.')
  })

  it('says the mode it is in, once on setup and for each change, for a caller that fetches the list by it', async () => {
    const wrapper = await mountPicker()
    expect(wrapper.emitted('update:mode')).toEqual([['list']])
    await radio(wrapper, 'Map').trigger('click')
    await radio(wrapper, 'List').trigger('click')
    expect(wrapper.emitted('update:mode')).toEqual([['list'], ['map'], ['list']])
  })

  it('keeps the chips in both modes, and what is picked on the map is in the list', async () => {
    const { wrapper, picked } = await mountPage()
    expect(chips(wrapper)).toEqual([])

    await radio(wrapper, 'Map').trigger('click')
    await vi.waitFor(() => expect(mapStub(wrapper).exists()).toBe(true))
    mapStub(wrapper).vm.$emit('update:selectedStations', [berlin])
    await nextTick()
    expect(picked.value).toEqual([berlin])
    expect(chips(wrapper)).toEqual(['Berlin-Tempelhof (00433) ×'])
    expect(mapStub(wrapper).attributes('data-selected')).toBe('00433')

    await radio(wrapper, 'List').trigger('click')
    // the chips stay, and the search has it chosen
    expect(chips(wrapper)).toEqual(['Berlin-Tempelhof (00433) ×'])
    expect(picker(wrapper).selectedItems).toEqual([{ label: 'Berlin-Tempelhof (ID: 00433, Berlin)', value: '00433' }])
  })

  it('shows on the map what is picked in the search', async () => {
    const { wrapper, picked } = await mountPage()

    picker(wrapper).selectedItems = [{ label: 'x', value: '03987' }, { label: 'y', value: '01975' }]
    await nextTick()
    expect(picked.value.map(station => station.station_id)).toEqual(['03987', '01975'])
    expect(chips(wrapper)).toEqual(['Potsdam (03987) ×', 'Hamburg-Fuhlsbüttel (01975) ×'])

    await radio(wrapper, 'Map').trigger('click')
    await vi.waitFor(() => expect(mapStub(wrapper).exists()).toBe(true))
    expect(mapStub(wrapper).attributes('data-selected')).toBe('03987,01975')
    expect(chips(wrapper)).toEqual(['Potsdam (03987) ×', 'Hamburg-Fuhlsbüttel (01975) ×'])
  })

  it('adds the stations tapped on the map for several, and takes the one tapped last for one', async () => {
    const several = await mountPage({ multiple: true })
    await radio(several.wrapper, 'Map').trigger('click')
    await vi.waitFor(() => expect(mapStub(several.wrapper).exists()).toBe(true))
    mapStub(several.wrapper).vm.$emit('update:selectedStations', [berlin, potsdam])
    expect(several.picked.value).toEqual([berlin, potsdam])

    const one = await mountPage({ multiple: false })
    await radio(one.wrapper, 'Map').trigger('click')
    await vi.waitFor(() => expect(mapStub(one.wrapper).exists()).toBe(true))
    mapStub(one.wrapper).vm.$emit('update:selectedStations', [berlin, potsdam])
    expect(one.picked.value).toEqual([potsdam])
  })

  it('takes one station from the search where it is for one, and none where it is cleared', async () => {
    const { wrapper, picked } = await mountPage({ multiple: false })

    picker(wrapper).selectedItems = { label: 'x', value: '03987' }
    await nextTick()
    expect(picked.value).toEqual([potsdam])
    expect(picker(wrapper).selectedItems).toEqual({ label: 'Potsdam (ID: 03987, Brandenburg)', value: '03987' })

    picker(wrapper).selectedItems = undefined
    await nextTick()
    expect(picked.value).toEqual([])
  })

  it('looks a station of the search up among those picked too, where the list has not come in yet', async () => {
    // a station restored from a link is picked before the list is fetched
    const picked = ref([berlin])
    const Host = defineComponent({
      setup: () => () => h(StationPicker as any, {
        'tool': 'explorer',
        'stations': [],
        'selected': picked.value,
        'multiple': true,
        'onUpdate:selected': (value: typeof stations) => {
          picked.value = value
        },
      }),
    })
    const wrapper = await mountSuspended(Host, { attachTo: document.body })
    onTestFinished(() => wrapper.unmount())

    picker(wrapper).selectedItems = [{ label: 'Berlin', value: '00433' }]
    await nextTick()
    expect(picked.value).toEqual([berlin])
  })
})

describe('the station picker\'s chips', () => {
  it('are buttons that take a station out of the choice by their name, in the list and on the map', async () => {
    const { wrapper, picked } = await mountPage({ selected: [berlin, potsdam, hamburg] })
    const first = wrapper.findAll('[data-station-chip]')[0]!
    expect(first.element.tagName).toBe('BUTTON')
    expect(first.attributes('aria-label')).toBe('Remove Berlin-Tempelhof (00433) from the selection')

    await first.trigger('click')
    expect(picked.value).toEqual([potsdam, hamburg])

    await radio(wrapper, 'Map').trigger('click')
    await wrapper.findAll('[data-station-chip]')[1]!.trigger('click')
    expect(picked.value).toEqual([potsdam])
  })

  it('give the focus to the chip that took the removed one\'s place, else to the one before, else to the toggle', async () => {
    const { wrapper, picked } = await mountPage({ selected: [berlin, potsdam, hamburg] })

    await wrapper.findAll('[data-station-chip]')[1]!.trigger('click')
    await vi.waitFor(() => expect(document.activeElement).toBe(wrapper.findAll('[data-station-chip]')[1]!.element))
    expect(chips(wrapper)).toEqual(['Berlin-Tempelhof (00433) ×', 'Hamburg-Fuhlsbüttel (01975) ×'])

    await wrapper.findAll('[data-station-chip]')[1]!.trigger('click')
    await vi.waitFor(() => expect(document.activeElement).toBe(wrapper.findAll('[data-station-chip]')[0]!.element))

    await wrapper.findAll('[data-station-chip]')[0]!.trigger('click')
    expect(picked.value).toEqual([])
    await vi.waitFor(() => expect(document.activeElement).toBe(radio(wrapper, 'List').element))
  })

  it('are cleared all at once for several stations, and the focus goes to the toggle', async () => {
    const { wrapper, picked } = await mountPage({ selected: [berlin, potsdam] })
    expect(wrapper.find('[data-testid="station-picker-chips"] h3').text()).toBe('Selected Stations:')

    await wrapper.findAll('button').find(b => b.text() === 'Clear all')!.trigger('click')
    expect(picked.value).toEqual([])
    expect(wrapper.find('[data-testid="station-picker-chips"]').exists()).toBe(false)
    await vi.waitFor(() => expect(document.activeElement).toBe(radio(wrapper, 'List').element))
  })

  it('are one chip for one station, with no clearing of all', async () => {
    const { wrapper } = await mountPage({ selected: [potsdam], multiple: false })
    expect(wrapper.find('[data-testid="station-picker-chips"] h3').text()).toBe('Selected station:')
    expect(chips(wrapper)).toEqual(['Potsdam (03987) ×'])
    expect(wrapper.findAll('button').some(b => b.text() === 'Clear all')).toBe(false)
  })

  it('name a station without a name by its id', async () => {
    const postcode = { station_id: '01067', name: null, region: null, latitude: null, longitude: null }
    const wrapper = await mountPicker({ selected: [postcode] as any })
    expect(chips(wrapper)).toEqual(['01067 ×'])
  })
})

describe('the station picker\'s label', () => {
  it('is visible, and the search\'s own label where the list is shown', async () => {
    const wrapper = await mountPicker({ label: 'Station' })
    const label = wrapper.find('label')
    expect(label.text()).toBe('Station')
    // tied to the search's button, not to nothing
    const target = document.getElementById(label.attributes('for')!)
    expect(target).not.toBeNull()
    expect(wrapper.find(`[id="${label.attributes('for')}"]`).exists()).toBe(true)

    // the search is not there on the map: the label stays, as text
    await radio(wrapper, 'Map').trigger('click')
    expect(wrapper.find('label').exists()).toBe(false)
    expect(wrapper.text()).toContain('Station')
  })

  it('is not there where none is given', async () => {
    const wrapper = await mountPicker()
    expect(wrapper.find('label').exists()).toBe(false)
  })
})

describe('the station picker\'s messages', () => {
  it('tells a list that could not be fetched, and one that is empty, in both modes', async () => {
    const wrapper = await mountPicker({ stations: [], error: true })
    expect(wrapper.text()).toContain('Failed to load stations')
    await radio(wrapper, 'Map').trigger('click')
    expect(wrapper.text()).toContain('Failed to load stations')

    await wrapper.setProps({ error: false, empty: true })
    expect(wrapper.text()).toContain('No stations found for the selected parameters')
    await wrapper.setProps({ loading: true })
    expect(wrapper.text()).not.toContain('No stations found')
  })
})

describe('the station picker\'s remembered mode', () => {
  it('is kept for the tool, and found again by it, where the other tools keep their own', async () => {
    const wrapper = await mountPicker({ tool: 'stripes', multiple: false })
    expect(checked(wrapper)).toBe('List')

    await radio(wrapper, 'Map').trigger('click')
    expect(JSON.parse(localStorage.getItem(STATION_PICKER_STORAGE_KEY)!)).toEqual({ stripes: 'map' })
    wrapper.unmount()

    const again = await mountPicker({ tool: 'stripes', multiple: false })
    expect(checked(again)).toBe('Map')
    // said at once, so that the caller fetches the list the map needs
    expect(again.emitted('update:mode')).toEqual([['map']])
    await vi.waitFor(() => expect(again.find('.leaflet-container').exists()).toBe(true))

    const other = await mountPicker({ tool: 'forecast', multiple: false })
    expect(checked(other)).toBe('List')
    await radio(other, 'Map').trigger('click')
    expect(JSON.parse(localStorage.getItem(STATION_PICKER_STORAGE_KEY)!)).toEqual({ stripes: 'map', forecast: 'map' })
  })

  it('is not written for the mode the picker starts in, only for the reader\'s change', async () => {
    localStorage.setItem(STATION_PICKER_STORAGE_KEY, JSON.stringify({ explorer: 'map' }))
    await mountPicker({ tool: 'explorer' })
    expect(localStorage.getItem(STATION_PICKER_STORAGE_KEY)).toBe(JSON.stringify({ explorer: 'map' }))
  })

  it.each([
    ['not JSON', 'map'],
    ['an array', '["map"]'],
    ['an unknown mode', '{"explorer":"satellite"}'],
    ['a mode of another type', '{"explorer":true}'],
  ])('starts on the list where what is stored is %s', async (_what, stored) => {
    localStorage.setItem(STATION_PICKER_STORAGE_KEY, stored)
    const wrapper = await mountPicker({ tool: 'explorer' })
    expect(checked(wrapper)).toBe('List')
  })

  describe('where the browser refuses its storage', () => {
    const original = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')

    afterEach(() => {
      if (original)
        Object.defineProperty(globalThis, 'localStorage', original)
      else
        delete (globalThis as any).localStorage
    })

    it('starts on the list and still changes mode, where the storage is blocked altogether', async () => {
      Object.defineProperty(globalThis, 'localStorage', {
        configurable: true,
        get() {
          throw new DOMException('The operation is insecure.', 'SecurityError')
        },
      })
      const wrapper = await mountPicker()
      expect(checked(wrapper)).toBe('List')

      await radio(wrapper, 'Map').trigger('click')
      expect(checked(wrapper)).toBe('Map')
      await vi.waitFor(() => expect(wrapper.find('.leaflet-container').exists()).toBe(true))
    })

    it('starts on the list and still changes mode, where a read and a write fail (a full storage, a private window)', async () => {
      const refuse = () => {
        throw new DOMException('The quota has been exceeded.', 'QuotaExceededError')
      }
      vi.stubGlobal('localStorage', { getItem: refuse, setItem: refuse, removeItem: refuse, clear: refuse })
      const wrapper = await mountPicker()
      expect(checked(wrapper)).toBe('List')

      await radio(wrapper, 'Map').trigger('click')
      expect(checked(wrapper)).toBe('Map')
      await radio(wrapper, 'List').trigger('click')
      expect(checked(wrapper)).toBe('List')
    })
  })
})
