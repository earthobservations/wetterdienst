/**
 * The option of the forecast chart (Apache ECharts): one grid for each panel and one above them for the days, the
 * hours and the weather symbols, all on one time axis whose zoom is linked (one `dataZoom` for every x axis), the
 * lines and bars as the library's own series, and what it has no series for (the day bands, the wind barbs, the day
 * names, the hours, the symbols) as `custom` series in the same coordinates. Pure: a model, a theme and a window in, an
 * option out, so that tests build it without a browser.
 */
import type { EChartsCoreOption } from 'echarts/core'
import type { ChartTheme } from './chart-theme'
import type { ChartLayout, TimeWindow } from './meteogram-geometry'
import type { DrawnSeries, MeteogramModel, Tone } from './meteogram-model'
import type { YrSymbol } from './weather-symbols'
import { seriesLabelColor, withAlpha } from './chart-theme'
import { withData } from './format'
import { every, GUTTER_LEFT, HOUR_MS, labelStepHours, MIN_SPAN_HOURS, windBarb } from './meteogram-geometry'
import { yrSymbolFor, yrSymbolUrl } from './weather-symbols'

/** The room a barb, a symbol and a label of the time axis need beside the next one, in px */
export const BARB_SPACING = 26
export const SYMBOL_SPACING = 32
export const LABEL_SPACING = 46
export const SYMBOL_SIZE = 30
/** Half the width of a label of the time axis, in px */
export const HOUR_LABEL_HALF_WIDTH = 18

/** The colours of the series: the line and the wash under it, in the light and the dark scheme */
const TONES: Record<Tone, { light: string, dark: string, fillLight?: string, fillDark?: string }> = {
  temp: { light: '#ef4444', dark: '#ef4444', fillLight: 'rgba(239,68,68,0.04)', fillDark: 'rgba(239,68,68,0.02)' },
  tempMax: { light: '#b91c1c', dark: '#fca5a5' },
  tempMin: { light: '#1d4ed8', dark: '#93c5fd' },
  dew: { light: '#a855f7', dark: '#a855f7' },
  rain: { light: '#3b82f6', dark: '#3b82f6' },
  mixed: { light: '#0ea5e9', dark: '#0ea5e9' },
  snow: { light: '#cbd5e1', dark: '#9ca3af' },
  wind: { light: '#06b6d4', dark: '#06b6d4', fillLight: 'rgba(6,182,212,0.08)', fillDark: 'rgba(6,182,212,0.04)' },
  gust: { light: '#06b6d4', dark: '#06b6d4' },
  pressure: { light: '#84cc16', dark: '#84cc16', fillLight: 'rgba(132,204,22,0.04)', fillDark: 'rgba(132,204,22,0.02)' },
  cloudHigh: { light: '#cbd5e1', dark: '#64748b', fillLight: 'rgba(203,213,225,0.15)', fillDark: 'rgba(148,163,184,0.1)' },
  cloudMid: { light: '#94a3b8', dark: '#475569', fillLight: 'rgba(148,163,184,0.22)', fillDark: 'rgba(100,116,139,0.15)' },
  cloudLow: { light: '#64748b', dark: '#334155', fillLight: 'rgba(100,116,139,0.3)', fillDark: 'rgba(71,85,105,0.22)' },
  cloudTotal: { light: '#334155', dark: '#e4e4e7' },
}

/** The colour of a series' line, in the scheme the chart is drawn in */
export function toneColor(tone: Tone, dark: boolean): string {
  return TONES[tone][dark ? 'dark' : 'light']
}

export interface OptionInput {
  model: MeteogramModel
  theme: ChartTheme
  layout: ChartLayout
  /** the chart's width in px and the width of its plot, from the gutters to the right edge */
  outerPx: number
  plotPx: number
  /** the left gutter in px, which grows by a line where an axis title is broken in two */
  gutterLeft: number
  window: TimeWindow
  /** the moment it is, which a line marks while the forecast spans it */
  now: number | null
  reducedMotion: boolean
  fontFamily: string
  locale: string
  /** the name of the day and the hour as the page writes it */
  hourLabel: (ms: number) => string
  /** the file of a symbol, which a test points elsewhere */
  symbolUrl?: (symbol: YrSymbol, dark: boolean) => string
}

/** A span of the axis cut to the plot: the pixels of a band's ends that lie inside it, or null where none does */
export function clampSpan(x0: number, x1: number, left: number, right: number): [number, number] | null {
  const a = Math.max(left, Math.min(x0, x1))
  const b = Math.min(right, Math.max(x0, x1))
  return b > a ? [a, b] : null
}

/** Whether a pixel lies outside the plot by more than `margin`: an item there is not drawn, which keeps the chart's elements to the window */
export function outsidePlot(x: number, left: number, right: number, margin = 40): boolean {
  return x < left - margin || x > right + margin
}

/** The daylight's colour, which cloud at noon fades */
export function bandColour(cloud: number, dark: boolean): string {
  const alpha = 0.55 - Math.min(0.35, cloud * 0.5)
  return dark ? `rgba(250,204,21,${(alpha * 0.15).toFixed(3)})` : `rgba(253,244,180,${alpha.toFixed(3)})`
}

const BACKDROP = { band: 0, midnight: 1, now: 2, freeze: 3, divider: 4 } as const

/** The option of the chart in `input` */
export function buildMeteogramOption(input: OptionInput): EChartsCoreOption {
  const { model, theme, layout, outerPx, plotPx, gutterLeft, window: win, now: nowInput, reducedMotion, fontFamily, locale, hourLabel } = input
  const symbolUrl = input.symbolUrl ?? yrSymbolUrl
  const dark = theme.dark
  const rows = layout.rows
  const gridCount = rows.length + 1
  const xIndexes = Array.from({ length: gridCount }, (_, i) => i)
  const gridColour = withAlpha(theme.text, 0.1)
  const dividerColour = withAlpha(theme.text, 0.18)
  const midnightColour = withAlpha(theme.text, 0.12)
  const nowColour = dark ? 'rgba(251,146,60,0.75)' : 'rgba(234,88,12,0.75)'
  const bounds = { start: model.minTime, end: model.maxTime }
  const now = nowInput !== null && nowInput > bounds.start && nowInput < bounds.end ? nowInput : null
  const numberTag = withData(locale, Intl.NumberFormat.supportedLocalesOf)

  const grids: any[] = [{ left: gutterLeft, width: plotPx, top: layout.header.top, height: layout.header.height, show: false }]
  const xAxes: any[] = [{ type: 'value', gridIndex: 0, min: bounds.start, max: bounds.end, show: false }]
  const yAxes: any[] = [{ type: 'value', gridIndex: 0, min: 0, max: 1, show: false }]
  rows.forEach((row, i) => {
    const axis = model.axes[row.id]!
    const labelColour = axis.label === 'slate' ? theme.textMuted : seriesLabelColor(axis.label, dark)
    const format = new Intl.NumberFormat(numberTag, { maximumFractionDigits: axis.decimals })
    grids.push({ left: gutterLeft, width: plotPx, top: row.top, height: row.height, show: false })
    xAxes.push({ type: 'value', gridIndex: i + 1, min: bounds.start, max: bounds.end, show: false })
    yAxes.push({
      type: 'value',
      gridIndex: i + 1,
      min: axis.range[0],
      max: axis.range[1],
      splitNumber: axis.splits,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: true, lineStyle: { color: gridColour, width: 1 } },
      axisLabel: {
        show: true,
        color: labelColour,
        fontSize: 12,
        fontFamily,
        margin: 8,
        // the top of a panel is where the panel above ends: its label would touch that one's bottom label, and the
        // ticks that remain are round numbers
        showMaxLabel: false,
        formatter: (value: number) => format.format(value),
      },
      name: axis.title,
      nameLocation: 'middle',
      nameRotate: 90,
      nameGap: axis.titleLines === 2 ? 60 : 52,
      nameTextStyle: { color: labelColour, fontSize: 12, fontFamily, lineHeight: 14 },
    })
  })

  const series: any[] = []
  const gridOf = (panel: string) => rows.findIndex(r => r.id === panel) + 1

  // the backdrop of each panel: the bands of daylight, the midnights, the moment now, the freezing point, the divider
  rows.forEach((row, i) => {
    const data: number[][] = []
    for (const day of model.days) {
      if (day.light)
        data.push([BACKDROP.band, day.light[0], day.light[1], day.cloud])
      if (day.start > model.minTime)
        data.push([BACKDROP.midnight, day.start, 0, 0])
    }
    if (now !== null)
      data.push([BACKDROP.now, now, 0, 0])
    if (row.id === 'temp' && model.freezing !== null)
      data.push([BACKDROP.freeze, 0, model.freezing, 0])
    if (i < rows.length - 1)
      data.push([BACKDROP.divider, 0, 0, 0])
    series.push({
      id: `backdrop-${row.id}`,
      type: 'custom',
      xAxisIndex: i + 1,
      yAxisIndex: i + 1,
      silent: true,
      clip: true,
      z: 1,
      animation: false,
      data,
      renderItem: (params: any, api: any) => {
        const cs = params.coordSys
        const left = cs.x
        const right = cs.x + cs.width
        const kind = api.value(0)
        if (kind === BACKDROP.band) {
          const span = clampSpan(api.coord([api.value(1), 0])[0], api.coord([api.value(2), 0])[0], left, right)
          return span ? { type: 'rect', silent: true, shape: { x: span[0], y: cs.y, width: span[1] - span[0], height: cs.height }, style: { fill: bandColour(api.value(3), dark) } } : null
        }
        if (kind === BACKDROP.midnight || kind === BACKDROP.now) {
          const x = api.coord([api.value(1), 0])[0]
          if (x < left || x > right)
            return null
          const isNow = kind === BACKDROP.now
          return { type: 'line', silent: true, shape: { x1: x, y1: cs.y, x2: x, y2: cs.y + cs.height }, style: { stroke: isNow ? nowColour : midnightColour, lineWidth: isNow ? 1.5 : 1, lineDash: isNow ? undefined : [2, 3] } }
        }
        if (kind === BACKDROP.freeze) {
          const y = api.coord([0, api.value(2)])[1]
          return { type: 'line', silent: true, shape: { x1: left, y1: y, x2: right, y2: y }, style: { stroke: theme.zeroline, lineWidth: 1 } }
        }
        // the divider under the panel, from the edge of the chart to the edge
        const y = cs.y + cs.height + (layout.rows[i + 1] ? (layout.rows[i + 1]!.top - (row.top + row.height)) / 2 : 0)
        return { type: 'line', silent: true, shape: { x1: 0, y1: y, x2: outerPx, y2: y }, style: { stroke: dividerColour, lineWidth: 1 } }
      },
    })
  })

  // the lines and bars
  const lineSeries = (s: DrawnSeries): any => {
    const colour = toneColor(s.tone, dark)
    const fill = dark ? TONES[s.tone].fillDark : TONES[s.tone].fillLight
    const index = gridOf(s.panel)
    const common = { id: s.id, xAxisIndex: index, yAxisIndex: index, silent: true, data: s.data, animation: !reducedMotion }
    if (s.kind === 'bar') {
      return { ...common, type: 'bar', stack: 'precipitation', barWidth: '90%', itemStyle: { color: colour }, z: 3 }
    }
    return {
      ...common,
      type: 'line',
      showSymbol: false,
      smooth: s.kind === 'line' ? 0.4 : false,
      smoothMonotone: 'x',
      step: s.kind === 'step' ? 'start' : false,
      connectNulls: false,
      lineStyle: { color: colour, width: s.width, type: s.dashed ? 'dashed' : 'solid' },
      itemStyle: { color: colour },
      areaStyle: s.area && fill ? { color: fill, origin: 'auto' } : undefined,
      z: s.tone === 'cloudTotal' ? 4 : 3,
    }
  }
  for (const s of model.series)
    series.push(lineSeries(s))

  // the wind barbs, on the speed line at their hour: thinned to the room there is at the zoom the chart is in
  if (model.barbs.length && rows.some(r => r.id === 'wind')) {
    const index = gridOf('wind')
    series.push({
      id: 'barbs',
      type: 'custom',
      xAxisIndex: index,
      yAxisIndex: index,
      silent: true,
      clip: true,
      z: 5,
      animation: false,
      data: model.barbs.map(b => [b.t, b.speed, b.dir, b.knots, b.cadence, b.index]),
      renderItem: (params: any, api: any) => {
        const step = every(api.size([HOUR_MS, 0])[0], api.value(4), BARB_SPACING)
        if (api.value(5) % step !== 0)
          return null
        const [x, y] = api.coord([api.value(0), api.value(1)])
        const cs = params.coordSys
        if (outsidePlot(x, cs.x, cs.x + cs.width, 30))
          return null
        const barb = windBarb(api.value(2), api.value(3))
        const style = { stroke: theme.textStrong, fill: theme.textStrong, lineWidth: barb.lineWidth }
        const children: any[] = []
        if (barb.calm !== null)
          children.push({ type: 'circle', silent: true, shape: { cx: 0, cy: 0, r: barb.calm }, style: { ...style, fill: 'none' } })
        if (barb.shaft)
          children.push({ type: 'line', silent: true, shape: { x1: barb.shaft[0], y1: barb.shaft[1], x2: barb.shaft[2], y2: barb.shaft[3] }, style })
        for (const tick of barb.ticks)
          children.push({ type: 'line', silent: true, shape: { x1: tick[0], y1: tick[1], x2: tick[2], y2: tick[3] }, style })
        for (const points of barb.pennants)
          children.push({ type: 'polygon', silent: true, shape: { points }, style })
        return { type: 'group', x, y, silent: true, children }
      },
    })
  }

  // the header: the day names, the hours and the weather symbols
  const header = layout.header
  const text = (value: string, x: number, y: number, fill: string, bold = false) => ({
    type: 'text',
    silent: true,
    style: { text: value, x, y, fill, font: `${bold ? '700 ' : ''}12px ${fontFamily}`, textAlign: 'center', textVerticalAlign: 'middle' },
  })
  series.push({
    id: 'day-names',
    type: 'custom',
    xAxisIndex: 0,
    yAxisIndex: 0,
    silent: true,
    clip: true,
    z: 5,
    animation: false,
    data: model.days.map((d, i) => [d.noon, d.start, d.end, i]),
    renderItem: (params: any, api: any) => {
      const cs = params.coordSys
      const day = model.days[api.value(3)]!
      const span = clampSpan(api.coord([api.value(1), 0])[0], api.coord([api.value(2), 0])[0], cs.x, cs.x + cs.width)
      if (!span)
        return null
      const width = span[1] - span[0]
      const full = `${day.weekday} ${day.dayMonth}`
      // a date is 7.4 px per character wide or more
      const label = width >= 7.4 * full.length + 8 ? full : width >= 7.4 * day.weekday.length + 8 ? day.weekday : ''
      const colour = day.weekend ? seriesLabelColor('red', dark) : theme.text
      const children: any[] = []
      if (label)
        children.push(text(label, (span[0] + span[1]) / 2, header.daysTop + 10, colour, true))
      const startX = api.coord([api.value(1), 0])[0]
      if (startX > cs.x && startX < cs.x + cs.width && api.value(1) > model.minTime)
        children.push({ type: 'line', silent: true, shape: { x1: startX, y1: header.daysTop + 2, x2: startX, y2: header.height }, style: { stroke: midnightColour, lineWidth: 1 } })
      return { type: 'group', silent: true, children }
    },
  })
  series.push({
    id: 'hours',
    type: 'custom',
    xAxisIndex: 0,
    yAxisIndex: 0,
    silent: true,
    clip: true,
    z: 5,
    animation: false,
    data: model.hours.map(h => [h.t, h.hour]),
    renderItem: (params: any, api: any) => {
      const step = labelStepHours(api.size([HOUR_MS, 0])[0], LABEL_SPACING)
      if (api.value(1) % step !== 0)
        return null
      const x = api.coord([api.value(0), 0])[0]
      // a label that the edge of the plot would cut is left out: half an hour is no hour
      if (outsidePlot(x, params.coordSys.x, params.coordSys.x + params.coordSys.width, -HOUR_LABEL_HALF_WIDTH))
        return null
      return text(hourLabel(api.value(0)), x, header.hoursTop + 9, theme.textMuted)
    },
  })
  if (model.symbols.length && header.symbolsTop !== null) {
    const top = header.symbolsTop
    const symbolFile = (point: typeof model.symbols[number]) => symbolUrl(yrSymbolFor({ kind: point.kind, night: point.night, precipitationMm: point.precipitationMm, sky: point.sky }), dark)
    series.push({
      id: 'symbols',
      type: 'custom',
      xAxisIndex: 0,
      yAxisIndex: 0,
      silent: true,
      clip: true,
      z: 5,
      animation: false,
      data: model.symbols.map((s, i) => [s.t, s.cadence, s.index, i]),
      renderItem: (params: any, api: any) => {
        const spacing = api.size([HOUR_MS, 0])[0]
        if (api.value(2) % every(spacing, api.value(1), SYMBOL_SPACING) !== 0)
          return null
        const x = api.coord([api.value(0), 0])[0]
        if (outsidePlot(x, params.coordSys.x, params.coordSys.x + params.coordSys.width, SYMBOL_SIZE))
          return null
        const point = model.symbols[api.value(3)]!
        return { type: 'image', silent: true, style: { image: symbolFile(point), x: x - SYMBOL_SIZE / 2, y: top + 2, width: SYMBOL_SIZE, height: SYMBOL_SIZE } }
      },
    })
  }

  return {
    animation: !reducedMotion,
    animationDuration: 300,
    animationDurationUpdate: 200,
    backgroundColor: 'transparent',
    textStyle: { fontFamily, color: theme.text },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: [{
      id: 'zoom',
      type: 'inside',
      xAxisIndex: xIndexes,
      startValue: win.start,
      endValue: win.end,
      filterMode: 'none',
      // a drag is a zoom box or the scroll, a wheel the page's: a pinch, and Ctrl and the wheel (a trackpad's pinch), zoom
      zoomOnMouseWheel: 'ctrl',
      moveOnMouseMove: false,
      moveOnMouseWheel: false,
      preventDefaultMouseMove: false,
      minValueSpan: MIN_SPAN_HOURS * HOUR_MS,
      maxValueSpan: bounds.end - bounds.start,
    }],
    series,
  }
}

/** The label of the left gutter: wider where an axis title takes two lines */
export function gutterLeftFor(model: MeteogramModel): number {
  return GUTTER_LEFT + (Object.values(model.axes).some(axis => axis?.titleLines === 2) ? 16 : 0)
}
