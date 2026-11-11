import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import FittingButtonGroup from '~/components/FittingButtonGroup.vue'

// The row of buttons stands one above the other where its box is too narrow for it, and goes back when there is room
// (GH-3985). The box's width is the one the test sets (a stand-in for `useElementSize`), the width of the row is what
// the stubbed `scrollWidth` says, and the observer's callback is the one the test calls.

const boxWidth = ref(0)
let observed: (() => void) | undefined
mockNuxtImport('useElementSize', () => () => ({ width: boxWidth, height: ref(0) }))
mockNuxtImport('useResizeObserver', () => (_target: unknown, callback: () => void) => {
  observed = callback
})

let rowWidth = 300
let scrollWidthSpy: ReturnType<typeof vi.spyOn> | undefined

beforeEach(() => {
  boxWidth.value = 0
  rowWidth = 300
  observed = undefined
  scrollWidthSpy = vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(() => rowWidth)
})
afterEach(() => scrollWidthSpy?.mockRestore())

async function mountRow() {
  const wrapper = await mountSuspended(FittingButtonGroup, { slots: { default: '<button type="button">A</button><button type="button">B</button>' } })
  return wrapper
}
const orientation = (wrapper: Awaited<ReturnType<typeof mountRow>>) => wrapper.find('[data-orientation]').attributes('data-orientation')
const nextFrame = () => new Promise(resolve => requestAnimationFrame(resolve))
const eventually = (check: () => void) => vi.waitFor(check, { timeout: 2000 })

describe('the row of buttons that fits its box', () => {
  it('stands as a row where it fits, and stacks where its box is narrower than it by more than a pixel', async () => {
    boxWidth.value = 301
    const fits = await mountRow()
    expect(orientation(fits)).toBe('horizontal')

    boxWidth.value = 256
    const narrow = await mountRow()
    // decided at once, so that it is never drawn as a row first
    expect(orientation(narrow)).toBe('vertical')
  })

  it('does not stack for a box that has no width', async () => {
    boxWidth.value = 0
    const wrapper = await mountRow()
    expect(orientation(wrapper)).toBe('horizontal')
  })

  it('does not measure again while it is stacked, and goes back to a row when the box grows past its width', async () => {
    boxWidth.value = 256
    const wrapper = await mountRow()
    expect(orientation(wrapper)).toBe('vertical')

    // stacked, the group is as wide as its widest button: that is not the width of the row
    rowWidth = 90
    expect(observed).toBeDefined()
    observed?.()
    boxWidth.value = 280
    // the box's change is applied a frame on, so two frames are waited for
    await nextFrame()
    await nextFrame()
    expect(orientation(wrapper)).toBe('vertical')

    boxWidth.value = 310
    await eventually(() => expect(orientation(wrapper)).toBe('horizontal'))
  })

  it('stacks on a later change of the box a frame on', async () => {
    boxWidth.value = 400
    const wrapper = await mountRow()
    expect(orientation(wrapper)).toBe('horizontal')

    boxWidth.value = 200
    await eventually(() => expect(orientation(wrapper)).toBe('vertical'))
  })

  it('measures the row again when the language changes', async () => {
    boxWidth.value = 256
    const wrapper = await mountRow()
    expect(orientation(wrapper)).toBe('vertical')

    // other names, a shorter row: it is a row again, once it is measured again
    rowWidth = 200
    await useNuxtApp().$i18n.setLocale('de')
    await eventually(() => expect(orientation(wrapper)).toBe('horizontal'))
    await useNuxtApp().$i18n.setLocale('en')
  })
})
