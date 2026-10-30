import { chartThemeLayout, drawnAxisNames, mergeLayouts, readDocumentChartTheme } from '~/utils/chart-theme'

// A chart that is saved is always the light one, whatever the screen shows, so that images in a report or
// a slide look alike. Plotly exports what is drawn, and has no say for the colours of the image, so the
// chart is drawn again, off screen, in the light theme, and that copy is exported.

interface PlotlyDrawing {
  newPlot: (element: any, data: any, layout?: any, config?: any) => Promise<unknown>
  purge: (element: any) => void
}

export interface OffscreenChart {
  /** The copy, in the page but out of sight: what Plotly's export is given */
  element: HTMLElement
  /** Takes the copy away, and has Plotly forget it */
  dispose: () => void
}

/** Draws `data` and `layout` in a copy out of sight, `width` by `height` px, for the export */
export async function drawOffscreen(plotly: PlotlyDrawing, data: unknown, layout: unknown, size: { width: number, height: number }): Promise<OffscreenChart> {
  const element = document.createElement('div')
  element.style.cssText = `position:fixed;left:-20000px;top:0;width:${size.width}px;height:${size.height}px;pointer-events:none`
  element.setAttribute('aria-hidden', 'true')
  document.body.appendChild(element)
  const dispose = () => {
    try {
      plotly.purge(element)
    }
    finally {
      element.remove()
    }
  }
  try {
    // a static chart: no modebar, no hover, nothing to listen to
    await plotly.newPlot(element, data, layout, { staticPlot: true })
  }
  catch (error) {
    dispose()
    throw error
  }
  return { element, dispose }
}

// Plotly draws into the layout it is given and keeps hold of it
function cloneLayout(layout: object): object {
  try {
    return structuredClone(layout)
  }
  catch {
    return JSON.parse(JSON.stringify(layout))
  }
}

/**
 * A drawn chart again in the light theme, as it is shown now (its data, its zoom and ranges, its sizes): the
 * chart's own layout with the light chrome over it. A chart that holds colours of its own in its text (the
 * stripes' years) builds its own copy instead.
 */
export function drawLightCopy(plotly: PlotlyDrawing, chart: HTMLElement): Promise<OffscreenChart> {
  const drawn = chart as HTMLElement & { data: unknown, layout: object }
  const layout = mergeLayouts(cloneLayout(drawn.layout), chartThemeLayout(readDocumentChartTheme('light'), drawnAxisNames(chart)))
  return drawOffscreen(plotly, drawn.data, layout, { width: chart.clientWidth, height: chart.clientHeight })
}
