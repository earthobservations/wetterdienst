import { isIOS } from '@vueuse/core'

// Which finger moves inside an open modal dialog are cancelled (GH-3761), on iOS. A modal dialog is a `role="dialog"`
// over a page that must not move: what moves is its own lists. The dialog library (reka-ui) holds the page on iOS with
// a `touchmove` guard of its own, installed for as long as a modal is open, but that one steps aside for every move
// whose target has an overflowing ancestor: it does not ask whether that ancestor can still move the way the finger
// goes. A list that is at its top or its end when the finger lands (the search's list of 31 entries, just opened) then
// lets the move go on to the page behind it, where `overscroll-behavior` is the only thing in the way. This guard is
// reka's, completed: the same platform, the same lifetime (`holdDialogTouch`, taken while a modal is open and let go
// of when the last one closes), and the question reka does not ask.
//
// What it does not cover: a move the browser has begun to scroll already is not cancelable (`event.cancelable` is
// false), so a gesture that began inside a list and went past its end is left to `overscroll-behavior`; a pan of the
// visual viewport that is not a touch move of the page (the keyboard's, which the browser makes itself) is not a move
// this sees; and a pan while the page is zoomed in is the reader's (WCAG 1.4.4), never cancelled.

const SCROLLS = /^(?:auto|scroll)$/

/** Under this many pixels of travel a move is not a direction yet (a finger resting on the glass jitters) */
const MIN_TRAVEL = 4

/**
 * Whether `element` can move the content under a finger that moved by (`dx`, `dy`) on its dominant axis: it overflows
 * on that axis, may scroll there (`overflow: auto` or `scroll`), and is not already at the end the finger pushes to
 * (a finger that moves down brings the content that is above it, so the box must be more than a pixel below its top;
 * a pixel is the rounding of a fractional scroll position)
 */
function scrollsFurther(element: HTMLElement, dx: number, dy: number): boolean {
  const style = getComputedStyle(element)
  if (Math.abs(dy) >= Math.abs(dx)) {
    if (!SCROLLS.test(style.overflowY) || element.scrollHeight - element.clientHeight <= 1)
      return false
    return dy > 0 ? element.scrollTop > 1 : element.scrollTop + element.clientHeight < element.scrollHeight - 1
  }
  if (!SCROLLS.test(style.overflowX) || element.scrollWidth - element.clientWidth <= 1)
    return false
  return dx > 0 ? element.scrollLeft > 1 : element.scrollLeft + element.clientWidth < element.scrollWidth - 1
}

/**
 * Whether a one-finger move that started on `target` is to be cancelled: it is inside a dialog and none of the boxes
 * between the target and the dialog (the dialog's own included) can still scroll the way the finger goes. A move that
 * has no dialog above its target is not this guard's. `dx` and `dy` are the finger's move.
 */
export function shouldCancelDialogTouch(target: EventTarget | null, dx: number, dy: number): boolean {
  if (!(target instanceof Element))
    return false
  const dialog = target.closest('[role="dialog"]')
  if (!dialog || (dx === 0 && dy === 0))
    return false
  for (let node: Element | null = target; node; node = node.parentElement) {
    if (node instanceof HTMLElement && scrollsFurther(node, dx, dy))
      return false
    if (node === dialog)
      break
  }
  return true
}

/** What the guard reads of the window: whether the page is zoomed in, which a test serves */
function isZoomedIn(): boolean {
  const viewport = typeof window === 'undefined' ? undefined : window.visualViewport
  return !!viewport && viewport.scale > 1
}

/**
 * The listeners of the guard for one gesture at a time. The direction of a move is the finger's travel from where it
 * was last measured, which is where it landed to begin with, and moves under `MIN_TRAVEL` are not measured (a direction
 * from two pixels is noise, and was a coin toss at a list's edge); a move that is measured moves that point on, so a
 * finger that turns round inside a list is read at once. A finger that is lifted while another stays (a pinch let go
 * of) starts again from where the one that stays is.
 */
export function createDialogTouchHandlers() {
  let lastX = 0
  let lastY = 0
  const rest = (touch: { clientX: number, clientY: number } | undefined) => {
    if (touch) {
      lastX = touch.clientX
      lastY = touch.clientY
    }
  }
  return {
    start: (event: TouchEvent) => rest(event.touches[0]),
    end: (event: TouchEvent) => rest(event.touches[0]),
    move: (event: TouchEvent) => {
      const touch = event.touches[0]
      // a pinch, and a pan of a page that is zoomed in, are the reader's (WCAG 1.4.4)
      if (!touch || event.touches.length > 1 || isZoomedIn())
        return
      const dx = touch.clientX - lastX
      const dy = touch.clientY - lastY
      if (Math.max(Math.abs(dx), Math.abs(dy)) < MIN_TRAVEL)
        return
      rest(touch)
      if (event.cancelable && shouldCancelDialogTouch(event.target, dx, dy))
        event.preventDefault()
    },
  }
}

// how many modal dialogs hold the guard, and what takes it down
let holders = 0
let release: (() => void) | undefined

/**
 * Takes the guard for a modal dialog that is open, on `target`'s document, and returns what lets go of it. The
 * listeners are put on the document at the first holder and taken off at the last, so a page with no modal open has none
 * of them. Only where reka-ui's own guard is (iOS; `ios` is that, and is read here so that a test can serve it): the
 * report is of iOS Safari, and the other browsers' scroll chaining is `overscroll-behavior`'s.
 */
export function holdDialogTouch(target: Document = document, ios: boolean = isIOS): () => void {
  if (!ios)
    return () => {}
  if (holders++ === 0) {
    const handlers = createDialogTouchHandlers()
    // capture, so that it sees the move before a handler of a part of the page that stops it
    target.addEventListener('touchstart', handlers.start, { passive: true, capture: true })
    target.addEventListener('touchend', handlers.end, { passive: true, capture: true })
    target.addEventListener('touchmove', handlers.move, { passive: false, capture: true })
    release = () => {
      target.removeEventListener('touchstart', handlers.start, { capture: true })
      target.removeEventListener('touchend', handlers.end, { capture: true })
      target.removeEventListener('touchmove', handlers.move, { capture: true })
    }
  }
  let held = true
  return () => {
    if (!held)
      return
    held = false
    if (--holders === 0) {
      release?.()
      release = undefined
    }
  }
}
