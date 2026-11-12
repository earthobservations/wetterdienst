// Charts on paper (GH-3518). Plotly draws a chart at the width of its box on the screen, in pixels, and a printed page
// is narrower than most screens: the chart was cut at the paper's edge. Before printing, every chart is scaled to the
// width of its box on paper, as a picture: each of its SVG layers gets a `viewBox` of the size it was drawn at, and its
// box the width of the column and the chart's own proportions. Nothing is redrawn, which Plotly does asynchronously,
// after a browser has already laid out the page for printing (its `beforeprint` handlers have to have done their work
// when they return). After printing, everything is as it was.

interface Scaled {
  container: HTMLElement
  style: string | null
  layers: { svg: SVGSVGElement, viewBox: string | null, preserve: string | null, style: string | null }[]
  /**
   * The chart's own box, which a page may have given the chart's height in pixels, and what is drawn over the chart
   * in a canvas of its size (the forecast's wind barbs), with their styles
   */
  boxes: { element: HTMLElement, style: string | null }[]
}

let scaled: Scaled[] = []

/** Scales every chart of the page to the width of its box; a chart that is printed already is left alone */
export function fitChartsToPaper(root: ParentNode = document) {
  if (scaled.length)
    return
  for (const container of root.querySelectorAll<HTMLElement>('.js-plotly-plot .svg-container')) {
    const layers = [...container.querySelectorAll<SVGSVGElement>(':scope > svg.main-svg')]
    const width = Number(layers[0]?.getAttribute('width'))
    const height = Number(layers[0]?.getAttribute('height'))
    if (!width || !height)
      continue
    const plot = container.closest<HTMLElement>('.js-plotly-plot')
    const overlays = plot ? [...plot.querySelectorAll<HTMLCanvasElement>(':scope > canvas')] : []
    scaled.push({
      container,
      style: container.getAttribute('style'),
      layers: layers.map(svg => ({ svg, viewBox: svg.getAttribute('viewBox'), preserve: svg.getAttribute('preserveAspectRatio'), style: svg.getAttribute('style') })),
      boxes: [plot, ...overlays].filter(element => !!element).map(element => ({ element: element!, style: element!.getAttribute('style') })),
    })
    // the box takes the height of the scaled chart, and a canvas over it is scaled with it, from the same corner
    plot?.style.setProperty('height', 'auto', 'important')
    plot?.style.setProperty('min-height', '0', 'important')
    for (const canvas of overlays) {
      canvas.style.setProperty('width', '100%', 'important')
      canvas.style.setProperty('height', 'auto', 'important')
    }
    container.style.setProperty('width', '100%', 'important')
    container.style.setProperty('height', 'auto', 'important')
    container.style.setProperty('aspect-ratio', `${width} / ${height}`)
    for (const svg of layers) {
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`)
      svg.setAttribute('preserveAspectRatio', 'xMinYMin meet')
      svg.style.setProperty('width', '100%', 'important')
      svg.style.setProperty('height', '100%', 'important')
    }
  }
}

/** Gives every chart back the size it had before printing */
export function restoreChartsAfterPrint() {
  const charts = scaled
  scaled = []
  const put = (element: Element, name: string, value: string | null) => value === null ? element.removeAttribute(name) : element.setAttribute(name, value)
  for (const { container, style, layers, boxes } of charts) {
    put(container, 'style', style)
    for (const box of boxes)
      put(box.element, 'style', box.style)
    for (const layer of layers) {
      put(layer.svg, 'viewBox', layer.viewBox)
      put(layer.svg, 'preserveAspectRatio', layer.preserve)
      put(layer.svg, 'style', layer.style)
    }
  }
}

/** Listens for printing: the print events, and the print medium where a browser announces it only that way */
export function installChartPrint(target: Window = window) {
  target.addEventListener('beforeprint', () => fitChartsToPaper(target.document))
  target.addEventListener('afterprint', () => restoreChartsAfterPrint())
  const media = target.matchMedia?.('print')
  media?.addEventListener?.('change', (event) => {
    if (event.matches)
      fitChartsToPaper(target.document)
    else
      restoreChartsAfterPrint()
  })
}
