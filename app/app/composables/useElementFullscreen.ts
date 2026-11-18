import type { Ref } from 'vue'
import type { FullscreenDocument, FullscreenMode } from '~/utils/fullscreen'
import { computed, onScopeDispose, ref } from 'vue'
import {
  exitNativeFullscreen,
  FULLSCREEN_EVENTS,
  fullscreenElementOf,
  inertOutside,
  requestNativeFullscreen,
  supportsNativeFullscreen,
} from '~/utils/fullscreen'

/** What the composable reads of the page: a test serves its own document */
type PageDocument = Document & FullscreenDocument

export interface ElementFullscreenOptions {
  /** The document the element is in (the page's own, where none is given) */
  doc?: PageDocument
  /** Whether something of the element has the Escape key before the element's full screen does (an open panel): asked at the key press */
  escapeTaken?: () => boolean
}

/**
 * The full screen of one element (GH-4227), a state machine of three states (`utils/fullscreen.ts` says what they are):
 * `off`, `native` (the browser's Fullscreen API) and `app` (the element covers the page, the rest of it inert).
 *
 * - `enter()` goes `off` to `native` where the document supports the API for the element, and to `app` where it does not
 *   and where the browser refuses the request. It does nothing while the element is full screen or a request is on its way.
 * - `exit()` goes back to `off` from either, and is a no-op when it is.
 * - A change made by the browser (its Escape, the exit control of an iPad) is taken: the state follows `fullscreenchange`.
 * - The Escape key leaves, unless `escapeTaken()` says something of the element has it (a popover that Escape closes
 *   first). In `native` the browser leaves by Escape itself (and does not always hand the key to the page); in `app` the
 *   page behind does not scroll and is `inert` for as long as it lasts.
 *
 * Focus is the caller's: it watches `mode` (the change is flushed synchronously) and knows where the focus goes.
 * The element is not moved or re-created by any of this, so what it holds (a map's view, a picked station) is kept.
 * Everything is put back when the scope ends, a route change included.
 */
export function useElementFullscreen(target: Ref<HTMLElement | null>, options: ElementFullscreenOptions = {}) {
  const mode = ref<FullscreenMode>('off')
  const active = computed(() => mode.value !== 'off')
  const doc = () => options.doc ?? (document as PageDocument)
  let requesting = false

  let releaseInert: (() => void) | undefined
  let releaseScroll: (() => void) | undefined
  let releaseKeys: (() => void) | undefined
  /** Whether the Escape of the press in hand was taken by something of the element: read at the press, in the capture phase, before that thing closes */
  let escapeWasTaken = false

  /** Whether the document would let the element go full screen by the API now (read when asked: the element is there only once mounted) */
  function canNative(): boolean {
    const element = target.value
    return Boolean(element && supportsNativeFullscreen(doc(), element))
  }

  function holdApp(element: HTMLElement) {
    releaseInert = inertOutside(element)
    const root = doc().documentElement
    const overflow = root.style.overflow
    root.style.overflow = 'hidden'
    releaseScroll = () => {
      root.style.overflow = overflow
    }
  }

  /** Escape leaves, in either mode: the browser leaves its own full screen by Escape first (and does not always hand the key on), and a browser that does finds nothing left to do */
  function holdKeys() {
    const before = (event: KeyboardEvent) => {
      if (event.key === 'Escape')
        escapeWasTaken = options.escapeTaken?.() ?? false
    }
    const after = (event: KeyboardEvent) => {
      if (event.key !== 'Escape')
        return
      const taken = escapeWasTaken
      escapeWasTaken = false
      if (taken || event.defaultPrevented)
        return
      event.preventDefault()
      void exit()
    }
    const view = doc().defaultView
    view?.addEventListener('keydown', before, true)
    view?.addEventListener('keydown', after)
    releaseKeys = () => {
      view?.removeEventListener('keydown', before, true)
      view?.removeEventListener('keydown', after)
    }
  }

  function letGoOf() {
    releaseKeys?.()
    releaseScroll?.()
    releaseInert?.()
    releaseKeys = releaseScroll = releaseInert = undefined
  }

  function set(next: FullscreenMode) {
    if (mode.value === next)
      return
    letGoOf()
    mode.value = next
    const element = target.value
    if (next !== 'off')
      holdKeys()
    if (next === 'app' && element)
      holdApp(element)
  }

  async function enter() {
    const element = target.value
    if (!element || mode.value !== 'off' || requesting)
      return
    if (!canNative()) {
      set('app')
      return
    }
    requesting = true
    try {
      await requestNativeFullscreen(element)
      // the event has usually said so already; a browser that is slow with it, or a prefixed one, is taken at its word
      if (mode.value === 'off')
        set('native')
    }
    catch {
      // refused (a frame that may not, a call that is no gesture): the app does what the browser would not
      if (mode.value === 'off')
        set('app')
    }
    finally {
      requesting = false
    }
  }

  async function exit() {
    if (mode.value === 'off')
      return
    const was = mode.value
    // the state goes first, so that the event of the browser that follows has nothing left to say
    set('off')
    if (was === 'native' && fullscreenElementOf(doc()) !== null) {
      try {
        await exitNativeFullscreen(doc())
      }
      catch {
        // already out of it
      }
    }
  }

  function toggle() {
    return mode.value === 'off' ? enter() : exit()
  }

  // the browser changed it: its Escape, an exit control, another element that took the screen
  const onChange = () => {
    const element = target.value
    const full = fullscreenElementOf(doc())
    if (element && full === element) {
      if (mode.value === 'off')
        set('native')
    }
    else if (mode.value === 'native') {
      set('off')
    }
  }
  if (typeof document !== 'undefined') {
    for (const name of FULLSCREEN_EVENTS)
      doc().addEventListener(name, onChange)
  }

  onScopeDispose(() => {
    for (const name of FULLSCREEN_EVENTS)
      doc().removeEventListener(name, onChange)
    const element = target.value
    if (mode.value === 'native' && element && fullscreenElementOf(doc()) === element)
      void exitNativeFullscreen(doc()).catch(() => {})
    letGoOf()
    mode.value = 'off'
  })

  return { mode, active, canNative, enter, exit, toggle }
}
