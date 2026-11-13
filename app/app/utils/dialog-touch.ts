// Which finger moves inside an open dialog must be cancelled (GH-3761). A dialog (`role="dialog"`) is modal: nothing
// behind it may move, and what does move in it is its own lists. The dialog library (reka-ui) holds the page on iOS
// with a `touchmove` guard of its own, but that one steps aside for every move whose target has an overflowing
// ancestor: it does not ask whether that ancestor can still move in the direction of the finger. A list that is
// at its top or its end when the finger lands (a dialog that has just opened is at its top: the search's list of 31
// entries) then lets the move go on to the page behind it, where `overscroll-behavior` is the only thing in the way
// (it is not enough on iOS with the on-screen keyboard up, where the visual viewport pans). These are the decisions,
// without the events (`useDialogTouchGuard`).

const SCROLLS = /^(?:auto|scroll)$/

/**
 * Whether `element` can move the content under a finger that moved by (`dx`, `dy`) on its dominant axis: it overflows
 * on that axis, may scroll there (`overflow: auto` or `scroll`), and is not already at the end the finger pushes to
 * (a finger that moves down brings the content that is above it, so the box must be below its top)
 */
function scrollsFurther(element: HTMLElement, dx: number, dy: number): boolean {
  const style = getComputedStyle(element)
  if (Math.abs(dy) >= Math.abs(dx)) {
    if (!SCROLLS.test(style.overflowY) || element.scrollHeight - element.clientHeight <= 1)
      return false
    return dy > 0 ? element.scrollTop > 0 : element.scrollTop + element.clientHeight < element.scrollHeight - 1
  }
  if (!SCROLLS.test(style.overflowX) || element.scrollWidth - element.clientWidth <= 1)
    return false
  return dx > 0 ? element.scrollLeft > 0 : element.scrollLeft + element.clientWidth < element.scrollWidth - 1
}

/**
 * Whether a one-finger move that started on `target` is to be cancelled: it is inside a dialog and none of the boxes
 * between the target and the dialog (the dialog's own included) can still scroll the way the finger goes. A move that
 * has no dialog above its target is not this guard's (the page's own scroll when no dialog is open, a toast).
 * `dx` and `dy` are the finger's move since its last position.
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
