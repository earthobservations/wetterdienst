// The charts are redrawn at the width of the paper for printing (GH-3518); see utils/chart-print.ts
export default defineNuxtPlugin(() => {
  installChartPrint()
})
