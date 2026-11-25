<script setup lang="ts">
import type { ECharts } from 'echarts/core'
/**
 * The climate stripes (GH-4068), drawn by Apache ECharts as SVG: a stripe for each year, the optional availability line,
 * and the title, the years and the source. The chart is as wide as the column gives it (up to the
 * cap of `.app-chart`) and as high as that width gives it at a fixed ratio of the stripes (`STRIPES_RATIO`, GH-4133).
 *
 * Where the pointer can do more than the keyboard, the keyboard can do the same (WCAG 2.1.1, 2.5.7): the chart is one
 * tab stop whose arrow keys step through the years, whose `+`, `-` and `0` zoom, and whose toolbar's buttons do what a
 * dragged box, a pinch and the keys do.
 *
 * The readout (what a tooltip would be) is an element of this component and not the library's: a pointer can move
 * onto it, it stays until the pointer or the focus leaves, and Escape closes it (WCAG 1.4.13).
 */
import type { StripesKind } from '#shared/types/api'
import type { ImageFormat } from '~/utils/chart-image'
import type { StripesReferenceView } from '~/utils/stripes'
import type { StripesInput, StripesVariant, StripesView, YearWindow } from '~/utils/stripes-model'
import type { StripesDisplay, StripesOptionInput } from '~/utils/stripes-option'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { downloadBlob, svgToBlob } from '~/utils/chart-image'
import { readDocumentChartTheme } from '~/utils/chart-theme'
import { formatNumber, formatSigned } from '~/utils/format'
import { processingNote } from '~/utils/processing-note'
import { barsSubtitle, stripeBand, stripeColour, stripesReferenceText, wrapChartTitle } from '~/utils/stripes'
import { buildStripesModel, clampWindow, fullWindow, isStripesDrawing, MIN_SPAN_STRIPES, panWindow, revealYear, sameWindow, STRIPES_VIEWS, zoomWindow } from '~/utils/stripes-model'
import { buildStripesOption, CAMERA_SCALE, CAMERA_WIDTH, extraLinesHeight, frameOf, STRIPES_FONT_FAMILY, stripesChartHeight, stripesLayout, SUBTITLE_SIZE, TITLE_PADDING, TITLE_SIZE, windowUpdate, xOfYear } from '~/utils/stripes-option'

const props = withDefaults(defineProps<{
  values: readonly StripesInput[]
  /** what the values' classes are relative to: what the line under the chart, the bars' subtitle and the image's caption say */
  reference: StripesReferenceView
  kind: StripesKind
  /** the unit's symbol, which the readout names the values in */
  unit: string
  title: string
  display: StripesDisplay
  /**
   * What is shown of the years: stripes, bars, bars with a scale (GH-4156) or the table (GH-4233); the switch above asks the page to change it.
   * The table is drawn by the page, under the switch: this component draws nothing then and has no toolbar.
   */
  variant?: StripesView
  /** the figure's name, and the element that describes it */
  label?: string
  describedBy?: string
  /** the name of the camera's file, without its extension */
  cameraFile: string
  /** the source line under the stripes where it is not DWD's (NOAA's GHCN daily, GH-4078) */
  sourceText?: string
  /** how the day's temperature was made, for a station of GHCN daily: one short line of a saved image, under what the colours are relative to (GH-4078) */
  methodLine?: string
  /** A line of a saved image on where the days came from where that is not NOAA's own file: the mirror on AWS, whose file may end early (GH-4390) */
  noticeLine?: string
}>(), { variant: 'stripes' })
const emit = defineEmits<{ 'update:variant': [variant: StripesView] }>()

/** Whether a chart is shown: the table is the one view that has none */
const drawing = computed(() => isStripesDrawing(props.variant))
// how the years are drawn: the one chosen last, kept while the table is shown, so that the image and the camera are of what the chart goes back to
const chartVariant = ref<StripesVariant>(isStripesDrawing(props.variant) ? props.variant : 'stripes')
watch(() => props.variant, (next) => {
  if (isStripesDrawing(next))
    chartVariant.value = next
})

const { t, locale } = useI18n()
const toast = useToast()
const { theme } = useChartTheme()

const rootEl = ref<HTMLElement | null>(null)
const stageEl = ref<HTMLElement | null>(null)
const chartEl = ref<HTMLElement | null>(null)
const readoutEl = ref<HTMLElement | null>(null)
const noticeEl = useTemplateRef<HTMLElement>('chartNotice')
const toolbarEl = ref<HTMLElement | null>(null)
const scrollerEl = ref<HTMLElement | null>(null)

const hintId = useId()
const readoutId = useId()

// the year the crosshair stands at, and whether the pointer, a key or a touch put it there
const cursor = ref<number | null>(null)
const cursorSource = ref<'pointer' | 'keyboard' | 'touch'>('pointer')
// where the pointer is in the chart, in px from its top, which the readout is level with
const pointerY = ref<number | null>(null)
const dismissed = ref(false)
const announcement = ref('')

// -- what is drawn ------------------------------------------------------------------------------------------------

const model = computed(() => buildStripesModel(props.values))
const bounds = computed<YearWindow | null>(() => model.value ? fullWindow(model.value) : null)
/** The years that have a stripe, in order, with where each is in the model */
const stripes = computed(() => (model.value?.years ?? []).map((year, index) => ({ year, index })).sort((a, b) => a.year - b.year))

// what the column gives the chart, in px; the width of a window that has none to measure (a test's) is a desktop's
const width = ref(0)
function measure() {
  // laid out for paper, the column is another width: the chart is scaled to the sheet by CSS (main.css) and is not drawn again for it
  if (window.matchMedia?.('print').matches)
    return
  const measured = rootEl.value?.clientWidth ?? 0
  width.value = measured > 0 ? measured : 800
}
const font = `${TITLE_SIZE}px ${STRIPES_FONT_FAMILY}`
// a title that does not fit the chart's width is broken into lines (GH-3961)
function titleLinesFor(chartWidth: number): string[] {
  return props.display.showTitle ? wrapChartTitle(props.title, chartWidth - 2 * TITLE_PADDING, font).text.split('<br>') : []
}
const titleLines = computed(() => titleLinesFor(width.value))
// what the bars with a scale are relative to, under the title and broken into the lines its width needs (the others have none)
const subtitleFont = `${SUBTITLE_SIZE}px ${STRIPES_FONT_FAMILY}`
function subtitleLinesFor(chartWidth: number): string[] {
  return chartVariant.value === 'barsScale' ? wrapChartTitle(barsSubtitle(props.reference, props.unit, t), chartWidth - 2 * TITLE_PADDING, subtitleFont).text.split('<br>') : []
}
const subtitleLines = computed(() => subtitleLinesFor(width.value))
const frame = computed(() => frameOf({ variant: chartVariant.value, subtitleLines: subtitleLines.value }))
// the stripes keep their shape: the chart is as high as its width gives it, the title and the years on top (GH-4133); the bars are as high
const height = computed(() => stripesChartHeight(props.display, width.value, titleLines.value.length, { frame: frame.value }))
const layout = computed(() => stripesLayout(props.display, width.value, height.value, titleLines.value.length, 0, frame.value))
const variantOptions = computed(() => STRIPES_VIEWS.map(value => ({ value, label: t(`stripes.variant.${value}`) })))
/** The numbers of the bars' y axis, with their sign, in the language of the page */
const formatTick = (value: number, decimals: number) => value === 0 ? formatNumber(0, locale.value, 0) : formatSigned(value, locale.value, decimals)

// -- the window of years the chart shows --------------------------------------------------------------------------

/** Null for all of it, which a reset goes back to */
const custom = ref<YearWindow | null>(null)
const win = computed<YearWindow>(() => custom.value ?? bounds.value ?? { start: 0, end: 1 })

function applyWindow(next: YearWindow) {
  const b = bounds.value
  if (!b)
    return
  const clamped = clampWindow(next, b)
  custom.value = sameWindow(clamped, b) ? null : clamped
}
function resetZoom() {
  custom.value = null
  dismissed.value = false
}
/** One step of the zoom buttons and keys: a third more or less of the years across */
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
const atMaxZoom = computed(() => win.value.end - win.value.start <= MIN_SPAN_STRIPES)
const atMinZoom = computed(() => !bounds.value || custom.value === null)

// other values for other years start the chart over; the same years, as a unit changed, keep the zoom
watch(bounds, (next, previous) => {
  if (!previous || !next || previous.start !== next.start || previous.end !== next.end) {
    custom.value = null
    cursor.value = null
  }
})

// -- the readout --------------------------------------------------------------------------------------------------

function formatValue(value: number): string {
  return `${formatNumber(value, locale.value, 2)} ${props.unit}`.trim()
}

function rowOf(year: number | null) {
  const m = model.value
  if (!m || year === null)
    return null
  const index = m.years.indexOf(year)
  return index < 0 ? null : { year, index, value: m.values[index]!, stripeClass: m.classes[index]!, anomaly: m.anomalies[index]! }
}

const outerPx = computed(() => width.value)
const cursorBox = computed(() => {
  const row = rowOf(cursor.value)
  if (!row || dismissed.value)
    return null
  const left = xOfYear(row.year - 0.5, layout.value, win.value)
  const right = xOfYear(row.year + 0.5, layout.value, win.value)
  const plot = layout.value.plot
  // a stripe wholly outside the window is out of sight, and so is what points at it
  if (right < plot.left || left > plot.left + plot.width)
    return null
  const x0 = Math.max(plot.left, left)
  const x1 = Math.min(plot.left + plot.width, right)
  return { left: x0, width: Math.max(2, x1 - x0), top: layout.value.stripes.top, height: layout.value.stripes.height }
})

const readout = computed(() => {
  const m = model.value
  const row = rowOf(cursor.value)
  if (!m || !row || !cursorBox.value)
    return null
  const rows = [{ id: 'value', label: t('stripes.hoverValue'), value: formatValue(row.value) }]
  // the class as `stripes-scale.ts` gives it, with how far the year lies from the mean of the reference
  rows.push({ id: 'class', label: t('stripes.table.class'), value: `${t(`stripes.table.classes.${props.kind}.${stripeBand(row.stripeClass)}`)} (${formatSigned(row.anomaly, locale.value, 1)} ${props.unit})`.trim() })
  return {
    year: String(row.year),
    colour: stripeColour(props.kind, row.stripeClass),
    rows,
  }
})

const READOUT_WIDTH = 200
/** What the readout's three rows and its year are high, which a readout that is level with the pointer is kept clear of the chart's foot by */
const READOUT_HEIGHT = 108
const READOUT_OVERLAP = 4
const readoutPx = computed(() => Math.min(READOUT_WIDTH, Math.max(120, Math.round(outerPx.value * 0.5))))
/**
 * Next to the stripe it is for, on the side that has room, and level with the pointer: the pointer moves onto it from the
 * stripe's edge without crossing another stripe, which would change what it says (1.4.13, hoverable). A key puts it at the
 * top of the stripes.
 */
const readoutStyle = computed(() => {
  const box = cursorBox.value
  const stripes = layout.value.stripes
  const plot = layout.value.plot
  const width = readoutPx.value
  const edge = outerPx.value - 4
  // a few px over the stripe's own edge: a pointer that leaves the stripe is on the readout and not on its neighbour, however the
  // edge falls on the pixels
  const left = box
    ? (box.left + box.width + width - READOUT_OVERLAP <= edge ? box.left + box.width - READOUT_OVERLAP : Math.max(4, box.left - width + READOUT_OVERLAP))
    : plot.left
  const byPointer = cursorSource.value !== 'keyboard' && pointerY.value !== null
  const top = byPointer
    ? Math.min(stripes.top + stripes.height - READOUT_HEIGHT, Math.max(stripes.top, pointerY.value! - 20))
    : stripes.top + 8
  return { top: `${top}px`, left: `${Math.min(left, edge - width)}px`, width: `${width}px` }
})

/**
 * Puts the crosshair at a year. A pointer's move to the year it is at already brings nothing back that Escape took away:
 * a jitter of a pixel is no new hover (1.4.13); a key, a tap or another year is.
 */
function select(year: number | null, source: 'pointer' | 'keyboard' | 'touch') {
  const same = year === cursor.value && source === cursorSource.value
  cursor.value = year
  cursorSource.value = source
  if (year !== null && (!same || source !== 'pointer'))
    dismissed.value = false
}
function dismiss() {
  // the Close button is what has the focus where it is used (a click, Enter, or Escape while it has it), and it goes with the
  // readout: the focus is handed to the chart first, or it falls to the page's body
  if (readoutEl.value?.contains(document.activeElement))
    stageEl.value?.focus({ preventScroll: true })
  dismissed.value = true
}

function readoutSentence(year: number): string {
  const row = rowOf(year)
  if (!row)
    return ''
  return `${row.year}${t('common.colon')} ${t('stripes.hoverValue')}${t('common.colon')} ${formatValue(row.value)}`
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

// the table has no crosshair: it is not left standing for the chart to find again
watch(drawing, (shown) => {
  if (!shown) {
    cursor.value = null
    drag.value = null
  }
})

function stageX(event: PointerEvent | MouseEvent): number {
  return event.clientX - (stageEl.value?.getBoundingClientRect().left ?? 0)
}
function yearAtX(x: number): number {
  const plot = layout.value.plot
  const w = win.value
  return w.start + ((x - plot.left) / plot.width) * (w.end - w.start)
}
function stageY(event: PointerEvent | MouseEvent): number {
  return event.clientY - (stageEl.value?.getBoundingClientRect().top ?? 0)
}
const insidePlot = (x: number) => x >= layout.value.plot.left && x <= layout.value.plot.left + layout.value.plot.width
/** Whether a point is on the stripes: the title, the years and the source around them, and the margin the availability line lies in, are not */
function onStripes(x: number, y: number): boolean {
  const { top, height } = layout.value.stripes
  return insidePlot(x) && y >= top && y <= top + height
}
const onReadout = (event: Event) => !!readoutEl.value && event.target instanceof Node && readoutEl.value.contains(event.target)
/** The year of the stripe at `x`, which a year without a value has none of */
function stripeAt(x: number): number | null {
  const year = Math.round(yearAtX(x))
  return stripes.value.some(stripe => stripe.year === year) ? year : null
}

function onPointerDown(event: PointerEvent) {
  // a mouse drags a box to zoom to; a touch pinches, and the library's own gesture does it
  if (event.pointerType !== 'mouse' || event.button !== 0 || onReadout(event))
    return
  const x = stageX(event)
  if (!onStripes(x, stageY(event)))
    return
  drag.value = { x0: x, x1: x, active: false }
  ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
}
function onPointerMove(event: PointerEvent) {
  if (event.pointerType === 'touch' || onReadout(event))
    return
  const x = stageX(event)
  const plot = layout.value.plot
  const y = stageY(event)
  pointerY.value = y
  if (drag.value) {
    const clamped = Math.min(plot.left + plot.width, Math.max(plot.left, x))
    drag.value = { ...drag.value, x1: clamped, active: drag.value.active || Math.abs(clamped - drag.value.x0) >= 6 }
    return
  }
  const year = onStripes(x, y) ? stripeAt(x) : null
  if (year === null) {
    if (cursorSource.value === 'pointer')
      select(null, 'pointer')
    return
  }
  select(year, 'pointer')
}
function onPointerUp(event: PointerEvent) {
  const d = drag.value
  drag.value = null
  ;(event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId)
  if (!d?.active)
    return
  // a click ends a drag too, and is not a tap to select
  suppressClick = true
  applyWindow({ start: yearAtX(Math.min(d.x0, d.x1)), end: yearAtX(Math.max(d.x0, d.x1)) })
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
  const y = stageY(event)
  if (!onStripes(x, y))
    return
  const year = stripeAt(x)
  pointerY.value = y
  // a tap stays until it is closed or tapped away: there is no leaving a touch
  if (year !== null)
    select(year, (event as PointerEvent).pointerType === 'touch' ? 'touch' : 'pointer')
}

// -- the keys -----------------------------------------------------------------------------------------------------

function jump(position: number) {
  const list = stripes.value
  const b = bounds.value
  if (!list.length || !b)
    return
  const year = list[Math.min(list.length - 1, Math.max(0, position))]!.year
  select(year, 'keyboard')
  // the window follows the crosshair
  applyWindow(revealYear(win.value, year, b))
  announcement.value = readoutSentence(year)
}
function step(by: number) {
  const list = stripes.value
  if (!list.length)
    return
  if (cursor.value === null) {
    // the first stripe in the window
    jump(Math.max(0, list.findIndex(stripe => stripe.year >= win.value.start)))
    return
  }
  jump(list.findIndex(stripe => stripe.year === cursor.value) + by)
}
/** The number of stripes in a number of years from the crosshair's */
function stripesIn(years: number): number {
  const list = stripes.value
  const from = list.findIndex(stripe => stripe.year === cursor.value)
  if (from < 0)
    return years
  const target = (cursor.value ?? 0) + years
  let best = from
  list.forEach((stripe, index) => {
    if (Math.abs(stripe.year - target) < Math.abs(list[best]!.year - target))
      best = index
  })
  return best - from
}

function onKeydown(event: KeyboardEvent) {
  if (event.altKey || event.ctrlKey || event.metaKey)
    return
  if (!model.value)
    return
  switch (event.key) {
    case 'ArrowRight':
      step(1)
      break
    case 'ArrowLeft':
      step(-1)
      break
    case 'PageUp':
      step(stripesIn(-10))
      break
    case 'PageDown':
      step(stripesIn(10))
      break
    case 'Home':
      jump(0)
      break
    case 'End':
      jump(stripes.value.length - 1)
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
// A drawing that fails while the focus is in the toolbar or on the chart puts both out of reach (inert), which would drop the focus
// to the page's body: it goes to the notice's Retry button instead. A focus anywhere else stays where it is.
watch(renderFailed, async (failed) => {
  if (!failed || ![toolbarEl.value, scrollerEl.value].some(element => element?.contains(document.activeElement)))
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

function optionInput(over: Partial<StripesOptionInput> = {}): StripesOptionInput | null {
  const m = model.value
  if (!m)
    return null
  return {
    model: m,
    kind: props.kind,
    theme: theme.value,
    display: props.display,
    width: width.value,
    height: height.value,
    window: win.value,
    titleLines: titleLines.value,
    availabilityText: t('stripes.plotDataAvailability'),
    sourceText: props.sourceText ?? t('stripes.plotSource'),
    variant: chartVariant.value,
    subtitleLines: subtitleLines.value,
    formatTick,
    ...over,
  }
}

let isRendering = false
let renderPending = false
// what the chart on the page was drawn from: a drawing for the same is none
let drawnFrom: unknown[] | null = null
const drawInputs = () => [model.value, props.kind, theme.value, props.display, width.value, height.value, titleLines.value.join('\n'), locale.value, chartVariant.value, subtitleLines.value.join('\n'), drawing.value]

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
  if (sameWindow({ start, end }, win.value))
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
  if (!chartEl.value || !model.value) {
    disposeChart()
    return
  }
  performance.mark('stripes:draw-start')
  await loadChartCode()
  // the page may have changed under the await
  const el = chartEl.value
  const input = optionInput()
  if (!el || !input || !echarts) {
    disposeChart()
    return
  }
  if (!chart || chart.getDom() !== el) {
    disposeChart()
    chart = echarts.init(el, null, { renderer: 'svg', width: input.width, height: input.height })
    chart.on('datazoom', onDataZoom)
  }
  chart.resize({ width: input.width, height: input.height })
  chart.setOption(buildStripesOption(input), { notMerge: true })
  // the size it is drawn at, as a viewBox: on paper (main.css) the SVG is as wide as the sheet and its content is scaled with it
  el.querySelector('svg')?.setAttribute('viewBox', `0 0 ${input.width} ${input.height}`)
  drawnFrom = drawInputs()
  el.dataset.chartScheme = input.theme.dark ? 'dark' : 'light'
  el.dataset.drawn = 'true'
  performance.mark('stripes:drawn')
}

watch(() => [model.value, props.kind, theme.value, props.display, width.value, height.value, titleLines.value.join('\n'), locale.value, chartVariant.value, subtitleLines.value.join('\n'), drawing.value], () => void render())
// the window moves without drawing the chart again: the zoom, and the years named at the ends of it
watch(win, () => {
  const input = optionInput()
  if (chart && input)
    chart.setOption(windowUpdate(input))
})

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

/** What the colours are relative to, in the short form a saved image carries under its source */
function referenceCaption() {
  return stripesReferenceText(props.reference, t, value => formatNumber(value, locale.value, 1), 'stripes.plotReference')
}

// -- saving the image ---------------------------------------------------------------------------------------------

/**
 * Saves the stripes as a file of `width` by `height` px (times `scale`, for a raster image). A saved image is always the
 * light one, whatever the page shows: the stripes are drawn again, off screen, in the light theme, laid out for the width
 * of the image (its title is broken into lines where the image is narrow, not where the page is), in the range the stripes
 * are zoomed to. It says what its colours are relative to under the source, in lines as many as its width needs, which
 * make it higher than `height` (the image's own, from the title to the source) by their room (GH-4157).
 */
async function save(options: { format: ImageFormat, filename: string, width: number, height: number, scale: number }) {
  const { format, filename, width: imageWidth, scale } = options
  const light = readDocumentChartTheme('light')
  const lines = titleLinesFor(imageWidth)
  const wrapped = (text: string) => wrapChartTitle(text, imageWidth - 40, `14px ${STRIPES_FONT_FAMILY}`).text.split('<br>')
  // the note of what wetterdienst did to the data comes directly under the source, and with it: no source line, no note (GH-3799)
  const extraLines = [
    ...(props.display.showSource ? wrapped(processingNote(t)) : []),
    ...wrapped(referenceCaption()),
    ...(props.methodLine ? wrapped(props.methodLine) : []),
    ...(props.noticeLine ? wrapped(props.noticeLine) : []),
  ]
  const imageHeight = options.height + extraLinesHeight(props.display, extraLines.length)
  // the paper is part of the image: a vector with dark text on nothing is unreadable on a dark page that shows it
  const paper = light.paper || '#ffffff'
  const input = optionInput({ theme: light, width: imageWidth, height: imageHeight, titleLines: lines, background: paper, extraLines, subtitleLines: subtitleLinesFor(imageWidth) })
  if (!input)
    return
  const lib = await loadChartCode()
  const copy = lib.init(null as any, null, { renderer: 'svg', ssr: true, width: imageWidth, height: imageHeight })
  let svg: string
  try {
    copy.setOption(buildStripesOption(input))
    svg = copy.renderToSVGString()
  }
  finally {
    copy.dispose()
  }
  const blob = await svgToBlob(svg, { format, width: imageWidth, height: imageHeight, scale: format === 'svg' ? 1 : scale, background: paper })
  downloadBlob(blob, `${filename}.${format}`)
}

/** The camera of the toolbar: a PNG of a fixed width, whatever the width of the page, with the stripes in the shape they have on the page (not held to its least and most) */
function saveCamera() {
  void save({
    format: 'png',
    filename: props.cameraFile,
    width: CAMERA_WIDTH,
    height: stripesChartHeight(props.display, CAMERA_WIDTH, titleLinesFor(CAMERA_WIDTH).length, { clamp: false, frame: frameOf({ variant: chartVariant.value, subtitleLines: subtitleLinesFor(CAMERA_WIDTH) }) }),
    scale: CAMERA_SCALE,
  }).catch((error: unknown) => {
    console.error('The chart image could not be saved', error)
    toast.add({ title: t('dataViewer.chartImageNotSaved'), color: 'error' })
  })
}

defineExpose({ save, resetZoom, zoomIn, zoomOut, shift, win, atStart, atEnd, atMaxZoom, atMinZoom, renderFailed, renderFailures, width, height })

const selectionStyle = computed(() => {
  const d = drag.value
  if (!d?.active)
    return null
  const plot = layout.value.plot
  return { left: `${Math.min(d.x0, d.x1)}px`, width: `${Math.abs(d.x1 - d.x0)}px`, top: `${plot.top}px`, height: `${plot.height}px` }
})
</script>

<template>
  <div ref="rootEl" class="stripes-chart app-chart bleed-in bleed-chart">
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

    <!-- the way to draw the years (GH-4156) and the buttons to the chart: on one row where they fit, the switch at the left -->
    <div class="sc-controls">
      <SegmentedControl
        :model-value="variant"
        :options="variantOptions"
        :label="t('stripes.variant.label')"
        @update:model-value="emit('update:variant', $event)"
      />
      <!-- the single-pointer ways to what a drag, a pinch and the keys do (WCAG 2.5.7), named by what they do -->
      <!-- inert while the chart could not be drawn: nothing to zoom, read or save of an empty chart -->
      <div v-if="drawing" ref="toolbarEl" class="sc-toolbar" role="group" :aria-label="t('stripes.chart.zoomGroup')" :inert="renderFailed || undefined">
        <ChartToolButton
          icon="i-ph-caret-left"
          :title="t('stripes.chart.earlier')" :aria-label="t('stripes.chart.earlier')" :unavailable="atStart" @click="shift(-0.5)"
        />
        <ChartToolButton
          icon="i-ph-caret-right"
          :title="t('stripes.chart.later')" :aria-label="t('stripes.chart.later')" :unavailable="atEnd" @click="shift(0.5)"
        />
        <ChartToolButton
          icon="i-ph-magnifying-glass-minus"
          :title="t('stripes.chart.zoomOut')" :aria-label="t('stripes.chart.zoomOut')" :unavailable="atMinZoom" @click="zoomOut()"
        />
        <ChartToolButton
          icon="i-ph-magnifying-glass-plus"
          :title="t('stripes.chart.zoomIn')" :aria-label="t('stripes.chart.zoomIn')" :unavailable="atMaxZoom" @click="zoomIn()"
        />
        <ChartToolButton
          icon="i-ph-arrow-counter-clockwise"
          :title="t('stripes.chart.resetZoom')" :aria-label="t('stripes.chart.resetZoom')" :unavailable="atMinZoom" @click="resetZoom()"
        />
        <UButton
          icon="i-ph-camera" size="sm" variant="outline" color="neutral" class="shrink-0"
          :title="t('stripes.chart.savePng')" :aria-label="t('stripes.chart.savePng')" @click="saveCamera()"
        />
      </div>
    </div>

    <div v-if="drawing" ref="scrollerEl" class="sc-scroller" :style="{ height: `${height}px` }" :inert="renderFailed || undefined">
      <!-- a figure, as the app's other charts, and no landmark; one tab stop for the whole chart (Chartability) -->
      <div
        ref="stageEl"
        class="sc-stage"
        role="figure"
        tabindex="0"
        :aria-label="label"
        :aria-describedby="[describedBy, hintId].filter(Boolean).join(' ')"
        aria-keyshortcuts="ArrowLeft ArrowRight PageUp PageDown Home End Plus - 0 Escape"
        :style="{ width: `${width}px`, height: `${height}px` }"
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
        <div ref="chartEl" class="sc-canvas" aria-hidden="true" :style="{ width: `${width}px`, height: `${height}px` }" />
        <div v-if="cursorBox" class="sc-cursor" aria-hidden="true" :style="{ left: `${cursorBox.left}px`, width: `${cursorBox.width}px`, top: `${cursorBox.top}px`, height: `${cursorBox.height}px` }" />
        <div v-if="selectionStyle" class="sc-selection" aria-hidden="true" :style="selectionStyle" />
        <div
          v-if="readout"
          :id="readoutId"
          ref="readoutEl"
          class="sc-readout"
          role="group"
          :aria-label="t('stripes.chart.readoutFor', { year: readout.year })"
          :style="readoutStyle"
          data-testid="stripes-readout"
        >
          <div class="flex items-start gap-2">
            <span class="sc-swatch" aria-hidden="true" :style="{ background: readout.colour }" />
            <div class="min-w-0 flex-1 font-semibold text-highlighted tabular-nums">
              {{ readout.year }}
            </div>
            <button
              type="button"
              class="sc-close"
              :aria-label="t('stripes.chart.readoutClose')"
              :title="t('stripes.chart.readoutClose')"
              @click.stop="dismiss"
            >
              <UIcon name="i-ph-x" class="size-3.5" aria-hidden="true" />
            </button>
          </div>
          <dl class="mt-1.5 grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5">
            <template v-for="row in readout.rows" :key="row.id">
              <dt class="text-toned">
                {{ row.label }}
              </dt>
              <dd class="m-0 text-end font-medium text-highlighted tabular-nums">
                {{ row.value }}
              </dd>
            </template>
          </dl>
        </div>
      </div>
    </div>
    <p v-if="drawing" :id="hintId" class="sr-only">
      {{ t('stripes.chart.keysHint') }}
    </p>
    <!-- said when a key steps the crosshair, and not for a pointer's hover -->
    <p v-if="drawing" class="sr-only" role="status" aria-live="polite" aria-atomic="true" data-testid="stripes-announce">
      {{ announcement }}
    </p>
  </div>
</template>

<style scoped>
.stripes-chart {
  position: relative;
}
.sc-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding-bottom: 0.5rem;
}
/* The switch of the four views is as wide as its labels need, and no wider than the chart. On a phone (below 30 rem) it is two rows of two
   segments, as wide as the chart: four labels in a row ("Barres avec échelle", "Sloupce se stupnicí", "Streifen", "Tabelle") did not fit 320 px
   in Firefox, whose text is a few px wider than Chromium's, and a segment of half the chart's width has room for any of them, with a margin.
   A label may still wrap onto a second line, never run past its segment, and a segment is 44 px high, the app's own measure of a target. The
   keys are the group's (the DOM order, left to right and down) and do not change with the layout. */
.sc-controls :deep([role='radiogroup']) {
  max-width: 100%;
}
.sc-controls :deep([role='radio']) {
  min-width: 0;
}
@media (max-width: 30rem) {
  .sc-controls :deep([role='radiogroup']) {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }
  .sc-controls :deep([role='radio']) {
    justify-content: center;
    min-height: 2.75rem;
    padding-inline: 0.5rem;
    text-align: center;
    white-space: normal;
    overflow-wrap: anywhere;
  }
}
.sc-toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.25rem;
  margin-left: auto;
}
.sc-scroller {
  position: relative;
  max-width: 100%;
}
.sc-stage {
  position: relative;
  max-width: 100%;
  /* the pinch is the chart's, not the page's zoom; the page still scrolls up and down */
  touch-action: pan-y;
  user-select: none;
  -webkit-user-select: none;
  cursor: crosshair;
}
.sc-stage:focus-visible {
  outline: 2px solid var(--app-focus-ring);
  outline-offset: -2px;
}
.sc-canvas {
  position: absolute;
  inset: 0 auto auto 0;
}
/* a black ring inside a white one: 3:1 on any colour of the scale and on the paper (WCAG 1.4.11) */
.sc-cursor {
  position: absolute;
  box-sizing: border-box;
  border: 2px solid #000;
  box-shadow: 0 0 0 2px #fff;
  pointer-events: none;
}
.sc-selection {
  position: absolute;
  background: color-mix(in srgb, var(--app-focus-ring) 14%, transparent);
  border: 1px solid var(--app-focus-ring);
  pointer-events: none;
}
.sc-readout {
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
.sc-swatch {
  width: 0.875rem;
  height: 0.875rem;
  margin-top: 0.1875rem;
  flex-shrink: 0;
  border-radius: 0.1875rem;
  border: 1px solid var(--ui-border-accented);
}
.sc-close {
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
.sc-close:hover {
  color: var(--ui-text-highlighted);
  background: var(--ui-bg-accented);
}
.sc-close:focus-visible {
  outline: 2px solid var(--app-focus-ring);
}
</style>
