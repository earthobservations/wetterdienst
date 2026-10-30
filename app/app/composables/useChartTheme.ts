import type { ChartTheme } from '~/utils/chart-theme'
import { EMPTY_CHART_THEME, readDocumentChartTheme } from '~/utils/chart-theme'

// The theme of the Plotly charts for the colour scheme the page is in (see utils/chart-theme.ts), one
// for all charts. It is read from the CSS tokens once the colour mode has put its class on <html>, and
// again whenever that class changes, so a chart that watches `theme` follows a switch of light, dark and
// system without a reload. A page being printed is light whatever the screen shows: for as long as the
// browser prints (`beforeprint` to `afterprint`, and the `print` media query where a browser only says so
// there), `theme` is the light one, and the charts draw in it. The page is client-rendered only (SSR is
// off), so there is nothing to read on the server and the theme is empty there.
const current = shallowRef<ChartTheme | null>(null)
const printing = ref(false)
let printTheme: ChartTheme | null = null
let observer: MutationObserver | null = null

function same(a: ChartTheme, b: ChartTheme) {
  return (Object.keys(a) as (keyof ChartTheme)[]).every(key => a[key] === b[key])
}

function refresh() {
  const next = readDocumentChartTheme()
  if (!current.value || !same(current.value, next))
    current.value = next
}

function startPrinting(on: boolean) {
  if (on)
    printTheme = readDocumentChartTheme('light')
  printing.value = on
}

export function useChartTheme() {
  if (import.meta.client && !observer) {
    refresh()
    observer = new MutationObserver(refresh)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    window.addEventListener('beforeprint', () => startPrinting(true))
    window.addEventListener('afterprint', () => startPrinting(false))
    window.matchMedia('print').addEventListener('change', event => startPrinting(event.matches))
  }
  const theme = computed(() => (printing.value ? printTheme : current.value) ?? EMPTY_CHART_THEME)
  return { theme, isDark: computed(() => theme.value.dark) }
}
