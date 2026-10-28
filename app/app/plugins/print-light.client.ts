// What the page does for paper (GH-3518). It is white: a page in dark mode prints in the light colours (the page: the charts
// take theirs from the colour mode, not from the class, and a redraw is not done in time, so they keep the screen's), and is
// dark again after the print. And it is narrow: a chart of Plotly has the width of the window it was drawn in (the pages with a
// chart use the whole width), which paper cuts off, and the cards the charts stand in clip rather than shrink. So each chart is
// scaled to the room it has on paper for the print, and back after it. `zoom` rather than a redraw: it is done when the print
// starts, which a redraw is not.
//
// The room is the column of the narrowest paper in use (A4 portrait, 1 inch margins: 602 CSS px) less what stands between the
// chart and the page's own column: the paddings and borders of the elements around it, measured where the chart is (the
// screen's are never smaller than the page's in print, so the room is never too large). Letter, and A4 with the browser's
// default margins (0.4 inch), have more room than that and get a little less of it.
const PRINT_COLUMN = 600
// the shadow ring of a card, rounding, a scroll bar's worth
const SLACK = 12

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
  const scaled = new Set<HTMLElement>()

  function restore() {
    if (!printing)
      return
    printing = false
    delete document.documentElement.dataset.printing
    if (wasDark)
      document.documentElement.classList.add('dark')
    wasDark = false
    for (const chart of scaled)
      chart.style.zoom = ''
    scaled.clear()
  }

  window.addEventListener('beforeprint', () => {
    const root = document.documentElement
    // a second beforeprint with no afterprint between (some browsers) must not forget that the page was dark
    wasDark = wasDark || root.classList.contains('dark')
    root.classList.remove('dark')
    printing = true
    // the pages that follow their chart's container (stripes.vue) leave it alone while it is scaled for the paper
    root.dataset.printing = ''

    for (const chart of document.querySelectorAll<HTMLElement>('.js-plotly-plot')) {
      if (scaled.has(chart))
        continue
      const drawn = chart.querySelector('.main-svg')?.getBoundingClientRect().width ?? 0
      const room = PRINT_COLUMN - insetsOf(chart) - SLACK
      if (drawn > room && room > 0) {
        chart.style.zoom = String(room / drawn)
        scaled.add(chart)
      }
    }
  })

  window.addEventListener('afterprint', restore)
  // where afterprint does not come (some browsers, a print that is cancelled in a way that skips it) the page is put back
  // when the print media stops applying, or when the page goes
  window.matchMedia('print').addEventListener('change', (event) => {
    if (!event.matches)
      restore()
  })
  window.addEventListener('pagehide', restore)
})
