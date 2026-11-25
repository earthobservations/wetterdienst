import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { TOAST_INSET_PROPERTY, TOAST_VIEWPORT_CLASS, useToastInset } from '~/composables/useToastInset'

// The toast region is Nuxt UI's, teleported to the body; here a stand-in of the class the app gives it, whose
// box the test sets, as the region stands at the bottom of the window.
const Harness = defineComponent({
  setup() {
    useToastInset()
    return { toasts: useToast() }
  },
  render: () => h('div'),
})

const inset = () => document.documentElement.style.getPropertyValue(TOAST_INSET_PROPERTY)

function region(top: number, height: number) {
  const element = document.createElement('div')
  element.className = TOAST_VIEWPORT_CLASS
  element.getBoundingClientRect = () => ({ top, height, bottom: top + height, left: 0, right: 0, width: 0, x: 0, y: top, toJSON: () => ({}) })
  document.body.append(element)
  return element
}

describe('the room a toast needs at the foot of the page', () => {
  afterEach(() => {
    document.querySelectorAll(`.${TOAST_VIEWPORT_CLASS}`).forEach(node => node.remove())
    useToast().clear()
    document.documentElement.style.removeProperty(TOAST_INSET_PROPERTY)
    document.documentElement.removeAttribute('data-bars')
  })

  it('is the height from the top of the toasts to the bottom of the window, while there is one', async () => {
    vi.spyOn(window, 'innerHeight', 'get').mockReturnValue(720)
    const wrapper = await mountSuspended(Harness)
    region(604, 100)
    wrapper.vm.toasts.add({ id: 'one', title: 'Something failed' })
    await vi.waitFor(() => expect(inset()).toBe('116px'))
  })

  it('is nothing once the toasts are gone', async () => {
    vi.spyOn(window, 'innerHeight', 'get').mockReturnValue(720)
    const wrapper = await mountSuspended(Harness)
    const element = region(604, 100)
    wrapper.vm.toasts.add({ id: 'one', title: 'Something failed' })
    await vi.waitFor(() => expect(inset()).toBe('116px'))
    // the region is as high as nothing when no toast is in it
    element.getBoundingClientRect = () => ({ top: 704, height: 0, bottom: 704, left: 0, right: 0, width: 0, x: 0, y: 704, toJSON: () => ({}) })
    wrapper.vm.toasts.clear()
    await nextTick()
    await vi.waitFor(() => expect(inset()).toBe('0px'))
  })

  it('is measured again when the bars of a phone slide away or come back, and when the region has stopped moving', async () => {
    vi.spyOn(window, 'innerHeight', 'get').mockReturnValue(720)
    const wrapper = await mountSuspended(Harness)
    const element = region(604, 100)
    const place = (top: number) => {
      element.getBoundingClientRect = () => ({ top, height: 100, bottom: top + 100, left: 0, right: 0, width: 0, x: 0, y: top, toJSON: () => ({}) })
    }
    wrapper.vm.toasts.add({ id: 'one', title: 'Something failed' })
    await vi.waitFor(() => expect(inset()).toBe('116px'))

    // the tab bar slides away (`data-bars` on <html>) and the region goes down by its height; it is still on its way when the
    // attribute changes, and the end of its transition has the last word
    place(660)
    document.documentElement.setAttribute('data-bars', 'hidden')
    place(670)
    element.dispatchEvent(new Event('transitionend', { bubbles: true }))
    await vi.waitFor(() => expect(inset()).toBe('50px'))

    // and back
    place(604)
    document.documentElement.removeAttribute('data-bars')
    element.dispatchEvent(new Event('transitionend', { bubbles: true }))
    await vi.waitFor(() => expect(inset()).toBe('116px'))
    wrapper.unmount()
  })

  it('is measured again after the slide even where no transition ends (reduced motion, a browser that does not transition)', async () => {
    vi.spyOn(window, 'innerHeight', 'get').mockReturnValue(720)
    const wrapper = await mountSuspended(Harness)
    const element = region(604, 100)
    wrapper.vm.toasts.add({ id: 'one', title: 'Something failed' })
    await vi.waitFor(() => expect(inset()).toBe('116px'))
    element.getBoundingClientRect = () => ({ top: 670, height: 100, bottom: 770, left: 0, right: 0, width: 0, x: 0, y: 670, toJSON: () => ({}) })
    document.documentElement.setAttribute('data-bars', 'hidden')
    await vi.waitFor(() => expect(inset()).toBe('50px'), { timeout: 2000 })
    document.documentElement.removeAttribute('data-bars')
    wrapper.unmount()
  })

  it('leaves the property off the page when the app goes', async () => {
    const wrapper = await mountSuspended(Harness)
    region(604, 100)
    wrapper.vm.toasts.add({ id: 'one', title: 'Something failed' })
    await vi.waitFor(() => expect(inset()).not.toBe(''))
    wrapper.unmount()
    expect(inset()).toBe('')
  })
})
