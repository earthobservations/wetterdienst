// What the page does for paper (GH-3518). It is white: a page in dark mode prints in the light colours (the page: the charts
// take theirs from the colour mode, not from the class, and a redraw is not done in time, so they keep the screen's), and is
// dark again after the print. And it is narrow: a chart of Plotly has the width of the screen it was drawn on (the pages with a chart use
// the whole width of the window), which paper cuts off, so each chart is scaled to the width of the paper for the print
// and back after it. `zoom` rather than a redraw: it is done when the print starts, which a redraw is not.
const PAPER_WIDTH = 700

export default defineNuxtPlugin(() => {
  let wasDark = false
  const scaled = new Set<HTMLElement>()

  window.addEventListener('beforeprint', () => {
    const root = document.documentElement
    // a second beforeprint with no afterprint between (some browsers) must not forget that the page was dark
    wasDark = wasDark || root.classList.contains('dark')
    root.classList.remove('dark')
    // the pages that follow their chart's container (stripes.vue) leave it alone while it is scaled for the paper
    root.dataset.printing = ''

    for (const chart of document.querySelectorAll<HTMLElement>('.js-plotly-plot')) {
      if (scaled.has(chart))
        continue
      const drawn = chart.querySelector('.main-svg')?.getBoundingClientRect().width ?? 0
      if (drawn > PAPER_WIDTH) {
        chart.style.zoom = String(PAPER_WIDTH / drawn)
        scaled.add(chart)
      }
    }
  })

  window.addEventListener('afterprint', () => {
    delete document.documentElement.dataset.printing
    if (wasDark)
      document.documentElement.classList.add('dark')
    wasDark = false
    for (const chart of scaled)
      chart.style.zoom = ''
    scaled.clear()
  })
})
