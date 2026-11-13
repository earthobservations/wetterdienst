<script setup lang="ts">
import type { SunTimes } from 'suncalc'
import type { Value } from '#shared/types/api'
import type { PanelId } from '~/composables/useMeteogramView'
import type { ChartTheme, SeriesLabel } from '~/utils/chart-theme'
import type { MeteogramView } from '~/utils/meteogram'
import type { Quantity } from '~/utils/units'
import { DateTime, Info } from 'luxon'
import tzLookup from 'tz-lookup'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { formatDayMonth, formatHour, plotlyHoverFormat, plotlySeparators, weekdayShort } from '~/utils/format'
import { extremeWindowHours, extremeWindowSteps, interpSeries, METEOGRAM_SERIES, resampleCadenceMs, wetBulbApprox } from '~/utils/meteogram'
import { meteogramDays } from '~/utils/meteogram-days'
import { buildSeries, findFirstAvailable, resampleSeries } from '~/utils/meteogram-series'
import { meteogramSummary, meteogramTable } from '~/utils/meteogram-summary'
import { fitAxisTitle, MARGIN_LEFT, MARGIN_RIGHT, plotWidth, tickStepHours } from '~/utils/meteogram-ticks'
import { meteogramUnits } from '~/utils/meteogram-units'
import { plotlyLocaleConfig } from '~/utils/plotly-locale'
import { digitsOf, withUnit } from '~/utils/units'
import { WEATHER_ICONS } from '~/utils/weather-kind'

const props = defineProps<{
  values: Value[]
  stationName?: string | null
  stationCoords?: { latitude: number | null, longitude: number | null } | null
  widget?: boolean
  /**
   * The day rows alone, with no chart and no controls: the forecast in the map's panel (GH-3650). The view is not
   * the reader's to choose and nothing is remembered or written to the address.
   */
  daysOnly?: boolean
  /**
   * The unit each parameter's values are in, by the parameter's canonical name, as the answer says (`metadata.parameters`
   * of an answer `with_metadata`, `unitsOfAnswer`). The labels of the charts, the table and the day rows are written
   * from it, and the verdicts (rain or snow, the weather of a day, the wind barbs) are judged in canonical units
   * whatever it is (GH-3980). A parameter the answer gives no unit for is read as the canonical unit of its quantity.
   */
  units?: Record<string, string>
}>()

const { t, locale } = useI18n()

// The language's own tag (`en-GB`, `de-DE`) where `locale` is the app's code (`en`), with the stand-in for a language
// the browser has no data for (`lb-LU` is written as `de-LU`): what the date formats, `Intl` and luxon are handed
const formatLanguage = useFormatLanguage()

const chartRef = ref<HTMLDivElement | null>(null)
let Plotly: any = null
// the theme the chart on the page was last drawn in, which its overlay of wind barbs is painted in
let drawnTheme: ChartTheme | null = null
// loaded once, as Plotly is: a drawing in the colours of a switched scheme, or of a print, has no wait for it
let SunCalc: typeof import('suncalc') | null = null
const plotlyLoaded = ref(false)
let overlayCanvas: HTMLCanvasElement | null = null
let overlayAttached = false

// The chart's chrome (paper, text, grid, hover label) is read from the app's CSS tokens for the colour
// scheme in force (utils/chart-theme.ts); a switch of the scheme draws the chart again below
const { theme, isDark } = useChartTheme()

// What the reader chose: the view (remembered, and in the address), the panels, the horizon
const { view, compact, visiblePanels, horizonHours, chooseView } = useMeteogramView(props)
// The chart's type in px (GH-3558): a printed chart is scaled down, so 12 px ticks print at about 6 pt
const TICK_FONT = 12
const chartHeight = computed(() => (compact.value ? '320px' : '540px'))
const viewOptions = computed<{ value: MeteogramView, label: string, icon: string }[]>(() => [
  { value: 'chart', label: t('meteogram.chart.viewChart'), icon: 'i-ph-chart-line' },
  { value: 'compact', label: t('meteogram.chart.viewCompact'), icon: 'i-ph-squares-four' },
  { value: 'table', label: t('meteogram.chart.viewTable'), icon: 'i-ph-table' },
])

// The panel toggles, in the order of the panels: the colour of each is that of its series' labels
// `icon` is the outline, `iconOn` the filled variant of the same icon: a toggle that is on draws the filled one, so that on
// and off differ by shape and not by colour alone (WCAG 1.4.1, GH-3951)
const panelToggles: { panel: PanelId, icon: string, iconOn: string, title: string, series: SeriesLabel }[] = [
  { panel: 'temp', icon: 'i-ph-thermometer', iconOn: 'i-ph-thermometer-fill', title: 'meteogram.chart.panelTemperature', series: 'red' },
  { panel: 'wind', icon: 'i-ph-wind', iconOn: 'i-ph-wind-fill', title: 'meteogram.chart.panelWind', series: 'cyan' },
  { panel: 'precip', icon: 'i-ph-cloud-rain', iconOn: 'i-ph-cloud-rain-fill', title: 'meteogram.chart.panelPrecipitation', series: 'blue' },
  { panel: 'cloud', icon: 'i-ph-cloud', iconOn: 'i-ph-cloud-fill', title: 'meteogram.chart.panelCloud', series: 'slate' },
  { panel: 'pressure', icon: 'i-ph-gauge', iconOn: 'i-ph-gauge-fill', title: 'meteogram.chart.panelPressure', series: 'lime' },
]
// a toggle that is on: the icon in the label colour, on a wash and in an edge of it
const activeToggleStyle = (series: SeriesLabel) => panelToggleStyle(seriesLabelColor(series, isDark.value))

const horizonOptions = computed(() => [
  { label: '24h', value: 24 },
  { label: '3d', value: 72 },
  { label: '7d', value: 168 },
  { label: t('meteogram.chart.horizonAll'), value: null },
])

const seriesCache = computed(() => buildSeries(props.values ?? []))

const units = computed(() => meteogramUnits(props.units, t))
const unitOf = (quantity: Quantity) => units.value.unitOf(quantity)
const canon = (quantity: Quantity, value: number) => units.value.canon(quantity, value)
const shown = (quantity: Quantity, value: number) => units.value.shown(quantity, value)
const stretch = (quantity: Quantity, delta: number) => units.value.stretch(quantity, delta)
const unitName = (quantity: Quantity) => units.value.unitName(quantity)
const digits = (quantity: Quantity) => units.value.digits(quantity)
const named = (key: string, quantity: Quantity) => units.value.named(key, quantity)
/** A number of a quantity with its unit after it, as the hover texts of the charts write it */
function hoverUnit(quantity: Quantity) {
  const unit = unitOf(quantity)
  return withUnit(`%{y:.${digitsOf(quantity, unit)}f}`, unit)
}
// overlay redraw handler ref for attach/detach
let overlayRedrawHandler: ((ev?: any) => void) | null = null

// Expose a reset function that re-applies original Plotly layout
function resetChart() {
  horizonHours.value = null
  if (!chartRef.value || !plotlyLoaded.value)
    return
  try {
    const el = chartRef.value as any
    Plotly.relayout(el, { 'xaxis.autorange': true })
    requestRender(false)
  }
  catch {
    // ignore
  }
}

onBeforeUnmount(() => {
  try {
    cleanupPlotlyOverlayHandlers()
  }
  catch {
    // ignore
  }
  try {
    cleanupOverlay()
  }
  catch {
    // ignore
  }
  if (Plotly && chartRef.value) {
    try {
      Plotly.purge(chartRef.value)
    }
    catch {
      // ignore
    }
  }
})

// Toolbar timezone label (updated when chart renders)
const toolbarTzLabel = ref<string>('UTC')

// The station's time zone, which the times of the table are written in, as the chart's axis is
const stationTimeZone = computed(() => {
  const { latitude, longitude } = props.stationCoords ?? {}
  if (latitude == null || longitude == null)
    return 'UTC'
  try {
    const zone = tzLookup(latitude, longitude)
    // a zone the browser does not know would make every date of the chart invalid
    return Info.isValidIANAZone(zone) ? zone : 'UTC'
  }
  catch {
    return 'UTC'
  }
})

// The date it is today at the station: a computed of its own, so that what reads it runs again at the station's
// midnight and not with every tick of the clock below (GH-3840)
const now = ref(Date.now())
const localToday = computed(() => DateTime.fromMillis(now.value, { zone: stationTimeZone.value }).toISODate()!)
// a page that stays open past midnight moves its Today on
let clock: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  clock = setInterval(() => {
    now.value = Date.now()
  }, 60_000)
})
onBeforeUnmount(() => {
  clearInterval(clock)
})

const compactDays = computed(() => meteogramDays(seriesCache.value, {
  zone: stationTimeZone.value,
  today: localToday.value,
  units: units.value,
  locale: locale.value,
  language: formatLanguage.value,
}))

// What the chart draws, as a table and a sentence (WCAG 1.1.1, 1.3.1, and 1.4.13 for the values that appear
// on hover only)
const chartTable = computed(() => meteogramTable(seriesCache.value, {
  panels: visiblePanels.value,
  horizonHours: horizonHours.value,
  zone: stationTimeZone.value,
  formatLanguage: formatLanguage.value,
  locale: locale.value,
  units: units.value,
  t,
  widget: !!props.widget,
}))
const summaryId = useId()
const chartLabel = computed(() => props.stationName ? t('meteogram.chart.label', { name: props.stationName }) : t('meteogram.chart.labelNoStation'))

const summaryStats = computed(() => meteogramSummary(seriesCache.value, units.value, locale.value))

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
    const el = chartRef.value
    const cs = window.getComputedStyle(el)
    if (cs.position === 'static')
      el.style.position = 'relative'
    el.appendChild(c)
    overlayCanvas = c
  }
}

function cleanupOverlay() {
  try {
    if (overlayRedrawHandler && typeof window !== 'undefined') {
      try {
        window.removeEventListener('resize', overlayRedrawHandler)
      }
      catch {
        // ignore
      }
    }
  }
  catch {
    // ignore
  }
  try {
    if (overlayCanvas && overlayCanvas.parentElement) {
      overlayCanvas.parentElement.removeChild(overlayCanvas)
    }
  }
  catch {
    // ignore
  }
  overlayCanvas = null
  overlayAttached = false
  overlayRedrawHandler = null
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
  if (!ctx)
    return
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.scale(dpr, dpr)
  ctx.clearRect(0, 0, w, h)
}

function drawBarb(ctx: CanvasRenderingContext2D, px: number, py: number, dirFrom: number, kt: number) {
  // Standard meteorological wind barbs: speed encoded in knots, which the caller works out from the speed in
  // metres per second whatever unit the chart shows (a barb is a drawing of the wind, not of a number)
  // Pennant = 50 kt, full barb = 10 kt, half barb = 5 kt
  const scale = compact.value ? 0.78 : 1.0
  // in the colours the chart was drawn in, which a switch of the scheme is yet to redraw it in
  const barbColor = (drawnTheme ?? theme.value).textStrong
  ctx.strokeStyle = barbColor
  ctx.fillStyle = barbColor
  ctx.lineWidth = Math.max(1, 1.5 * scale)

  if (kt < 2.5) {
    // Calm: draw a small circle at the observation point
    ctx.beginPath()
    ctx.arc(px, py, Math.round(4 * scale), 0, 2 * Math.PI)
    ctx.stroke()
    return
  }

  // Shaft: tip at (px, py), tail extends in the "from" direction
  const rad = (dirFrom * Math.PI) / 180
  const shaftLen = Math.round(20 * scale)
  const tailX = px + shaftLen * Math.sin(rad)
  const tailY = py - shaftLen * Math.cos(rad)
  const shaftUX = (tailX - px) / shaftLen
  const shaftUY = (tailY - py) / shaftLen

  // Barb perpendicular: 90° CW from tip→tail = left of wind (NH convention)
  const barbPerpX = -Math.cos(rad)
  const barbPerpY = -Math.sin(rad)
  const barbLen = Math.round(8 * scale)
  const barbSpacing = Math.round(5 * scale)

  let remaining = kt
  const pennants = Math.floor(remaining / 50)
  remaining -= pennants * 50
  const fullBarbs = Math.floor(remaining / 10)
  remaining -= fullBarbs * 10
  const halfBarbs = remaining >= 5 ? 1 : 0

  ctx.beginPath()
  ctx.moveTo(px, py)
  ctx.lineTo(tailX, tailY)
  ctx.stroke()

  let offset = 0
  for (let i = 0; i < pennants; i++) {
    const bx = tailX - offset * shaftUX
    const by = tailY - offset * shaftUY
    const bx2 = tailX - (offset + barbSpacing * 2) * shaftUX
    const by2 = tailY - (offset + barbSpacing * 2) * shaftUY
    ctx.beginPath()
    ctx.moveTo(bx, by)
    ctx.lineTo(bx + barbLen * barbPerpX, by + barbLen * barbPerpY)
    ctx.lineTo(bx2, by2)
    ctx.closePath()
    ctx.fill()
    offset += barbSpacing * 2 + Math.round(2 * scale)
  }
  for (let i = 0; i < fullBarbs; i++) {
    const bx = tailX - offset * shaftUX
    const by = tailY - offset * shaftUY
    ctx.beginPath()
    ctx.moveTo(bx, by)
    ctx.lineTo(bx + barbLen * barbPerpX, by + barbLen * barbPerpY)
    ctx.stroke()
    offset += barbSpacing
  }
  if (halfBarbs > 0) {
    if (pennants === 0 && fullBarbs === 0)
      offset += barbSpacing
    const bx = tailX - offset * shaftUX
    const by = tailY - offset * shaftUY
    ctx.beginPath()
    ctx.moveTo(bx, by)
    ctx.lineTo(bx + Math.round(barbLen * 0.5) * barbPerpX, by + Math.round(barbLen * 0.5) * barbPerpY)
    ctx.stroke()
  }
}

function drawWindBarbs(arrowInfos: { timeMs: number, dir: number, speed: number, knots: number }[], minTime: number, maxTime: number, layoutObj: any, axisRange: [number, number], axisDomain: [number, number]) {
  if (!chartRef.value || !visiblePanels.value.wind)
    return
  ensureOverlay()
  updateOverlaySize()
  if (!overlayCanvas)
    return
  const ctx = overlayCanvas.getContext('2d')
  if (!ctx)
    return

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

  // Clip to the plot area so barbs outside the visible time window
  // (e.g. after zooming) cannot bleed into the margins.
  ctx.save()
  ctx.beginPath()
  ctx.rect(plotLeft, plotTop, plotWidth, plotHeight)
  ctx.clip()

  for (const a of arrowInfos) {
    const px = xToPx(a.timeMs)
    const py = yToPx(a.speed)
    drawBarb(ctx, px, py, a.dir, a.knots)
  }

  ctx.restore()
}

function attachOverlayListeners(getParams: () => { arrowInfos: { timeMs: number, dir: number, speed: number, knots: number }[], minTime: number, maxTime: number, layoutObj: any, axisRange: [number, number], axisDomain: [number, number] }) {
  if (!chartRef.value)
    return
  if (overlayAttached)
    return
  // plotly_relayout fires BEFORE _fullLayout is updated, so drawing barbs
  // there uses a stale range and produces misplaced artefacts. Just clear
  // the canvas immediately so the wind panel is blank while Plotly re-renders
  // its SVG, then do the real redraw in plotly_afterplot when _fullLayout is
  // definitively up to date.
  const clearOnly = () => {
    ensureOverlay()
    updateOverlaySize() // resets canvas & clears
  }

  const redraw = () => {
    const p = getParams()
    // Read the live zoomed range from Plotly's internal layout so barbs are
    // positioned against the current viewport, not the full data span.
    let minTime = p.minTime
    let maxTime = p.maxTime
    try {
      const xRange = (chartRef.value as any)?._fullLayout?.xaxis?.range
      if (xRange?.[0] != null && xRange?.[1] != null) {
        const t0 = new Date(xRange[0]).getTime()
        const t1 = new Date(xRange[1]).getTime()
        if (Number.isFinite(t0) && Number.isFinite(t1) && t0 < t1) {
          minTime = t0
          maxTime = t1
        }
      }
    }
    catch { /* ignore */ }
    drawWindBarbs(p.arrowInfos, minTime, maxTime, p.layoutObj, p.axisRange, p.axisDomain)
  }
  try {
    if ((chartRef.value as any).on) {
      ;(chartRef.value as any).on('plotly_relayout', clearOnly)
      ;(chartRef.value as any).on('plotly_afterplot', redraw)
      ;(chartRef.value as any).__overlay_handlers = ((chartRef.value as any).__overlay_handlers || [])
      ;(chartRef.value as any).__overlay_handlers.push({ name: 'plotly_relayout', fn: clearOnly })
      ;(chartRef.value as any).__overlay_handlers.push({ name: 'plotly_afterplot', fn: redraw })
    }
  }
  catch {
    // ignore
  }
  overlayRedrawHandler = redraw
  window.addEventListener('resize', redraw)
  overlayAttached = true
  // Plotly emits plotly_afterplot of the drawing before the promise of newPlot resolves, and these
  // handlers are attached once it has: the chart's first afterplot is already gone. Without this
  // the barbs are absent until something makes Plotly draw again (a resize of the window).
  redraw()
}

function cleanupPlotlyOverlayHandlers() {
  if (!chartRef.value)
    return
  try {
    const el = chartRef.value as any
    const handlers = el.__overlay_handlers as { name: string, fn: any }[] | undefined
    if (handlers && el.removeAllListeners) {
      for (const h of handlers) {
        try {
          if (el.removeListener) {
            el.removeListener(h.name, h.fn)
          }
        }
        catch {
          // ignore
        }
        try {
          if (el.removeAllListeners) {
            el.removeAllListeners(h.name)
          }
        }
        catch {
          // ignore
        }
      }
    }
    el.__overlay_handlers = []
  }
  catch {
    // ignore
  }
}

function windArrow(fromDeg: number): string {
  const a = ['↓', '↙', '←', '↖', '↑', '↗', '→', '↘']
  return a[Math.round(((fromDeg % 360) + 360) % 360 / 45) % 8]!
}

function getMidnights(startMs: number, endMs: number, tz: string = 'UTC'): Date[] {
  const result: Date[] = []
  let dt = DateTime.fromMillis(startMs, { zone: tz }).startOf('day').plus({ days: 1 })
  while (dt.toMillis() < endMs) {
    result.push(dt.toJSDate())
    dt = dt.plus({ days: 1 })
  }
  return result
}

function getCalendarDays(startMs: number, endMs: number, tz: string = 'UTC'): Date[] {
  const days: Date[] = []
  let dt = DateTime.fromMillis(startMs, { zone: tz }).startOf('day')
  const endDt = DateTime.fromMillis(endMs, { zone: tz }).startOf('day')
  while (dt.toMillis() <= endDt.toMillis()) {
    days.push(dt.toJSDate())
    dt = dt.plus({ days: 1 })
  }
  return days
}

let isRendering = false
let renderPending = false
// The newest render threw -- Plotly's import or its drawing -- and the chart area says so; failures
// counted, so a Retry that fails too is told again
const renderFailed = ref(false)
const renderFailures = ref(0)
// The newest render could not import the chart's code: Plotly, or suncalc for the day bands. Where a
// redeploy has replaced its chunk, a Retry asks for the same chunk again and fails every time, and
// only reloading the page loads the new one: the chart area says so, and offers the reload. Set by
// the render under way, which is one at a time, and taken up as it fails
const chartCodeNotLoaded = ref(false)
let codeImportFailed = false
// a Retry that works hands its focus on to the chart it drew
const chartNotice = useTemplateRef<HTMLElement>('chartNotice')
useFocusAfterRetry(renderFailed, chartNotice, chartRef)

function importChartCode<T>(load: () => Promise<T>): Promise<T> {
  return load().catch((error) => {
    codeImportFailed = true
    throw error
  })
}

function reloadPage() {
  // forced: the user's click, not a reload loop, which is what Nuxt's guard stops. Unforced, a
  // second click within ten seconds of a first that did not help would do nothing
  reloadNuxtApp({ force: true })
}

async function renderChart() {
  if (isRendering) {
    renderPending = true
    return
  }
  isRendering = true
  renderPending = false

  codeImportFailed = false
  try {
    await renderChartActual()
    renderFailed.value = false
  }
  catch (error) {
    console.error('The chart could not be drawn', error)
    // a render queued meanwhile draws next, and tells its own outcome
    if (!renderPending) {
      renderFailed.value = true
      chartCodeNotLoaded.value = codeImportFailed
      renderFailures.value++
    }
  }
  finally {
    isRendering = false
    if (renderPending) {
      void renderChart()
    }
  }
}

// Whether the next drawing keeps the zoom the chart is in: only a drawing in other colours (the scheme
// switched, a print) does, and drawings asked for are merged while one is under way, so a drawing for
// anything else (a horizon, a panel, new values) among them starts the chart over. null: none asked for
let keepZoomNext: boolean | null = null

function requestRender(keepZoom: boolean) {
  keepZoomNext = (keepZoomNext ?? true) && keepZoom
  void renderChart()
}

async function renderChartActual() {
  const keepZoom = keepZoomNext ?? false
  keepZoomNext = null
  await nextTick()
  if (!chartRef.value) {
    try {
      cleanupPlotlyOverlayHandlers()
    }
    catch {}
    try {
      cleanupOverlay()
    }
    catch {}
    return
  }

  const vals = props.values ?? []
  if (!vals.length) {
    try {
      cleanupPlotlyOverlayHandlers()
    }
    catch {}
    try {
      cleanupOverlay()
    }
    catch {}
    if (Plotly && chartRef.value)
      Plotly.purge(chartRef.value)
    return
  }

  if (!plotlyLoaded.value) {
    Plotly = await importChartCode(() => import('plotly.js-basic-dist-min'))
    plotlyLoaded.value = true
  }

  const series = seriesCache.value
  const available = new Set(series.keys())

  const tempKey = findFirstAvailable(METEOGRAM_SERIES.temperature, available)
  const precipKey = findFirstAvailable(METEOGRAM_SERIES.precipitation, available)
  const windKey = findFirstAvailable(METEOGRAM_SERIES.windSpeed, available)
  const windDirKey = findFirstAvailable(METEOGRAM_SERIES.windDirection, available)
  const gustKey = findFirstAvailable(METEOGRAM_SERIES.gust, available)
  const cloudKey = findFirstAvailable(METEOGRAM_SERIES.cloudCover, available)
  const cloudLowKey = findFirstAvailable(METEOGRAM_SERIES.cloudCoverLow, available)
  const cloudMidKey = findFirstAvailable(METEOGRAM_SERIES.cloudCoverMid, available)
  const cloudHighKey = findFirstAvailable(METEOGRAM_SERIES.cloudCoverHigh, available)
  const humidityKey = findFirstAvailable(METEOGRAM_SERIES.humidity, available)
  const dewKey = findFirstAvailable(METEOGRAM_SERIES.dewPoint, available)
  const pressureKey = findFirstAvailable(METEOGRAM_SERIES.pressure, available)
  const txKey = findFirstAvailable(METEOGRAM_SERIES.temperatureMax, available)
  const tnKey = findFirstAvailable(METEOGRAM_SERIES.temperatureMin, available)

  const allTimes = [...series.values()].flatMap(s => s.x.map(d => d.getTime()))
  const minTime = Math.min(...allTimes)
  const maxTime = Math.max(...allTimes)
  const displayMaxTime = horizonHours.value !== null
    ? Math.min(maxTime, minTime + horizonHours.value * 3_600_000)
    : maxTime

  // Resample all series to fixed cadence; precipitation uses nearest-neighbor (not interpolated)
  const precipStepKeys = new Set([precipKey].filter((k): k is string => !!k))
  const resampledSeries = resampleSeries(series, minTime, displayMaxTime, precipStepKeys)

  // Build mapping of original ISO date strings
  const isoMap = new Map<number, string>()
  for (const v of vals) {
    try {
      const ms = new Date(String(v.timestamp)).getTime()
      if (!isoMap.has(ms))
        isoMap.set(ms, String(v.timestamp))
    }
    catch { /* ignore */ }
  }
  const isoMs = Array.from(isoMap.keys()).sort((a, b) => a - b)
  const isoDates = isoMs.map(m => new Date(m))

  // Determine timezone
  const stationTZ = stationTimeZone.value

  // Build custom tick values & labels
  let customTickVals: string[] | undefined
  let customTickText: string[] | undefined
  // extra layout padding requested by annotations (top/right)
  const extraTop = 0
  const extraRight = 0
  const annotations: any[] = []

  // Available plot width drives tick density: it avoids overlap on narrow mobile screens
  const plotInnerWidth = plotWidth(chartRef.value?.clientWidth || 800)
  const rangeHours = (displayMaxTime - minTime) / 3_600_000

  if (isoDates.length > 0) {
    const tickMs = tickStepHours(rangeHours, plotInnerWidth) * 3_600_000

    const startTick = Math.ceil(minTime / tickMs) * tickMs
    const tickVals: string[] = []
    const tickText: string[] = []
    for (let t = startTick; t <= displayMaxTime; t += tickMs) {
      tickVals.push(new Date(t).toISOString())
      // the hour as the language writes a time of day (Danish "04.00"), in the station's zone
      tickText.push(formatHour(t, formatLanguage.value, stationTZ))
    }
    customTickVals = tickVals
    customTickText = tickText

    // Compute a toolbar-friendly timezone label and store it for display above the chart.
    try {
      let tzLabel = stationTZ
      try {
        const offsetMin = DateTime.fromMillis(minTime, { zone: stationTZ }).offset
        const sign = offsetMin >= 0 ? '+' : '-'
        const h = String(Math.floor(Math.abs(offsetMin) / 60)).padStart(2, '0')
        const m = String(Math.abs(offsetMin) % 60).padStart(2, '0')
        tzLabel = `${stationTZ} (UTC${sign}${h}:${m})`
      }
      catch {
        // ignore offset formatting errors
      }
      toolbarTzLabel.value = tzLabel
      // keep extraTop/extraRight at defaults (we no longer need extra plot margins)
    }
    catch {
      // ignore
    }
  }

  // Build cloud fraction lookup
  const cloudMap = new Map<number, number>()
  if (cloudKey) {
    const cs = resampledSeries.get(cloudKey)!
    // a share from 0 to 1, whatever unit the cloud cover is in
    cs.x.forEach((d, i) => cloudMap.set(d.getTime(), canon('fraction', cs.y[i] ?? 0) / 100))
  }

  // Build per-day day-band shapes
  const dayShapes: any[] = []
  const days = getCalendarDays(minTime, displayMaxTime, stationTZ)
  if (props.stationCoords && props.stationCoords.latitude != null && props.stationCoords.longitude != null) {
    SunCalc ??= await importChartCode(() => import('suncalc'))
    const lat = props.stationCoords.latitude
    const lon = props.stationCoords.longitude
    for (const day of days) {
      const localDayDt = DateTime.fromMillis(day.getTime(), { zone: stationTZ })
      const localNoon = localDayDt.plus({ hours: 12 }).toJSDate()
      const times: SunTimes = SunCalc.getTimes(localNoon, lat, lon)
      const sunrise = times.sunrise ?? times.sunriseEnd ?? localDayDt.plus({ hours: 4 }).toJSDate()
      const sunset = times.sunset ?? times.sunsetStart ?? localDayDt.plus({ hours: 20 }).toJSDate()
      const middayCf = cloudMap.get(localNoon.getTime()) ?? 0
      const alpha = 0.55 - Math.min(0.35, middayCf * 0.5)
      dayShapes.push({
        type: 'rect',
        xref: 'x',
        yref: 'paper',
        x0: sunrise.toISOString(),
        x1: sunset.toISOString(),
        y0: 0,
        y1: 1,
        fillcolor: isDark.value ? `rgba(250,204,21,${alpha * 0.15})` : `rgba(253,244,180,${alpha})`,
        line: { width: 0 },
        layer: 'below',
      })
    }
  }
  else {
    for (const day of days) {
      const localDayDt = DateTime.fromMillis(day.getTime(), { zone: stationTZ })
      const x0 = localDayDt.plus({ hours: 4 }).toJSDate()
      const x1 = localDayDt.plus({ hours: 20 }).toJSDate()
      dayShapes.push({
        type: 'rect',
        xref: 'x',
        yref: 'paper',
        x0: x0.toISOString(),
        x1: x1.toISOString(),
        y0: 0,
        y1: 1,
        fillcolor: isDark.value ? 'rgba(250,204,21,0.08)' : 'rgba(253,244,180,0.55)',
        line: { width: 0 },
        layer: 'below',
      })
    }
  }

  // Day separators
  const separators: any[] = getMidnights(minTime, displayMaxTime, stationTZ).map(m => ({
    type: 'line',
    xref: 'x',
    yref: 'paper',
    x0: m.toISOString(),
    x1: m.toISOString(),
    y0: 0,
    y1: 1,
    line: { color: isDark.value ? 'rgba(244,244,245,0.08)' : 'rgba(55,65,81,0.08)', width: 1, dash: 'dot' },
  }))

  // "Now" marker
  const nowMs = Date.now()
  if (nowMs > minTime && nowMs < displayMaxTime) {
    separators.push({
      type: 'line',
      xref: 'x',
      yref: 'paper',
      x0: new Date(nowMs).toISOString(),
      x1: new Date(nowMs).toISOString(),
      y0: 0,
      y1: 1,
      line: { color: isDark.value ? 'rgba(251,146,60,0.75)' : 'rgba(234,88,12,0.75)', width: 1.5 },
    })
  }

  // Day names annotations (all date parts computed in station-local timezone)
  const totalDays = Math.max(1, rangeHours / 24)
  const dayWidthPx = plotInnerWidth / totalDays
  for (const day of getCalendarDays(minTime, displayMaxTime, stationTZ)) {
    const localDt = DateTime.fromMillis(day.getTime(), { zone: stationTZ })
    const tenAm = localDt.plus({ hours: 10 }).toJSDate()
    if (tenAm.getTime() < minTime || tenAm.getTime() > displayMaxTime)
      continue
    const dayMonth = formatDayMonth(localDt, formatLanguage.value)
    const isWeekend = localDt.weekday >= 6 // 6=Sat, 7=Sun in Luxon
    // On narrow screens drop the date suffix to prevent overlap; shrink font below 50 px/day.
    const annotFontSize = dayWidthPx < 50 ? 10 : 12
    // The date is 7.4 px per character wide or more: 59 px for the eight characters of "Mo 05.10", which
    // a language that writes the date longer ("Čt 15. 10.") needs more of
    const weekday = weekdayShort(localDt, formatLanguage.value)
    const annotText = dayWidthPx < 7.4 * `${weekday} ${dayMonth}`.length
      ? `<b>${weekday}</b>`
      : `<b>${weekday}</b> ${dayMonth}`
    annotations.push({
      x: tenAm.toISOString(),
      y: 1.06,
      xref: 'x',
      yref: 'paper',
      text: annotText,
      showarrow: false,
      font: { size: annotFontSize, color: isWeekend ? seriesLabelColor('red', isDark.value) : theme.value.text },
      xanchor: 'center',
      yanchor: 'bottom',
    })
  }

  // Traces
  const traces: any[] = []

  // 1. Temperature & Dew Point
  // the axis holds the freezing point, which Plotly's zero line is only in degrees Celsius
  const freezing = shown('temperature', 0)
  let tempMinY = freezing
  let tempMaxY = shown('temperature', 25)
  if (tempKey && visiblePanels.value.temp) {
    const s = resampledSeries.get(tempKey)!
    tempMinY = Math.min(freezing, ...s.y)
    tempMaxY = Math.max(...s.y)
    const xs = s.x.map(d => d.toISOString())

    // The maximum and minimum are held across the hours each covers, not resampled to a line between
    // their few stamps, which let the curve out of the band (GH-2647)
    const stepMs = resampleCadenceMs(minTime, displayMaxTime)
    const extremeSteps = (key: string | undefined) => {
      const raw = key ? series.get(key) : undefined
      return raw ? extremeWindowSteps(raw.x, raw.y, extremeWindowHours(key!) * 3_600_000, minTime, displayMaxTime, stepMs) : null
    }
    const sTx = extremeSteps(txKey)
    const sTn = extremeSteps(tnKey)
    const hasTxTn = !!(sTx?.x.length && sTn?.x.length)

    const dewLookup = new Map<string, number>()
    if (dewKey && resampledSeries.has(dewKey)) {
      const ds = resampledSeries.get(dewKey)!
      ds.x.forEach((d, i) => dewLookup.set(d.toISOString(), ds.y[i]!))
    }
    else if (humidityKey && resampledSeries.has(humidityKey)) {
      const hs = resampledSeries.get(humidityKey)!
      for (let i = 0; i < xs.length; i++) {
        const tMs = new Date(xs[i]!).getTime()
        const rh = interpSeries(hs.x, hs.y, tMs)
        const reading = s.y[i]
        if (rh !== null && reading !== undefined && !Number.isNaN(reading)) {
          // Magnus' formula, in degrees Celsius and percent, and the dew point back in the unit of the chart
          const T = canon('temperature', reading)
          const rhPct = canon('fraction', rh)
          const a = 17.27
          const b = 237.7
          const alpha = (a * T) / (b + T) + Math.log(rhPct / 100)
          const td = (b * alpha) / (a - alpha)
          dewLookup.set(xs[i]!, shown('temperature', td))
        }
      }
    }

    traces.push({
      name: hasTxTn ? named('meteogram.chart.seriesMeanTemp', 'temperature') : named('meteogram.chart.seriesTemperature', 'temperature'),
      x: xs,
      y: s.y,
      type: 'scatter',
      mode: 'lines',
      line: { color: '#ef4444', width: 2, shape: 'spline' },
      fill: 'tozeroy',
      fillcolor: isDark.value ? 'rgba(239,68,68,0.02)' : 'rgba(239,68,68,0.04)',
      yaxis: 'y3',
      hovertemplate: hasTxTn
        ? `<b>${t('meteogram.chart.hoverMeanTemp')}</b>${t('common.colon')} ${hoverUnit('temperature')}<extra></extra>`
        : `<b>${t('meteogram.chart.hoverTemperature')}</b>${t('common.colon')} ${hoverUnit('temperature')}<extra></extra>`,
    })

    if (hasTxTn && sTx && sTn) {
      traces.push({
        name: named('meteogram.chart.seriesMaxTemp', 'temperature'),
        x: sTx.x.map(d => d.toISOString()),
        y: sTx.y,
        type: 'scatter',
        mode: 'lines',
        line: { color: isDark.value ? '#fca5a5' : '#b91c1c', width: 1.5, dash: 'dash', shape: 'vh' },
        yaxis: 'y3',
        hovertemplate: `<b>${t('meteogram.chart.hoverMaxTemp')}</b>${t('common.colon')} ${hoverUnit('temperature')}<extra></extra>`,
        showlegend: false,
      })
      traces.push({
        name: named('meteogram.chart.seriesMinTemp', 'temperature'),
        x: sTn.x.map(d => d.toISOString()),
        y: sTn.y,
        type: 'scatter',
        mode: 'lines',
        line: { color: isDark.value ? '#93c5fd' : '#1d4ed8', width: 1.5, dash: 'dash', shape: 'vh' },
        yaxis: 'y3',
        hovertemplate: `<b>${t('meteogram.chart.hoverMinTemp')}</b>${t('common.colon')} ${hoverUnit('temperature')}<extra></extra>`,
        showlegend: false,
      })
      tempMinY = Math.min(tempMinY, ...sTn.y.filter((v): v is number => v !== null))
      tempMaxY = Math.max(tempMaxY, ...sTx.y.filter((v): v is number => v !== null))
    }

    if (dewKey && resampledSeries.has(dewKey)) {
      const ds = resampledSeries.get(dewKey)!
      const dxs = ds.x.map(d => d.toISOString())
      traces.push({
        name: t('meteogram.chart.seriesDewPoint'),
        x: dxs,
        y: ds.y,
        type: 'scatter',
        mode: 'lines',
        line: { color: '#a855f7', width: 1.6, shape: 'spline' },
        yaxis: 'y3',
        hovertemplate: `<b>${t('meteogram.chart.hoverDewPoint')}</b>${t('common.colon')} ${hoverUnit('temperature')}<extra></extra>`,
        showlegend: false,
      })
      tempMinY = Math.min(tempMinY, ...ds.y)
      tempMaxY = Math.max(tempMaxY, ...ds.y)
    }
    else if (humidityKey && resampledSeries.has(humidityKey)) {
      const hs = resampledSeries.get(humidityKey)!
      const dewXs: string[] = []
      const dewYs: number[] = []
      for (let i = 0; i < xs.length; i++) {
        const tIso = xs[i]!
        const tMs = new Date(tIso).getTime()
        const rh = interpSeries(hs.x, hs.y, tMs)
        if (rh === null || rh === undefined)
          continue
        const rhPct = canon('fraction', rh)
        const a = 17.27
        const b = 237.7
        const reading = s.y[i] ?? Number.NaN
        if (Number.isNaN(reading) || rhPct <= 0)
          continue
        const T = canon('temperature', reading)
        const alpha = (a * T) / (b + T) + Math.log(rhPct / 100)
        const td = (b * alpha) / (a - alpha)
        dewXs.push(tIso)
        dewYs.push(shown('temperature', td))
      }
      if (dewXs.length) {
        traces.push({
          name: t('meteogram.chart.seriesDewPoint'),
          x: dewXs,
          y: dewYs,
          type: 'scatter',
          mode: 'lines',
          line: { color: '#a855f7', width: 1.6, shape: 'spline' },
          yaxis: 'y3',
          hovertemplate: `<b>${t('meteogram.chart.hoverDewPoint')}</b>${t('common.colon')} ${hoverUnit('temperature')}<extra></extra>`,
          showlegend: false,
        })
        tempMinY = Math.min(tempMinY, ...dewYs)
        tempMaxY = Math.max(tempMaxY, ...dewYs)
      }
    }
  }

  // 2. Precipitation
  if (precipKey && visiblePanels.value.precip) {
    const s = resampledSeries.get(precipKey)!
    const rainYs: number[] = []
    const snowYs: number[] = []
    const mixedYs: number[] = []
    const pxs = s.x.map(d => d.toISOString())
    for (let i = 0; i < pxs.length; i++) {
      const tIso = pxs[i]!
      const pVal = s.y[i] ?? 0
      let isSnow = false
      let isMixed = false
      if (tempKey && resampledSeries.has(tempKey)) {
        const tSeries = resampledSeries.get(tempKey)!
        const reading = interpSeries(tSeries.x, tSeries.y, new Date(tIso).getTime())
        if (reading !== null && !Number.isNaN(reading)) {
          // the wet bulb is worked out in degrees Celsius and percent, and judged against 0.5 and 2 degrees Celsius,
          // whatever the units the chart is drawn in (GH-3980)
          const tval = canon('temperature', reading)
          let tw = tval
          if (humidityKey && resampledSeries.has(humidityKey)) {
            const hSeries = resampledSeries.get(humidityKey)!
            const rh = interpSeries(hSeries.x, hSeries.y, new Date(tIso).getTime())
            if (rh !== null)
              tw = wetBulbApprox(tval, canon('fraction', rh))
          }
          if (tw <= 0.5)
            isSnow = true
          else if (tw <= 2.0)
            isMixed = true
          else isSnow = false
        }
      }
      if (isSnow) {
        snowYs.push(pVal)
        rainYs.push(0)
        mixedYs.push(0)
      }
      else if (isMixed) {
        mixedYs.push(pVal)
        rainYs.push(0)
        snowYs.push(0)
      }
      else {
        rainYs.push(pVal)
        snowYs.push(0)
        mixedYs.push(0)
      }
    }

    traces.push({ name: t('meteogram.chart.seriesRain'), x: pxs, y: rainYs, type: 'bar', marker: { color: '#3b82f6' }, yaxis: 'y2', hovertemplate: `<b>${t('meteogram.chart.hoverRain')}</b><br>${hoverUnit('precipitation')}<extra></extra>`, visible: true })
    traces.push({ name: t('meteogram.chart.seriesMixed'), x: pxs, y: mixedYs, type: 'bar', marker: { color: '#0ea5e9' }, yaxis: 'y2', hovertemplate: `<b>${t('meteogram.chart.hoverMixed')}</b><br>${hoverUnit('precipitation')}<extra></extra>`, visible: true })
    traces.push({ name: t('meteogram.chart.seriesSnow'), x: pxs, y: snowYs, type: 'bar', marker: { color: isDark.value ? '#9ca3af' : '#cbd5e1' }, yaxis: 'y2', hovertemplate: `<b>${t('meteogram.chart.hoverSnow')}</b><br>${hoverUnit('precipitation')}<extra></extra>`, visible: true })
  }

  // 3. Pressure
  let pressureMin = shown('pressure', 1000)
  let pressureMax = shown('pressure', 1020)
  if (pressureKey && visiblePanels.value.pressure) {
    const ps = resampledSeries.get(pressureKey)!
    const pxs = ps.x.map(d => d.toISOString())
    traces.push({
      name: named('meteogram.chart.seriesPressure', 'pressure'),
      x: pxs,
      y: ps.y,
      type: 'scatter',
      mode: 'lines',
      line: { color: '#84cc16', width: 1.6, shape: 'spline' },
      fill: 'tozeroy',
      fillcolor: isDark.value ? 'rgba(132,204,22,0.02)' : 'rgba(132,204,22,0.04)',
      yaxis: 'y4',
      hovertemplate: `<b>${t('meteogram.chart.hoverPressure')}</b><br>${hoverUnit('pressure')}<extra></extra>`,
    })
    pressureMin = Math.min(...ps.y)
    pressureMax = Math.max(...ps.y)
  }

  // 4. Wind & Gusts
  let windMaxY = shown('speed', 10)
  if (windKey && visiblePanels.value.wind) {
    const s = resampledSeries.get(windKey)!
    windMaxY = Math.max(...s.y, shown('speed', 5))

    const gustSeries = (gustKey && resampledSeries.has(gustKey)) ? resampledSeries.get(gustKey)! : undefined
    if (gustSeries) {
      windMaxY = Math.max(windMaxY, ...gustSeries.y)
    }

    // Build per-timestep direction lookup for wind speed hover
    const dirByMs = new Map<number, number>()
    if (windDirKey) {
      const dirS = resampledSeries.get(windDirKey)!
      dirS.x.forEach((d, i) => dirByMs.set(d.getTime(), dirS.y[i]!))
    }
    const windSpeedCustom = s.x.map(d => dirByMs.get(d.getTime()) ?? null)
    const hasDir = windSpeedCustom.some(v => v !== null)

    traces.push({
      name: named('meteogram.chart.seriesWind', 'speed'),
      x: s.x.map(d => d.toISOString()),
      y: s.y,
      customdata: windSpeedCustom,
      type: 'scatter',
      mode: 'lines',
      line: { color: '#06b6d4', width: 2, shape: 'spline' },
      fill: 'tozeroy',
      fillcolor: isDark.value ? 'rgba(6,182,212,0.04)' : 'rgba(6,182,212,0.08)',
      yaxis: 'y',
      hovertemplate: hasDir
        ? `<b>${t('meteogram.chart.hoverWind')}</b> ${hoverUnit('speed')} → ${withUnit(`%{customdata:.${digits('angle')}f}`, unitOf('angle'))}<extra></extra>`
        : `<b>${t('meteogram.chart.hoverWindSpeed')}</b> ${hoverUnit('speed')}<extra></extra>`,
    })

    if (gustSeries) {
      traces.push({
        name: named('meteogram.chart.seriesWindGust', 'speed'),
        x: gustSeries.x.map(d => d.toISOString()),
        y: gustSeries.y,
        type: 'scatter',
        mode: 'lines',
        line: { color: '#06b6d4', width: 1.6, dash: 'dash', shape: 'spline' },
        yaxis: 'y',
        hovertemplate: `<b>${t('meteogram.chart.hoverWindGust')}</b> ${hoverUnit('speed')}<extra></extra>`,
      })
    }

    if (windDirKey) {
      const dirS = resampledSeries.get(windDirKey)!
      const dirMap = new Map<number, number>()
      // the arrow points from the direction in degrees, whatever unit the direction is in
      dirS.x.forEach((d, i) => dirMap.set(d.getTime(), canon('angle', dirS.y[i]!)))

      const arrowX: string[] = []
      const arrowText: string[] = []
      s.x.forEach((date, i) => {
        if (i % 3 !== 0)
          return
        const dir = dirMap.get(date.getTime())
        if (dir !== undefined) {
          arrowX.push(date.toISOString())
          arrowText.push(windArrow(dir))
        }
      })

      traces.push({
        name: `${t('meteogram.chart.seriesDirection')} ${unitName('angle')}`,
        x: arrowX,
        y: Array.from({ length: arrowX.length }).fill(windMaxY * 1.36),
        text: arrowText,
        type: 'scatter',
        mode: 'text',
        textfont: { size: 13, color: isDark.value ? 'rgba(255,255,255,0.7)' : 'rgba(15,23,42,0.85)' },
        hoverinfo: 'skip',
        yaxis: 'y',
        showlegend: false,
      })
    }
  }

  // 5. Cloud Layers (Low, Mid, High & Total)
  if (cloudKey && visiblePanels.value.cloud) {
    // Overlapping cloud layers by altitude
    if (cloudHighKey && resampledSeries.has(cloudHighKey)) {
      const s = resampledSeries.get(cloudHighKey)!
      traces.push({
        name: named('meteogram.chart.seriesHighClouds', 'fraction'),
        x: s.x.map(d => d.toISOString()),
        y: s.y,
        type: 'scatter',
        mode: 'lines',
        line: { color: isDark.value ? '#64748b' : '#cbd5e1', width: 1, shape: 'spline' },
        fill: 'tozeroy',
        fillcolor: isDark.value ? 'rgba(148,163,184,0.1)' : 'rgba(203,213,225,0.15)',
        yaxis: 'y5',
        hovertemplate: `<b>${t('meteogram.chart.hoverHighClouds')}</b><br>${hoverUnit('fraction')}<extra></extra>`,
      })
    }

    if (cloudMidKey && resampledSeries.has(cloudMidKey)) {
      const s = resampledSeries.get(cloudMidKey)!
      traces.push({
        name: named('meteogram.chart.seriesMidClouds', 'fraction'),
        x: s.x.map(d => d.toISOString()),
        y: s.y,
        type: 'scatter',
        mode: 'lines',
        line: { color: isDark.value ? '#475569' : '#94a3b8', width: 1, shape: 'spline' },
        fill: 'tozeroy',
        fillcolor: isDark.value ? 'rgba(100,116,139,0.15)' : 'rgba(148,163,184,0.22)',
        yaxis: 'y5',
        hovertemplate: `<b>${t('meteogram.chart.hoverMidClouds')}</b><br>${hoverUnit('fraction')}<extra></extra>`,
      })
    }

    if (cloudLowKey && resampledSeries.has(cloudLowKey)) {
      const s = resampledSeries.get(cloudLowKey)!
      traces.push({
        name: named('meteogram.chart.seriesLowClouds', 'fraction'),
        x: s.x.map(d => d.toISOString()),
        y: s.y,
        type: 'scatter',
        mode: 'lines',
        line: { color: isDark.value ? '#334155' : '#64748b', width: 1, shape: 'spline' },
        fill: 'tozeroy',
        fillcolor: isDark.value ? 'rgba(71,85,105,0.22)' : 'rgba(100,116,139,0.3)',
        yaxis: 'y5',
        hovertemplate: `<b>${t('meteogram.chart.hoverLowClouds')}</b><br>${hoverUnit('fraction')}<extra></extra>`,
      })
    }

    // Total Cloud Cover line on top
    const s = resampledSeries.get(cloudKey)!
    traces.push({
      name: named('meteogram.chart.seriesTotalCloud', 'fraction'),
      x: s.x.map(d => d.toISOString()),
      y: s.y,
      type: 'scatter',
      mode: 'lines',
      line: { color: isDark.value ? '#e4e4e7' : '#334155', width: 2, shape: 'spline' },
      yaxis: 'y5',
      hovertemplate: `<b>${t('meteogram.chart.hoverTotalCloud')}</b><br>${hoverUnit('fraction')}<extra></extra>`,
    })
  }

  // Panel geometry calculations
  const gap = compact.value ? 0.006 : 0.01
  const panelOrder = [
    { id: 'wind', present: !!windKey && visiblePanels.value.wind },
    { id: 'precip', present: !!precipKey && visiblePanels.value.precip },
    { id: 'cloud', present: !!cloudKey && !compact.value && visiblePanels.value.cloud },
    { id: 'temp', present: !!tempKey && visiblePanels.value.temp },
    { id: 'pressure', present: !!pressureKey && visiblePanels.value.pressure },
  ]

  const panels = panelOrder.filter(p => p.present)
  const nPanels = Math.max(1, panels.length)
  const totalGap = gap * Math.max(0, nPanels - 1)
  const panelHeight = (1 - totalGap) / nPanels

  const domains: Record<string, [number, number]> = {}
  let currentTop = 1.0
  for (const p of panels) {
    const top = currentTop
    const bottom = top - panelHeight
    domains[p.id] = [bottom, top]
    currentTop = bottom - gap
  }

  // Dark-on-light or light-on-dark tokens
  // washes of the text colour for the hairlines; the tick labels are the muted text colour itself, as
  // a wash of 65 % of the text colour is 3.9:1 on white
  const W = (a: number) => withAlpha(theme.value.text, a)
  const GRID = W(0.08)
  const TICK = theme.value.textMuted
  // the colour of the text that names a series: its hue, dark enough to read on the paper (GH-3618)
  const LABEL = (series: SeriesLabel) => seriesLabelColor(series, isDark.value)

  // Panel divider lines
  const dividers: any[] = []
  const panelIds = panels.map(p => p.id)
  for (let i = 0; i < panelIds.length - 1; i++) {
    const id = panelIds[i]!
    const bottom = domains[id] ? domains[id][0] : 0
    const width = compact.value ? 0.8 : 1
    dividers.push({ type: 'line', xref: 'paper', yref: 'paper', x0: 0, x1: 1, y0: bottom, y1: bottom, line: { color: W(0.18), width } })
  }

  // Compute default axis ranges per panel
  const axisRanges: Record<string, [number, number]> = {}
  axisRanges.wind = [0, windMaxY * 1.60]

  if (precipKey && resampledSeries.has(precipKey)) {
    const ps = resampledSeries.get(precipKey)!
    const pMax = Math.max(...ps.y.map(v => (v ?? 0)))
    axisRanges.precip = [0, Math.max(shown('precipitation', 1), pMax * 1.15)]
  }
  else {
    axisRanges.precip = [0, shown('precipitation', 1)]
  }

  // the cloud cover's axis is the whole of the scale: 0 to 100 %, 0 to 1, 0 to 8 oktas
  const cloudTop = shown('fraction', 100)
  // a degree and a hectopascal, in the unit of the chart: a degree is 1.8 degrees Fahrenheit, a hectopascal 100 pascals
  const degree = stretch('temperature', 1)
  const hectopascal = stretch('pressure', 1)
  axisRanges.cloud = [0, cloudTop]
  axisRanges.temp = [tempMinY - degree, tempMaxY + 3 * degree]
  axisRanges.pressure = [pressureMin - 2 * hectopascal, pressureMax + 2 * hectopascal]

  const originalRanges: Record<string, [number, number]> = {
    wind: [0, windMaxY * 1.60],
    precip: axisRanges.precip,
    cloud: [0, cloudTop],
    temp: [tempMinY - degree, tempMaxY + 3 * degree],
    pressure: [pressureMin - 2 * hectopascal, pressureMax + 2 * hectopascal],
  }

  const nticksMap: Record<string, number> = { wind: 4, precip: 3, cloud: 3, temp: 4, pressure: 3 }
  const axisTickVals: Record<string, number[]> = {}

  function niceNum(range: number, round: boolean) {
    if (range <= 0)
      return 1
    const exp = Math.floor(Math.log10(range))
    const f = range / 10 ** exp
    let nf = 1
    if (round) {
      if (f < 1.5)
        nf = 1
      else if (f < 3)
        nf = 2
      else if (f < 7)
        nf = 5
      else nf = 10
    }
    else {
      if (f <= 1)
        nf = 1
      else if (f <= 2)
        nf = 2
      else if (f <= 5)
        nf = 5
      else nf = 10
    }
    return nf * 10 ** exp
  }

  function niceTickSpacing(range: number, n: number) {
    if (n <= 1)
      return Math.max(1, range)
    const raw = range / Math.max(1, n - 1)
    return niceNum(raw, true)
  }

  for (const k of Object.keys(nticksMap)) {
    const key = k as keyof typeof nticksMap
    const rng = originalRanges[key as string] || [0, 1]
    const lo = rng[0]
    const hi = rng[1]
    if (!(hi > lo)) {
      axisTickVals[key] = [lo]
      continue
    }
    const n = nticksMap[key]
    if (n === undefined)
      continue
    const adjustedN = compact.value ? Math.max(2, Math.round(n * 0.8)) : n
    const step = niceTickSpacing(hi - lo, adjustedN)
    const niceHi = Math.ceil(hi / step) * step
    const ticks: number[] = []
    const count = Math.max(1, Math.ceil((niceHi - lo) / step) + 1)
    for (let i = 0; i < count; i++) ticks.push(Number((lo + i * step).toFixed(6)))
    axisTickVals[key] = ticks
  }

  for (let i = 0; i < panels.length - 1; i++) {
    const belowId = panels[i + 1]!.id
    const belowTicks = axisTickVals[belowId] ?? []
    if (belowTicks.length > 0) {
      belowTicks.pop()
      axisTickVals[belowId] = belowTicks
    }
  }

  for (const k of Object.keys(originalRanges)) {
    const key = k as keyof typeof originalRanges
    const rng = originalRanges[key as string]
    if (!rng)
      continue
    const lo = rng[0]
    const hi = rng[1]
    if (!(hi > lo))
      continue
    const ticks = axisTickVals[key] ?? []
    if (ticks.length === 0)
      continue
    const step = niceTickSpacing(hi - lo, Math.max(2, ticks.length))
    const niceHi = Math.ceil(hi / step) * step
    const newCount = Math.max(1, Math.ceil((niceHi - lo) / step) + 1)
    const newTicks: number[] = []
    for (let i = 0; i < newCount; i++) newTicks.push(Number((lo + i * step).toFixed(6)))
    axisTickVals[key] = newTicks
  }

  // Filter traces dynamically depending on panel visibility
  const axisToPanel: Record<string, string> = { y: 'wind', y2: 'precip', y3: 'temp', y4: 'pressure', y5: 'cloud' }
  const activeTraces = traces.filter((tr) => {
    const yaxisName = tr.yaxis || 'y'
    const panelId = axisToPanel[yaxisName]
    return !panelId || visiblePanels.value[panelId as keyof typeof visiblePanels.value] !== false
  })

  // The axis titles are written along their panel (88 px of a 540 px chart), which a long one of 12 px does not
  // fit (German "Niederschlag mm"): such a title is broken into two lines, and the left margin grows by the second
  const titleFont = compact.value ? 10 : TICK_FONT
  const plotHeight = (chartRef.value?.clientHeight ?? 540) - ((compact.value ? 44 : 72) + extraTop) - (compact.value ? 4 : 8)
  const axisTitleTexts = {
    wind: named('meteogram.chart.axisWind', 'speed'),
    precip: named('meteogram.chart.axisPrecip', 'precipitation'),
    cloud: named('meteogram.chart.axisCloud', 'fraction'),
    temp: named('meteogram.chart.axisTemp', 'temperature'),
    pressure: named('meteogram.chart.axisPressure', 'pressure'),
  }
  const axisTitles = Object.fromEntries(Object.entries(axisTitleTexts).map(([key, title]) => {
    const domain = domains[key]
    return [key, fitAxisTitle(title, domain ? (domain[1] - domain[0]) * plotHeight : Infinity, titleFont)]
  })) as Record<keyof typeof axisTitleTexts, ReturnType<typeof fitAxisTitle>>
  const wrapsTitle = Object.values(axisTitles).some(title => title.lines === 2)

  // the freezing point of the temperature panel where Plotly's zero line is not it
  const freezingLine: any[] = freezing !== 0 && domains.temp
    ? [{ type: 'line', xref: 'paper', yref: 'y3', x0: 0, x1: 1, y0: freezing, y1: freezing, line: { color: theme.value.zeroline, width: 1 }, layer: 'below' }]
    : []

  // Layout
  const layout: any = {
    autosize: true,
    // the hover texts and the axes write the language's decimal separator, as Plotly writes a point otherwise
    separators: plotlySeparators(locale.value),
    margin: { l: MARGIN_LEFT + (wrapsTitle ? titleFont + 2 : 0), r: MARGIN_RIGHT + extraRight, t: (compact.value ? 44 : 72) + extraTop, b: compact.value ? 4 : 8 },
    font: { family: '"Inter", system-ui, sans-serif', size: 11 },
    hovermode: 'x unified',
    hoverlabel: { font: { family: '"Inter", system-ui, sans-serif' } },
    bargap: 0.05,
    barmode: 'stack',
    shapes: [...dayShapes, ...separators, ...dividers, ...freezingLine],
    annotations,
    showlegend: false,

    xaxis: {
      type: 'date',
      domain: [0, 1],
      anchor: 'free',
      side: 'top',
      position: 1.0,
      showgrid: false,
      linecolor: 'rgba(0,0,0,0)',
      tickformat: '%H',
      hoverformat: plotlyHoverFormat(formatLanguage.value),
      dtick: 6 * 3_600_000,
      tickfont: { size: TICK_FONT, color: TICK },
      tickcolor: W(0.25),
      range: [new Date(minTime).toISOString(), new Date(displayMaxTime).toISOString()],
      ...(customTickVals ? { tickvals: customTickVals, ticktext: customTickText } : {}),
    },

    yaxis: {
      visible: !!domains.wind,
      domain: domains.wind ?? [0, 0],
      title: { text: axisTitles.wind.text, font: { size: titleFont, color: LABEL('cyan') }, standoff: 2 },
      gridcolor: GRID,
      linecolor: 'rgba(0,0,0,0)',
      zeroline: false,
      rangemode: 'tozero',
      range: originalRanges.wind,
      tickvals: axisTickVals.wind ?? undefined,
      tickfont: { size: TICK_FONT, color: LABEL('cyan') },
      tickcolor: 'rgba(6,182,212,0.45)',
      nticks: 4,
      fixedrange: true,
    },

    yaxis2: {
      visible: !!domains.precip,
      domain: domains.precip ?? [0, 0],
      title: { text: axisTitles.precip.text, font: { size: titleFont, color: LABEL('blue') }, standoff: 2 },
      gridcolor: GRID,
      linecolor: 'rgba(0,0,0,0)',
      zeroline: false,
      rangemode: 'tozero',
      range: originalRanges.precip,
      tickvals: axisTickVals.precip ?? undefined,
      tickfont: { size: TICK_FONT, color: LABEL('blue') },
      tickcolor: 'rgba(37,99,235,0.45)',
      nticks: 3,
      fixedrange: true,
    },

    yaxis5: {
      visible: !!domains.cloud,
      domain: domains.cloud ?? [0, 0],
      title: { text: axisTitles.cloud.text, font: { size: titleFont, color: theme.value.textMuted }, standoff: 2 },
      gridcolor: GRID,
      linecolor: 'rgba(0,0,0,0)',
      zeroline: false,
      range: originalRanges.cloud,
      tickvals: axisTickVals.cloud ?? undefined,
      tickfont: { size: TICK_FONT, color: theme.value.textMuted },
      tickcolor: 'rgba(148,163,184,0.45)',
      nticks: 3,
      fixedrange: true,
    },

    yaxis3: {
      visible: !!domains.temp,
      domain: domains.temp ?? [0, 0],
      title: { text: axisTitles.temp.text, font: { size: titleFont, color: LABEL('red') }, standoff: 2 },
      gridcolor: GRID,
      linecolor: 'rgba(0,0,0,0)',
      // Plotly's zero line is the freezing point in degrees Celsius only: in another unit the line is drawn at the
      // freezing point, as a shape (and the zero of Kelvin or of Fahrenheit is no line to draw)
      zeroline: freezing === 0,
      zerolinecolor: theme.value.zeroline,
      zerolinewidth: 1,
      range: originalRanges.temp,
      tickvals: axisTickVals.temp ?? undefined,
      tickfont: { size: TICK_FONT, color: LABEL('red') },
      tickcolor: 'rgba(239,68,68,0.45)',
      fixedrange: true,
    },

    yaxis4: {
      visible: !!domains.pressure,
      domain: domains.pressure ?? [0, 0],
      title: { text: axisTitles.pressure.text, font: { size: titleFont, color: LABEL('lime') }, standoff: 2 },
      gridcolor: GRID,
      linecolor: 'rgba(0,0,0,0)',
      zeroline: false,
      rangemode: 'normal',
      range: originalRanges.pressure,
      tickvals: axisTickVals.pressure ?? undefined,
      tickfont: { size: TICK_FONT, color: LABEL('lime') },
      tickcolor: 'rgba(132,204,22,0.45)',
      nticks: 3,
      fixedrange: true,
    },
  }

  const isTouchDevice = typeof window !== 'undefined' && window.matchMedia('(hover: none) and (pointer: coarse)').matches
  // the weekday of the hover heading is written by Plotly, which knows English only unless it is given the language
  const config = { responsive: true, displayModeBar: false, ...(await plotlyLocaleConfig(locale.value, formatLanguage.value)), ...(isTouchDevice ? { dragmode: 'pan', scrollZoom: false } : {}) }

  if (chartRef.value) {
    try {
      cleanupPlotlyOverlayHandlers()
    }
    catch {}
    try {
      cleanupOverlay()
    }
    catch {}
    // the time range the chart shows now, if it is a redraw of the same chart in other colours
    const kept = keepZoom ? drawnRanges(chartRef.value).xaxis : undefined
    // the theme it is drawn in is taken before the drawing, which a switch of the scheme can come in the middle of
    const drawnIn = theme.value
    drawnTheme = drawnIn
    Plotly.purge(chartRef.value)
    await Plotly.newPlot(chartRef.value, activeTraces, themedLayout(layout, drawnIn), config)
    // said at once, before anything after it can fail: the chart is drawn in these colours whatever follows
    markChartScheme(chartRef.value, drawnIn)
    // drawn in the range of the layout, which is what the chart's reset goes back to, and then moved to the one it was in
    if (kept)
      await Plotly.relayout(chartRef.value, { 'xaxis.range': kept.range })

    // Setup overlay drawing of wind barbs using a canvas overlay
    if (typeof window !== 'undefined' && windKey && chartRef.value && visiblePanels.value.wind) {
      const arrowInfos: { timeMs: number, dir: number, speed: number, knots: number }[] = []
      const s = resampledSeries.get(windKey)!
      const dirSeries = windDirKey ? resampledSeries.get(windDirKey) : undefined
      const subsample = compact.value ? 2 : 3
      for (let i = 0; i < s.x.length; i++) {
        if (i % subsample !== 0)
          continue
        const timeMs = s.x[i]!.getTime()
        const speed = s.y[i] ?? 0
        // the barb points from the direction in degrees and has the knots of the speed in metres per second
        const dir = canon('angle', dirSeries ? (dirSeries.y[i] ?? dirSeries.y[0] ?? 0) : 0)
        arrowInfos.push({ timeMs, dir, speed, knots: (canon('speed', speed) * 3600) / 1852 })
      }

      const gustSeriesY = (gustKey ? resampledSeries.get(gustKey)?.y : undefined) ?? [0]
      const axisMax = Math.max(shown('speed', 1), ...((resampledSeries.get(windKey)?.y) ?? [shown('speed', 10)]), ...gustSeriesY)
      const axisDomain = domains.wind ? domains.wind : [0, 0]
      const getParams = () => ({ arrowInfos, minTime, maxTime: displayMaxTime, layoutObj: layout, axisRange: [0, axisMax] as [number, number], axisDomain: axisDomain as [number, number] })
      attachOverlayListeners(getParams)
    }
  }
}

watch(
  () => props.values,
  () => {
    requestRender(false)
  },
  { immediate: true, deep: true },
)
watch(
  view,
  () => {
    requestRender(false)
  },
)
watch(
  theme,
  () => {
    requestRender(true)
  },
)
watch(
  locale,
  () => {
    requestRender(false)
  },
)
watch(
  visiblePanels,
  () => {
    requestRender(false)
  },
  { deep: true },
)
watch(
  horizonHours,
  () => {
    requestRender(false)
  },
)
</script>

<template>
  <div>
    <UEmpty
      v-if="!values || values.length === 0"
      icon="i-ph-cloud-slash"
      :title="t('meteogram.chart.noData')"
    />

    <div v-if="values && values.length > 0" class="space-y-5">
      <!-- Premium Overhauled Filter / Controls Toolbar -->
      <div v-if="!widget" class="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-gray-50/70 dark:bg-gray-800/40 p-3.5 rounded-xl border border-gray-100 dark:border-gray-800 shadow-sm">
        <!-- Left group: panel toggles + horizon selector (wraps as a unit on narrow viewports) -->
        <div v-if="!compact" class="flex flex-wrap items-center gap-2 min-w-0">
          <!-- Interactive Panel Selectors -->
          <div class="flex items-center gap-1">
            <span class="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-widest mr-1 select-none">{{ t('meteogram.chart.panels') }}</span>

            <!-- the colours are those of the series' labels (SERIES_LABEL, WCAG 1.4.11 and 1.4.3: tests/unit/button-contrast.test.ts), not the series' own -->
            <button
              v-for="toggle in panelToggles"
              :key="toggle.panel"
              type="button"
              :title="t(toggle.title)"
              :aria-label="t(toggle.title)"
              :data-panel="toggle.panel"
              :aria-pressed="visiblePanels[toggle.panel]"
              class="inline-flex items-center p-1.5 rounded-full border transition-all duration-200 cursor-pointer select-none active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none"
              :class="visiblePanels[toggle.panel]
                ? ''
                : 'bg-white/40 dark:bg-gray-900/40 border-gray-200/80 dark:border-gray-800/80 text-gray-500 dark:text-gray-400 hover:bg-white dark:hover:bg-gray-900 hover:text-gray-700 dark:hover:text-gray-200 hover:border-gray-300 dark:hover:border-gray-700'"
              :style="visiblePanels[toggle.panel] ? activeToggleStyle(toggle.series) : undefined"
              :disabled="toggle.panel === 'cloud' && compact"
              @click="visiblePanels[toggle.panel] = !visiblePanels[toggle.panel]"
            >
              <UIcon :name="visiblePanels[toggle.panel] ? toggle.iconOn : toggle.icon" class="w-3.5 h-3.5" />
            </button>
          </div>

          <!-- Forecast Horizon Selector -->
          <div class="flex items-center bg-gray-100 dark:bg-gray-800/70 rounded-lg p-0.5 gap-0.5">
            <button
              v-for="opt in horizonOptions"
              :key="String(opt.value)"
              type="button"
              class="text-xs px-2.5 py-1 rounded-md transition-all duration-150 select-none cursor-pointer"
              :class="horizonHours === opt.value
                ? 'bg-white dark:bg-gray-700 shadow-sm text-gray-900 dark:text-white font-semibold'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-300'"
              @click="horizonHours = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <!-- View Controls & Zoom Reset: the view first on a narrow screen, where the toolbar stacks -->
        <div class="flex items-center gap-2 md:ml-auto shrink-0 order-first md:order-last">
          <UButton
            v-if="view === 'chart'"
            icon="i-ph-arrow-counter-clockwise"
            size="sm"
            variant="outline"
            color="neutral"
            :title="t('meteogram.chart.resetZoom')"
            :aria-label="t('meteogram.chart.resetZoom')"
            class="shrink-0"
            @click="resetChart"
          />
          <SegmentedControl
            :model-value="view"
            :options="viewOptions"
            :label="t('meteogram.chart.viewLabel')"
            @update:model-value="chooseView"
          />
        </div>
      </div>

      <!-- Summary stats: same order as the panel toggles (temp/wind/precip/cloud/pressure) -->
      <div v-if="summaryStats && !widget" class="flex flex-wrap gap-x-5 gap-y-2 px-1 text-sm">
        <div v-if="summaryStats.temp" class="flex items-center gap-1.5">
          <UIcon name="i-ph-thermometer" class="w-4 h-4 shrink-0" data-summary-icon="temp" :style="{ color: seriesLabelColor('red', isDark) }" />
          <span class="text-blue-600 dark:text-blue-400 font-semibold">{{ summaryStats.temp.min }}</span>
          <span class="text-gray-500 dark:text-gray-400">/</span>
          <span class="text-red-600 dark:text-red-400 font-semibold">{{ summaryStats.temp.max }}</span>
        </div>
        <div class="flex items-center gap-1.5">
          <UIcon name="i-ph-wind" class="w-4 h-4 shrink-0" data-summary-icon="wind" :style="{ color: seriesLabelColor('cyan', isDark) }" />
          <span class="font-semibold text-gray-800 dark:text-gray-100">{{ summaryStats.gust.value }}</span>
          <span class="text-gray-500 dark:text-gray-400 text-xs">{{ summaryStats.gust.unit }}</span>
        </div>
        <div class="flex items-center gap-1.5">
          <UIcon name="i-ph-cloud-rain" class="w-4 h-4 shrink-0" data-summary-icon="precip" :style="{ color: seriesLabelColor('blue', isDark) }" />
          <span class="font-semibold text-gray-800 dark:text-gray-100">{{ summaryStats.precip.value }}</span>
          <span class="text-gray-500 dark:text-gray-400 text-xs">{{ summaryStats.precip.unit }}</span>
        </div>
        <div class="flex items-center gap-1.5">
          <UIcon name="i-ph-cloud" class="w-4 h-4 shrink-0" data-summary-icon="cloud" :style="{ color: seriesLabelColor('slate', isDark) }" />
          <span class="font-semibold text-gray-800 dark:text-gray-100">{{ summaryStats.cloud.value }}</span>
          <span class="text-gray-500 dark:text-gray-400 text-xs">{{ summaryStats.cloud.unit }}</span>
        </div>
        <div v-if="summaryStats.pressure" class="flex items-center gap-1.5">
          <UIcon name="i-ph-gauge" class="w-4 h-4 shrink-0" data-summary-icon="pressure" :style="{ color: seriesLabelColor('lime', isDark) }" />
          <span class="font-semibold text-gray-800 dark:text-gray-100">{{ summaryStats.pressure.range }}</span>
          <span class="text-gray-500 dark:text-gray-400 text-xs">{{ summaryStats.pressure.unit }}</span>
        </div>
        <!-- the time zone of the chart's axis: the table names its own in its header -->
        <div v-if="view === 'chart'" class="hidden sm:block ml-auto self-center text-xs text-gray-500 dark:text-gray-400 select-none">
          {{ toolbarTzLabel }}
        </div>
      </div>

      <!-- Main Interactive Chart Container -->
      <div v-if="view === 'chart'">
        <div class="rounded-xl border border-gray-200 dark:border-gray-800 bg-default shadow-sm overflow-hidden">
          <div
            v-if="renderFailed"
            ref="chartNotice"
            class="flex flex-wrap items-center justify-center gap-3 p-4 text-red-600 dark:text-red-400"
          >
            <!-- mounted anew for each failure, so a Retry that fails too is announced again; the
                 button stays, and keeps its focus -->
            <span :key="renderFailures" role="alert" class="text-center">
              <span class="font-medium">{{ t('dataViewer.chartNotDrawn') }}</span>
              <!-- a sentence apart from the note, which ends with no full stop: the alert's text, as
                   a screen reader reads it, otherwise runs the two together -->
              <template v-if="chartCodeNotLoaded">
                <span class="sr-only">{{ '. ' }}</span>
                <span class="block text-sm">{{ t('dataViewer.chartCodeNotLoaded') }}</span>
              </template>
            </span>
            <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" @click="requestRender(false)" />
            <UButton v-if="chartCodeNotLoaded" :label="t('common.reloadPage')" icon="i-ph-arrows-clockwise" size="sm" color="neutral" variant="outline" @click="reloadPage()" />
          </div>
          <!-- a figure, as the app's other charts, and no landmark; drawn without Plotly's modebar, it holds
               no controls of Plotly's to keep reachable. Described by what it shows; the table has the values -->
          <div
            ref="chartRef" tabindex="-1" role="figure" :class="widget ? 'w-full' : 'app-chart'"
            :aria-label="chartLabel"
            :aria-describedby="chartTable ? summaryId : undefined"
            :style="{ height: chartHeight, position: 'relative' }"
          />
        </div>
        <template v-if="chartTable">
          <p :id="summaryId" class="sr-only">
            {{ chartTable.summary }}
          </p>
          <!-- the widget has no control to choose the table with: its text alternative stays below the chart -->
          <ChartTable v-if="widget" :caption="chartLabel" :columns="chartTable.columns" :rows="chartTable.rows" />
        </template>
      </div>

      <!-- The values the chart draws, as a table of their own at the width of the page -->
      <div v-else-if="view === 'table'">
        <ValuesTable v-if="chartTable" full :caption="chartLabel" :columns="chartTable.columns" :rows="chartTable.rows" />
        <UEmpty v-else icon="i-ph-table" :title="t('meteogram.chart.noData')" />
      </div>

      <!-- in the map's panel, one row a day: the day, its weather, its rain and its temperatures -->
      <!-- every day of the run is before today at the station: no row to show -->
      <p v-else-if="daysOnly && !compactDays.length" class="text-sm text-muted" data-testid="day-rows-empty">
        {{ t('widget.noData') }}
      </p>
      <ul v-else-if="daysOnly" class="divide-y divide-default" data-testid="day-rows">
        <li v-for="(d, idx) in compactDays" :key="idx" class="grid grid-cols-[minmax(4.5rem,auto)_2rem_1fr_auto] items-center gap-x-3 py-2">
          <span class="text-sm" :class="d.isToday ? 'font-bold text-highlighted' : 'text-toned'">
            {{ d.isToday ? t('meteogram.chart.today') : d.weekday }}
            <span class="block text-xs font-normal text-muted tabular-nums">{{ d.dayMonth }}</span>
            <span v-if="d.partialHours" class="block text-xs font-normal text-muted" data-testid="partial-day">{{ t('meteogram.chart.partialDay', { hours: d.partialHours }) }}</span>
          </span>
          <!-- the icon is a decoration; the words are what a screen reader reads (WCAG 1.1.1). text-toned: 3:1 and more on the row, by day and at night -->
          <UIcon :name="WEATHER_ICONS[d.kind]" class="size-6 text-toned" aria-hidden="true" :data-weather="d.kind" />
          <span class="text-sm text-toned">
            <span class="sr-only">{{ t(`meteogram.chart.weather.${d.kind}`) }}</span>
            <span v-if="d.precipLabel" class="text-blue-700 dark:text-blue-300 tabular-nums">
              <span class="sr-only">{{ ', ' }}{{ t('meteogram.chart.panelPrecipitation') }}{{ t('common.colon') }}{{ ' ' }}</span>{{ d.precipLabel }}
            </span>
          </span>
          <span v-if="d.tempLabel" class="text-sm font-bold text-highlighted tabular-nums text-end">{{ d.tempLabel }}</span>
        </li>
      </ul>

      <UEmpty v-else-if="!compactDays.length" icon="i-ph-cloud-slash" :title="t('meteogram.chart.noData')" />

      <!-- Premium Compact Overview Grid -->
      <div v-else class="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-950 shadow-md p-4">
        <!-- relative: the cards' visually hidden texts are positioned, and would otherwise lie outside the box that scrolls and make the page scroll sideways (WCAG 1.4.10) -->
        <div class="relative flex items-center justify-start gap-4 overflow-x-auto whitespace-nowrap py-1 px-1">
          <template v-for="(d, idx) in compactDays" :key="idx">
            <div
              class="inline-flex flex-col items-center justify-center text-center p-4 rounded-2xl border transition-all duration-300 min-w-[105px] flex-shrink-0" :class="[
                d.isToday
                  ? 'bg-blue-500/5 dark:bg-blue-500/10 border-blue-600 dark:border-blue-400 ring-1 ring-blue-400/20 shadow-md shadow-blue-500/5'
                  : 'bg-gray-50/50 dark:bg-gray-900/30 border-gray-100 dark:border-gray-800 hover:bg-gray-100 dark:hover:bg-gray-900/70 hover:border-gray-200 dark:hover:border-gray-700',
              ]"
            >
              <div class="text-xs font-bold text-gray-600 dark:text-gray-400 uppercase tracking-widest mb-1">
                {{ d.isToday ? t('meteogram.chart.today') : d.weekday }}
              </div>
              <!-- the icon is a decoration; the words are what a screen reader reads (WCAG 1.1.1) -->
              <div class="my-3 animate-bounce-slow">
                <UIcon :name="WEATHER_ICONS[d.kind]" class="size-8 text-toned" aria-hidden="true" :data-weather="d.kind" />
              </div>
              <div class="sr-only">
                {{ t(`meteogram.chart.weather.${d.kind}`) }}
              </div>
              <div class="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">
                {{ d.dayMonth }}
              </div>
              <div v-if="d.partialHours" class="text-xs text-gray-600 dark:text-gray-400 mb-2" data-testid="partial-day">
                {{ t('meteogram.chart.partialDay', { hours: d.partialHours }) }}
              </div>
              <div v-if="d.tempLabel" class="text-xs font-extrabold text-gray-700 dark:text-gray-200 mt-1 bg-white dark:bg-gray-800/80 px-2 py-0.5 rounded-lg border border-gray-100 dark:border-gray-700 shadow-xs">
                {{ d.tempLabel }}
              </div>
              <div v-if="d.precipLabel" class="text-xs font-semibold text-blue-600 dark:text-blue-400 mt-1 select-none">
                <UIcon name="i-ph-drop" class="size-3.5 align-text-bottom" aria-hidden="true" />
                <span class="sr-only">{{ t('meteogram.chart.panelPrecipitation') }}{{ t('common.colon') }}{{ ' ' }}</span>{{ d.precipLabel }}
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Smooth custom bounce animation for the weather icons. Once, and not at all for a visitor who asked
   for less motion: movement that starts by itself and goes on for more than five seconds needs a way
   to be stopped (WCAG 2.2.2), and a decoration is not worth one. */
@keyframes bounce-slow {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}
@media (prefers-reduced-motion: no-preference) {
  .animate-bounce-slow {
    animation: bounce-slow 4s ease-in-out 1;
  }
}
</style>
