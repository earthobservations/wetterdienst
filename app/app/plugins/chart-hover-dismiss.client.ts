// Escape dismisses the hover label of every Plotly chart (WCAG 1.4.13); see utils/chart-hover.ts
export default defineNuxtPlugin(() => {
  installChartHoverDismiss()
})
