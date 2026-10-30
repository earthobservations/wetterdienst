import { afterEach, describe, expect, it } from 'vitest'
import { fitChartsToPaper, restoreChartsAfterPrint } from '~/utils/chart-print'

// Charts on paper (GH-3518): scaled to the width of their box before printing, as a picture, and given their size back
// after it.

const SVG = 'http://www.w3.org/2000/svg'

function chart(width: number, height: number, layers = 2) {
  const plot = document.createElement('div')
  plot.className = 'js-plotly-plot'
  const container = document.createElement('div')
  container.className = 'svg-container'
  container.setAttribute('style', `position: relative; width: ${width}px; height: ${height}px;`)
  for (let index = 0; index < layers; index++) {
    const svg = document.createElementNS(SVG, 'svg')
    svg.setAttribute('class', 'main-svg')
    svg.setAttribute('width', String(width))
    svg.setAttribute('height', String(height))
    container.append(svg)
  }
  plot.append(container)
  document.body.append(plot)
  return container
}

afterEach(() => {
  restoreChartsAfterPrint()
  document.body.replaceChildren()
})

describe('printing the charts of a page', () => {
  it('scales every layer of a chart to its box, keeping its proportions', () => {
    const container = chart(1100, 550)
    fitChartsToPaper()

    expect(container.style.width).toBe('100%')
    expect(container.style.aspectRatio.replace(/\s/g, '')).toBe('1100/550')
    for (const svg of container.querySelectorAll('svg')) {
      expect(svg.getAttribute('viewBox')).toBe('0 0 1100 550')
      expect(svg.getAttribute('preserveAspectRatio')).toBe('xMinYMin meet')
      expect(svg.style.width).toBe('100%')
    }
  })

  it('gives every chart its size back after printing', () => {
    const container = chart(900, 400)
    const style = container.getAttribute('style')
    fitChartsToPaper()
    restoreChartsAfterPrint()

    expect(container.getAttribute('style')).toBe(style)
    for (const svg of container.querySelectorAll('svg')) {
      expect(svg.hasAttribute('viewBox')).toBe(false)
      expect(svg.hasAttribute('preserveAspectRatio')).toBe(false)
      expect(svg.hasAttribute('style')).toBe(false)
    }
  })

  it('scales once for a print that announces itself twice (the event and the medium)', () => {
    const container = chart(800, 300)
    const style = container.getAttribute('style')
    fitChartsToPaper()
    fitChartsToPaper()
    restoreChartsAfterPrint()
    expect(container.getAttribute('style')).toBe(style)
  })

  it('leaves a chart that is not drawn yet', () => {
    const container = chart(0, 0)
    fitChartsToPaper()
    expect(container.style.aspectRatio).toBe('')
  })
})
