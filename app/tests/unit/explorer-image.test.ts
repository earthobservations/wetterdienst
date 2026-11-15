import { describe, expect, it } from 'vitest'
import { EMPTY_CHART_THEME } from '../../app/utils/chart-theme'
import { loadEcharts } from '../../app/utils/echarts-loader'
import { stackSvgs } from '../../app/utils/explorer-image'
import { boundsOf } from '../../app/utils/explorer-model'
import { buildExplorerOption, explorerFrame } from '../../app/utils/explorer-option'

const DAY = 86_400_000
const START = Date.UTC(2026, 8, 1)

function drawn(width: number, height: number, name: string) {
  const series = [{ id: name, name, colorIndex: 0, kind: 'values' as const, x: [0, 1, 2].map(i => START + i * DAY), y: [1, 3, 2] }]
  const bounds = boundsOf(series)!
  const input = { series, hidden: new Set<string>(), theme: { ...EMPTY_CHART_THEME, paper: 'rgb(255, 255, 255)' }, window: bounds, bounds, width, height, large: false, locale: 'en', background: 'rgb(255, 255, 255)', measure: (text: string) => text.length * 7 }
  const frame = explorerFrame(input)
  const chart = loadEcharts().init(null as any, null, { renderer: 'svg', ssr: true, width: frame.width, height: frame.height })
  try {
    chart.setOption(buildExplorerOption(input, frame) as any)
    return { svg: chart.renderToSVGString(), width: frame.width, height: frame.height }
  }
  finally {
    chart.dispose()
  }
}

describe('stackSvgs', () => {
  it('puts the charts one under the other on a sheet as wide as the widest and as high as all of them', () => {
    const parts = [drawn(700, 300, 'Wind'), drawn(760, 300, 'Rain')]
    const sheet = stackSvgs(parts)
    expect(sheet.width).toBe(760)
    expect(sheet.height).toBe(600)
    expect(sheet.svg).toMatch(/^<svg [^>]*width="760" height="600" viewBox="0 0 760 600">/)
    // the second at 300 px down, each with the size it was drawn at
    expect(sheet.svg).toContain('x="0" y="0" width="700" height="300" viewBox="0 0 700 300"')
    expect(sheet.svg).toContain('x="0" y="300" width="760" height="300" viewBox="0 0 760 300"')
  })

  it('keeps what each chart drew, in the order given', () => {
    const sheet = stackSvgs([drawn(700, 300, 'Wind'), drawn(700, 300, 'Rain')])
    expect(sheet.svg.indexOf('Wind')).toBeGreaterThan(-1)
    expect(sheet.svg.indexOf('Rain')).toBeGreaterThan(sheet.svg.indexOf('Wind'))
  })

  it('is an SVG that parses, with an element for each chart', () => {
    const sheet = stackSvgs([drawn(700, 300, 'Wind'), drawn(700, 300, 'Rain'), drawn(700, 300, 'Snow')])
    // every opening and closing tag has its mate: the nesting did not break the markup
    expect((sheet.svg.match(/<svg\b/g) ?? []).length).toBe(4)
    expect((sheet.svg.match(/<\/svg>/g) ?? []).length).toBe(4)
  })

  it('takes a chart with an XML prolog, and refuses a text that is no SVG', () => {
    const part = drawn(700, 300, 'Wind')
    expect(stackSvgs([{ ...part, svg: `<?xml version="1.0"?>\n${part.svg}` }]).svg).toContain('Wind')
    expect(() => stackSvgs([{ svg: '<html></html>', width: 1, height: 1 }])).toThrow(/not an SVG/)
  })

  it('is an empty sheet for no charts', () => {
    expect(stackSvgs([])).toMatchObject({ width: 0, height: 0 })
  })
})
