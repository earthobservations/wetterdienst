import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest'
import { clearNuxtState } from '#app'
import UseMyLocation from '~/components/UseMyLocation.vue'
import { LOCATION_STORAGE_KEY } from '~/utils/geolocation'

// "Use my location" (GH-3651, GH-4011, GH-4010): the one component of the station map, "Ask the weather" and the station
// picker. What it shows follows what is in hand and what is stored: only the button at first; after a press, the box
// and its note; once a position is stored, the "Stored" control beside the button instead. The browser's APIs are mocks.

function mockBrowser(fix = { latitude: 53.5512, longitude: 9.9934 }) {
  const getCurrentPosition = vi.fn((success: (position: unknown) => void) => success({ coords: fix }))
  Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition } })
  Object.defineProperty(navigator, 'permissions', { configurable: true, value: { query: vi.fn(async () => ({ state: 'prompt' })) } })
  return getCurrentPosition
}

beforeEach(() => {
  clearNuxtState()
  localStorage.clear()
})
afterEach(() => {
  delete (navigator as any).geolocation
  delete (navigator as any).permissions
  localStorage.clear()
  clearNuxtState()
})

async function mountControl(props: Record<string, unknown> = {}) {
  const wrapper = await mountSuspended(UseMyLocation, { props, attachTo: document.body })
  onTestFinished(() => wrapper.unmount())
  return wrapper
}

type Wrapper = Awaited<ReturnType<typeof mountControl>>
const button = (wrapper: Wrapper) => wrapper.find('[data-testid="use-my-location-button"]')
const box = (wrapper: Wrapper) => wrapper.find('[data-testid="use-my-location-remember"] button[role="checkbox"], button[role="checkbox"]')
const note = (wrapper: Wrapper) => wrapper.find('[data-testid="use-my-location-note"]')
const chip = (wrapper: Wrapper) => wrapper.find('[data-testid="use-my-location-stored"]')
const status = (wrapper: Wrapper) => wrapper.find('[data-testid="use-my-location-status"]')
// the popover's content is teleported to the body
const forgetButton = () => document.body.querySelector<HTMLButtonElement>('[data-testid="use-my-location-forget"]')
const remembered = () => document.body.querySelector('[data-testid="use-my-location-remembered"]')
const stored = () => localStorage.getItem(LOCATION_STORAGE_KEY)

async function press(wrapper: Wrapper) {
  await button(wrapper).trigger('click')
  await vi.waitFor(() => expect(box(wrapper).exists() || chip(wrapper).exists()).toBe(true))
}

async function tick(wrapper: Wrapper) {
  await box(wrapper).trigger('click')
  await vi.waitFor(() => expect(chip(wrapper).exists()).toBe(true))
}

async function forget(wrapper: Wrapper) {
  await chip(wrapper).trigger('click')
  await vi.waitFor(() => expect(forgetButton()).not.toBeNull())
  forgetButton()!.click()
  await vi.waitFor(() => expect(chip(wrapper).exists()).toBe(false))
}

describe('at first', () => {
  it('shows only the button: no box, no note, no "Stored" control, and asks the browser for nothing', async () => {
    const getCurrentPosition = mockBrowser()
    const wrapper = await mountControl()
    expect(button(wrapper).text()).toBe('Use my location')
    expect(box(wrapper).exists()).toBe(false)
    expect(note(wrapper).exists()).toBe(false)
    expect(chip(wrapper).exists()).toBe(false)
    expect(button(wrapper).attributes('aria-describedby')).toBeUndefined()
    expect(getCurrentPosition).not.toHaveBeenCalled()
  })

  it('has the status and the alert regions of the page in the tree from the start, the status empty and never `hidden`', async () => {
    mockBrowser()
    const wrapper = await mountControl()
    expect(status(wrapper).attributes('role')).toBe('status')
    expect(status(wrapper).attributes('aria-live')).toBe('polite')
    expect(status(wrapper).attributes('hidden')).toBeUndefined()
    expect(status(wrapper).classes()).toContain('empty:sr-only')
    expect(status(wrapper).text()).toBe('')
    expect(wrapper.find('[data-testid="use-my-location-problem"]').exists()).toBe(false)
  })

  it('tells what the page says in the status, and a failure of the page in an alert', async () => {
    mockBrowser()
    const wrapper = await mountControl({ status: 'Nearest station: Kiel.', problem: 'The station could not be looked up.' })
    expect(status(wrapper).text()).toBe('Nearest station: Kiel.')
    const alert = wrapper.find('[data-testid="use-my-location-problem"]')
    expect(alert.attributes('role')).toBe('alert')
    expect(alert.text()).toBe('The station could not be looked up.')
  })
})

describe('after a press, with a position in hand and nothing stored', () => {
  it('hands the rounded position to the page and shows the box and its note, which the button is described by', async () => {
    mockBrowser()
    const wrapper = await mountControl()
    await press(wrapper)
    expect(wrapper.emitted('position')).toEqual([[{ latitude: 53.55, longitude: 9.99 }]])

    expect(box(wrapper).attributes('aria-checked')).toBe('false')
    expect(wrapper.text()).toContain('Remember my position in this browser')
    expect(note(wrapper).text()).toContain('Rounded to about 1 km and used only to find the nearest station. It stays in this browser only if you tick the box.')
    const link = wrapper.find('[data-testid="use-my-location-privacy"]')
    expect(link.text()).toBe('More in the privacy policy')
    expect(link.attributes('href')).toBe('/datenschutz#location')
    expect(button(wrapper).attributes('aria-describedby')).toBe(note(wrapper).attributes('id'))
    expect(chip(wrapper).exists()).toBe(false)
    // nothing is kept until the box is ticked
    expect(stored()).toBeNull()
  })

  it('shows neither the box nor the note when the press found no position', async () => {
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition: (_ok: unknown, no: (error: unknown) => void) => no({ code: 2 }) } })
    const wrapper = await mountControl()
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="use-my-location-problem"]').exists()).toBe(true))
    expect(box(wrapper).exists()).toBe(false)
    expect(note(wrapper).exists()).toBe(false)
    expect(chip(wrapper).exists()).toBe(false)
  })
})

describe('once a position is stored', () => {
  it('replaces the box and the note with a "Stored" control, named as such, and keeps the rounded position in the browser', async () => {
    mockBrowser()
    const wrapper = await mountControl()
    await press(wrapper)
    await tick(wrapper)

    expect(JSON.parse(stored()!)).toEqual({ latitude: 53.55, longitude: 9.99 })
    expect(box(wrapper).exists()).toBe(false)
    expect(note(wrapper).exists()).toBe(false)
    expect(chip(wrapper).element.tagName).toBe('BUTTON')
    expect(chip(wrapper).text()).toBe('Stored')
    // the name says what is stored, and opens with the word that is seen (WCAG 2.5.3)
    expect(chip(wrapper).attributes('aria-label')).toBe('Stored: my position in this browser')
    expect(button(wrapper).attributes('aria-describedby')).toBeUndefined()
  })

  it('takes the focus to the control, since the box that had it is gone', async () => {
    mockBrowser()
    const wrapper = await mountControl()
    await press(wrapper)
    ;(box(wrapper).element as HTMLElement).focus()
    await tick(wrapper)
    await vi.waitFor(() => expect(document.activeElement).toBe(chip(wrapper).element))
  })

  it('opens to the rounded position and "Forget my position": a native button, which the keyboard presses as a click (e2e)', async () => {
    mockBrowser()
    const wrapper = await mountControl()
    await press(wrapper)
    await tick(wrapper)
    expect(chip(wrapper).attributes('aria-expanded')).toBe('false')
    expect(chip(wrapper).attributes('tabindex')).toBeUndefined()
    expect(forgetButton()).toBeNull()

    await chip(wrapper).trigger('click')
    await vi.waitFor(() => expect(forgetButton()).not.toBeNull())
    expect(chip(wrapper).attributes('aria-expanded')).toBe('true')
    expect(remembered()!.textContent).toContain('Remembered position: 53.55, 9.99')
    expect(forgetButton()!.textContent).toContain('Forget my position')
  })

  it('is shown at once for a position that an earlier visit stored, with no box and no note, and the browser is not asked', async () => {
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify({ latitude: 52.52, longitude: 13.4 }))
    const getCurrentPosition = mockBrowser()
    const wrapper = await mountControl()
    expect(chip(wrapper).exists()).toBe(true)
    expect(chip(wrapper).attributes('aria-label')).toBe('Stored: my position in this browser')
    expect(box(wrapper).exists()).toBe(false)
    expect(note(wrapper).exists()).toBe(false)
    expect(getCurrentPosition).not.toHaveBeenCalled()

    // it opens to that position, and a press uses it without asking the browser
    await chip(wrapper).trigger('click')
    await vi.waitFor(() => expect(remembered()?.textContent).toContain('52.52, 13.4'))
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('position')).toEqual([[{ latitude: 52.52, longitude: 13.4 }]]))
    expect(getCurrentPosition).not.toHaveBeenCalled()
  })
})

describe('"Forget my position"', () => {
  it('deletes what is stored, takes the control away, and returns to the button alone', async () => {
    mockBrowser()
    const wrapper = await mountControl()
    await press(wrapper)
    await tick(wrapper)
    await forget(wrapper)

    expect(stored()).toBeNull()
    expect(chip(wrapper).exists()).toBe(false)
    // no position is in hand: the box cannot be ticked, so it is not offered
    expect(box(wrapper).exists()).toBe(false)
    expect(note(wrapper).exists()).toBe(false)
    expect(forgetButton()).toBeNull()
  })

  it('puts the focus back on the button', async () => {
    mockBrowser()
    const wrapper = await mountControl()
    await press(wrapper)
    await tick(wrapper)
    await forget(wrapper)
    await vi.waitFor(() => expect(document.activeElement).toBe(button(wrapper).element))
  })

  it('that was stored by an earlier visit goes the same way', async () => {
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify({ latitude: 52.52, longitude: 13.4 }))
    mockBrowser()
    const wrapper = await mountControl()
    await forget(wrapper)
    expect(stored()).toBeNull()
    expect(box(wrapper).exists()).toBe(false)
  })
})

describe('the sequence of GH-4010: press, tick, forget, press, tick', () => {
  it('stores the position again, and shows the "Stored" control, each time', async () => {
    mockBrowser()
    const wrapper = await mountControl()

    for (const fix of [{ latitude: 53.5512, longitude: 9.9934 }, { latitude: 48.1371, longitude: 11.5754 }]) {
      mockBrowser(fix)
      expect(stored()).toBeNull()
      expect(chip(wrapper).exists()).toBe(false)

      await press(wrapper)
      expect(box(wrapper).attributes('aria-checked')).toBe('false')
      expect(stored()).toBeNull()

      await tick(wrapper)
      expect(JSON.parse(stored()!)).toEqual({ latitude: Math.round(fix.latitude * 100) / 100, longitude: Math.round(fix.longitude * 100) / 100 })
      expect(box(wrapper).exists()).toBe(false)

      await forget(wrapper)
      expect(stored()).toBeNull()
    }
  })

  it('stores the position again after a forget, with the box ticked from the control that the second press shows', async () => {
    mockBrowser()
    const wrapper = await mountControl()
    await press(wrapper)
    await tick(wrapper)
    await forget(wrapper)

    // the box is gone with the position: it cannot be ticked into a state that keeps nothing
    expect(box(wrapper).exists()).toBe(false)
    await press(wrapper)
    await tick(wrapper)
    expect(JSON.parse(stored()!)).toEqual({ latitude: 53.55, longitude: 9.99 })
    expect(chip(wrapper).text()).toBe('Stored')
    expect(wrapper.emitted('position')).toHaveLength(2)
  })
})
