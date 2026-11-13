<script setup lang="ts">
/**
 * The forecast chart (GH-4059): the panels on one time axis, drawn by Apache ECharts as SVG, at a fixed height for each
 * panel and a fixed width for each hour, so that the screen and the way it is held never change its shape. A narrow
 * screen shows part of the forecast and the rest is a scroll away, with the axes in view; a wide one shows more.
 *
 * The chart is as wide as the screen gives it and stays in place while a strip of the forecast's length scrolls
 * under it: the scroll moves the chart's window of time (`utils/meteogram-geometry.ts`), and a zoom, a pinch, a
 * dragged box, the keys and the buttons move the same window, so the axes are always in view and the scroll bar,
 * the touch scroll and the arrow keys are the browser's own.
 *
 * The readout (what a tooltip would be) is an element of this component and not the library's: a pointer can move
 * onto it, it stays until the pointer or the focus leaves, and Escape closes it (WCAG 1.4.13).
 */
import type { ECharts } from 'echarts/core'
import type { PanelName, TimeWindow } from '~/utils/meteogram-geometry'
import type { MeteogramModel, SunLibrary } from '~/utils/meteogram-model'
import type { SeriesMap } from '~/utils/meteogram-series'
import type { MeteogramUnits } from '~/utils/meteogram-units'
import { DateTime } from 'luxon'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { formatDayMonth, formatNumber, hourFormatter, weekdayShort } from '~/utils/format'
import { findNearestIndex } from '~/utils/meteogram'
import { chartLayout, clampWindow, GUTTER_LEFT, GUTTER_RIGHT, HOUR_MS, hourWidth, MIN_SPAN_HOURS, panWindow, plotWidthFor, revealInstant, scrollStrip, windowFromScroll, zoomWindow } from '~/utils/meteogram-geometry'
import { buildMeteogramModel, readoutValue } from '~/utils/meteogram-model'
import { buildMeteogramOption, gutterLeftFor, toneColor } from '~/utils/meteogram-option'
import { withUnit } from '~/utils/units'
import { yrSymbolFor, yrSymbolUrl } from '~/utils/weather-symbols'

const props = defineProps<{
  series: SeriesMap
  panels: Record<PanelName, boolean>
  /** the hours of the run that are shown, from its start; null for all of it */
  horizonHours: number | null
  /** the station's time zone */
  zone: string
  stationCoords?: { latitude: number | null, longitude: number | null } | null
  units: MeteogramUnits
  /** the figure's name, and the element that describes it */
  label: string
  describedBy?: string
  widget?: boolean
}>()

const { t, locale } = useI18n()
const formatLanguage = useFormatLanguage()
const { theme } = useChartTheme()

const rootEl = ref<HTMLElement | null>(null)
const scrollerEl = ref<HTMLElement | null>(null)
const stageEl = ref<HTMLElement | null>(null)
const chartEl = ref<HTMLElement | null>(null)
const readoutEl = ref<HTMLElement | null>(null)
const noticeEl = useTemplateRef<HTMLElement>('chartNotice')

// the hour the crosshair stands at, and whether it was the pointer or a key that put it there
const cursor = ref<number | null>(null)
const cursorSource = ref<'pointer' | 'keyboard' | 'touch'>('pointer')
const pointerY = ref(0)
const dismissed = ref(false)
const announcement = ref('')
// the line of now moves on a minute at a time
const now = ref<number | null>(Date.now())

const hintId = useId()
const readoutId = useId()

// -- what is drawn ------------------------------------------------------------------------------------------------

// loaded when the chart is first drawn, as the chart's code is
const sun = shallowRef<SunLibrary | null>(null)

// primitives, not the object the page hands over afresh with each of its renders: the chart is drawn again only for a change
const latitude = computed(() => props.stationCoords?.latitude ?? null)
const longitude = computed(() => props.stationCoords?.longitude ?? null)

const model = computed<MeteogramModel | null>(() => buildMeteogramModel({
  series: props.series,
  panels: props.panels,
  horizonHours: props.horizonHours,
  zone: props.zone,
  language: formatLanguage.value,
  coords: { latitude: latitude.value, longitude: longitude.value },
  sun: sun.value,
  units: props.units,
  t,
}))
const bounds = computed<TimeWindow | null>(() => model.value ? { start: model.value.minTime, end: model.value.maxTime } : null)
const hours = computed(() => bounds.value ? (bounds.value.end - bounds.value.start) / HOUR_MS : 0)
const layout = computed(() => model.value ? chartLayout(model.value.panels, model.value.symbols.length > 0) : null)
const gutterLeft = computed(() => model.value ? gutterLeftFor(model.value) : GUTTER_LEFT)

// -- the size: fixed panel heights, a fixed width for the hour ----------------------------------------------------

// what the screen gives the chart, in px; the width of a window that has none to measure (a test's) is a desktop's
const availablePx = ref(0)
function measure() {
  const width = rootEl.value?.clientWidth ?? 0
  availablePx.value = width > 0 ? width : 800
}
const freePlotPx = computed(() => Math.max(0, availablePx.value - gutterLeft.value - GUTTER_RIGHT))
const plotPx = computed(() => plotWidthFor(availablePx.value, hours.value, gutterLeft.value))
const outerPx = computed(() => plotPx.value + gutterLeft.value + GUTTER_RIGHT)
const defaultPxPerHour = computed(() => hourWidth(freePlotPx.value, hours.value))

// -- the window of time the chart shows ---------------------------------------------------------------------------

// where it starts, and how wide an hour is in it: null for the first hour and the fixed spacing, which a reset goes back to
const startMs = ref<number | null>(null)
const pxPerHour = ref<number | null>(null)

const win = computed<TimeWindow>(() => {
  const b = bounds.value
  if (!b)
    return { start: 0, end: HOUR_MS }
  const px = pxPerHour.value ?? defaultPxPerHour.value
  const span = Math.min(b.end - b.start, (plotPx.value / px) * HOUR_MS)
  const start = startMs.value ?? b.start
  return clampWindow({ start, end: start + span }, b)
})

function applyWindow(next: TimeWindow) {
  const b = bounds.value
  if (!b)
    return
  const clamped = clampWindow(next, b)
  const px = (plotPx.value * HOUR_MS) / Math.max(1, clamped.end - clamped.start)
  startMs.value = clamped.start
  pxPerHour.value = Math.abs(px - defaultPxPerHour.value) < 0.01 ? null : px
}

function resetZoom() {
  startMs.value = null
  pxPerHour.value = null
  dismissed.value = false
}
/** One step of the zoom buttons and keys: a third more or less of the hours across the plot */
const ZOOM_STEP = 1.5
function anchorOf(): number {
  return cursor.value ?? (win.value.start + win.value.end) / 2
}
function zoomIn() {
  if (bounds.value)
    applyWindow(zoomWindow(win.value, 1 / ZOOM_STEP, anchorOf(), bounds.value))
}
function zoomOut() {
  if (bounds.value)
    applyWindow(zoomWindow(win.value, ZOOM_STEP, anchorOf(), bounds.value))
}
/** Moves the window by `fraction` of its width */
function shift(fraction: number) {
  if (bounds.value)
    applyWindow(panWindow(win.value, (win.value.end - win.value.start) * fraction, bounds.value))
}
const atStart = computed(() => !bounds.value || win.value.start <= bounds.value.start)
const atEnd = computed(() => !bounds.value || win.value.end >= bounds.value.end)
const atMaxZoom = computed(() => (win.value.end - win.value.start) / HOUR_MS <= MIN_SPAN_HOURS)
const atMinZoom = computed(() => !bounds.value || win.value.end - win.value.start >= bounds.value.end - bounds.value.start)

// a new forecast, or another horizon, starts the chart over
watch(bounds, (next, previous) => {
  if (!previous || !next || previous.start !== next.start || previous.end !== next.end) {
    startMs.value = null
    pxPerHour.value = null
    cursor.value = null
  }
})

// -- the strip that scrolls ---------------------------------------------------------------------------------------

const strip = computed(() => bounds.value ? scrollStrip(win.value, bounds.value, plotPx.value, outerPx.value) : { width: 0, left: 0 })

function onScroll() {
  const scroller = scrollerEl.value
  const b = bounds.value
  if (!scroller || !b || Math.abs(scroller.scrollLeft - strip.value.left) <= 1)
    return
  // a scroll of the reader's: the window follows
  const span = win.value.end - win.value.start
  const next = windowFromScroll(scroller.scrollLeft, span, b, plotPx.value)
  startMs.value = next.start
}

// the window moved by anything else: the strip follows
watch(strip, async (next) => {
  await nextTick()
  const scroller = scrollerEl.value
  if (scroller && Math.abs(scroller.scrollLeft - next.left) > 1)
    scroller.scrollLeft = next.left
}, { flush: 'post' })

// -- the readout --------------------------------------------------------------------------------------------------

function timeAtX(x: number): number {
  const w = win.value
  return w.start + ((x - gutterLeft.value) / Math.max(1, plotPx.value)) * (w.end - w.start)
}
function xOfTime(time: number): number {
  const w = win.value
  return gutterLeft.value + ((time - w.start) / Math.max(1, w.end - w.start)) * plotPx.value
}
function nearestStamp(time: number): number | null {
  const stamps = model.value?.stamps
  if (!stamps?.length)
    return null
  const index = findNearestIndex(stamps.map(s => new Date(s)), time)
  return stamps[index] ?? null
}

const cursorX = computed(() => cursor.value === null ? null : xOfTime(cursor.value))
const cursorVisible = computed(() => cursorX.value !== null && cursorX.value >= gutterLeft.value - 0.5 && cursorX.value <= gutterLeft.value + plotPx.value + 0.5 && !dismissed.value)

const hourLabel = computed(() => hourFormatter(formatLanguage.value, props.zone))
function writeTime(ms: number): string {
  const day = DateTime.fromMillis(ms, { zone: props.zone })
  return `${weekdayShort(day, formatLanguage.value)} ${formatDayMonth(day, formatLanguage.value)} ${hourLabel.value(ms)}`
}

const readout = computed(() => {
  const m = model.value
  const time = cursor.value
  if (!m || time === null || !cursorVisible.value)
    return null
  const rows: { id: string, label: string, value: string, colour: string }[] = []
  for (const series of m.readout) {
    const value = readoutValue(series, time)
    if (value === null)
      continue
    rows.push({
      id: series.id,
      label: series.hover,
      value: withUnit(formatNumber(value, locale.value, series.digits), series.unit),
      colour: toneColor(series.tone, theme.value.dark),
    })
  }
  const kind = m.weather.get(time) ?? null
  const symbol = kind ? m.symbols.find(s => s.t === time) : undefined
  return {
    time: writeTime(time),
    weather: kind ? t(`meteogram.chart.weather.${kind}`) : '',
    symbol: symbol ? yrSymbolUrl(yrSymbolFor({ kind: symbol.kind, night: symbol.night, precipitationMm: symbol.precipitationMm, sky: symbol.sky }), theme.value.dark) : null,
    rows,
  }
})

// at the right of the crosshair, or at its left where the right has no room; level with the pointer, so that the pointer
// is moved onto it by moving across the one step to the crosshair's hour, and no further
const READOUT_WIDTH = 216
const readoutStyle = computed(() => {
  const x = cursorX.value ?? 0
  const right = x + READOUT_WIDTH + 6 <= outerPx.value
  const height = layout.value?.height ?? 0
  const estimated = 56 + (readout.value?.rows.length ?? 0) * 20
  const top = cursorSource.value === 'pointer'
    ? Math.max(layout.value?.header.height ?? 0, Math.min(pointerY.value - 24, height - estimated))
    : (layout.value?.header.height ?? 0)
  return { top: `${Math.max(0, top)}px`, ...(right ? { left: `${x + 2}px` } : { left: `${x - READOUT_WIDTH - 2}px` }), width: `${READOUT_WIDTH}px` }
})

function select(time: number | null, source: 'pointer' | 'keyboard' | 'touch') {
  cursor.value = time
  cursorSource.value = source
  dismissed.value = false
}
function dismiss() {
  dismissed.value = true
}

function readoutSentence(time: number): string {
  const m = model.value
  if (!m)
    return ''
  const parts: string[] = []
  const kind = m.weather.get(time)
  if (kind)
    parts.push(t(`meteogram.chart.weather.${kind}`))
  for (const series of m.readout) {
    const value = readoutValue(series, time)
    if (value !== null)
      parts.push(`${series.hover}${t('common.colon')} ${withUnit(formatNumber(value, locale.value, series.digits), series.unit)}`)
  }
  return `${writeTime(time)}${t('common.colon')} ${parts.join('; ')}`
}

// Escape closes the readout wherever the pointer or the focus is, and is left to whatever else it closes (a dialog)
function onDocumentKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && readout.value)
    dismiss()
}
watch(() => readout.value !== null, (open) => {
  if (open)
    document.addEventListener('keydown', onDocumentKeydown)
  else
    document.removeEventListener('keydown', onDocumentKeydown)
})

// -- the pointer --------------------------------------------------------------------------------------------------

interface Drag { x0: number, x1: number, active: boolean }
const drag = ref<Drag | null>(null)
let suppressClick = false

function stageX(event: PointerEvent | MouseEvent): number {
  return event.clientX - (stageEl.value?.getBoundingClientRect().left ?? 0)
}
function stageY(event: PointerEvent | MouseEvent): number {
  return event.clientY - (stageEl.value?.getBoundingClientRect().top ?? 0)
}
const insidePlot = (x: number) => x >= gutterLeft.value && x <= gutterLeft.value + plotPx.value
const onReadout = (event: Event) => !!readoutEl.value && event.target instanceof Node && readoutEl.value.contains(event.target)

function onPointerDown(event: PointerEvent) {
  // a mouse drags a box to zoom to; a touch scrolls the strip and a pinch is the library's
  if (event.pointerType !== 'mouse' || event.button !== 0 || onReadout(event))
    return
  const x = stageX(event)
  if (!insidePlot(x))
    return
  drag.value = { x0: x, x1: x, active: false }
  ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
}
function onPointerMove(event: PointerEvent) {
  if (event.pointerType === 'touch' || onReadout(event))
    return
  const x = stageX(event)
  pointerY.value = stageY(event)
  if (drag.value) {
    const clamped = Math.min(gutterLeft.value + plotPx.value, Math.max(gutterLeft.value, x))
    drag.value = { ...drag.value, x1: clamped, active: drag.value.active || Math.abs(clamped - drag.value.x0) >= 6 }
    return
  }
  if (!insidePlot(x)) {
    if (cursorSource.value === 'pointer')
      cursor.value = null
    return
  }
  const stamp = nearestStamp(timeAtX(x))
  if (stamp !== null)
    select(stamp, 'pointer')
}
function onPointerUp(event: PointerEvent) {
  const d = drag.value
  drag.value = null
  ;(event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId)
  if (!d?.active)
    return
  // a click ends a drag too, and is not a tap to select
  suppressClick = true
  const a = timeAtX(Math.min(d.x0, d.x1))
  const b = timeAtX(Math.max(d.x0, d.x1))
  applyWindow({ start: a, end: b })
}
function onPointerLeave(event: PointerEvent) {
  if (event.pointerType === 'touch' || drag.value)
    return
  // the readout is inside the stage: only leaving the whole of it takes the readout away
  if (cursorSource.value === 'pointer')
    cursor.value = null
}
function onClick(event: MouseEvent) {
  if (suppressClick) {
    suppressClick = false
    return
  }
  if (onReadout(event))
    return
  const x = stageX(event)
  if (!insidePlot(x))
    return
  const stamp = nearestStamp(timeAtX(x))
  if (stamp !== null) {
    pointerY.value = stageY(event)
    // a tap stays until it is closed or tapped away: there is no leaving a touch
    select(stamp, (event as PointerEvent).pointerType === 'touch' ? 'touch' : 'pointer')
  }
}

// -- the keys -----------------------------------------------------------------------------------------------------

function step(stampsToMove: number) {
  const m = model.value
  if (!m || !m.stamps.length)
    return
  const stamps = m.stamps
  let index: number
  if (cursor.value === null) {
    // the first hour in the window
    index = Math.max(0, stamps.findIndex(s => s >= win.value.start))
  }
  else {
    index = Math.min(stamps.length - 1, Math.max(0, stamps.indexOf(cursor.value) + stampsToMove))
  }
  jump(index)
}
function jump(index: number) {
  const m = model.value
  const b = bounds.value
  if (!m || !b)
    return
  const time = m.stamps[Math.min(m.stamps.length - 1, Math.max(0, index))]!
  select(time, 'keyboard')
  // the window follows the crosshair
  applyWindow(revealInstant(win.value, time, b))
  announcement.value = readoutSentence(time)
}
/** The stamps in a number of hours from the crosshair's */
function stampsIn(hoursAway: number): number {
  const m = model.value
  if (!m || cursor.value === null)
    return hoursAway
  const from = m.stamps.indexOf(cursor.value)
  const target = cursor.value + hoursAway * HOUR_MS
  const to = findNearestIndex(m.stamps.map(s => new Date(s)), target)
  return from < 0 ? hoursAway : to - from
}

function onKeydown(event: KeyboardEvent) {
  if (event.altKey || event.ctrlKey || event.metaKey)
    return
  const m = model.value
  if (!m)
    return
  const sign = (key: string) => key === 'ArrowRight' ? 1 : -1
  switch (event.key) {
    case 'ArrowRight':
    case 'ArrowLeft':
      step(event.shiftKey ? stampsIn(6 * sign(event.key)) : sign(event.key))
      break
    case 'PageUp':
    case 'PageDown':
      step(stampsIn(24 * (event.key === 'PageDown' ? 1 : -1)))
      break
    case 'Home':
      jump(0)
      break
    case 'End':
      jump(m.stamps.length - 1)
      break
    case '+':
    case '=':
      zoomIn()
      break
    case '-':
    case '_':
      zoomOut()
      break
    case '0':
      resetZoom()
      break
    default:
      // anything else, Escape included, is left alone: the document's listener closes the readout, and a dialog still closes
      return
  }
  event.preventDefault()
}
function onBlur(event: FocusEvent) {
  // the focus left the chart: a readout it put there goes with it
  if (cursorSource.value === 'keyboard' && !stageEl.value?.contains(event.relatedTarget as Node | null))
    cursor.value = null
}

// -- drawing ------------------------------------------------------------------------------------------------------

let echarts: ReturnType<typeof import('~/utils/echarts-loader').loadEcharts> | null = null
let chart: ECharts | null = null
let observer: ResizeObserver | null = null

// the newest drawing threw -- the chart's code or its drawing -- and the chart area says so; failures counted, so a Retry
// that fails too is told again
const renderFailed = ref(false)
const renderFailures = ref(0)
// The newest drawing could not import the chart's code: ECharts, or suncalc for the day bands. Where a redeploy has
// replaced its chunk, a Retry asks for the same chunk again and fails every time, and only reloading the page loads the
// new one: the chart area says so, and offers the reload.
const chartCodeNotLoaded = ref(false)
let codeImportFailed = false
// a Retry that works hands its focus on to the chart it drew
useFocusAfterRetry(renderFailed, noticeEl, stageEl)

function importChartCode<T>(load: () => Promise<T>): Promise<T> {
  return load().catch((error) => {
    codeImportFailed = true
    throw error
  })
}
function reloadPage() {
  // forced: the user's click, not a reload loop, which is what Nuxt's guard stops
  reloadNuxtApp({ force: true })
}

let isRendering = false
let renderPending = false
// what the chart on the page was drawn from: a drawing for the same is none (the sun's code arriving changes the model
// the drawing that waited for it has already used)
let drawnFrom: unknown[] | null = null
const drawInputs = () => [model.value, theme.value, outerPx.value, locale.value, now.value]

async function render() {
  if (isRendering) {
    renderPending = true
    return
  }
  if (drawnFrom && chart && drawInputs().every((input, i) => input === drawnFrom![i]))
    return
  isRendering = true
  renderPending = false
  codeImportFailed = false
  try {
    await draw()
    renderFailed.value = false
  }
  catch (error) {
    console.error('The chart could not be drawn', error)
    // a drawing queued meanwhile draws next, and tells its own outcome
    if (!renderPending) {
      renderFailed.value = true
      chartCodeNotLoaded.value = codeImportFailed
      renderFailures.value++
    }
  }
  finally {
    isRendering = false
    if (renderPending)
      void render()
  }
}

function fontFamily(): string {
  return getComputedStyle(document.body).fontFamily || 'system-ui, sans-serif'
}

function onDataZoom(event: any) {
  const b = bounds.value
  if (!b)
    return
  const e = event?.batch?.[0] ?? event
  let start: number | undefined = e.startValue
  let end: number | undefined = e.endValue
  if (start === undefined || end === undefined) {
    if (e.start === undefined || e.end === undefined)
      return
    start = b.start + (e.start / 100) * (b.end - b.start)
    end = b.start + (e.end / 100) * (b.end - b.start)
  }
  // the echo of a window this component set itself is no news
  if (Math.abs(start - win.value.start) < 1000 && Math.abs(end - win.value.end) < 1000)
    return
  applyWindow({ start, end })
}

function disposeChart() {
  chart?.dispose()
  chart = null
  drawnFrom = null
}

async function draw() {
  await nextTick()
  if (!chartEl.value || !model.value || !layout.value) {
    disposeChart()
    return
  }
  performance.mark('meteogram:draw-start')
  echarts ??= await importChartCode(async () => (await import('~/utils/echarts-loader')).loadEcharts())
  // the day bands are the sun at the station; without a station there are none to work out
  if (latitude.value !== null && longitude.value !== null && !sun.value)
    sun.value = await importChartCode(() => import('suncalc'))
  // the page may have changed under the awaits
  const el = chartEl.value
  const m = model.value
  const lay = layout.value
  if (!el || !m || !lay) {
    disposeChart()
    return
  }
  if (!chart || chart.getDom() !== el) {
    disposeChart()
    chart = echarts.init(el, null, { renderer: 'svg', width: outerPx.value, height: lay.height })
    chart.on('datazoom', onDataZoom)
  }
  chart.resize({ width: outerPx.value, height: lay.height })
  chart.setOption(buildMeteogramOption({
    model: m,
    theme: theme.value,
    layout: lay,
    outerPx: outerPx.value,
    plotPx: plotPx.value,
    gutterLeft: gutterLeft.value,
    window: win.value,
    now: now.value,
    fontFamily: fontFamily(),
    locale: locale.value,
    hourLabel: hourLabel.value,
  }), { notMerge: true })
  drawnFrom = drawInputs()
  el.dataset.chartScheme = theme.value.dark ? 'dark' : 'light'
  el.dataset.drawn = 'true'
  performance.mark('meteogram:drawn')
}

let clock: ReturnType<typeof setInterval> | undefined

watch([model, theme, outerPx, locale, now], () => void render())
// the window moves without drawing the chart again
watch(win, (next) => {
  chart?.dispatchAction({ type: 'dataZoom', dataZoomId: 'zoom', startValue: next.start, endValue: next.end })
})

onMounted(() => {
  measure()
  if (typeof ResizeObserver !== 'undefined' && rootEl.value) {
    observer = new ResizeObserver(() => measure())
    observer.observe(rootEl.value)
  }
  clock = setInterval(() => {
    now.value = Date.now()
  }, 60_000)
  void render()
})
onBeforeUnmount(() => {
  observer?.disconnect()
  clearInterval(clock)
  document.removeEventListener('keydown', onDocumentKeydown)
  disposeChart()
})

defineExpose({ resetZoom, zoomIn, zoomOut, shift, win, atStart, atEnd, atMaxZoom, atMinZoom, renderFailed, renderFailures })

const selectionStyle = computed(() => {
  const d = drag.value
  if (!d?.active)
    return null
  return { left: `${Math.min(d.x0, d.x1)}px`, width: `${Math.abs(d.x1 - d.x0)}px`, top: `${layout.value?.header.height ?? 0}px`, height: `${(layout.value?.height ?? 0) - (layout.value?.header.height ?? 0)}px` }
})
</script>

<template>
  <div ref="rootEl" class="meteogram-chart" :class="widget ? undefined : 'app-chart'" :data-widget="widget ? '' : undefined">
    <div
      v-if="renderFailed"
      ref="chartNotice"
      class="flex flex-wrap items-center justify-center gap-3 p-4 text-red-600 dark:text-red-400"
    >
      <!-- mounted anew for each failure, so a Retry that fails too is announced again; the button stays, and keeps its focus -->
      <span :key="renderFailures" role="alert" class="text-center">
        <span class="font-medium">{{ t('dataViewer.chartNotDrawn') }}</span>
        <!-- a sentence apart from the note, which ends with no full stop: the alert's text, as a screen reader reads it,
             otherwise runs the two together -->
        <template v-if="chartCodeNotLoaded">
          <span class="sr-only">{{ '. ' }}</span>
          <span class="block text-sm">{{ t('dataViewer.chartCodeNotLoaded') }}</span>
        </template>
      </span>
      <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" @click="render()" />
      <UButton v-if="chartCodeNotLoaded" :label="t('common.reloadPage')" icon="i-ph-arrows-clockwise" size="sm" color="neutral" variant="outline" @click="reloadPage()" />
    </div>

    <!-- the strip scrolls and the chart stays where it is: the axes are always in view -->
    <div ref="scrollerEl" class="mg-scroller" data-testid="meteogram-scroller" @scroll.passive="onScroll">
      <div class="mg-track" :style="{ width: `${strip.width || outerPx}px`, height: `${layout?.height ?? 0}px` }">
        <!-- a figure, as the app's other charts, and no landmark; one tab stop for the whole chart (Chartability) -->
        <div
          ref="stageEl"
          class="mg-stage"
          role="figure"
          tabindex="0"
          :aria-label="label"
          :aria-describedby="[describedBy, hintId].filter(Boolean).join(' ')"
          aria-keyshortcuts="ArrowLeft ArrowRight Shift+ArrowLeft Shift+ArrowRight PageUp PageDown Home End + - 0 Escape"
          :style="{ width: `${outerPx}px`, height: `${layout?.height ?? 0}px` }"
          @keydown="onKeydown"
          @blur.capture="onBlur"
          @pointerdown="onPointerDown"
          @pointermove="onPointerMove"
          @pointerup="onPointerUp"
          @pointercancel="onPointerUp"
          @pointerleave="onPointerLeave"
          @click="onClick"
          @dblclick="resetZoom"
        >
          <div ref="chartEl" class="mg-canvas" aria-hidden="true" :style="{ width: `${outerPx}px`, height: `${layout?.height ?? 0}px` }" />
          <div
            v-if="cursorVisible && cursorX !== null"
            class="mg-cursor"
            aria-hidden="true"
            :style="{ left: `${cursorX}px`, top: `${layout?.header.height ?? 0}px`, height: `${(layout?.height ?? 0) - (layout?.header.height ?? 0)}px` }"
          />
          <div v-if="selectionStyle" class="mg-selection" aria-hidden="true" :style="selectionStyle" />
          <div
            v-if="readout"
            :id="readoutId"
            ref="readoutEl"
            class="mg-readout"
            role="group"
            :aria-label="t('meteogram.chart.readoutFor', { time: readout.time })"
            :style="readoutStyle"
            data-testid="meteogram-readout"
          >
            <div class="flex items-start gap-2">
              <img v-if="readout.symbol" :src="readout.symbol" alt="" width="28" height="28" class="size-7 shrink-0">
              <div class="min-w-0 flex-1">
                <div class="font-semibold text-highlighted tabular-nums">
                  {{ readout.time }}
                </div>
                <div v-if="readout.weather" class="text-xs text-muted">
                  {{ readout.weather }}
                </div>
              </div>
              <button
                type="button"
                class="mg-close"
                :aria-label="t('meteogram.chart.readoutClose')"
                :title="t('meteogram.chart.readoutClose')"
                @click.stop="dismiss"
              >
                <UIcon name="i-ph-x" class="size-3.5" aria-hidden="true" />
              </button>
            </div>
            <dl class="mt-1.5 grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5">
              <template v-for="row in readout.rows" :key="row.id">
                <dt class="flex items-center gap-1.5 text-toned">
                  <span class="size-2 shrink-0 rounded-full" aria-hidden="true" :style="{ background: row.colour }" />{{ row.label }}
                </dt>
                <dd class="m-0 text-end font-medium text-highlighted tabular-nums">
                  {{ row.value }}
                </dd>
              </template>
            </dl>
          </div>
        </div>
      </div>
    </div>
    <!-- the symbols are the work of Yr, under CC BY 4.0, which asks for this credit where they are shown -->
    <i18n-t v-if="model?.symbols.length" keypath="meteogram.chart.symbolsCredit" tag="p" scope="global" class="px-2 pb-1.5 pt-1 text-xs text-muted" data-testid="meteogram-credit">
      <template #yr>
        <a href="https://github.com/nrkno/yr-weather-symbols" target="_blank" rel="noopener" class="underline underline-offset-2">Yr</a>
      </template>
      <template #licence>
        <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener" class="underline underline-offset-2">CC BY 4.0</a>
      </template>
    </i18n-t>
    <p :id="hintId" class="sr-only">
      {{ t('meteogram.chart.keysHint') }}
    </p>
    <!-- said when a key steps the crosshair, and not for a pointer's hover -->
    <p class="sr-only" role="status" aria-live="polite" aria-atomic="true" data-testid="meteogram-announce">
      {{ announcement }}
    </p>
  </div>
</template>

<style scoped>
.meteogram-chart {
  position: relative;
}
.mg-scroller {
  overflow-x: auto;
  overflow-y: hidden;
  /* the scroll bar is the browser's, and lies under the chart */
  overscroll-behavior-x: contain;
}
.mg-track {
  position: relative;
}
.mg-stage {
  position: sticky;
  left: 0;
  /* the browser scrolls the strip and the page; the pinch is the chart's, not the page's zoom */
  touch-action: pan-x pan-y;
  user-select: none;
  -webkit-user-select: none;
  cursor: crosshair;
}
.mg-stage:focus-visible {
  outline: 2px solid var(--app-focus-ring);
  outline-offset: -2px;
}
.mg-canvas {
  position: absolute;
  inset: 0 auto auto 0;
}
.mg-cursor {
  position: absolute;
  width: 0;
  border-left: 1px solid var(--ui-text-muted);
  pointer-events: none;
}
.mg-selection {
  position: absolute;
  background: color-mix(in srgb, var(--app-focus-ring) 14%, transparent);
  border: 1px solid var(--app-focus-ring);
  pointer-events: none;
}
.mg-readout {
  position: absolute;
  z-index: 10;
  box-sizing: border-box;
  padding: 0.5rem 0.625rem;
  border-radius: 0.5rem;
  border: 1px solid var(--ui-border-accented);
  background: var(--ui-bg-elevated);
  color: var(--ui-text);
  font-size: 0.8125rem;
  line-height: 1.25rem;
  box-shadow: 0 4px 14px rgb(0 0 0 / 0.18);
  cursor: default;
  user-select: text;
  -webkit-user-select: text;
}
.mg-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  flex-shrink: 0;
  border-radius: 9999px;
  color: var(--ui-text-muted);
  cursor: pointer;
}
.mg-close:hover {
  color: var(--ui-text-highlighted);
  background: var(--ui-bg-accented);
}
.mg-close:focus-visible {
  outline: 2px solid var(--app-focus-ring);
}
</style>
