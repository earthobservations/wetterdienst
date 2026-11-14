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
    /**
     * The titles of the axes of the last drawing, from the top panel down: the words turned to read upwards, the lines of a
     * title that is broken in two joined by a space, and the colour of the first
     */
    axisTitles: () => {
      const lines = [...svg.matchAll(/<text([^>]*)>([^<]*)<\/text>/g)]
        .map(match => ({ attributes: match[1]!, text: match[2]!.replaceAll('&amp;', '&') }))
        .map(({ attributes, text }) => {
          const turned = /transform="translate\(([\d.-]+) ([\d.-]+)\)[^"]*rotate\(/.exec(attributes) ?? /transform="matrix\(0,-1,1,0,([\d.-]+),([\d.-]+)\)/.exec(attributes)
          return turned ? { x: Number(turned[1]), y: Math.round(Number(turned[2])), text, fill: /fill="([^"]*)"/.exec(attributes)?.[1] ?? '' } : null
        })
        .filter((line): line is NonNullable<typeof line> => line !== null)
      const panels = new Map<number, typeof lines>()
      for (const line of lines)
        panels.set(line.y, [...(panels.get(line.y) ?? []), line].sort((a, b) => a.x - b.x))
      return [...panels.entries()].sort(([a], [b]) => a - b).map(([, parts]) => ({ text: parts.map(part => part.text).join(' '), fill: parts[0]!.fill }))
    },
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
