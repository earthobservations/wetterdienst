import type { ChartTheme } from '~/utils/chart-theme'
import { EMPTY_CHART_THEME, readDocumentChartTheme } from '~/utils/chart-theme'

// The theme of the Plotly charts for the colour scheme the page is in (see utils/chart-theme.ts), one
// for all charts. It is read from the CSS tokens once the colour mode has put its class on <html>, and
// again whenever that class changes, so a chart that watches `theme` follows a switch of light, dark and
// system without a reload. The page is client-rendered only (SSR is off), so there is nothing to read
// on the server and the theme is empty there.
const current = shallowRef<ChartTheme | null>(null)
let observer: MutationObserver | null = null

function same(a: ChartTheme, b: ChartTheme) {
  return (Object.keys(a) as (keyof ChartTheme)[]).every(key => a[key] === b[key])
}

function refresh() {
  const next = readDocumentChartTheme()
  if (!current.value || !same(current.value, next))
    current.value = next
}

export function useChartTheme() {
  if (import.meta.client && !observer) {
    refresh()
    observer = new MutationObserver(refresh)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
  }
  const theme = computed(() => current.value ?? EMPTY_CHART_THEME)
  return { theme, isDark: computed(() => theme.value.dark) }
}
