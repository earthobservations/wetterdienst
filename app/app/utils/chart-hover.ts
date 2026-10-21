/**
 * Escape dismisses the hover label of a Plotly chart (WCAG 2.2 1.4.13, Content on Hover or Focus).
 *
 * Plotly draws the label of a point when the pointer is over it and takes it away when the pointer
 * leaves, and has no key for it: a reader who magnifies the screen, or whose pointer rests on the
 * chart, could not look at what lies under the label. With the pointer over a chart, Escape marks
 * the chart `data-hover-dismissed`, and `main.css` hides its hover label (and the modebar's button
 * names, which are shown on hover too) while the mark is there. The mark goes when the pointer moves
 * on, as a new hover has its own label, or leaves the chart.
 *
 * What stays: the label is not hoverable. Plotly draws it in the SVG without pointer events, so a
 * pointer that moves towards it leaves the point and it goes; it is no element to move onto or to
 * copy from. The values it shows are in the table that every chart offers ("Show as table").
 */
export const HOVER_DISMISSED = 'data-hover-dismissed'

const PLOT = '.js-plotly-plot'

/**
 * Starts listening on `doc`; the returned function stops it and removes the mark.
 *
 * Escape is not stopped or prevented: it still closes a dialog or a menu that is open.
 */
export function installChartHoverDismiss(doc: Document = document): () => void {
  // the chart under the pointer, and where the pointer was last seen
  let hovered: HTMLElement | null = null
  let x = Number.NaN
  let y = Number.NaN
  // the chart whose label was dismissed, and where the pointer was then
  let dismissed: HTMLElement | null = null
  let dismissedAt: [number, number] = [Number.NaN, Number.NaN]

  function restore() {
    dismissed?.removeAttribute(HOVER_DISMISSED)
    dismissed = null
  }

  function onPointerMove(event: PointerEvent) {
    x = event.clientX
    y = event.clientY
    hovered = event.target instanceof Element ? event.target.closest<HTMLElement>(PLOT) : null
    // a pointer that has moved is a new hover; one that rests (a move event with the same position,
    // which some browsers send after a layout) is not
    if (dismissed && (hovered !== dismissed || x !== dismissedAt[0] || y !== dismissedAt[1]))
      restore()
  }

  function onPointerLeave() {
    hovered = null
    restore()
  }

  function onKeyDown(event: KeyboardEvent) {
    if (event.key !== 'Escape' || !hovered?.isConnected)
      return
    restore()
    dismissed = hovered
    dismissedAt = [x, y]
    hovered.setAttribute(HOVER_DISMISSED, 'true')
  }

  doc.addEventListener('pointermove', onPointerMove, { capture: true, passive: true })
  doc.documentElement.addEventListener('pointerleave', onPointerLeave)
  doc.addEventListener('keydown', onKeyDown)
  return () => {
    doc.removeEventListener('pointermove', onPointerMove, { capture: true })
    doc.documentElement.removeEventListener('pointerleave', onPointerLeave)
    doc.removeEventListener('keydown', onKeyDown)
    restore()
    hovered = null
  }
}
