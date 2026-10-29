import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { UApp } from '#components'
import { clearNuxtState, useNuxtApp, usePalette, usePlace, useRouter } from '#imports'
import SearchPalette from '~/components/SearchPalette.vue'

// The command palette (components/SearchPalette.vue): an ARIA combobox whose listbox holds the questions, the pages,
// the settings of appearance and language, and the places the backend finds by name. The keys and the focus are
// held in a browser by the keyboard test of tests/e2e/accessibility.spec.ts; this holds what it finds and does.

registerEndpoint('/api/stations', () => ({
  stations: [
    { station_id: '02564', name: 'Kiel-Holtenau', region: 'Schleswig-Holstein', latitude: 54.3776, longitude: 10.1424, elevation: 28, start_timestamp: '1974-01-01T00:00:00+00:00', end_timestamp: null },
    // closed long ago: no weather to ask about
    { station_id: '02565', name: 'Kiel-Kronshagen', region: 'Schleswig-Holstein', latitude: 54.3378, longitude: 10.0929, elevation: 17, start_timestamp: '1940-01-01T00:00:00+00:00', end_timestamp: '1988-10-15T00:00:00+00:00' },
  ],
}))

const Wrapped = defineComponent({ setup: () => () => h(UApp, null, { default: () => h(SearchPalette) }) })

const mounted: Array<{ unmount: () => void }> = []
afterEach(() => {
  mounted.splice(0).forEach(wrapper => wrapper.unmount())
  clearNuxtState(['palette-open', 'palette-scope', 'place'])
  document.body.innerHTML = ''
})

async function openPalette() {
  await useNuxtApp().$i18n.setLocale('en')
  const wrapper = await mountSuspended(Wrapped, { attachTo: document.body })
  mounted.push(wrapper)
  usePalette().openPalette()
  const input = await vi.waitFor(() => {
    const found = document.querySelector<HTMLInputElement>('[data-testid="palette-input"]')
    expect(found).not.toBeNull()
    return found!
  })
  return input
}

async function type(input: HTMLInputElement, text: string) {
  input.value = text
  input.dispatchEvent(new Event('input'))
  await nextTick()
}

const options = () => [...document.querySelectorAll('[role="option"]')]
const labels = () => options().map(option => option.querySelector('.font-medium')?.textContent?.trim())

describe('the command palette', () => {
  it('is a combobox that controls a listbox of named options, the first of them active', async () => {
    const input = await openPalette()
    expect(input.getAttribute('role')).toBe('combobox')
    expect(input.getAttribute('aria-expanded')).toBe('true')
    const list = document.getElementById(input.getAttribute('aria-controls')!)!
    expect(list.getAttribute('role')).toBe('listbox')
    expect(input.getAttribute('aria-activedescendant')).toBe(options()[0]!.id)
    expect(options()[0]!.getAttribute('aria-selected')).toBe('true')
    // the groups are named by their heading
    for (const group of list.querySelectorAll('[role="group"]'))
      expect(document.getElementById(group.getAttribute('aria-labelledby')!)?.textContent?.trim()).toBeTruthy()
  })

  it('lists the questions, every page with a line on what it is for, and the appearance and language settings', async () => {
    await openPalette()
    expect(labels()).toContain('Will it rain in Kiel-Holtenau tomorrow?')
    for (const page of ['Ask', 'Forecast', 'Climate stripes', 'Explorer', 'History', 'Providers', 'Glossary', 'API', 'Settings', 'About', 'Support', 'Legal notice', 'Privacy'])
      expect(labels()).toContain(page)
    expect(labels()).toContain('Appearance: Dark')
    expect(labels().filter(label => label?.startsWith('Language: '))).toHaveLength(11)
    expect(options().every(option => option.textContent!.trim().length > 0)).toBe(true)
  })

  it('narrows by every word typed, ignoring case and accents, and moves by the arrow keys', async () => {
    const input = await openPalette()
    await type(input, 'GLOSS')
    expect(labels()).toEqual(['Glossary'])
    await type(input, 'cestina')
    expect(labels()).toEqual(['Language: 🇨🇿 Čeština'])
    await type(input, 'appearance:')
    expect(labels()).toHaveLength(3)
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown' }))
    await nextTick()
    expect(input.getAttribute('aria-activedescendant')).toBe(options()[1]!.id)
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp' }))
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp' }))
    await nextTick()
    // round from the first to the last
    expect(input.getAttribute('aria-activedescendant')).toBe(options()[2]!.id)
  })

  it('says when nothing is found, and leaves the listbox out', async () => {
    const input = await openPalette()
    // one letter, which no entry has and which is too short to be looked for among the places
    await type(input, 'ж')
    await vi.waitFor(() => expect(document.querySelector('[data-testid="palette-status"]')!.textContent).toContain('Nothing found.'))
    expect(input.getAttribute('aria-expanded')).toBe('false')
    expect(input.hasAttribute('aria-activedescendant')).toBe(false)
  })

  it('finds places by name, leaves out a station closed long ago, and asks about the one chosen', async () => {
    const input = await openPalette()
    await type(input, 'kiel')
    await vi.waitFor(() => expect(labels()).toContain('Kiel-Holtenau'), { timeout: 3000 })
    expect(labels()).not.toContain('Kiel-Kronshagen')
    const push = vi.spyOn(useRouter(), 'push')
    // the places come first: Enter runs the active one
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
    await vi.waitFor(() => expect(push).toHaveBeenCalledWith({ path: '/', query: { place: '02564' } }))
    expect(usePlace().place.value.name).toBe('Kiel-Holtenau')
    expect(usePalette().open.value).toBe(false)
  })

  it('opens on Ctrl+K and on ⌘K, and closes on it again', async () => {
    await openPalette()
    usePalette().open.value = false
    await vi.waitFor(() => expect(document.querySelector('[data-testid="palette-input"]')).toBeNull())
    const focused = document.activeElement as HTMLElement | null
    focused?.blur()
    await nextTick()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }))
    expect(usePalette().open.value).toBe(true)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))
    expect(usePalette().open.value).toBe(false)
  })
})
