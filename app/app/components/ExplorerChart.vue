<script setup lang="ts">
import type { ECharts } from 'echarts/core'
import type { ImageFormat } from '~/utils/chart-image'
import type { SvgPart } from '~/utils/explorer-image'
/**
 * The chart of the Explorer (GH-4096), drawn by Apache ECharts as SVG: a line for each station's parameter (with markers
 * where they are few), a y axis of its own scale that follows the window, a legend whose items turn a series off, and
 * the times in UTC. One component draws one chart: the single chart, or one facet.
 *
 * Where the pointer can do more than the keyboard, the keyboard can do the same (WCAG 2.1.1, 2.5.7): the chart is one
 * tab stop whose arrow keys step through the moments that have a value, whose `+`, `-` and `0` zoom, and whose toolbar's
 * buttons do what a dragged box, a pinch and the keys do.
 *
 * The readout (what a tooltip would be) is an element of this component and not the library's: a pointer can move onto it,
 * it stays until the pointer or the focus leaves, and Escape closes it (WCAG 1.4.13).
 */
import type { ExplorerSeries, ExplorerWindow } from '~/utils/explorer-model'
import type { ExplorerOptionInput } from '~/utils/explorer-option'
import type { ReadoutSide } from '~/utils/meteogram-geometry'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { downloadBlob, svgToBlob } from '~/utils/chart-image'
import { readDocumentChartTheme } from '~/utils/chart-theme'
import { boundsOf, buildTimeline, clampExplorerWindow, minSpanOf, nearestIndex, panExplorerWindow, readoutRows, revealMoment, sameExplorerWindow, seriesColour, shownSeries, zoomExplorerWindow } from '~/utils/explorer-model'
import { buildExplorerOption, cursorUpdate, explorerFrame, hasTimeOfDay, momentLabel, timeAtX, valueFormat, xOfTime } from '~/utils/explorer-option'
import { READOUT_WIDTH, readoutPlacement } from '~/utils/meteogram-geometry'

const props = defineProps<{
  series: readonly ExplorerSeries[]
  /** a chart of many points: a thin line and no markers */
  large: boolean
  /** the height the chart is given on the page, which a legend of many rows makes a little more */
  height: number
  /** the figure's name, and the element that describes it */
  label: string
  describedBy?: string
  /** the name of the camera's file, without its extension */
  cameraFile: string
}>()

const { t, locale } = useI18n()
const toast = useToast()
const { theme } = useChartTheme()

const rootEl = ref<HTMLElement | null>(null)
const stageEl = ref<HTMLElement | null>(null)
const chartEl = ref<HTMLElement | null>(null)
const readoutEl = ref<HTMLElement | null>(null)
const noticeEl = useTemplateRef<HTMLElement>('chartNotice')
const toolbarEl = ref<HTMLElement | null>(null)
const frameEl = ref<HTMLElement | null>(null)

const hintId = useId()
const readoutId = useId()

// the moment the crosshair stands at, and whether the pointer, a key or a touch put it there
const cursor = ref<number | null>(null)
const cursorSource = ref<'pointer' | 'keyboard' | 'touch'>('pointer')
const dismissed = ref(false)
const announcement = ref('')
const readoutSide = ref<ReadoutSide | null>(null)

// -- what is drawn ------------------------------------------------------------------------------------------------

/** The series the legend turned off: replaced, never changed, so that a drawing sees it change */
const hidden = shallowRef<ReadonlySet<string>>(new Set())
function toggleSeries(id: string) {
  const next = new Set(hidden.value)
  if (!next.delete(id))
    next.add(id)
  hidden.value = next
}
// a series that an answer no longer has is not turned off any more
watch(() => props.series, (series) => {
  const ids = new Set(series.map(item => item.id))
  if ([...hidden.value].some(id => !ids.has(id)))
    hidden.value = new Set([...hidden.value].filter(id => ids.has(id)))
})

const shown = computed(() => shownSeries(props.series, hidden.value))
const bounds = computed<ExplorerWindow | null>(() => boundsOf(props.series))
const minSpan = computed(() => minSpanOf(props.series))
const timeline = computed(() => buildTimeline(shown.value))
const withTime = computed(() => hasTimeOfDay(props.series))

// what the column gives the chart, in px; the width of a window that has none to measure (a test's) is a desktop's
const width = ref(0)
function measure() {
  // laid out for paper, the column is another width: the chart is scaled to the sheet by CSS (main.css) and is not drawn again for it
  if (window.matchMedia?.('print').matches)
    return
  const measured = rootEl.value?.clientWidth ?? 0
  width.value = measured > 0 ? measured : 800
}

// -- the window of time the chart shows ---------------------------------------------------------------------------

/** Null for all of it, which a reset goes back to */
const custom = ref<ExplorerWindow | null>(null)
const win = computed<ExplorerWindow>(() => custom.value ?? bounds.value ?? { start: 0, end: 1 })

function applyWindow(next: ExplorerWindow) {
  const b = bounds.value
  if (!b)
    return
  const clamped = clampExplorerWindow(next, b, minSpan.value)
  custom.value = sameExplorerWindow(clamped, b) ? null : clamped
}
function resetZoom() {
  custom.value = null
  dismissed.value = false
}
/** One step of the zoom buttons and keys: a third more or less of the time across */
const ZOOM_STEP = 1.5
function anchorOf(): number {
  return cursor.value ?? (win.value.start + win.value.end) / 2
}
function zoomIn() {
  if (bounds.value)
    applyWindow(zoomExplorerWindow(win.value, 1 / ZOOM_STEP, anchorOf(), bounds.value, minSpan.value))
}
function zoomOut() {
  if (bounds.value)
    applyWindow(zoomExplorerWindow(win.value, ZOOM_STEP, anchorOf(), bounds.value, minSpan.value))
}
/** Moves the window by `fraction` of its width */
function shift(fraction: number) {
  if (bounds.value)
    applyWindow(panExplorerWindow(win.value, (win.value.end - win.value.start) * fraction, bounds.value, minSpan.value))
}
const atStart = computed(() => !bounds.value || win.value.start <= bounds.value.start)
const atEnd = computed(() => !bounds.value || win.value.end >= bounds.value.end)
const atMaxZoom = computed(() => win.value.end - win.value.start <= minSpan.value)
const atMinZoom = computed(() => !bounds.value || custom.value === null)

// other values for other times start the chart over; the same times, as a unit changed, keep the zoom
watch(bounds, (next, previous) => {
  if (!previous || !next || previous.start !== next.start || previous.end !== next.end) {
    custom.value = null
    cursor.value = null
  }
})

// -- the frame ----------------------------------------------------------------------------------------------------

function optionInput(over: Partial<ExplorerOptionInput> = {}): ExplorerOptionInput | null {
  const b = bounds.value
  if (!b || !width.value)
    return null
  return {
    series: props.series,
    hidden: hidden.value,
    theme: theme.value,
    window: win.value,
    bounds: b,
    width: width.value,
    height: props.height,
    large: props.large,
    locale: locale.value,
    ...over,
  }
}
/** Where everything is, and what is drawn: the pointer's and the readout's places are read from it */
const frame = computed(() => {
  const input = optionInput()
  return input ? explorerFrame(input) : null
})
const stageHeight = computed(() => frame.value?.height ?? props.height)

// -- the readout --------------------------------------------------------------------------------------------------

const cursorX = computed(() => {
  const f = frame.value
  if (!f || cursor.value === null)
    return null
  const x = xOfTime(cursor.value, f, win.value)
  // a moment outside the window is out of sight, and so is what points at it
  return x < f.plot.left - 1 || x > f.plot.left + f.plot.width + 1 ? null : x
})

const readout = computed(() => {
  const time = cursor.value
  if (time === null || dismissed.value || cursorX.value === null)
    return null
  const rows = readoutRows(shown.value, time)
  if (!rows.length)
    return null
  const format = valueFormat(locale.value)
  return {
    time: momentLabel(time, locale.value, withTime.value),
    rows: rows.map(row => ({ id: row.id, name: row.name, value: format.format(row.value), colour: seriesColour(row.colorIndex, theme.value.dark) })),
  }
})

// docked at an edge of the chart, on the side the crosshair is not on (`readoutPlacement`), and at the top of the plot
const readoutStyle = computed(() => {
  const placement = readoutPlacement(cursorX.value ?? 0, width.value, readoutSide.value, READOUT_WIDTH)
  const top = (frame.value?.plot.top ?? 0) + 4
  return { top: `${top}px`, left: `${placement.left}px`, width: `${placement.width}px` }
})

/**
 * Puts the crosshair at a moment. A pointer's move to the moment it is at already brings nothing back that Escape took
 * away: a jitter of a pixel is no new hover (1.4.13); a key, a tap or another moment is.
 */
function select(time: number | null, source: 'pointer' | 'keyboard' | 'touch') {
  const same = time === cursor.value && source === cursorSource.value
  cursor.value = time
  cursorSource.value = source
  if (time === null) {
    readoutSide.value = null
    return
  }
  if (!same || source !== 'pointer')
    dismissed.value = false
  const f = frame.value
  // a key puts the readout on the side the crosshair is not on; a pointer keeps the side it found
  if (f)
    readoutSide.value = readoutPlacement(xOfTime(time, f, win.value), width.value, source === 'pointer' ? readoutSide.value : null, READOUT_WIDTH).side
}
function dismiss() {
  // the Close button is what has the focus where it is used (a click, Enter, or Escape while it has it), and it goes with the
  // readout: the focus is handed to the chart first, or it falls to the page's body
  if (readoutEl.value?.contains(document.activeElement))
    stageEl.value?.focus({ preventScroll: true })
  dismissed.value = true
}

function readoutSentence(time: number): string {
  const rows = readoutRows(shown.value, time)
  if (!rows.length)
    return ''
  const format = valueFormat(locale.value)
  return `${momentLabel(time, locale.value, withTime.value)}${t('common.colon')} ${rows.map(row => `${row.name}${t('common.colon')} ${format.format(row.value)}`).join('; ')}`
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
/** Whether a point is on the plot: the legend above it, the labels below and the gutter beside it are not */
function onPlot(x: number, y: number): boolean {
  const plot = frame.value?.plot
  return !!plot && x >= plot.left && x <= plot.left + plot.width && y >= plot.top && y <= plot.top + plot.height
}
const onReadout = (event: Event) => !!readoutEl.value && event.target instanceof Node && readoutEl.value.contains(event.target)
/** The moment with a value that is nearest to the pointer, null where there is none */
function momentAt(x: number): number | null {
  const f = frame.value
  const list = timeline.value
  if (!f || !list.length)
    return null
  return list[nearestIndex(list, timeAtX(x, f, win.value))] ?? null
}

function onPointerDown(event: PointerEvent) {
  // a mouse drags a box to zoom to; a touch pinches, and the library's own gesture does it
  if (event.pointerType !== 'mouse' || event.button !== 0 || onReadout(event))
    return
  const x = stageX(event)
  if (!onPlot(x, stageY(event)))
    return
  drag.value = { x0: x, x1: x, active: false }
  ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
}
function onPointerMove(event: PointerEvent) {
  if (event.pointerType === 'touch' || onReadout(event))
    return
  const plot = frame.value?.plot
  if (!plot)
    return
  const x = stageX(event)
  if (drag.value) {
    const clamped = Math.min(plot.left + plot.width, Math.max(plot.left, x))
    drag.value = { ...drag.value, x1: clamped, active: drag.value.active || Math.abs(clamped - drag.value.x0) >= 6 }
    return
  }
  if (!onPlot(x, stageY(event))) {
    if (cursorSource.value === 'pointer')
      select(null, 'pointer')
    return
  }
  const moment = momentAt(x)
  if (moment !== null)
    select(moment, 'pointer')
}
function onPointerUp(event: PointerEvent) {
  const d = drag.value
  drag.value = null
  ;(event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId)
  const f = frame.value
  if (!d?.active || !f)
    return
  // a click ends a drag too, and is not a tap to select
  suppressClick = true
  applyWindow({ start: timeAtX(Math.min(d.x0, d.x1), f, win.value), end: timeAtX(Math.max(d.x0, d.x1), f, win.value) })
}
function onPointerLeave(event: PointerEvent) {
  if (event.pointerType === 'touch' || drag.value)
    return
  // the readout is inside the stage: only leaving the whole of it takes the readout away
  if (cursorSource.value === 'pointer')
    select(null, 'pointer')
}
function onClick(event: MouseEvent) {
  if (suppressClick) {
    suppressClick = false
    return
  }
  if (onReadout(event))
    return
  const x = stageX(event)
  if (!onPlot(x, stageY(event)))
    return
  const moment = momentAt(x)
  // a tap stays until it is closed or tapped away: there is no leaving a touch
  if (moment !== null)
    select(moment, (event as PointerEvent).pointerType === 'touch' ? 'touch' : 'pointer')
}

// -- the keys -----------------------------------------------------------------------------------------------------

function jump(index: number) {
  const list = timeline.value
  const b = bounds.value
  if (!list.length || !b)
    return
  const time = list[Math.min(list.length - 1, Math.max(0, index))]!
  select(time, 'keyboard')
  // the window follows the crosshair
  applyWindow(revealMoment(win.value, time, b, minSpan.value))
  announcement.value = readoutSentence(time)
}
function step(by: number) {
  const list = timeline.value
  if (!list.length)
    return
  if (cursor.value === null) {
    // the first moment in the window
    jump(Math.max(0, list.findIndex(moment => moment >= win.value.start)))
    return
  }
  jump(nearestIndex(list, cursor.value) + by)
}
/** The number of moments in a window's width from the crosshair's, which Page Up and Page Down go by */
function momentsInWindow(sign: 1 | -1): number {
  const list = timeline.value
  if (cursor.value === null || !list.length)
    return sign
  const from = nearestIndex(list, cursor.value)
  const to = nearestIndex(list, cursor.value + sign * (win.value.end - win.value.start))
  return to === from ? sign : to - from
}

function onKeydown(event: KeyboardEvent) {
  // the legend's buttons and the readout's are inside the stage's box and keep their own keys
  if (event.target !== stageEl.value || event.altKey || event.ctrlKey || event.metaKey)
    return
  if (!timeline.value.length)
    return
  switch (event.key) {
    case 'ArrowRight':
      step(event.shiftKey ? 10 : 1)
      break
    case 'ArrowLeft':
      step(event.shiftKey ? -10 : -1)
      break
    case 'PageUp':
      step(momentsInWindow(-1))
      break
    case 'PageDown':
      step(momentsInWindow(1))
      break
    case 'Home':
      jump(0)
      break
    case 'End':
      jump(timeline.value.length - 1)
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
    select(null, 'keyboard')
}

// -- drawing ------------------------------------------------------------------------------------------------------

let echarts: ReturnType<typeof import('~/utils/echarts-loader').loadEcharts> | null = null
let chart: ECharts | null = null
let observer: ResizeObserver | null = null

// the newest drawing threw -- the chart's code or its drawing -- and the chart area says so; failures counted, so a Retry
// that fails too is told again
const renderFailed = ref(false)
const renderFailures = ref(0)
// The newest drawing could not import the chart's code. Where a redeploy has replaced its chunk, a Retry asks for the same chunk
// again and fails every time, and only reloading the page loads the new one: the chart area says so, and offers the reload.
const chartCodeNotLoaded = ref(false)
let codeImportFailed = false
// a Retry that works hands its focus on to the chart it drew
useFocusAfterRetry(renderFailed, noticeEl, stageEl)
// A drawing that fails while the focus is in the toolbar, the legend or on the chart puts them out of reach (inert), which would
// drop the focus to the page's body: it goes to the notice's Retry button instead. A focus anywhere else stays where it is.
watch(renderFailed, async (failed) => {
  if (!failed || ![toolbarEl.value, frameEl.value].some(element => element?.contains(document.activeElement)))
    return
  await nextTick()
  noticeEl.value?.querySelector('button')?.focus()
}, { flush: 'pre' })

async function loadChartCode() {
  try {
    echarts ??= (await import('~/utils/echarts-loader')).loadEcharts()
  }
  catch (error) {
    codeImportFailed = true
    throw error
  }
  return echarts
}
function reloadPage() {
  // forced: the user's click, not a reload loop, which is what Nuxt's guard stops
  reloadNuxtApp({ force: true })
}

let isRendering = false
let renderPending = false
// what the chart on the page was drawn from: a drawing for the same is none
let drawnFrom: unknown[] | null = null
const drawInputs = () => [frame.value, theme.value, props.series, hidden.value, props.large, locale.value, bounds.value]

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
  if (sameExplorerWindow({ start, end }, win.value))
    return
  applyWindow({ start, end })
}

function disposeChart() {
  chart?.dispose()
  chart = null
  drawnFrom = null
}

/** The crosshair of the moment: what is drawn over the lines, merged into the option and not a drawing of its own */
const crosshair = computed(() => {
  const time = dismissed.value || cursorX.value === null ? null : cursor.value
  return { time, rows: time === null ? [] : readoutRows(shown.value, time) }
})
function drawCrosshair() {
  if (!chart)
    return
  chart.setOption(cursorUpdate(theme.value, crosshair.value.time, crosshair.value.rows))
}

async function draw() {
  await nextTick()
  const input = optionInput()
  if (!chartEl.value || !input || !frame.value) {
    disposeChart()
    return
  }
  performance.mark('explorer:draw-start')
  await loadChartCode()
  // the page may have changed under the await
  const el = chartEl.value
  const current = optionInput()
  const f = frame.value
  if (!el || !current || !f || !echarts) {
    disposeChart()
    return
  }
  if (!chart || chart.getDom() !== el) {
    disposeChart()
    chart = echarts.init(el, null, { renderer: 'svg', width: f.width, height: f.height })
    chart.on('datazoom', onDataZoom)
  }
  chart.resize({ width: f.width, height: f.height })
  chart.setOption(buildExplorerOption(current, f), { notMerge: true })
  // the size it is drawn at, as a viewBox: on paper (main.css) the SVG is as wide as the sheet and its content is scaled with it
  el.querySelector('svg')?.setAttribute('viewBox', `0 0 ${f.width} ${f.height}`)
  drawnFrom = drawInputs()
  el.dataset.chartScheme = current.theme.dark ? 'dark' : 'light'
  el.dataset.drawn = 'true'
  // the window the chart shows, in ms since the epoch: what a test reads a zoom by
  el.dataset.window = `${current.window.start}/${current.window.end}`
  drawCrosshair()
  performance.mark('explorer:drawn')
}

watch(() => [frame.value, theme.value, props.series, hidden.value, props.large, locale.value, bounds.value], () => void render())
watch(crosshair, () => drawCrosshair())

onMounted(() => {
  measure()
  if (typeof ResizeObserver !== 'undefined' && rootEl.value) {
    observer = new ResizeObserver(() => measure())
    observer.observe(rootEl.value)
  }
  void render()
})
onBeforeUnmount(() => {
  observer?.disconnect()
  document.removeEventListener('keydown', onDocumentKeydown)
  disposeChart()
})

// -- saving the image ---------------------------------------------------------------------------------------------

/**
 * The chart as an SVG of the size it is shown at, in the light theme whatever the page shows: drawn again, off screen, in
 * the window it is zoomed to, with the series the legend has on. The paper is part of the image: a vector with dark text on
 * nothing is unreadable on a dark page that shows it.
 */
async function renderSvg(): Promise<SvgPart & { paper: string }> {
  const light = readDocumentChartTheme('light')
  const paper = light.paper || '#ffffff'
  const input = optionInput({ theme: light, background: paper })
  if (!input)
    throw new Error('There is no chart to save')
  const f = explorerFrame(input)
  const lib = await loadChartCode()
  const copy = lib.init(null as any, null, { renderer: 'svg', ssr: true, width: f.width, height: f.height })
  try {
    copy.setOption(buildExplorerOption(input, f))
    return { svg: copy.renderToSVGString(), width: f.width, height: f.height, paper }
  }
  finally {
    copy.dispose()
  }
}

/** Saves the chart as a file of the size it is shown at (one pixel to a pixel, as it always was) */
async function save(options: { format: ImageFormat, filename: string }) {
  const { svg, width: imageWidth, height: imageHeight, paper } = await renderSvg()
  const blob = await svgToBlob(svg, { format: options.format, width: imageWidth, height: imageHeight, scale: 1, background: paper })
  downloadBlob(blob, `${options.filename}.${options.format}`)
}

/** The camera of the toolbar: a PNG named `newplot`, as Plotly's was */
function saveCamera() {
  void save({ format: 'png', filename: props.cameraFile }).then(() => {
    toast.add({ title: t('dataViewer.downloaded'), description: t('dataViewer.downloadedChart', { format: 'PNG' }), color: 'success' })
  }, (error: unknown) => {
    console.error('The chart image could not be saved', error)
    toast.add({ title: t('dataViewer.chartImageNotSaved'), color: 'error' })
  })
}

defineExpose({ save, renderSvg, resetZoom, zoomIn, zoomOut, shift, win, atStart, atEnd, atMaxZoom, atMinZoom, renderFailed, renderFailures, width, hidden })

const selectionStyle = computed(() => {
  const d = drag.value
  const plot = frame.value?.plot
  if (!d?.active || !plot)
    return null
  return { left: `${Math.min(d.x0, d.x1)}px`, width: `${Math.abs(d.x1 - d.x0)}px`, top: `${plot.top}px`, height: `${plot.height}px` }
})
</script>

<template>
  <div ref="rootEl" class="explorer-chart app-chart">
    <div
      v-if="renderFailed"
      ref="chartNotice"
      class="flex flex-wrap items-center justify-center gap-3 pb-4 text-red-600 dark:text-red-400"
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

    <!-- the single-pointer ways to what a drag, a pinch and the keys do (WCAG 2.5.7), named by what they do -->
    <!-- inert while the chart could not be drawn: nothing to zoom, read or save of an empty chart -->
    <div ref="toolbarEl" class="xc-toolbar" role="group" :aria-label="t('dataViewer.chart.zoomGroup')" :inert="renderFailed || undefined">
      <UButton
        icon="i-ph-caret-left" size="sm" variant="outline" color="neutral" class="shrink-0"
        :title="t('dataViewer.chart.earlier')" :aria-label="t('dataViewer.chart.earlier')" :disabled="atStart" @click="shift(-0.5)"
      />
      <UButton
        icon="i-ph-caret-right" size="sm" variant="outline" color="neutral" class="shrink-0"
        :title="t('dataViewer.chart.later')" :aria-label="t('dataViewer.chart.later')" :disabled="atEnd" @click="shift(0.5)"
      />
      <UButton
        icon="i-ph-magnifying-glass-minus" size="sm" variant="outline" color="neutral" class="shrink-0"
        :title="t('dataViewer.chart.zoomOut')" :aria-label="t('dataViewer.chart.zoomOut')" :disabled="atMinZoom" @click="zoomOut()"
      />
      <UButton
        icon="i-ph-magnifying-glass-plus" size="sm" variant="outline" color="neutral" class="shrink-0"
        :title="t('dataViewer.chart.zoomIn')" :aria-label="t('dataViewer.chart.zoomIn')" :disabled="atMaxZoom" @click="zoomIn()"
      />
      <UButton
        icon="i-ph-arrow-counter-clockwise" size="sm" variant="outline" color="neutral" class="shrink-0"
        :title="t('dataViewer.chart.resetZoom')" :aria-label="t('dataViewer.chart.resetZoom')" :disabled="atMinZoom" @click="resetZoom()"
      />
      <UButton
        icon="i-ph-camera" size="sm" variant="outline" color="neutral" class="shrink-0"
        :title="t('dataViewer.chart.savePng')" :aria-label="t('dataViewer.chart.savePng')" @click="saveCamera()"
      />
    </div>

    <div ref="frameEl" class="xc-frame" :style="{ height: `${stageHeight}px` }" :inert="renderFailed || undefined">
      <!-- The legend is drawn in the chart (so that a saved image has it) and operated from here: a button over each of its items, which
           turns the series off and on and says which it is. They come before the chart in the tab order. -->
      <div v-if="frame && frame.legend.items.length" class="xc-legend" role="group" :aria-label="t('dataViewer.chart.legendGroup')" :style="{ height: `${frame.legend.height}px` }">
        <button
          v-for="item in frame.legend.items"
          :key="item.id"
          type="button"
          class="xc-legend-item"
          :aria-pressed="!hidden.has(item.id)"
          :aria-label="series[item.index]?.name"
          :title="series[item.index]?.name"
          :data-series="item.id"
          :style="{ left: `${item.x - 4}px`, top: `${item.y - 1}px`, width: `${item.width + 8}px`, height: `${item.height}px` }"
          @click="toggleSeries(item.id)"
        />
      </div>

      <!-- a figure, as the app's other charts, and no landmark; one tab stop for the whole chart (Chartability) -->
      <div
        ref="stageEl"
        class="xc-stage"
        role="figure"
        tabindex="0"
        :aria-label="label"
        :aria-describedby="[describedBy, hintId].filter(Boolean).join(' ')"
        aria-keyshortcuts="ArrowLeft ArrowRight PageUp PageDown Home End Plus - 0 Escape"
        :style="{ width: `${width}px`, height: `${stageHeight}px` }"
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
        <div ref="chartEl" class="xc-canvas" aria-hidden="true" :style="{ width: `${width}px`, height: `${stageHeight}px` }" />
        <div v-if="selectionStyle" class="xc-selection" aria-hidden="true" :style="selectionStyle" />
        <div
          v-if="readout"
          :id="readoutId"
          ref="readoutEl"
          class="xc-readout"
          role="group"
          :aria-label="t('dataViewer.chart.readoutFor', { moment: readout.time })"
          :style="readoutStyle"
          data-testid="explorer-readout"
        >
          <div class="flex items-start gap-2">
            <div class="min-w-0 flex-1 font-semibold text-highlighted tabular-nums">
              {{ readout.time }}
            </div>
            <button
              type="button"
              class="xc-close"
              :aria-label="t('dataViewer.chart.readoutClose')"
              :title="t('dataViewer.chart.readoutClose')"
              @click.stop="dismiss"
            >
              <UIcon name="i-ph-x" class="size-3.5" aria-hidden="true" />
            </button>
          </div>
          <dl class="mt-1.5 grid grid-cols-[minmax(0,1fr)_auto] gap-x-2 gap-y-1">
            <template v-for="row in readout.rows" :key="row.id">
              <dt class="flex min-w-0 items-start gap-1.5 text-toned">
                <span class="xc-swatch" aria-hidden="true" :style="{ background: row.colour }" />
                <span class="min-w-0 break-words">{{ row.name }}</span>
              </dt>
              <dd class="m-0 text-end font-medium text-highlighted tabular-nums">
                {{ row.value }}
              </dd>
            </template>
          </dl>
        </div>
      </div>
    </div>
    <p :id="hintId" class="sr-only">
      {{ t('dataViewer.chart.keysHint') }}
    </p>
    <!-- said when a key steps the crosshair, and not for a pointer's hover -->
    <p class="sr-only" role="status" aria-live="polite" aria-atomic="true" data-testid="explorer-announce">
      {{ announcement }}
    </p>
  </div>
</template>

<style scoped>
.explorer-chart {
  position: relative;
}
.xc-toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.25rem;
  padding-bottom: 0.5rem;
}
.xc-frame {
  position: relative;
  max-width: 100%;
}
.xc-stage {
  position: relative;
  max-width: 100%;
  /* the pinch is the chart's, not the page's zoom; the page still scrolls up and down */
  touch-action: pan-y;
  user-select: none;
  -webkit-user-select: none;
  cursor: crosshair;
}
.xc-stage:focus-visible {
  outline: 2px solid var(--app-focus-ring);
  outline-offset: -2px;
}
.xc-canvas {
  position: absolute;
  inset: 0 auto auto 0;
}
.xc-legend {
  position: absolute;
  z-index: 5;
  inset: 0 0 auto 0;
  pointer-events: none;
}
/* a button over each legend item: nothing of its own to see, but the focus ring and the pointer */
.xc-legend-item {
  position: absolute;
  box-sizing: border-box;
  padding: 0;
  border: 0;
  border-radius: 0.25rem;
  background: transparent;
  cursor: pointer;
  pointer-events: auto;
}
.xc-legend-item:hover {
  background: color-mix(in srgb, var(--ui-text) 8%, transparent);
}
.xc-legend-item:focus-visible {
  outline: 2px solid var(--app-focus-ring);
  outline-offset: 0;
}
.xc-selection {
  position: absolute;
  background: color-mix(in srgb, var(--app-focus-ring) 14%, transparent);
  border: 1px solid var(--app-focus-ring);
  pointer-events: none;
}
.xc-readout {
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
/* a short line in the colour of the series, as the legend has it */
.xc-swatch {
  width: 0.875rem;
  height: 0.25rem;
  margin-top: 0.5rem;
  flex-shrink: 0;
  border-radius: 0.125rem;
}
.xc-close {
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
.xc-close:hover {
  color: var(--ui-text-highlighted);
  background: var(--ui-bg-accented);
}
.xc-close:focus-visible {
  outline: 2px solid var(--app-focus-ring);
}
</style>
