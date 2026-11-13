// @vitest-environment happy-dom
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, ref } from 'vue'
import { useModalDialogHold } from '../../app/composables/useModalDialogHold'
import { lockPage } from '../../app/utils/page-lock'

// The page behind an open modal dialog is held for real on iOS (GH-3761): fixed where it stands, with its offset kept
// and given back, and the dialog laid out by the visual viewport. These are the styles it writes and restores, with a
// window of our own that serves the scroll offset and a visual viewport.

vi.mock('@vueuse/core', () => ({ isIOS: true }))

class FakeViewport extends EventTarget {
  height = 700
  offsetTop = 0
  scale = 1
  move(height: number, offsetTop: number) {
    this.height = height
    this.offsetTop = offsetTop
    this.dispatchEvent(new Event('resize'))
  }
}

function fakeWindow(scrollY = 0, scrollX = 0, viewport: FakeViewport | null = new FakeViewport()) {
  const scrollTo = vi.fn()
  return {
    scrollX,
    scrollY,
    scrollTo,
    visualViewport: viewport,
  } as unknown as Window & { scrollTo: ReturnType<typeof vi.fn> }
}

const root = () => document.documentElement
const body = () => document.body

describe('the page behind a modal dialog (GH-3761)', () => {
  beforeEach(() => {
    body().removeAttribute('style')
    root().removeAttribute('style')
    root().removeAttribute('data-page-locked')
  })

  afterEach(() => {
    body().removeAttribute('style')
    root().removeAttribute('style')
    root().removeAttribute('data-page-locked')
  })

  it('takes the body out of the flow where it stands, with no bounce and no pull-to-refresh', () => {
    const win = fakeWindow(640)
    const unlock = lockPage(document, win, true)
    expect(body().style.position).toBe('fixed')
    expect(body().style.top).toBe('-640px')
    expect(body().style.left).toBe('0px')
    expect(body().style.right).toBe('0px')
    expect(body().style.width).toBe('100%')
    expect(body().style.getPropertyValue('overscroll-behavior')).toBe('none')
    expect(root().style.getPropertyValue('overscroll-behavior')).toBe('none')
    expect(root().hasAttribute('data-page-locked')).toBe(true)
    unlock()
  })

  it('gives back what the body and the root had, and the exact scroll offset, at once and not smoothly', () => {
    body().style.setProperty('overflow', 'hidden')
    body().style.setProperty('padding-right', '15px')
    body().style.setProperty('top', '3px')
    root().style.setProperty('overscroll-behavior', 'contain')
    const win = fakeWindow(1234, 5)
    const unlock = lockPage(document, win, true)
    // the lock does not touch what reka-ui's lock writes
    expect(body().style.overflow).toBe('hidden')
    expect(body().style.paddingRight).toBe('15px')
    unlock()
    expect(body().style.position).toBe('')
    expect(body().style.top).toBe('3px')
    expect(body().style.left).toBe('')
    expect(body().style.width).toBe('')
    expect(body().style.getPropertyValue('overscroll-behavior')).toBe('')
    expect(body().style.overflow).toBe('hidden')
    expect(body().style.paddingRight).toBe('15px')
    expect(root().style.getPropertyValue('overscroll-behavior')).toBe('contain')
    expect(root().hasAttribute('data-page-locked')).toBe(false)
    expect(win.scrollTo).toHaveBeenCalledExactlyOnceWith({ left: 5, top: 1234, behavior: 'instant' })
  })

  it('is one lock for modals that overlap, taken at the first and let go of at the last, from the first offset', () => {
    const win = fakeWindow(300)
    const first = lockPage(document, win, true)
    // the second opens while the first closes: the page is already fixed, and reads no offset of its own (it is 0 now)
    Object.defineProperty(win, 'scrollY', { value: 0, configurable: true })
    const second = lockPage(document, win, true)
    expect(body().style.top).toBe('-300px')
    first()
    first()
    expect(body().style.position).toBe('fixed')
    expect(win.scrollTo).not.toHaveBeenCalled()
    second()
    expect(body().style.position).toBe('')
    expect(win.scrollTo).toHaveBeenCalledExactlyOnceWith({ left: 0, top: 300, behavior: 'instant' })
  })

  it('is taken again, from the offset of the time, by a modal that opens after the last has closed', () => {
    const win = fakeWindow(300)
    lockPage(document, win, true)()
    Object.defineProperty(win, 'scrollY', { value: 900, configurable: true })
    const unlock = lockPage(document, win, true)
    expect(body().style.top).toBe('-900px')
    unlock()
    expect(win.scrollTo).toHaveBeenLastCalledWith({ left: 0, top: 900, behavior: 'instant' })
  })

  it('is not taken off iOS, where reka-ui\'s overflow holds the page and the keyboard resizes it', () => {
    const win = fakeWindow(640)
    const unlock = lockPage(document, win, false)
    expect(body().style.position).toBe('')
    expect(root().hasAttribute('data-page-locked')).toBe(false)
    unlock()
    expect(win.scrollTo).not.toHaveBeenCalled()
  })

  it('writes the visual viewport\'s height and top, follows it, and stops when it lets go', () => {
    const viewport = new FakeViewport()
    const win = fakeWindow(0, 0, viewport)
    const unlock = lockPage(document, win, true)
    expect(root().style.getPropertyValue('--app-vv-height')).toBe('700px')
    expect(root().style.getPropertyValue('--app-vv-top')).toBe('0px')
    // the keyboard comes up and the browser pans to the field
    viewport.move(350, 120)
    expect(root().style.getPropertyValue('--app-vv-height')).toBe('350px')
    expect(root().style.getPropertyValue('--app-vv-top')).toBe('120px')
    // a pan alone (scroll of the visual viewport)
    viewport.offsetTop = 80
    viewport.dispatchEvent(new Event('scroll'))
    expect(root().style.getPropertyValue('--app-vv-top')).toBe('80px')
    unlock()
    expect(root().style.getPropertyValue('--app-vv-height')).toBe('')
    expect(root().style.getPropertyValue('--app-vv-top')).toBe('')
    viewport.move(500, 0)
    expect(root().style.getPropertyValue('--app-vv-height')).toBe('')
  })

  it('holds a page that has no visual viewport as well', () => {
    const unlock = lockPage(document, fakeWindow(10, 0, null), true)
    expect(body().style.position).toBe('fixed')
    expect(root().style.getPropertyValue('--app-vv-height')).toBe('')
    unlock()
    expect(body().style.position).toBe('')
  })
})

describe('the hold of a modal dialog is its page lock and its touch guard (GH-3761)', () => {
  afterEach(() => {
    body().removeAttribute('style')
    root().removeAttribute('data-page-locked')
  })

  it('locks the page while a modal is open, once for modals that overlap, and lets go when the last closes', () => {
    const scope = effectScope()
    const search = ref(false)
    const sheet = ref(false)
    // the settings popover is no modal: it does not call the composable, so nothing of it is here
    scope.run(() => {
      useModalDialogHold(search)
      useModalDialogHold(sheet)
    })
    expect(body().style.position).toBe('')
    search.value = true
    expect(body().style.position).toBe('fixed')
    sheet.value = true
    search.value = false
    expect(body().style.position).toBe('fixed')
    sheet.value = false
    expect(body().style.position).toBe('')

    // a modal that is open when its component goes is let go of
    search.value = true
    expect(body().style.position).toBe('fixed')
    scope.stop()
    expect(body().style.position).toBe('')
    expect(root().hasAttribute('data-page-locked')).toBe(false)
  })
})

describe('the dialogs are laid out by the visual viewport (GH-3761)', () => {
  const css = readFileSync(join(__dirname, '..', '..', 'app', 'assets', 'css', 'main.css'), 'utf8')

  it('lays the search and the place dialog out by it, below sm in the middle of it and from sm at its 12 %', () => {
    expect(css).toMatch(/html\[data-page-locked\] \.app-vv-dialog \{\s*top: calc\(var\(--app-vv-top, 0px\) \+ var\(--app-vv-height, 100dvh\) \/ 2\);\s*max-height: min\(36rem, calc\(var\(--app-vv-height, 100dvh\) - 2rem\)\);/)
    expect(css).toMatch(/@media \(width >= 40rem\) \{\s*html\[data-page-locked\] \.app-vv-dialog \{\s*top: calc\(var\(--app-vv-top, 0px\) \+ var\(--app-vv-height, 100dvh\) \* 0\.12\);/)
  })

  it('is the class of those two dialogs', () => {
    for (const file of ['AppSearch.vue', 'AskTheWeather.vue']) {
      const text = readFileSync(join(__dirname, '..', '..', 'app', 'components', file), 'utf8')
      expect(text, file).toContain('content: \'app-vv-dialog ')
      expect(text, file).toMatch(/useModalDialogHold\(/)
    }
    const bar = readFileSync(join(__dirname, '..', '..', 'app', 'components', 'AppTabBar.vue'), 'utf8')
    expect(bar).toMatch(/useModalDialogHold\(/)
  })
})
