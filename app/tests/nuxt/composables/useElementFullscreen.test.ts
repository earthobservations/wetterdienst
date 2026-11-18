import type { EffectScope } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import { useElementFullscreen } from '~/composables/useElementFullscreen'
import { inertOutside } from '~/utils/fullscreen'

// The state machine of the map's full screen (GH-4227): off, native (the browser's API), app (the page covered by the element),
// with the Fullscreen API served by hand, present and absent.

interface Api {
  fullscreenEnabled?: boolean
  fullscreenElement?: Element | null
  exitFullscreen?: () => Promise<void>
  webkitFullscreenEnabled?: boolean
  webkitFullscreenElement?: Element | null
  webkitExitFullscreen?: () => void
}
const doc = document as unknown as Api

/** The page: `<main><div class="before"/><div id="stage"/><div class="after"/></main>`, and the element that goes full screen */
function page() {
  const root = document.createElement('div')
  root.innerHTML = '<header class="bar"></header><main><section class="before"></section><div id="stage"><button id="inside"></button></div><section class="after"></section></main><footer class="foot"></footer>'
  document.body.append(root)
  const stage = root.querySelector<HTMLElement>('#stage')!
  return { root, stage }
}

/** What the document and the element do where the browser has the API: the element is full screen when the request is made */
function serveApi(stage: HTMLElement, options: { reject?: boolean } = {}) {
  doc.fullscreenEnabled = true
  doc.fullscreenElement = null
  const request = vi.fn(async () => {
    if (options.reject)
      throw new TypeError('Permissions check failed')
    doc.fullscreenElement = stage
    document.dispatchEvent(new Event('fullscreenchange'))
  })
  ;(stage as unknown as { requestFullscreen: unknown }).requestFullscreen = request
  const exit = vi.fn(async () => {
    doc.fullscreenElement = null
    document.dispatchEvent(new Event('fullscreenchange'))
  })
  doc.exitFullscreen = exit
  return { request, exit }
}

function withoutApi() {
  doc.fullscreenEnabled = false
  doc.fullscreenElement = null
  doc.exitFullscreen = undefined
}

let scope: EffectScope
function machine(stage: HTMLElement, options: Parameters<typeof useElementFullscreen>[1] = {}) {
  return scope.run(() => useElementFullscreen(ref(stage), options))!
}
const press = (key: string) => window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))

let fixture: ReturnType<typeof page>
beforeEach(() => {
  fixture = page()
  scope = effectScope()
})
afterEach(() => {
  scope.stop()
  fixture.root.remove()
  document.documentElement.style.overflow = ''
  delete doc.fullscreenEnabled
  delete doc.fullscreenElement
  delete doc.exitFullscreen
  delete doc.webkitFullscreenEnabled
  delete doc.webkitFullscreenElement
  delete doc.webkitExitFullscreen
  vi.useRealTimers()
})

describe('where the browser has the Fullscreen API for an element', () => {
  it('goes from off to native on enter, and back on exit', async () => {
    const { request, exit } = serveApi(fixture.stage)
    const fullscreen = machine(fixture.stage)
    expect(fullscreen.mode.value).toBe('off')
    expect(fullscreen.canNative()).toBe(true)

    await fullscreen.enter()
    expect(request).toHaveBeenCalledOnce()
    expect(fullscreen.mode.value).toBe('native')
    expect(fullscreen.active.value).toBe(true)
    // the browser's own full screen leaves the page as it is: nothing is made inert, nothing is locked
    expect(document.querySelectorAll('[inert]')).toHaveLength(0)

    await fullscreen.exit()
    expect(exit).toHaveBeenCalledOnce()
    expect(fullscreen.mode.value).toBe('off')
  })

  it('toggles, and does nothing twice: a second enter while full screen asks nothing again', async () => {
    const { request } = serveApi(fixture.stage)
    const fullscreen = machine(fixture.stage)
    await Promise.all([fullscreen.enter(), fullscreen.enter()])
    await fullscreen.enter()
    expect(request).toHaveBeenCalledOnce()
    await fullscreen.toggle()
    expect(fullscreen.mode.value).toBe('off')
    await fullscreen.toggle()
    expect(fullscreen.mode.value).toBe('native')
  })

  it('follows the browser out of full screen (its own Escape, an exit control), with no call of ours', async () => {
    const { exit } = serveApi(fixture.stage)
    const fullscreen = machine(fixture.stage)
    await fullscreen.enter()
    doc.fullscreenElement = null
    document.dispatchEvent(new Event('fullscreenchange'))
    expect(fullscreen.mode.value).toBe('off')
    expect(exit).not.toHaveBeenCalled()
  })

  it('follows another element taking the screen as leaving it', async () => {
    serveApi(fixture.stage)
    const fullscreen = machine(fixture.stage)
    await fullscreen.enter()
    doc.fullscreenElement = document.body
    document.dispatchEvent(new Event('fullscreenchange'))
    expect(fullscreen.mode.value).toBe('off')
  })

  it('leaves by Escape where the page is handed the key, unless something of the element has it', async () => {
    const { exit } = serveApi(fixture.stage)
    let taken = false
    const fullscreen = machine(fixture.stage, { escapeTaken: () => taken })
    await fullscreen.enter()
    taken = true
    press('Escape')
    expect(fullscreen.mode.value).toBe('native')
    taken = false
    press('Escape')
    await nextTick()
    expect(fullscreen.mode.value).toBe('off')
    expect(exit).toHaveBeenCalledOnce()
    // no longer listening
    await fullscreen.enter()
    press('Enter')
    expect(fullscreen.mode.value).toBe('native')
  })

  it('covers the page itself where the browser refuses the request, as a browser with no API would', async () => {
    const { request } = serveApi(fixture.stage, { reject: true })
    const fullscreen = machine(fixture.stage)
    await fullscreen.enter()
    expect(request).toHaveBeenCalledOnce()
    expect(fullscreen.mode.value).toBe('app')
    expect(fixture.root.querySelector('.bar')?.hasAttribute('inert')).toBe(true)
  })

  it('gives the screen back when the scope ends (a route change)', async () => {
    const { exit } = serveApi(fixture.stage)
    const inner = effectScope()
    const fullscreen = inner.run(() => useElementFullscreen(ref(fixture.stage)))!
    await fullscreen.enter()
    inner.stop()
    expect(exit).toHaveBeenCalledOnce()
    expect(fullscreen.mode.value).toBe('off')
  })
})

/** WebKit's prefixed API: the call answers nothing, and an event says what came of it */
function servePrefixedApi(stage: HTMLElement, outcome: 'enters' | 'refuses' | 'silence') {
  doc.fullscreenEnabled = undefined
  doc.webkitFullscreenEnabled = true
  doc.webkitFullscreenElement = null
  const request = vi.fn(() => {
    if (outcome === 'enters') {
      doc.webkitFullscreenElement = stage
      document.dispatchEvent(new Event('webkitfullscreenchange'))
    }
    else if (outcome === 'refuses') {
      document.dispatchEvent(new Event('webkitfullscreenerror'))
    }
  })
  ;(stage as unknown as { webkitRequestFullscreen: unknown }).webkitRequestFullscreen = request
  doc.webkitExitFullscreen = vi.fn(() => {
    doc.webkitFullscreenElement = null
    document.dispatchEvent(new Event('webkitfullscreenchange'))
  })
  return request
}

describe('where the browser has the prefixed API only (WebKit)', () => {
  it('goes to native when the change event says it went', async () => {
    const request = servePrefixedApi(fixture.stage, 'enters')
    const fullscreen = machine(fixture.stage)
    expect(fullscreen.canNative()).toBe(true)
    await fullscreen.enter()
    expect(request).toHaveBeenCalledOnce()
    expect(fullscreen.mode.value).toBe('native')
    await fullscreen.exit()
    expect(doc.webkitExitFullscreen).toHaveBeenCalledOnce()
    expect(fullscreen.mode.value).toBe('off')
  })

  it('covers the page itself when the error event says it was refused, not stays native', async () => {
    servePrefixedApi(fixture.stage, 'refuses')
    const fullscreen = machine(fixture.stage)
    await fullscreen.enter()
    expect(fullscreen.mode.value).toBe('app')
    expect(fixture.root.querySelector('.bar')?.hasAttribute('inert')).toBe(true)
    // and can be left, and asked again
    await fullscreen.exit()
    expect(fullscreen.mode.value).toBe('off')
  })

  it('covers the page itself when neither event comes, after a moment, and waits for nothing else meanwhile', async () => {
    vi.useFakeTimers()
    servePrefixedApi(fixture.stage, 'silence')
    const fullscreen = machine(fixture.stage)
    const entering = fullscreen.enter()
    await vi.advanceTimersByTimeAsync(100)
    expect(fullscreen.mode.value).toBe('off')
    await vi.advanceTimersByTimeAsync(2000)
    await entering
    expect(fullscreen.mode.value).toBe('app')
  })

  it('takes the standard error event for a refusal too', async () => {
    servePrefixedApi(fixture.stage, 'silence')
    const fullscreen = machine(fixture.stage)
    const entering = fullscreen.enter()
    document.dispatchEvent(new Event('fullscreenerror'))
    await entering
    expect(fullscreen.mode.value).toBe('app')
  })
})

describe('where the browser has none (iPhone Safari)', () => {
  beforeEach(withoutApi)

  it('goes from off to app on enter, with the page behind it inert and still', async () => {
    const fullscreen = machine(fixture.stage)
    expect(fullscreen.canNative()).toBe(false)
    await fullscreen.enter()
    expect(fullscreen.mode.value).toBe('app')
    const root = fixture.root
    // everything of the page but the stage and what it is in
    for (const selector of ['.bar', '.before', '.after', '.foot'])
      expect(root.querySelector(selector)?.hasAttribute('inert'), selector).toBe(true)
    expect(fixture.stage.hasAttribute('inert')).toBe(false)
    expect(fixture.stage.parentElement?.hasAttribute('inert')).toBe(false)
    expect(root.querySelector('main')?.hasAttribute('inert')).toBe(false)
    expect(document.documentElement.style.overflow).toBe('hidden')
  })

  it('puts everything back on exit, and leaves what was inert before as it was', async () => {
    fixture.root.querySelector('.foot')!.setAttribute('inert', '')
    document.documentElement.style.overflow = 'scroll'
    const fullscreen = machine(fixture.stage)
    await fullscreen.enter()
    await fullscreen.exit()
    expect(fullscreen.mode.value).toBe('off')
    expect(fixture.root.querySelector('.bar')?.hasAttribute('inert')).toBe(false)
    expect(fixture.root.querySelector('.before')?.hasAttribute('inert')).toBe(false)
    expect(fixture.root.querySelector('.foot')?.hasAttribute('inert')).toBe(true)
    expect(document.documentElement.style.overflow).toBe('scroll')
  })

  it('leaves by Escape, and a panel that Escape closes first has the first press', async () => {
    let panelOpen = true
    const fullscreen = machine(fixture.stage, { escapeTaken: () => panelOpen })
    await fullscreen.enter()
    // the panel closes on its own handler, which may run before ours: the press is read as it came
    window.addEventListener('keydown', () => {
      panelOpen = false
    }, { capture: true, once: true })
    press('Escape')
    expect(fullscreen.mode.value).toBe('app')
    press('Escape')
    expect(fullscreen.mode.value).toBe('off')
    expect(fixture.root.querySelector('.bar')?.hasAttribute('inert')).toBe(false)
  })

  it('does not leave by a press that something else has answered (defaultPrevented)', async () => {
    const fullscreen = machine(fixture.stage)
    // answered by a handler that was there first (a popover's, which prevents the default of the key it takes)
    const handler = (event: KeyboardEvent) => event.preventDefault()
    window.addEventListener('keydown', handler)
    await fullscreen.enter()
    press('Escape')
    window.removeEventListener('keydown', handler)
    expect(fullscreen.mode.value).toBe('app')
  })

  it('has no element to cover until the page has one: enter is a no-op', async () => {
    const fullscreen = scope.run(() => useElementFullscreen(ref<HTMLElement | null>(null)))!
    await fullscreen.enter()
    expect(fullscreen.mode.value).toBe('off')
  })

  it('lets go of the page when the scope ends', async () => {
    const inner = effectScope()
    const fullscreen = inner.run(() => useElementFullscreen(ref(fixture.stage)))!
    await fullscreen.enter()
    inner.stop()
    expect(fixture.root.querySelector('.bar')?.hasAttribute('inert')).toBe(false)
    expect(document.documentElement.style.overflow).toBe('')
    expect(fullscreen.mode.value).toBe('off')
  })
})

describe('inertOutside', () => {
  it('makes the siblings of the element and of its ancestors inert, up to the body, and no more', () => {
    const { root, stage } = fixture
    const release = inertOutside(stage)
    expect(stage.querySelector('#inside')?.hasAttribute('inert')).toBe(false)
    expect(document.body.hasAttribute('inert')).toBe(false)
    release()
    expect(root.querySelectorAll('[inert]')).toHaveLength(0)
  })
})
