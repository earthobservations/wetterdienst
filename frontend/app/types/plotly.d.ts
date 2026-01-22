declare module 'plotly.js-dist-min' {
  export interface Data {
    name?: string
    x?: (Date | number | string)[]
    y?: (number | string)[]
    type?: 'scatter' | 'scattergl' | 'bar' | 'pie' | 'heatmap' | string
    mode?: 'lines' | 'markers' | 'lines+markers' | 'none' | string
    marker?: {
      size?: number
      color?: string
      symbol?: string
    }
    line?: {
      color?: string
      width?: number
      dash?: 'solid' | 'dot' | 'dash' | 'longdash' | 'dashdot' | 'longdashdot' | string
    }
    showlegend?: boolean
    [key: string]: unknown
  }

  export interface Layout {
    autosize?: boolean
    width?: number
    height?: number
    margin?: {
      l?: number
      r?: number
      t?: number
      b?: number
      pad?: number
    }
    title?: string | { text: string, [key: string]: unknown }
    xaxis?: {
      title?: string
      type?: 'linear' | 'log' | 'date' | 'category'
      [key: string]: unknown
    }
    yaxis?: {
      title?: string
      type?: 'linear' | 'log' | 'date' | 'category'
      [key: string]: unknown
    }
    legend?: {
      orientation?: 'v' | 'h'
      x?: number
      y?: number
      [key: string]: unknown
    }
    hovermode?: 'closest' | 'x' | 'y' | 'x unified' | 'y unified' | false
    [key: string]: unknown
  }

  export interface Config {
    responsive?: boolean
    displayModeBar?: boolean | 'hover'
    modeBarButtonsToRemove?: string[]
    displaylogo?: boolean
    [key: string]: unknown
  }

  export function newPlot(
    root: HTMLElement,
    data: Data[],
    layout?: Partial<Layout>,
    config?: Partial<Config>,
  ): Promise<void>

  export function react(
    root: HTMLElement,
    data: Data[],
    layout?: Partial<Layout>,
    config?: Partial<Config>,
  ): Promise<void>

  export function purge(root: HTMLElement): void

  export function downloadImage(
    root: HTMLElement,
    opts: {
      format?: 'png' | 'jpeg' | 'webp' | 'svg'
      filename?: string
      width?: number
      height?: number
      scale?: number
    },
  ): Promise<string>
}
