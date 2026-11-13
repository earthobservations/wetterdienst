import { BarChart, CustomChart, LineChart } from 'echarts/charts'
import { DataZoomInsideComponent, GridComponent } from 'echarts/components'
import * as real from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { vi } from 'vitest'

// registered here and not through `~/utils/echarts-loader`, which the tests replace with this
real.use([LineChart, BarChart, CustomChart, GridComponent, DataZoomInsideComponent, SVGRenderer])

/**
 * ECharts as a test of a component has it: the real library, drawing to an SVG string in a document-less chart
 * (`ssr: true`), with every call recorded. A test reads the option the component gave it, or the SVG that option made,
 * which is what a reader would see: the day names, the hours, the barbs. It replaces `~/utils/echarts-loader`
 * (`vi.mock`), whose `loadEcharts` answers the same `init`.
 */
export function createSsrEcharts() {
  const setOption = vi.fn()
  const dispatchAction = vi.fn()
  const dispose = vi.fn()
  const resize = vi.fn()
  const on = vi.fn()
  const inits = vi.fn()
  let svg = ''
  let current: real.ECharts | null = null
  let element: HTMLElement | null = null

  const chart = {
    on,
    resize: (size: { width: number, height: number }) => {
      resize(size)
      current?.resize(size)
    },
    setOption: (option: any, flags?: unknown) => {
      setOption(option, flags)
      current!.setOption(option, flags as any)
      svg = current!.renderToSVGString()
    },
    dispatchAction: (action: unknown) => {
      dispatchAction(action)
    },
    getDom: () => element,
    dispose: () => {
      dispose()
      current?.dispose()
      current = null
    },
  }

  return {
    init: (target: HTMLElement, _theme: unknown, options: { width: number, height: number }) => {
      inits(target, _theme, options)
      element = target
      current = real.init(null as any, null, { renderer: 'svg', ssr: true, width: options.width, height: options.height })
      return chart
    },
    chart,
    calls: { setOption, dispatchAction, dispose, resize, on, inits },
    /** The SVG of the last drawing */
    svg: () => svg,
    /** The texts of the last drawing, in order */
    texts: () => [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(match => match[1]!.replaceAll('&amp;', '&')),
    /** The option of the last drawing */
    option: () => setOption.mock.lastCall![0] as any,
    clear: () => {
      setOption.mockClear()
      dispatchAction.mockClear()
      dispose.mockClear()
      resize.mockClear()
      on.mockClear()
      inits.mockClear()
    },
  }
}
