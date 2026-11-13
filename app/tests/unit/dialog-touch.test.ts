// @vitest-environment happy-dom
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import { useDialogTouchGuard } from '../../app/composables/useDialogTouchGuard'
import { createDialogTouchHandlers, holdDialogTouch, shouldCancelDialogTouch } from '../../app/utils/dialog-touch'

// reka-ui's own guard is on iOS only (`isIOS` of vueuse), and so is this one: the tests that go through the default
// are of an iPhone, the ones that look at the other browsers pass `false`
vi.mock('@vueuse/core', () => ({ isIOS: true }))
vi.mock('@tailwindcss/vite', () => ({ default: () => ({ name: 'tailwindcss-stub' }) }))

// Which finger moves inside an open modal dialog are cancelled (GH-3761). happy-dom has no layout, so the boxes are
// served their scroll metrics; the guard reads them and the box's `overflow`.

function box(element: Element, metrics: { top?: number, height: number, content: number, overflow?: string }) {
  const el = element as HTMLElement
  el.style.overflowY = metrics.overflow ?? 'auto'
  Object.defineProperties(el, {
    scrollTop: { value: metrics.top ?? 0, configurable: true },
    clientHeight: { value: metrics.height, configurable: true },
    scrollHeight: { value: metrics.content, configurable: true },
  })
  return el
}

function dialog(list: { top?: number, content?: number } = {}) {
  document.body.innerHTML = `
    <main id="page"><p id="behind">behind</p></main>
    <div role="dialog" id="dialog">
      <div id="field"><input id="input"></div>
      <div id="list"><div id="option">option</div></div>
      <p id="status">status</p>
    </div>`
  box(document.getElementById('dialog')!, { height: 576, content: 576, overflow: 'hidden' })
  box(document.getElementById('list')!, { top: list.top, height: 480, content: list.content ?? 1895 })
  return (id: string) => document.getElementById(id)!
}

// the finger moves down (dy > 0) to bring up what is above, or up (dy < 0) to bring up what is below
const DOWN = 12
const UP = -12

describe('a one-finger move in an open dialog (GH-3761)', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('is let through where the list can still scroll the way the finger goes', () => {
    const at = dialog({ top: 0 })
    // at its top, it scrolls down (the finger goes up) ...
    expect(shouldCancelDialogTouch(at('option'), 0, UP)).toBe(false)
    // ... and in the middle both ways
    const middle = dialog({ top: 400 })
    expect(shouldCancelDialogTouch(middle('option'), 0, UP)).toBe(false)
    expect(shouldCancelDialogTouch(middle('option'), 0, DOWN)).toBe(false)
  })

  it('is cancelled where the list is at its top and the finger pulls further up, the state right after opening', () => {
    const at = dialog({ top: 0 })
    expect(shouldCancelDialogTouch(at('option'), 0, DOWN)).toBe(true)
    expect(shouldCancelDialogTouch(at('list'), 0, DOWN)).toBe(true)
  })

  it('is cancelled where the list is at its end and the finger pushes further on', () => {
    // 1895 - 480 = 1415: scrolled to the end
    const at = dialog({ top: 1415 })
    expect(shouldCancelDialogTouch(at('option'), 0, UP)).toBe(true)
    expect(shouldCancelDialogTouch(at('option'), 0, DOWN)).toBe(false)
  })

  it('takes a pixel from the top and from the end for rounding, the same at both', () => {
    // a scroll position of 1 is the top, as a position of 1414 (a pixel short of 1415) is the end
    expect(shouldCancelDialogTouch(dialog({ top: 1 })('option'), 0, DOWN)).toBe(true)
    expect(shouldCancelDialogTouch(dialog({ top: 2 })('option'), 0, DOWN)).toBe(false)
    expect(shouldCancelDialogTouch(dialog({ top: 1414 })('option'), 0, UP)).toBe(true)
    expect(shouldCancelDialogTouch(dialog({ top: 1413 })('option'), 0, UP)).toBe(false)
    // and sideways
    const wide = dialog()
    const list = wide('list')
    list.style.overflowX = 'auto'
    Object.defineProperties(list, {
      scrollLeft: { value: 1, configurable: true },
      clientWidth: { value: 300, configurable: true },
      scrollWidth: { value: 900, configurable: true },
    })
    expect(shouldCancelDialogTouch(wide('option'), 30, 0)).toBe(true)
    Object.defineProperty(list, 'scrollLeft', { value: 2, configurable: true })
    expect(shouldCancelDialogTouch(wide('option'), 30, 0)).toBe(false)
  })

  it('is cancelled on a list that does not overflow, and on the parts that do not scroll', () => {
    const short = dialog({ content: 480 })
    expect(shouldCancelDialogTouch(short('option'), 0, UP)).toBe(true)
    expect(shouldCancelDialogTouch(short('option'), 0, DOWN)).toBe(true)
    const at = dialog({ top: 400 })
    for (const id of ['input', 'field', 'status', 'dialog']) {
      expect(shouldCancelDialogTouch(at(id), 0, UP), id).toBe(true)
      expect(shouldCancelDialogTouch(at(id), 0, DOWN), id).toBe(true)
    }
  })

  it('is cancelled on a list that overflows but may not scroll (overflow hidden)', () => {
    const at = dialog({ top: 400 })
    box(at('list'), { top: 400, height: 480, content: 1895, overflow: 'hidden' })
    expect(shouldCancelDialogTouch(at('option'), 0, UP)).toBe(true)
  })

  it('is not this guard\'s outside a dialog, or for a move that did not move', () => {
    const at = dialog({ top: 0 })
    expect(shouldCancelDialogTouch(at('behind'), 0, UP)).toBe(false)
    expect(shouldCancelDialogTouch(at('option'), 0, 0)).toBe(false)
    expect(shouldCancelDialogTouch(null, 0, UP)).toBe(false)
    expect(shouldCancelDialogTouch(document, 0, UP)).toBe(false)
  })

  it('follows the dominant axis: a sideways move on a list that scrolls only up and down is cancelled', () => {
    const at = dialog({ top: 400 })
    expect(shouldCancelDialogTouch(at('option'), 30, 5)).toBe(true)
  })
})

/** A touch event as the handlers read it: the fingers' positions, the target, and whether it can be cancelled */
function touch(target: Element, fingers: [number, number][], cancelable = true) {
  const event = {
    target,
    cancelable,
    touches: fingers.map(([clientX, clientY]) => ({ clientX, clientY })),
    preventDefault: vi.fn(),
  }
  return event as unknown as TouchEvent & { preventDefault: ReturnType<typeof vi.fn> }
}

function zoomed(scale: number | undefined) {
  Object.defineProperty(window, 'visualViewport', { value: scale === undefined ? undefined : { scale }, configurable: true })
}

describe('the handlers of the guard (GH-3761)', () => {
  afterEach(() => {
    document.body.innerHTML = ''
    zoomed(undefined)
  })

  it('cancels a move down at the top of the list, and not one up', () => {
    const at = dialog({ top: 0 })
    const handlers = createDialogTouchHandlers()
    handlers.start(touch(at('option'), [[100, 300]]))
    const up = touch(at('option'), [[100, 280]])
    handlers.move(up)
    expect(up.preventDefault).not.toHaveBeenCalled()
    const down = touch(at('option'), [[100, 300]])
    handlers.move(down)
    expect(down.preventDefault).toHaveBeenCalledOnce()
  })

  it('does not cancel an event the browser has begun to scroll (not cancelable)', () => {
    const at = dialog({ top: 0 })
    const handlers = createDialogTouchHandlers()
    handlers.start(touch(at('option'), [[100, 300]]))
    const down = touch(at('option'), [[100, 320]], false)
    handlers.move(down)
    expect(down.preventDefault).not.toHaveBeenCalled()
  })

  it('leaves a pan of a zoomed-in page alone, where the list is at its edge as everywhere (WCAG 1.4.4)', () => {
    const at = dialog({ top: 0 })
    const handlers = createDialogTouchHandlers()
    handlers.start(touch(at('option'), [[100, 300]]))
    zoomed(2)
    const down = touch(at('option'), [[100, 330]])
    handlers.move(down)
    expect(down.preventDefault).not.toHaveBeenCalled()
    // a scale of 1 is no zoom, and a page that reports no visual viewport is not zoomed
    zoomed(1)
    handlers.move(down)
    expect(down.preventDefault).toHaveBeenCalledOnce()
    zoomed(undefined)
    handlers.start(touch(at('option'), [[100, 300]]))
    const again = touch(at('option'), [[100, 330]])
    handlers.move(again)
    expect(again.preventDefault).toHaveBeenCalledOnce()
  })

  it('leaves a pinch alone', () => {
    const at = dialog({ top: 0 })
    const handlers = createDialogTouchHandlers()
    handlers.start(touch(at('option'), [[100, 300], [200, 300]]))
    const pinch = touch(at('option'), [[100, 330], [200, 270]])
    handlers.move(pinch)
    expect(pinch.preventDefault).not.toHaveBeenCalled()
  })

  it('reads the direction from the travel since the finger was last measured, not from a jitter of a pixel or two', () => {
    const at = dialog({ top: 0 })
    const handlers = createDialogTouchHandlers()
    handlers.start(touch(at('option'), [[100, 300]]))
    // 1 px down: not a direction (a list at its top would have been cancelled for it)
    const jitter = touch(at('option'), [[100, 301]])
    handlers.move(jitter)
    expect(jitter.preventDefault).not.toHaveBeenCalled()
    // 10 px up from where it landed: the list's, however the jitter went
    const up = touch(at('option'), [[100, 290]])
    handlers.move(up)
    expect(up.preventDefault).not.toHaveBeenCalled()
    // and turning round is read at once, from the point it was last measured at
    const back = touch(at('option'), [[100, 296]])
    handlers.move(back)
    expect(back.preventDefault).toHaveBeenCalledOnce()
  })

  it('starts again from the finger that stays when the other of a pinch is lifted', () => {
    const at = dialog({ top: 0 })
    const handlers = createDialogTouchHandlers()
    handlers.start(touch(at('option'), [[100, 100], [200, 100]]))
    // the pinch lets go of one: the one that stays is at y = 300
    handlers.end(touch(at('option'), [[200, 300]]))
    // 10 px up from there is the list's; from the first finger's 100 it would have been 190 px down, cancelled
    const up = touch(at('option'), [[200, 290]])
    handlers.move(up)
    expect(up.preventDefault).not.toHaveBeenCalled()
  })
})

describe('the guard is held while a modal dialog is open, on iOS (GH-3761)', () => {
  let added: Array<[string, unknown]>
  let removed: string[]

  beforeEach(() => {
    added = []
    removed = []
    const add = document.addEventListener.bind(document)
    const remove = document.removeEventListener.bind(document)
    vi.spyOn(document, 'addEventListener').mockImplementation((type: string, listener: any, options?: any) => {
      if (type.startsWith('touch'))
        added.push([type, options])
      return add(type, listener, options)
    })
    vi.spyOn(document, 'removeEventListener').mockImplementation((type: string, listener: any, options?: any) => {
      if (type.startsWith('touch'))
        removed.push(type)
      return remove(type, listener, options)
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('puts the listeners on the document at the first holder and takes them off at the last', () => {
    const first = holdDialogTouch(document, true)
    expect(added.map(([type]) => type).sort()).toEqual(['touchend', 'touchmove', 'touchstart'])
    // the move listener is the one that may cancel, so it is not passive
    expect(added.find(([type]) => type === 'touchmove')![1]).toMatchObject({ passive: false, capture: true })
    const second = holdDialogTouch(document, true)
    expect(added).toHaveLength(3)
    first()
    first()
    expect(removed).toEqual([])
    second()
    expect(removed.sort()).toEqual(['touchend', 'touchmove', 'touchstart'])
  })

  it('puts none on a browser that is not iOS, which has no guard of reka-ui\'s to complete either', () => {
    const release = holdDialogTouch(document, false)
    expect(added).toEqual([])
    release()
    expect(removed).toEqual([])
  })

  it('is held by a modal while it is open: none with a popover open alone, one at a time with modals', async () => {
    const scope = effectScope()
    const search = ref(false)
    const sheet = ref(false)
    // the settings popover has a `role="dialog"` and no modal: it does not call the composable, so it has no ref here
    scope.run(() => {
      useDialogTouchGuard(search)
      useDialogTouchGuard(sheet)
    })
    await nextTick()
    expect(added).toEqual([])

    search.value = true
    expect(added.map(([type]) => type).sort()).toEqual(['touchend', 'touchmove', 'touchstart'])
    sheet.value = true
    expect(added).toHaveLength(3)
    search.value = false
    expect(removed).toEqual([])
    sheet.value = false
    expect(removed.sort()).toEqual(['touchend', 'touchmove', 'touchstart'])

    // a modal that is open when its component goes is let go of
    removed = []
    search.value = true
    scope.stop()
    expect(removed.sort()).toEqual(['touchend', 'touchmove', 'touchstart'])
  })

  it('is held by a modal that is open from the start', () => {
    const scope = effectScope()
    scope.run(() => useDialogTouchGuard(ref(true)))
    expect(added).toHaveLength(3)
    scope.stop()
    expect(removed).toHaveLength(3)
  })
})

describe('the layout under a page that covers the window (GH-3761)', () => {
  const css = readFileSync(join(__dirname, '..', '..', 'app', 'assets', 'css', 'main.css'), 'utf8')
  /** The declarations of the first rule that has `selector` as its own selector */
  const rule = (selector: string) => {
    const start = css.search(new RegExp(`^\\s*${selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\{`, 'm'))
    expect(start, selector).toBeGreaterThanOrEqual(0)
    return css.slice(start, css.indexOf('}', start))
  }

  beforeEach(() => {
    vi.stubGlobal('defineNuxtConfig', (config: any) => config)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('covers the window, so that the safe-area insets are reported', async () => {
    const config = (await import('../../nuxt.config')).default as any
    expect(config.app.head.viewport).toContain('viewport-fit=cover')
    expect(config.app.head.viewport).toContain('width=device-width')
    for (const side of ['top', 'left', 'right', 'bottom'])
      expect(css).toContain(`--safe-${side}: env(safe-area-inset-${side}`)
  })

  it('makes the header\'s height the whole of it, the status bar\'s room included, for what stands under it to measure from', () => {
    expect(css).toMatch(/--header-height:\s*calc\(var\(--header-bar\) \+ var\(--safe-top\)\)/)
    expect(rule('.app-header')).toMatch(/height:\s*var\(--header-height\)/)
    expect(rule('.app-header')).toMatch(/padding-top:\s*var\(--safe-top\)/)
    // sticky below it, the page under it and the scroll clear of it: all from that height, none adds the inset again
    expect(rule('.bar-sticky')).toMatch(/top:\s*var\(--header-height\)/)
    expect(rule('.app-main')).toMatch(/calc\(100dvh - var\(--header-height\)\)/)
    expect(rule('html')).toMatch(/scroll-padding-top:\s*calc\(var\(--header-height\) \+ 1rem\)/)
    expect(css).not.toMatch(/var\(--header-height\)[^;]*var\(--safe-top\)/)
    const map = readFileSync(join(__dirname, '..', '..', 'app', 'pages', 'map.vue'), 'utf8')
    expect(map).toContain('top: calc(var(--header-height) + 1rem)')
    // the bar proper has its own measure, which the low window lowers
    expect(css).toMatch(/--header-bar:\s*4rem/)
    expect(css).toMatch(/--header-bar:\s*3\.5rem/)
  })

  it('keeps what is fixed to an edge clear of the inset at that edge', () => {
    expect(rule('.app-tabbar')).toMatch(/padding:\s*0 var\(--safe-right\) var\(--safe-bottom\) var\(--safe-left\)/)
    expect(rule('.app-footer')).toMatch(/padding-bottom:\s*max\(var\(--tabbar-height\), var\(--safe-bottom\)\)/)
    expect(rule('.skip-link')).toMatch(/top:\s*calc\(0\.5rem \+ var\(--safe-top\)\)/)
    expect(rule('.skip-link')).toMatch(/left:\s*max\(var\(--frame-gutter\), var\(--safe-left\)\)/)
    expect(rule('.app-toast-viewport')).toMatch(/bottom:\s*calc\(max\(var\(--tabbar-height\), var\(--safe-bottom\)\) \+ 1rem\)/)
    expect(rule('.app-toast-viewport')).toMatch(/right:\s*calc\(1rem \+ var\(--safe-right\)\)/)
    expect(rule('.frame')).toMatch(/padding-inline:\s*max\(var\(--frame-gutter\), var\(--safe-left\)\) max\(var\(--frame-gutter\), var\(--safe-right\)\)/)
  })

  it('pads the menu sheet only where it is a sheet on the window\'s foot (below sm, 40 rem)', () => {
    const at = css.indexOf('.menu-sheet {')
    expect(at).toBeGreaterThan(0)
    expect(css.slice(css.lastIndexOf('@media', at), at)).toMatch(/@media \(width < 40rem\)\s*\{\s*$/)
    expect(rule('.menu-sheet')).toMatch(/padding-bottom:\s*var\(--safe-bottom\)/)
  })
})
