<script setup lang="ts">
import type { Value } from '~/shared/types/api'
import { ref, watch, nextTick } from 'vue'

const props = defineProps<{
  values: Value[]
  stationName?: string | null
  stationCoords?: { latitude: number; longitude: number } | null
}>()

const chartRef = ref<HTMLDivElement | null>(null)
let Plotly: any = null
const plotlyLoaded = ref(false)
let overlayCanvas: HTMLCanvasElement | null = null
let overlayAttached = false
let lastArrowInfos: { timeMs: number; dir: number; speed: number }[] = []
let lastOverlayParams: { minTime: number; maxTime: number; layout: any; axisRange: [number, number]; axisDomain: [number, number] } | null = null

function ensureOverlay() {
  if (!chartRef.value)
    return
  if (!overlayCanvas) {
    const c = document.createElement('canvas')
    c.className = 'meteogram-overlay-canvas'
    c.style.position = 'absolute'
    c.style.left = '0'
    c.style.top = '0'
    c.style.width = '100%'
    c.style.height = '100%'
    c.style.pointerEvents = 'none'
    c.style.zIndex = '11'
    // ensure the parent can position absolute children
    const el = chartRef.value
    const cs = window.getComputedStyle(el)
    if (cs.position === 'static')
      el.style.position = 'relative'
    el.appendChild(c)
    overlayCanvas = c
  }
}

function updateOverlaySize() {
  if (!overlayCanvas || !chartRef.value)
    return
  const dpr = window.devicePixelRatio || 1
  const w = chartRef.value.clientWidth
  const h = chartRef.value.clientHeight
  overlayCanvas.width = Math.round(w * dpr)
  overlayCanvas.height = Math.round(h * dpr)
  overlayCanvas.style.width = `${w}px`
  overlayCanvas.style.height = `${h}px`
  const ctx = overlayCanvas.getContext('2d')
  if (!ctx) return
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.scale(dpr, dpr)
  ctx.clearRect(0, 0, w, h)
}

function drawBarb(ctx: CanvasRenderingContext2D, px: number, py: number, dirFrom: number, speed: number) {
  // dirFrom = wind FROM degrees; barb points TO = from + 180
  const toDeg = (dirFrom + 180) % 360
  const angle = (toDeg * Math.PI) / 180
  const shaft = 18
  const headLen = 6
  const tailX = px - shaft * Math.cos(angle)
  const tailY = py - shaft * Math.sin(angle)

  ctx.strokeStyle = '#0f172a'
  ctx.fillStyle = '#0f172a'
  ctx.lineWidth = 1.5

  // shaft
  ctx.beginPath()
  ctx.moveTo(tailX, tailY)
  ctx.lineTo(px, py)
  ctx.stroke()

  // arrow head (triangle)
  const baseX = px - headLen * Math.cos(angle)
  const baseY = py - headLen * Math.sin(angle)
  const perpX = Math.sin(angle) * (headLen * 0.9)
  const perpY = -Math.cos(angle) * (headLen * 0.9)
  ctx.beginPath()
  ctx.moveTo(px, py)
  ctx.lineTo(baseX + perpX, baseY + perpY)
  ctx.lineTo(baseX - perpX, baseY - perpY)
  ctx.closePath()
  ctx.fill()

  // small barbs for speed (one barb per ~2.5 m/s, cap 3 for clarity)
  const barbCount = Math.min(3, Math.floor(speed / 2.5))
  for (let i = 0; i < barbCount; i++) {
    const dist = headLen + 4 + i * 6
    const bx = px - dist * Math.cos(angle)
    const by = py - dist * Math.sin(angle)
    const barbLen = 6
    const barbAngle = angle + Math.PI / 4 // 45° outward
    const ex = bx + barbLen * Math.cos(barbAngle)
    const ey = by + barbLen * Math.sin(barbAngle)
    ctx.beginPath()
    ctx.moveTo(bx, by)
    ctx.lineTo(ex, ey)
    ctx.stroke()
  }
}

function drawWindBarbs(arrowInfos: { timeMs: number; dir: number; speed: number }[], minTime: number, maxTime: number, layoutObj: any, axisRange: [number, number], axisDomain: [number, number]) {
  if (!chartRef.value) return
  ensureOverlay()
  updateOverlaySize()
  if (!overlayCanvas) return
  const ctx = overlayCanvas.getContext('2d')
  if (!ctx) return

  const rect = chartRef.value.getBoundingClientRect()
  const margin = layoutObj?.margin ?? { l: 48, r: 8, t: 8, b: 32 }
  const plotLeft = margin.l
  const plotTop = margin.t
  const plotWidth = rect.width - margin.l - margin.r
  const plotHeight = rect.height - margin.t - margin.b

  function xToPx(timeMs: number) {
    const t = (timeMs - minTime) / Math.max(1, (maxTime - minTime))
    return plotLeft + t * plotWidth
  }

  const domainLow = axisDomain[0]
  const domainHigh = axisDomain[1]
  const axisMin = axisRange[0]
  const axisMax = axisRange[1]

  function yToPx(value: number) {
    const frac = (value - axisMin) / Math.max(1e-6, (axisMax - axisMin))
    const paperY = domainLow + frac * (domainHigh - domainLow)
    return plotTop + (1 - paperY) * plotHeight
  }

  // draw each barb
  for (const a of arrowInfos) {
    const px = xToPx(a.timeMs)
    const py = yToPx(a.speed)
    drawBarb(ctx, px, py, a.dir, a.speed)
  }
}

function attachOverlayListeners(getParams: () => { arrowInfos: { timeMs: number; dir: number; speed: number }[]; minTime: number; maxTime: number; layoutObj: any; axisRange: [number, number]; axisDomain: [number, number] }) {
  if (!chartRef.value || overlayAttached) return
  const redraw = () => {
    const p = getParams()
    lastArrowInfos = p.arrowInfos
    lastOverlayParams = { minTime: p.minTime, maxTime: p.maxTime, layout: p.layoutObj, axisRange: p.axisRange, axisDomain: p.axisDomain }
    drawWindBarbs(p.arrowInfos, p.minTime, p.maxTime, p.layoutObj, p.axisRange, p.axisDomain)
  }
  // Plotly events
  try {
    ;(chartRef.value as any).on && (chartRef.value as any).on('plotly_relayout', redraw)
    ;(chartRef.value as any).on && (chartRef.value as any).on('plotly_afterplot', redraw)
  }
  catch (e) {
    // ignore if not available
  }
  window.addEventListener('resize', redraw)
  overlayAttached = true
}

function findFirstAvailable(names: string[], available: Set<string>) {
  for (const n of names) {
    if (available.has(n))
      return n
  }
  return undefined
}

function buildSeries(values: Value[]) {
  const series = new Map<string, { x: Date[], y: number[] }>()
  for (const v of values) {
    const p = String(v.parameter)
    if (!series.has(p))
      series.set(p, { x: [], y: [] })
    if (v.value !== null && v.value !== undefined) {
      series.get(p)!.x.push(new Date(v.date))
      series.get(p)!.y.push(v.value)
    }
  }
  for (const [, s] of series) {
    const pairs = s.x.map((d, i) => ({ d, y: s.y[i]! })).sort((a, b) => a.d.getTime() - b.d.getTime())
    s.x = pairs.map(p => p.d)
    s.y = pairs.map(p => p.y)
  }
  return series
}

// Wind direction FROM → arrow points TO
function windArrow(fromDeg: number): string {
  const a = ['↓', '↙', '←', '↖', '↑', '↗', '→', '↘']
  return a[Math.round(((fromDeg % 360) + 360) % 360 / 45) % 8]!
}

/**
 * Sky colour at a given UTC hour, blended toward overcast grey by cloudFraction [0-1].
 * Keyframes calibrated for Central Europe (CEST = UTC+2):
 *   UTC 4 ≈ local sunrise, UTC 10 ≈ local noon, UTC 20 ≈ local sunset.
 */
function skyRgb(utcHour: number, cloudFraction: number = 0): [number, number, number] {
  const kf: [number, number, number, number][] = [
    // [hour, r, g, b]
    [0,  5,   8,  28],  // deep night navy
    [3,  12,  18,  55],  // pre-dawn blue-purple
    [4,  55,  20,  65],  // dawn purple blush
    [5,  190, 85,  35],  // sunrise orange
    [6,  235, 168, 62],  // golden hour
    [7,  175, 205, 228], // morning haze
    [10, 100, 165, 215], // morning sky blue
    [13, 78,  148, 210], // midday blue
    [16, 108, 172, 215], // afternoon
    [18, 215, 155, 65],  // late-afternoon warm
    [19, 228, 102, 38],  // sunset orange-red
    [20, 88,  32,  78],  // dusk purple
    [21, 18,  10,  48],  // early night
    [24, 5,   8,   28],  // back to deep night
  ]

  const h = ((utcHour % 24) + 24) % 24
  let r = 5, g = 8, b = 28
  for (let i = 0; i < kf.length - 1; i++) {
    const [h0, r0, g0, b0] = kf[i]!
    const [h1, r1, g1, b1] = kf[i + 1]!
    if (h >= h0 && h < h1) {
      const t = (h - h0) / (h1 - h0)
      r = Math.round(r0 + t * (r1 - r0))
      g = Math.round(g0 + t * (g1 - g0))
      b = Math.round(b0 + t * (b1 - b0))
      break
    }
  }

  // Blend toward overcast grey as cloud cover increases
  const cf = Math.max(0, Math.min(1, cloudFraction))
  const grey = 158
  return [
    Math.round(r + cf * (grey - r)),
    Math.round(g + cf * (grey - g)),
    Math.round(b + cf * (grey - b)),
  ]
}

const DAY_DE = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa']

function getMidnights(startMs: number, endMs: number): Date[] {
  const result: Date[] = []
  const d = new Date(startMs)
  d.setUTCHours(0, 0, 0, 0)
  d.setUTCDate(d.getUTCDate() + 1)
  while (d.getTime() < endMs) {
    result.push(new Date(d))
    d.setUTCDate(d.getUTCDate() + 1)
  }
  return result
}

function getCalendarDays(startMs: number, endMs: number): Date[] {
  const days: Date[] = []
  const d = new Date(startMs)
  d.setUTCHours(0, 0, 0, 0)
  while (d.getTime() <= endMs) {
    days.push(new Date(d))
    d.setUTCDate(d.getUTCDate() + 1)
  }
  return days
}

async function renderChart() {
  await nextTick()
  if (!chartRef.value)
    return

  const vals = props.values ?? []
  if (!vals.length) {
    if (Plotly && chartRef.value)
      Plotly.purge(chartRef.value)
    return
  }

  if (!plotlyLoaded.value) {
    Plotly = await import('plotly.js-dist-min')
    plotlyLoaded.value = true
  }

  const series = buildSeries(vals)
  const available = new Set(series.keys())

  const tempKey = findFirstAvailable(['temperature_air_mean_2m', 'ttt'], available)
  const precipKey = findFirstAvailable(['precipitation_height_last_1h', 'rr1', 'rr1c'], available)
  const windKey = findFirstAvailable(['wind_speed', 'ff'], available)
  const windDirKey = findFirstAvailable(['wind_direction', 'dd'], available)
  const cloudKey = findFirstAvailable(['cloud_cover_total', 'n'], available)

  const allTimes = [...series.values()].flatMap(s => s.x.map(d => d.getTime()))
  const minTime = Math.min(...allTimes)
  const maxTime = Math.max(...allTimes)

  // Build cloud fraction lookup (used to optionally tint day bands)
  const cloudMap = new Map<number, number>()
  if (cloudKey) {
    const cs = series.get(cloudKey)!
    cs.x.forEach((d, i) => cloudMap.set(d.getTime(), (cs.y[i]! ?? 0) / 100))
  }

  // Build per-day day-band shapes using per-station sunrise/sunset if coords are available.
  // Falls back to a proxy sunrise/sunset (UTC 04:00-20:00) when coords are missing.
  const dayShapes: any[] = []
  const days = getCalendarDays(minTime, maxTime)
  if (props.stationCoords && props.stationCoords.latitude != null && props.stationCoords.longitude != null) {
    // dynamic import of suncalc keeps bundle small
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const SunCalc = (await import('suncalc')) as any
    const lat = props.stationCoords.latitude
    const lon = props.stationCoords.longitude
    for (const day of days) {
      const midday = new Date(day.getTime()); midday.setUTCHours(12, 0, 0, 0)
      const times = SunCalc.getTimes(midday, lat, lon) as Record<string, Date | undefined>
      const sunrise = times.sunrise ?? times.sunriseEnd ?? new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), 4))
      const sunset = times.sunset ?? times.sunsetStart ?? new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), 20))
      // Optionally tint day band slightly toward grey by cloud fraction at midday
      const middayCf = cloudMap.get(midday.getTime()) ?? 0
      const alpha = 0.55 - Math.min(0.35, middayCf * 0.5)
      dayShapes.push({
        type: 'rect', xref: 'x', yref: 'paper',
        x0: sunrise.toISOString(), x1: sunset.toISOString(),
        y0: 0, y1: 1,
        fillcolor: `rgba(253,244,180,${alpha})`,
        line: { width: 0 },
        layer: 'below',
      })
    }
  }
  else {
    for (const day of days) {
      const x0 = new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), 4))
      const x1 = new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), 20))
      dayShapes.push({
        type: 'rect', xref: 'x', yref: 'paper',
        x0: x0.toISOString(), x1: x1.toISOString(),
        y0: 0, y1: 1,
        fillcolor: 'rgba(253,244,180,0.55)',
        line: { width: 0 },
        layer: 'below',
      })
    }
  }

  // ── Day separators (dotted white line at midnight) ────────────────
  const separators: any[] = getMidnights(minTime, maxTime).map(m => ({
    type: 'line',
    xref: 'x', yref: 'paper',
    x0: m.toISOString(), x1: m.toISOString(),
    y0: 0, y1: 1,
    line: { color: 'rgba(255,255,255,0.22)', width: 1, dash: 'dot' },
  }))

  // ── Day name annotations (just above the plot area) ───────────────
  const annotations: any[] = []
  for (const day of getCalendarDays(minTime, maxTime)) {
    const noon = new Date(day)
    noon.setUTCHours(10, 0, 0, 0) // UTC 10 ≈ CEST noon
    if (noon.getTime() < minTime || noon.getTime() > maxTime)
      continue
    const dd = String(day.getUTCDate()).padStart(2, '0')
    const mm = String(day.getUTCMonth() + 1).padStart(2, '0')
    const isWeekend = day.getUTCDay() === 0 || day.getUTCDay() === 6
    annotations.push({
      x: noon.toISOString(),
      y: 1.0,
      xref: 'x', yref: 'paper',
      text: `<b>${DAY_DE[day.getUTCDay()]}</b> ${dd}.${mm}`,
      showarrow: false,
      font: { size: 10, color: isWeekend ? '#fbbf24' : 'rgba(255,255,255,0.80)' },
      xanchor: 'center',
      yanchor: 'bottom',
    })
  }

  // ── Traces ───────────────────────────────────────────────────────
  const traces: any[] = []

  // Temperature – glow halo + crisp white spline
  let tempMinY = 0, tempMaxY = 25
  if (tempKey) {
    const s = series.get(tempKey)!
    tempMinY = Math.min(0, ...s.y)
    tempMaxY = Math.max(...s.y)
    const xs = s.x.map(d => d.toISOString())
    // Wide warm glow underneath
    traces.push({
      x: xs, y: s.y,
      type: 'scatter', mode: 'lines',
      line: { color: 'rgba(255,200,80,0.18)', width: 12, shape: 'spline', smoothing: 0.6 },
      showlegend: false, yaxis: 'y3', hoverinfo: 'skip',
    })
    // Actual white line
    traces.push({
      name: 'Temperature °C',
      x: xs, y: s.y,
      type: 'scatter', mode: 'lines',
      line: { color: '#ffffff', width: 2.5, shape: 'spline', smoothing: 0.6 },
      yaxis: 'y3',
      hovertemplate: '%{y:.1f}°C<extra>Temperature</extra>',
    })
  }

  // Precipitation – ice-blue bars
  if (precipKey) {
    const s = series.get(precipKey)!
    traces.push({
      name: 'Precip mm',
      x: s.x.map(d => d.toISOString()), y: s.y,
      type: 'bar',
      marker: { color: 'rgba(180,225,255,0.72)', line: { color: 'rgba(220,242,255,0.9)', width: 0.5 } },
      yaxis: 'y2',
      hovertemplate: '%{y:.2f} mm<extra>Precipitation</extra>',
    })
  }

  // Wind speed (cyan fill) + direction arrows fixed at top
  let windMaxY = 10
  if (windKey) {
    const s = series.get(windKey)!
    windMaxY = Math.max(...s.y, 5)

    traces.push({
      name: 'Wind m/s',
      x: s.x.map(d => d.toISOString()), y: s.y,
      type: 'scatter', mode: 'lines',
      line: { color: 'rgba(100,235,210,0.90)', width: 2 },
      fill: 'tozeroy',
      fillcolor: 'rgba(100,235,210,0.10)',
      yaxis: 'y',
      hovertemplate: '%{y:.1f} m/s<extra>Wind</extra>',
    })

    if (windDirKey) {
      const dirS = series.get(windDirKey)!
      const dirMap = new Map<string, number>()
      dirS.x.forEach((d, i) => dirMap.set(d.toISOString(), dirS.y[i]!))

      const arrowX: string[] = []
      const arrowCustom: number[] = []
      const arrowText: string[] = []
      s.x.forEach((date, i) => {
        if (i % 3 !== 0)
          return
        const iso = date.toISOString()
        const dir = dirMap.get(iso)
        if (dir !== undefined) {
          arrowX.push(iso)
          arrowText.push(windArrow(dir))
          arrowCustom.push(dir)
        }
      })

      traces.push({
        name: 'Direction',
        x: arrowX,
        y: Array(arrowX.length).fill(windMaxY * 1.36),
        customdata: arrowCustom,
        text: arrowText,
        type: 'scatter', mode: 'text',
        textfont: { size: 13, color: 'rgba(255,255,255,0.88)' },
        hovertemplate: 'From %{customdata:.0f}°<extra>Wind direction</extra>',
        yaxis: 'y',
        showlegend: false,
      })
    }
  }

  // ── Panel geometry (bottom→top: wind | precip | temp) ────────────
  const gap = 0.025
  const windTop = 0.18
  const precipBot = windTop + gap
  const precipTop = 0.35
  const tempBot = precipTop + gap

  // ── Shared style constants (dark-on-light tokens)
  // Use neutral dark base for axis/tick/grid on light background
  const W = (a: number) => `rgba(55,65,81,${a})`   // #374151 with alpha
  const GRID = W(0.08)
  const TICK = W(0.65)
  const ZERO = W(0.20)

  // ── Panel divider lines ──────────────────────────────────────────
  const dividers: any[] = [
    { type: 'line', xref: 'paper', yref: 'paper', x0: 0, x1: 1, y0: windTop + gap / 2, y1: windTop + gap / 2, line: { color: W(0.18), width: 1 } },
    { type: 'line', xref: 'paper', yref: 'paper', x0: 0, x1: 1, y0: precipTop + gap / 2, y1: precipTop + gap / 2, line: { color: W(0.18), width: 1 } },
  ]

  // ── Layout ───────────────────────────────────────────────────────
  const layout: any = {
    autosize: true,
    margin: { l: 48, r: 8, t: 8, b: 32 },
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff',
    font: { family: '"Inter", system-ui, sans-serif', size: 11, color: '#374151' },
    hovermode: 'x unified',
    bargap: 0.05,
    shapes: [...dayShapes, ...separators, ...dividers],
    annotations,
    legend: {
      x: 0.01, y: 0.98,
      xanchor: 'left', yanchor: 'top',
      bgcolor: 'rgba(255,255,255,0.9)',
      bordercolor: '#e5e7eb',
      borderwidth: 1,
      font: { size: 10, color: '#374151' },
    },

    xaxis: {
      type: 'date',
      domain: [0, 1],
      anchor: 'y',
      showgrid: false,
      linecolor: 'rgba(0,0,0,0)',
      tickformat: '%H',
      dtick: 6 * 3_600_000,
      tickfont: { size: 9, color: TICK },
      tickcolor: W(0.25),
      range: [new Date(minTime).toISOString(), new Date(maxTime).toISOString()],
    },

    // Wind – bottom
    yaxis: {
      domain: [0, windTop],
      title: { text: 'Wind m/s', font: { size: 9, color: W(0.55) }, standoff: 2 },
      gridcolor: GRID,
      linecolor: 'rgba(0,0,0,0)',
      zeroline: false,
      rangemode: 'tozero',
      range: [0, windMaxY * 1.60],   // headroom for arrow row
      tickfont: { size: 9, color: TICK },
      tickcolor: W(0.15),
      nticks: 4,
      fixedrange: true,
    },

    // Precipitation
    yaxis2: {
      domain: [precipBot, precipTop],
      title: { text: 'Precip mm', font: { size: 9, color: W(0.55) }, standoff: 2 },
      gridcolor: GRID,
      linecolor: 'rgba(0,0,0,0)',
      zeroline: false,
      rangemode: 'tozero',
      tickfont: { size: 9, color: TICK },
      tickcolor: W(0.15),
      nticks: 3,
      fixedrange: true,
    },

    // Temperature – dominant top panel
    yaxis3: {
      domain: [tempBot, 1.0],
      title: { text: 'Temp °C', font: { size: 9, color: W(0.55) }, standoff: 2 },
      gridcolor: GRID,
      linecolor: 'rgba(0,0,0,0)',
      zeroline: true,
      zerolinecolor: ZERO,
      zerolinewidth: 1,
      range: [tempMinY - 1, tempMaxY + 3],
      tickfont: { size: 9, color: TICK },
      tickcolor: W(0.15),
      fixedrange: true,
    },
  }

  const config = { responsive: true, displayModeBar: false }

  if (chartRef.value) {
    Plotly.purge(chartRef.value)
    await Plotly.newPlot(chartRef.value, traces, layout, config)

    // Setup overlay drawing of wind barbs using a canvas overlay
    if (typeof window !== 'undefined' && windKey && chartRef.value) {
      const arrowInfos: { timeMs: number; dir: number; speed: number }[] = []
      if (windKey) {
        const s = series.get(windKey)!
        const dirSeries = windDirKey ? series.get(windDirKey) : undefined
        for (let i = 0; i < s.x.length; i++) {
          if (i % 3 !== 0) continue // subsample
          const timeMs = s.x[i]!.getTime()
          const speed = s.y[i] ?? 0
          const dir = dirSeries ? (dirSeries.y[i] ?? dirSeries.y[0] ?? 0) : 0
          arrowInfos.push({ timeMs, dir, speed })
        }
      }

      const getParams = () => ({ arrowInfos, minTime, maxTime, layoutObj: layout, axisRange: [0, Math.max(1, ...((series.get(windKey)?.y) ?? [10]))] as [number, number], axisDomain: [0, windTop] as [number, number] })
      attachOverlayListeners(getParams)
    }
  }
}

watch(() => props.values, () => { void renderChart() }, { immediate: true, deep: true })
</script>

<template>
  <div>
    <div v-if="!values || values.length === 0" class="py-12 text-center text-gray-500">
      No data available for the selected query
    </div>
    <!-- v-show keeps the div in DOM so chartRef is never null when values arrive -->
    <div v-show="values && values.length > 0" ref="chartRef" style="width: 100%; height: 500px; border-radius: 8px; overflow: hidden;" />
  </div>
</template>
