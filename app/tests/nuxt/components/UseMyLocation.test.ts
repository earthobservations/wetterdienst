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
  vi.unstubAllGlobals()
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
const box = (wrapper: Wrapper) => wrapper.find('button[role="checkbox"][data-testid="use-my-location-remember"]')
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
    // and so is the box itself: the checkbox element has the note as its description, not only the wrapper round it
    expect(box(wrapper).attributes('aria-describedby')).toBe(note(wrapper).attributes('id'))
    expect(note(wrapper).attributes('id')).toBeTruthy()
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

  it('is a disclosure: Escape closes the position and "Forget" with the focus on the control, a click on it toggles them', async () => {
    mockBrowser()
    const wrapper = await mountControl()
    await press(wrapper)
    await tick(wrapper)
    await chip(wrapper).trigger('click')
    await vi.waitFor(() => expect(forgetButton()).not.toBeNull())
    // the details follow the control, and are named by it
    expect(chip(wrapper).attributes('aria-controls')).toBe(remembered()!.getAttribute('id'))
    expect(wrapper.element.contains(forgetButton())).toBe(true)

    // Escape with the focus on "Forget": the details close and the focus goes to the control, not to the page's body
    forgetButton()!.focus()
    expect(document.activeElement).toBe(forgetButton())
    await wrapper.find('[data-testid="use-my-location-forget"]').trigger('keydown', { key: 'Escape' })
    await vi.waitFor(() => expect(forgetButton()).toBeNull())
    expect(chip(wrapper).attributes('aria-expanded')).toBe('false')
    // closed, the control names no element that is not there
    expect(chip(wrapper).attributes('aria-controls')).toBeUndefined()
    expect(document.activeElement).toBe(chip(wrapper).element)

    await chip(wrapper).trigger('click')
    await vi.waitFor(() => expect(forgetButton()).not.toBeNull())
    await chip(wrapper).trigger('click')
    await vi.waitFor(() => expect(forgetButton()).toBeNull())
  })

  it('leaves the focus where it is when Escape is pressed on the "Use my location" button while the details are open', async () => {
    mockBrowser()
    const wrapper = await mountControl()
    await press(wrapper)
    await tick(wrapper)
    await chip(wrapper).trigger('click')
    await vi.waitFor(() => expect(forgetButton()).not.toBeNull())

    ;(button(wrapper).element as HTMLElement).focus()
    await button(wrapper).trigger('keydown', { key: 'Escape' })
    expect(forgetButton()).not.toBeNull()
    expect(chip(wrapper).attributes('aria-expanded')).toBe('true')
    expect(document.activeElement).toBe(button(wrapper).element)
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

// a browser that refuses to keep anything (GH-4014): a private window, blocked site data, a full quota
function blockStorage() {
  vi.stubGlobal('localStorage', {
    getItem: () => null,
    setItem: () => {
      throw new DOMException('full', 'QuotaExceededError')
    },
    removeItem: () => {},
  })
}
const notKept = (wrapper: Wrapper) => wrapper.find('[data-testid="use-my-location-not-kept"]')

describe('where the browser refuses to keep the position (GH-4014)', () => {
  it('does not show "Stored" for what is not stored: the box stays, unticked, and an alert says it is for this visit only', async () => {
    mockBrowser()
    const wrapper = await mountControl()
    await press(wrapper)
    blockStorage()
    expect(notKept(wrapper).exists()).toBe(false)

    await box(wrapper).trigger('click')
    await vi.waitFor(() => expect(notKept(wrapper).exists()).toBe(true))
    expect(notKept(wrapper).attributes('role')).toBe('alert')
    expect(notKept(wrapper).text()).toBe('Your browser did not allow the position to be stored. It is used for this visit only.')
    expect(chip(wrapper).exists()).toBe(false)
    expect(box(wrapper).attributes('aria-checked')).toBe('false')
    expect(stored()).toBeNull()
  })

  it('tells it on the map\'s station card too, which has no alert of its own', async () => {
    mockBrowser()
    const full = await mountControl()
    await press(full)
    full.unmount()
    blockStorage()

    const card = await mountControl({ offerOnly: true })
    await box(card).trigger('click')
    await vi.waitFor(() => expect(notKept(card).exists()).toBe(true))
    expect(chip(card).exists()).toBe(false)
  })

  it('takes the alert back when the box is ticked again and the browser keeps it', async () => {
    mockBrowser()
    const wrapper = await mountControl()
    await press(wrapper)
    blockStorage()
    await box(wrapper).trigger('click')
    await vi.waitFor(() => expect(notKept(wrapper).exists()).toBe(true))

    vi.unstubAllGlobals()
    await box(wrapper).trigger('click')
    await vi.waitFor(() => expect(chip(wrapper).exists()).toBe(true))
    expect(notKept(wrapper).exists()).toBe(false)
    expect(JSON.parse(stored()!)).toEqual({ latitude: 53.55, longitude: 9.99 })
  })
})

// "Forget" with a press on its way (GH-4014): the position request that is still waiting for the browser is let go
describe('"Forget my position" during a press', () => {
  it('drops the position that the browser gives late: it is not put back for the visit', async () => {
    mockBrowser()
    const wrapper = await mountControl()
    await press(wrapper)
    expect(wrapper.emitted('position')).toHaveLength(1)

    // the next press waits: the browser does not answer yet
    const answers: Array<(position: unknown) => void> = []
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { getCurrentPosition: vi.fn((success: (position: unknown) => void) => void answers.push(success)) },
    })
    await button(wrapper).trigger('click')
    await vi.waitFor(() => expect(answers).toHaveLength(1))
    expect(button(wrapper).attributes('aria-busy')).toBe('true')

    // the first position is stored and forgotten while the second is still awaited
    await tick(wrapper)
    await forget(wrapper)
    expect(button(wrapper).attributes('aria-busy')).toBe('false')

    answers[0]!({ coords: { latitude: 48.1371, longitude: 11.5754 } })
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(wrapper.emitted('position')).toHaveLength(1)
    expect(box(wrapper).exists()).toBe(false)
    expect(chip(wrapper).exists()).toBe(false)
    expect(stored()).toBeNull()
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

// the map's station card (GH-4011): the position's result is shown where the button is not, so the option to keep the
// position, or the control that says it is kept, is there alone (`offerOnly`): no button, no status, no alert
describe('with `offerOnly`, as on the map\'s station card', () => {
  it('shows nothing where no position is in hand', async () => {
    mockBrowser()
    const wrapper = await mountControl({ offerOnly: true })
    expect(button(wrapper).exists()).toBe(false)
    expect(box(wrapper).exists()).toBe(false)
    expect(note(wrapper).exists()).toBe(false)
    expect(chip(wrapper).exists()).toBe(false)
  })

  it('shows the box and the note for a position in hand, which the one full copy found, and the control once it is ticked', async () => {
    mockBrowser()
    const full = await mountControl()
    await press(full)
    // the page shows one copy at a time: the full one is gone when the card is shown
    full.unmount()

    const card = await mountControl({ offerOnly: true })
    expect(button(card).exists()).toBe(false)
    expect(card.find('[data-testid="use-my-location-status"]').exists()).toBe(false)
    expect(card.find('[data-testid="use-my-location-problem"]').exists()).toBe(false)
    expect(box(card).attributes('aria-checked')).toBe('false')
    expect(box(card).attributes('aria-describedby')).toBe(note(card).attributes('id'))
    expect(note(card).text()).toContain('Rounded to about 1 km')
    expect(stored()).toBeNull()

    await tick(card)
    expect(JSON.parse(stored()!)).toEqual({ latitude: 53.55, longitude: 9.99 })
    expect(box(card).exists()).toBe(false)
    expect(chip(card).attributes('aria-label')).toBe('Stored: my position in this browser')
    await vi.waitFor(() => expect(document.activeElement).toBe(chip(card).element))
  })

  it('forgets from the control, tells the page so it can place the focus, and shows nothing again', async () => {
    localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify({ latitude: 52.52, longitude: 13.4 }))
    mockBrowser()
    const card = await mountControl({ offerOnly: true })
    await forget(card)
    expect(card.emitted('forgotten')).toHaveLength(1)
    expect(stored()).toBeNull()
    expect(box(card).exists()).toBe(false)
    expect(chip(card).exists()).toBe(false)
  })
})
