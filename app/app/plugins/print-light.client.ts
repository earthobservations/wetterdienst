// What the page does for paper (GH-3518). It is white: a page in dark mode prints in the light colours (the page: the charts
// take theirs from the colour mode, not from the class, and a redraw by the components is not done in time, so they keep the
// screen's), and is dark again after the print. And it is narrow: a chart of Plotly has the width of the window it was
// drawn in (the pages with a chart use the whole width), which paper cuts off, and the cards the charts stand in clip rather
// than shrink. So each chart wider than the room it has is scaled to it (`zoom`) when the print starts and back after it.
//
// `zoom`, not a new `Plotly.relayout` at the room's width, which would keep the type size: a chart drawn again in the
// `beforeprint` handler of a real print (Chrome's print dialog, `page.pdf`) comes out of the print without its traces, as the
// print starts before Plotly has finished; it works only when it is done before the print. So a chart on paper is whole and
// about half the size of the screen's (its type 4.5 to 6 pt): see the pull request.
//
// The room is the column of the narrowest paper in use (A4 portrait, 1 inch margins: 602 CSS px) less what stands between the
// chart and the page's own column: the paddings and borders of the elements around it, measured with the print's gutters and
// card paddings in force (`html[data-printing]` in main.css, set first, then read). Letter and A4 with the browser's default
// margins (0.4 inch) have more room than that and get a little less of it.
//
// The browser sends `beforeprint` once and `afterprint` when the print dialog closes; in between it prints and reprints
// (paper, margins, scale) and the print media comes and goes, so the page is put back by `afterprint` only (and `pagehide`).
const PRINT_COLUMN = 600
// the shadow ring of a card, rounding, a scroll bar's worth
const SLACK = 12
// below this a chart is not scaled (the room is not one)
const LEAST = 240

const px = (value: string) => Number.parseFloat(value) || 0

/** What the elements from a chart up to the page's column take of the width, in pixels */
function insetsOf(chart: HTMLElement): number {
  let insets = 0
  for (let element: HTMLElement | null = chart; element && element !== document.body; element = element.parentElement) {
    const style = getComputedStyle(element)
    insets += px(style.paddingLeft) + px(style.paddingRight) + px(style.borderLeftWidth) + px(style.borderRightWidth)
    if (element.hasAttribute('data-width'))
      break
  }
  return insets
}

export default defineNuxtPlugin(() => {
  let wasDark = false
  let printing = false
  // what had the focus: the sidebar is not printed (it is hidden for the print), and a hidden element loses the focus
  let focused: HTMLElement | null = null
  // the charts that were scaled, and the handler with which Plotly draws a chart at its container's width again on a resize
  const scaled = new Map<HTMLElement, (() => void) | undefined>()

  function restore() {
    if (!printing)
      return
    printing = false
    delete document.documentElement.dataset.printing
    if (wasDark)
      document.documentElement.classList.add('dark')
    wasDark = false
    // the print media may still apply here, and a hidden element (the sidebar is) takes no focus: given again once it is shown
    const refocus = focused
    focused = null
    let tries = 0
    const giveFocusBack = () => {
      if (!refocus?.isConnected || (document.activeElement && document.activeElement !== document.body))
        return
      if (refocus.getClientRects().length > 0)
        refocus.focus({ preventScroll: true })
      else if (++tries < 30)
        requestAnimationFrame(giveFocusBack)
    }
    giveFocusBack()
    for (const [chart, handler] of scaled) {
      chart.style.zoom = ''
      // only if it is still the chart's: one drawn anew meanwhile (purged, drawn again) has a handler of its own, and the old one
      // would be a second
      if (handler && chart.isConnected && (chart as any)._responsiveChartHandler === handler)
        window.addEventListener('resize', handler)
    }
    scaled.clear()
  }

  window.addEventListener('beforeprint', () => {
    const root = document.documentElement
    // a second beforeprint with no afterprint between (some browsers) must not forget that the page was dark
    wasDark = wasDark || root.classList.contains('dark')
    root.classList.remove('dark')
    printing = true
    if (!focused && document.activeElement instanceof HTMLElement && document.activeElement !== document.body)
      focused = document.activeElement
    // the print's gutters and paddings (main.css), which the measures below read; the pages that follow their chart's
    // container (stripes.vue) leave it alone meanwhile
    root.dataset.printing = ''

    for (const chart of document.querySelectorAll<HTMLElement>('.js-plotly-plot')) {
      if (scaled.has(chart))
        continue
      const drawn = chart.querySelector('.main-svg')?.getBoundingClientRect().width ?? 0
      const room = PRINT_COLUMN - insetsOf(chart) - SLACK
      if (drawn <= room || room < LEAST)
        continue
      const handler = (chart as any)._responsiveChartHandler as (() => void) | undefined
      // a resize while the print is prepared must not draw the chart at its container's width again (it would be as wide as
      // the screen's again, and scaled)
      if (handler)
        window.removeEventListener('resize', handler)
      chart.style.zoom = String(room / drawn)
      scaled.set(chart, handler)
    }
  })

  window.addEventListener('afterprint', restore)
  window.addEventListener('pagehide', restore)
})
