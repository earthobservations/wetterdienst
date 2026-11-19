import { computed, onScopeDispose, watch } from 'vue'
import { PHONE_QUERY } from '~/composables/usePhone'
import { BAR_HIDE_AFTER, BAR_SCROLL_THRESHOLD, shownBarScroll, stepBarScroll } from '~/utils/bar-scroll'

/** The attribute of `<html>` that says the bars are hidden: `main.css` slides them away by it, on a phone only */
export const BARS_ATTRIBUTE = 'data-bars'

/** What the bars are: the top bar and the tab bar, whatever is focused in them brings both back */
export const BARS_SELECTOR = '.app-header, .app-tabbar'

/** The window as low as the bars stop being fixed (`main.css`): they scroll with the page there, and need no hiding */
const LOW_WINDOW_QUERY = '(max-height: 30rem)'

/**
 * Something that floats over the page and belongs to a bar or to the page's own tools: a modal dialog, and the popover,
 * menu or list of a trigger that says it is open. The bars stay where they are while one is, since a popover that hangs
 * under the top bar would be left in the air by it.
 */
const OVERLAY_SELECTOR = '[role="dialog"][data-state="open"], [aria-haspopup][aria-expanded="true"], [role="combobox"][aria-expanded="true"]'

/** Whether a dialog, popover, menu or list is open in `doc` */
export function overlayIsOpen(doc: Document): boolean {
  return doc.querySelector(OVERLAY_SELECTOR) !== null
}

export interface BarsHideOptions {
  /** The window and its document: a test serves its own */
  win?: Window
}

/**
 * The bars of the phone hide on scroll (GH-4226): scrolling down slides the top bar up and the tab bar down, scrolling up
 * or reaching the top brings them back, and `<html data-bars="hidden">` says which (the slide itself is CSS, a transform
 * and `--bars-shown` in `main.css`, so the page does not change its height and does not jump).
 *
 * Only below 40 rem (`PHONE_QUERY`), and not where the bars are not fixed (a phone on its side, a window as low as 30 rem).
 * A page can say it keeps them (`definePageMeta({ barsHide: false })`, the map, which fills the window between them), and the
 * widget has none. The bars are shown, never hidden, while a dialog, a popover or the search is open, and a focus in either
 * bar brings both back, so a keyboard that tabs into a hidden bar sees where it is (WCAG 2.4.7, 2.4.11); the bars are not
 * `display: none` or `visibility: hidden`, so the landmarks and the tab order are as they were. The direction logic is
 * `utils/bar-scroll.ts`. Call it once, in the root component.
 */
export function useBarsHideOnScroll(options: BarsHideOptions = {}) {
  if (import.meta.server)
    return

  const win = options.win ?? window
  const doc = win.document
  const root = doc.documentElement
  const route = useRoute()
  const phone = useMediaQuery(PHONE_QUERY, { window: win })
  const low = useMediaQuery(LOW_WINDOW_QUERY, { window: win })
  const enabled = computed(() =>
    phone.value && !low.value && route.meta.barsHide !== false && !isWidgetPath(route.path))

  const position = () => ({ y: win.scrollY, max: root.scrollHeight - win.innerHeight })
  let state = shownBarScroll(win.scrollY)

  function apply(next: typeof state) {
    state = next
    if (next.shown)
      root.removeAttribute(BARS_ATTRIBUTE)
    else
      root.setAttribute(BARS_ATTRIBUTE, 'hidden')
  }

  /** Both bars back, and the count begins where the page is */
  function show() {
    apply(shownBarScroll(win.scrollY))
  }

  function onScroll() {
    // the page is held for a dialog (its scroll offset is put back when the dialog closes): nothing of that is the reader's scroll
    if (overlayIsOpen(doc)) {
      state = { ...state, anchor: Math.max(0, win.scrollY) }
      return
    }
    const next = stepBarScroll(state, position(), { threshold: BAR_SCROLL_THRESHOLD, hideAfter: BAR_HIDE_AFTER })
    if (next !== state)
      apply(next)
  }

  function onFocusIn(event: FocusEvent) {
    // the target is an element, or the document or window for a focus that has left
    const target = event.target as Partial<Element> | null
    if (!state.shown && typeof target?.closest === 'function' && target.closest(BARS_SELECTOR))
      show()
  }

  let stop: (() => void) | undefined
  watch(enabled, (on) => {
    stop?.()
    stop = undefined
    show()
    if (!on)
      return
    win.addEventListener('scroll', onScroll, { passive: true })
    doc.addEventListener('focusin', onFocusIn)
    stop = () => {
      win.removeEventListener('scroll', onScroll)
      doc.removeEventListener('focusin', onFocusIn)
    }
  }, { immediate: true })

  // another page begins at its own top, with the bars in view
  watch(() => route.fullPath, () => {
    if (enabled.value)
      show()
  })

  onScopeDispose(() => {
    stop?.()
    root.removeAttribute(BARS_ATTRIBUTE)
  })
}
