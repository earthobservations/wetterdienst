import { BarChart, CustomChart, LineChart } from 'echarts/charts'
import { DataZoomInsideComponent, GridComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'

/**
 * Apache ECharts as the forecast chart needs it, and no more: the core, the line, bar and custom series, the grid and
 * the inside zoom (a pinch and Ctrl with the wheel), drawn as SVG. No tooltip or axis pointer: the readout of the chart
 * is the component's own (a real element a pointer can move onto, which Escape closes). Imported when a chart is first
 * drawn (`import('~/utils/echarts-loader')`), so that the page, the map's day rows and every route that draws no chart
 * load none of it; a test replaces this module with a recorder.
 */
let registered = false

export function loadEcharts(): typeof echarts {
  if (!registered) {
    echarts.use([LineChart, BarChart, CustomChart, GridComponent, DataZoomInsideComponent, SVGRenderer])
    registered = true
  }
  return echarts
}
