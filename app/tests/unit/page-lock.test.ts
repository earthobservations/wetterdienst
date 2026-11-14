// @vitest-environment happy-dom
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import { useModalDialogHold } from '../../app/composables/useModalDialogHold'
import { holdViewportLayout, lockPage } from '../../app/utils/page-lock'

// The page behind an open modal dialog is held for real on iOS (GH-3761): fixed where it stands, with its offset kept
// and given back, and the dialog laid out by the visual viewport until it has left. These are the styles it writes and
// restores, with a window of our own that serves the scroll offset, the address, the history and a visual viewport.

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

/**
 * A window that is an event target, so that `popstate` can be sent to it, with a scroll offset and an address. Its
 * offsets are own accessors, as a browser's are, which `scrollTo` of the browser (`browserScrollTo`) moves
 */
class FakeWindow extends EventTarget {
  scrollTo = vi.fn()
  location = { href: 'https://example.test/a' }
  private offset = [0, 0]
  scrollX!: number
  scrollY!: number
  constructor(scrollY = 0, scrollX = 0, public visualViewport: FakeViewport | null = new FakeViewport()) {
    super()
    this.offset = [scrollX, scrollY]
    for (const [name, index] of [['scrollX', 0], ['scrollY', 1]] as const) {
      Object.defineProperty(this, name, {
        configurable: true,
        get: () => this.offset[index],
        set: (value: number) => {
          this.offset[index] = value
        },
      })
    }
  }

  /** What the browser does to the window's own offset when the body is fixed: it has nothing to scroll */
  browserScrollTo(x: number, y: number) {
    this.offset = [x, y]
  }
}

const fakeWindow = (scrollY = 0, scrollX = 0, viewport: FakeViewport | null = new FakeViewport()) => new FakeWindow(scrollY, scrollX, viewport) as unknown as Window & FakeWindow

const root = () => document.documentElement
const body = () => document.body

function clean() {
  body().removeAttribute('style')
  root().removeAttribute('style')
  root().removeAttribute('data-dialog-viewport')
}

describe('the page behind a modal dialog (GH-3761)', () => {
  beforeEach(clean)
  afterEach(clean)

  it('takes the body out of the flow where it stands, asking for no bounce and no pull-to-refresh', () => {
    const win = fakeWindow(640)
    const unlock = lockPage(document, win, true)
    expect(body().style.position).toBe('fixed')
    expect(body().style.top).toBe('-640px')
    expect(body().style.left).toBe('0px')
    expect(body().style.right).toBe('0px')
    expect(body().style.width).toBe('100%')
    expect(body().style.getPropertyValue('overscroll-behavior')).toBe('none')
    expect(root().style.getPropertyValue('overscroll-behavior')).toBe('none')
    unlock()
  })

  it('keeps a sideways offset as the left of the body too', () => {
    const win = fakeWindow(100, 5)
    const unlock = lockPage(document, win, true)
    expect(body().style.left).toBe('-5px')
    unlock()
    expect(win.scrollTo).toHaveBeenCalledExactlyOnceWith({ left: 5, top: 100, behavior: 'instant' })
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
    expect(win.scrollTo).toHaveBeenCalledExactlyOnceWith({ left: 5, top: 1234, behavior: 'instant' })
  })

  it('is one lock for modals that overlap, taken at the first and let go of at the last, from the first offset', () => {
    const win = fakeWindow(300)
    const first = lockPage(document, win, true)
    // the second opens while the first closes: the page is already fixed, and reads no offset of its own
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
    win.scrollY = 900
    const unlock = lockPage(document, win, true)
    expect(body().style.top).toBe('-900px')
    unlock()
    expect(win.scrollTo).toHaveBeenLastCalledWith({ left: 0, top: 900, behavior: 'instant' })
  })

  it('is not taken off iOS, where reka-ui\'s overflow holds the page and the keyboard resizes it', () => {
    const win = fakeWindow(640)
    const unlock = lockPage(document, win, false)
    expect(body().style.position).toBe('')
    unlock()
    expect(win.scrollTo).not.toHaveBeenCalled()
  })

  it('answers the offset of the page, not the window\'s own (0 under a fixed body), for as long as it is on', () => {
    const win = fakeWindow(2000, 7)
    const unlock = lockPage(document, win, true)
    // the body is fixed and the window has nothing to scroll: its own offset is 0 now
    win.browserScrollTo(0, 0)
    // what the router reads to save the page it leaves
    expect([win.scrollX, win.scrollY]).toEqual([7, 2000])
    unlock()
    // the window's own again: it follows the browser
    expect([win.scrollX, win.scrollY]).toEqual([0, 0])
    win.browserScrollTo(3, 5)
    expect([win.scrollX, win.scrollY]).toEqual([3, 5])
    win.scrollY = 9
    expect(win.scrollY).toBe(9)
  })

  it('answers the offset to the last of the holders, and the window\'s own after', () => {
    const win = fakeWindow(300)
    const first = lockPage(document, win, true)
    const second = lockPage(document, win, true)
    win.browserScrollTo(0, 0)
    first()
    expect(win.scrollY).toBe(300)
    second()
    expect(win.scrollY).toBe(0)
  })

  describe('with a step of the history', () => {
    it('puts the offset back only where the address is the one it was taken at (a dialog that closes with the route does not)', () => {
      const win = fakeWindow(2000)
      const unlock = lockPage(document, win, true)
      // the route changed under the open dialog, which closes with it
      win.location.href = 'https://example.test/b'
      unlock()
      expect(body().style.position).toBe('')
      expect(win.scrollTo).not.toHaveBeenCalled()
    })

    it('puts it back where the address is the same, a change of the query or hash aside from the page', () => {
      const win = fakeWindow(2000)
      const unlock = lockPage(document, win, true)
      unlock()
      expect(win.scrollTo).toHaveBeenCalledExactlyOnceWith({ left: 0, top: 2000, behavior: 'instant' })
    })

    it('has the router save the page that is left at its offset, as it reads it when `popstate` comes', () => {
      const win = fakeWindow(2000)
      const unlock = lockPage(document, win, true)
      let saved: number | undefined
      // the body is fixed and the window has nothing to scroll: its own offset is 0 now
      win.browserScrollTo(0, 0)
      // the router's listener: it reads the offset of the page that is left, then the address is the new one
      win.addEventListener('popstate', () => {
        saved = win.scrollY
      })
      win.location.href = 'https://example.test/b'
      win.dispatchEvent(new Event('popstate'))
      expect(saved).toBe(2000)
      // and the dialog that closes with the route puts nothing back on the page that is arrived at
      unlock()
      expect(win.scrollTo).not.toHaveBeenCalled()
      expect(body().style.position).toBe('')
    })
  })
})

describe('the layout by the visual viewport (GH-3761)', () => {
  beforeEach(clean)
  afterEach(clean)

  it('writes the visual viewport\'s height and top, follows it, and stops when it lets go', () => {
    const viewport = new FakeViewport()
    const win = fakeWindow(0, 0, viewport)
    const release = holdViewportLayout(document, win, true)
    expect(root().hasAttribute('data-dialog-viewport')).toBe(true)
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
    release()
    expect(root().hasAttribute('data-dialog-viewport')).toBe(false)
    expect(root().style.getPropertyValue('--app-vv-height')).toBe('')
    expect(root().style.getPropertyValue('--app-vv-top')).toBe('')
    viewport.move(500, 0)
    expect(root().style.getPropertyValue('--app-vv-height')).toBe('')
  })

  it('is one layout for dialogs that overlap, let go of at the last, and none off iOS', () => {
    const win = fakeWindow()
    const first = holdViewportLayout(document, win, true)
    const second = holdViewportLayout(document, win, true)
    first()
    first()
    expect(root().hasAttribute('data-dialog-viewport')).toBe(true)
    second()
    expect(root().hasAttribute('data-dialog-viewport')).toBe(false)
    holdViewportLayout(document, win, false)()
    expect(root().hasAttribute('data-dialog-viewport')).toBe(false)
  })

  it('is not the lock: the page is not fixed by it', () => {
    const release = holdViewportLayout(document, fakeWindow(300), true)
    expect(body().style.position).toBe('')
    release()
  })

  it('holds a page that has no visual viewport as well', () => {
    const release = holdViewportLayout(document, fakeWindow(10, 0, null), true)
    expect(root().hasAttribute('data-dialog-viewport')).toBe(true)
    expect(root().style.getPropertyValue('--app-vv-height')).toBe('')
    release()
    expect(root().hasAttribute('data-dialog-viewport')).toBe(false)
  })
})

describe('the hold of a modal dialog is its page lock, its touch guard and its layout (GH-3761)', () => {
  beforeEach(clean)
  afterEach(() => {
    clean()
    document.body.innerHTML = ''
  })

  it('locks the page while a modal is open, once for modals that overlap, and lets go when the last closes', () => {
    const scope = effectScope()
    const search = ref(false)
    const sheet = ref(false)
    // the settings popover is no modal: it does not call the composable, so nothing of it is here
    scope.run(() => {
      useModalDialogHold(search)
      useModalDialogHold(sheet, { layout: false })
    })
    expect(body().style.position).toBe('')
    search.value = true
    expect(body().style.position).toBe('fixed')
    sheet.value = true
    search.value = false
    expect(body().style.position).toBe('fixed')
    sheet.value = false
    expect(body().style.position).toBe('')

    // a modal that is open when its component goes is let go of, the layout too
    search.value = true
    expect(body().style.position).toBe('fixed')
    scope.stop()
    expect(body().style.position).toBe('')
    expect(root().hasAttribute('data-dialog-viewport')).toBe(false)
  })

  it('keeps the layout by the visual viewport until the dialog has left, and not for a dialog with no field', async () => {
    const scope = effectScope()
    const search = ref(false)
    const sheet = ref(false)
    let searchHold!: ReturnType<typeof useModalDialogHold>
    let sheetHold!: ReturnType<typeof useModalDialogHold>
    scope.run(() => {
      searchHold = useModalDialogHold(search)
      sheetHold = useModalDialogHold(sheet, { layout: false })
    })
    sheet.value = true
    expect(root().hasAttribute('data-dialog-viewport')).toBe(false)
    sheetHold.afterLeave()
    sheet.value = false

    search.value = true
    expect(root().hasAttribute('data-dialog-viewport')).toBe(true)
    // closed: the page is let go of at once, the dialog is still on its way out and stays where the keyboard leaves it
    search.value = false
    await nextTick()
    expect(body().style.position).toBe('')
    expect(root().hasAttribute('data-dialog-viewport')).toBe(true)
    // it has left
    searchHold.afterLeave()
    expect(root().hasAttribute('data-dialog-viewport')).toBe(false)

    // opened again before the first has left: its `after:leave` does not take the layout from the open one
    search.value = true
    search.value = false
    search.value = true
    searchHold.afterLeave()
    expect(root().hasAttribute('data-dialog-viewport')).toBe(true)
    scope.stop()
    expect(root().hasAttribute('data-dialog-viewport')).toBe(false)
  })

  it('blurs the field of the dialog before the page is let go of, so that the keyboard drops first', () => {
    document.body.innerHTML = '<div role="dialog"><input id="field"></div><button id="outside">x</button>'
    const field = document.getElementById('field') as HTMLInputElement
    const outside = document.getElementById('outside') as HTMLButtonElement
    const scope = effectScope()
    const open = ref(false)
    scope.run(() => useModalDialogHold(open))

    const order: string[] = []
    open.value = true
    expect(body().style.position).toBe('fixed')
    field.focus()
    field.addEventListener('blur', () => order.push(`blur, the body is ${body().style.position || 'in the flow'}`))
    open.value = false
    order.push(`closed, the body is ${body().style.position || 'in the flow'}`)
    expect(order).toEqual(['blur, the body is fixed', 'closed, the body is in the flow'])

    // a focus that is not in a dialog is not touched
    open.value = true
    outside.focus()
    const blurred = vi.fn()
    outside.addEventListener('blur', blurred)
    open.value = false
    expect(blurred).not.toHaveBeenCalled()
    scope.stop()
  })
})

describe('the dialogs are laid out by the visual viewport (GH-3761)', () => {
  const css = readFileSync(join(__dirname, '..', '..', 'app', 'assets', 'css', 'main.css'), 'utf8')
  const component = (file: string) => readFileSync(join(__dirname, '..', '..', 'app', 'components', file), 'utf8')

  it('lays the search and the place dialog out by it, below sm in the middle of it and from sm at its 12 %', () => {
    expect(css).toMatch(/html\[data-dialog-viewport\] \.app-vv-dialog \{\s*top: calc\(var\(--app-vv-top, 0px\) \+ var\(--app-vv-height, 100dvh\) \/ 2\);\s*max-height: min\(36rem, calc\(var\(--app-vv-height, 100dvh\) - 2rem\)\);/)
    expect(css).toMatch(/@media \(width >= 40rem\) \{\s*html\[data-dialog-viewport\] \.app-vv-dialog \{\s*top: calc\(var\(--app-vv-top, 0px\) \+ var\(--app-vv-height, 100dvh\) \* 0\.12\);/)
  })

  it('is the class of those two dialogs, which end the layout when they have left', () => {
    for (const file of ['AppSearch.vue', 'AskTheWeather.vue']) {
      const text = component(file)
      expect(text, file).toContain('content: \'app-vv-dialog ')
      expect(text, file).toMatch(/useModalDialogHold\(/)
      expect(text, file).toMatch(/@after:leave="\w+\.afterLeave"/)
    }
    expect(component('AppTabBar.vue')).toMatch(/useModalDialogHold\(open, \{ layout: false \}\)/)
  })

  it('closes the search with the route, as the menu sheet is', () => {
    expect(component('AppSearch.vue')).toMatch(/watch\(\(\) => route\.path, \(\) => \{\s*open\.value = false\s*\}\)/)
  })
})
