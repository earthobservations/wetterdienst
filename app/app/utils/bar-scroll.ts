/**
 * When the bars of the phone hide (GH-4226): the direction of the scroll, read from where the page is, not from the events.
 * The pure part of `useBarsHideOnScroll`; it knows nothing of the DOM, so a test can walk a page up and down.
 *
 * The bars are shown at the top; scrolling down by `BAR_SCROLL_THRESHOLD` px hides them (past `BAR_HIDE_AFTER`, so a
 * page that has hardly left its top keeps them); scrolling up by the threshold shows them; the top shows them at once.
 * The state keeps one anchor, the farthest point reached in the direction the bars last went (the lowest point while
 * they are shown, the highest while they are hidden), so a reader who turns round after 300 px of scrolling has the
 * bars back after 12 px of the way back, and a finger that trembles by a few pixels changes nothing.
 *
 * Where the page is reported outside what it can scroll to (iOS Safari's rubber band: a negative offset above the top,
 * more than the scrollable length under the foot) it is read as the nearest end, so that the bounce back from the foot is
 * no scroll up and does not bring the bars back.
 */

/** How far the page is scrolled in one direction before the bars change, in px: a tremble and a small flick change nothing */
export const BAR_SCROLL_THRESHOLD = 12

/** How far from the top the page has to be before the bars may hide, in px: about the height of the top bar */
export const BAR_HIDE_AFTER = 48

export interface BarScrollState {
  /** Whether the bars are shown */
  shown: boolean
  /** The farthest point reached in the direction the bars last went, in px from the top */
  anchor: number
}

/** The page where the scroll is read */
export interface BarScrollPosition {
  /** `scrollY`: negative above the top on iOS's rubber band */
  y: number
  /** The longest the page can be scrolled (`scrollHeight - innerHeight`): 0 or less where the page does not scroll */
  max: number
}

/** The state of a page at `y` with the bars shown: the start, and what a focus in a bar, a new page or a closed dialog puts back */
export function shownBarScroll(y = 0): BarScrollState {
  return { shown: true, anchor: Math.max(0, y) }
}

/**
 * The state after the page was scrolled to `position`. Returns the same object when nothing changed.
 * `threshold` and `hideAfter` are the tuning, in px; a test passes its own.
 */
export function stepBarScroll(
  state: BarScrollState,
  position: BarScrollPosition,
  { threshold = BAR_SCROLL_THRESHOLD, hideAfter = BAR_HIDE_AFTER }: { threshold?: number, hideAfter?: number } = {},
): BarScrollState {
  // a page that does not scroll has nothing to make room for
  if (position.max <= 0)
    return state.shown && state.anchor === 0 ? state : shownBarScroll()
  const y = Math.min(Math.max(position.y, 0), position.max)
  // the top, and above it: the bars are there
  if (y <= 0)
    return state.shown && state.anchor === 0 ? state : shownBarScroll()

  if (state.shown) {
    // the lowest point since the bars were shown: a turn upwards starts the count anew
    const anchor = Math.min(state.anchor, y)
    if (y > hideAfter && y - anchor >= threshold)
      return { shown: false, anchor: y }
    return anchor === state.anchor ? state : { shown: true, anchor }
  }
  // the highest point since they were hidden
  const anchor = Math.max(state.anchor, y)
  if (anchor - y >= threshold)
    return { shown: true, anchor: y }
  return anchor === state.anchor ? state : { shown: false, anchor }
}
