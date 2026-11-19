import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import MapLayers from '~/components/MapLayers.vue'

// The panel of the layers button closes with one tap (GH-4242). A press outside the panel dismisses it, but a touch's is
// dismissed at its click, while a focus that leaves the panel is dismissed at once: Safari moves the focus to the page behind
// the button it is tapped, in the middle of the tap, and the panel that closed on it was opened again by the tap's click on
// the button. A focus that leaves during a touch is no leaving, and the click closes the panel or toggles it.

const PROPS = {
  layer: 'forecast' as const,
  layerItems: [
    { value: 'forecast' as const, label: 'Forecast', icon: 'i-ph-cloud-sun' },
    { value: 'measured' as const, label: 'Measured', icon: 'i-ph-thermometer' },
  ],
  grouped: true,
  showGrouping: true,
  compulsory: false,
  note: '',
}

let mounted: Awaited<ReturnType<typeof mountSuspended>> | undefined
let outside: HTMLElement | undefined

/** The panel, open, with a focusable element of the page behind it, as `main` is: what a press on the page moves the focus to */
async function openPanel() {
  outside = document.createElement('main')
  outside.tabIndex = -1
  document.body.append(outside)
  mounted = await mountSuspended(MapLayers, {
    props: { ...PROPS, 'open': true, 'onUpdate:open': (value: boolean) => mounted!.setProps({ open: value }) },
    attachTo: document.body,
  })
  await flushPromises()
  // the popover listens for a press outside from the next tick of its opening
  await new Promise(resolve => setTimeout(resolve, 20))
  expect(document.querySelector('[data-testid="map-layers-panel"]')).not.toBeNull()
}

/** The layers button, which the finger presses */
const trigger = () => document.querySelector('.map-layers-button')!

function press(target: Element, pointerType: 'touch' | 'mouse') {
  target.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, pointerType }))
}

/** The focus going to an element outside the panel */
async function focusOutside() {
  outside!.focus()
  outside!.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
  await flushPromises()
  await new Promise(resolve => setTimeout(resolve, 20))
}

const isOpen = () => document.querySelector('[data-testid="map-layers-panel"]') !== null

afterEach(() => {
  mounted?.unmount()
  mounted = undefined
  outside?.remove()
  outside = undefined
})

describe('the panel of the layers button, closed by a press outside it', () => {
  it('stays open when the focus leaves it in the middle of a tap on the button, and is closed by the click of the tap', async () => {
    await openPanel()
    press(trigger(), 'touch')
    await focusOutside()
    expect(isOpen()).toBe(true)
    trigger().dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
    await flushPromises()
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(isOpen()).toBe(false)
  })

  it('is closed by the focus of a tap that is on something else, which may stop its click as Leaflet\'s zoom buttons do', async () => {
    await openPanel()
    press(outside!, 'touch')
    await focusOutside()
    expect(isOpen()).toBe(false)
  })

  it('is closed by a focus that leaves it where there is no touch, as a keyboard that tabs out of it', async () => {
    await openPanel()
    await focusOutside()
    expect(isOpen()).toBe(false)
  })

  it('is closed by a focus that leaves it after a tap on the button whose click came inside the panel: the click released the guard', async () => {
    await openPanel()
    // the popover's own wait for the click of a touch would also ignore the focus after it, so the press is kept from it
    trigger().addEventListener('pointerdown', event => event.stopPropagation(), { once: true })
    press(trigger(), 'touch')
    document.querySelector('[data-testid="map-layers-panel"]')!.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
    await flushPromises()
    expect(isOpen()).toBe(true)
    await focusOutside()
    expect(isOpen()).toBe(false)
  })

  it('is closed by a focus that leaves it 500 ms after a touch on the button that had no click (a pan, a long press), and not before', async () => {
    await openPanel()
    press(trigger(), 'touch')
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      const focusOutsideAfter = async (ms: number) => {
        await vi.advanceTimersByTimeAsync(ms)
        outside!.focus()
        outside!.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
        await flushPromises()
        await vi.advanceTimersByTimeAsync(20)
      }
      trigger().dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, pointerType: 'touch' }))
      await focusOutsideAfter(400)
      expect(isOpen()).toBe(true)
      await focusOutsideAfter(100)
      expect(isOpen()).toBe(false)
    }
    finally {
      vi.useRealTimers()
    }
  })
})
