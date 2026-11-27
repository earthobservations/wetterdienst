<script setup lang="ts">
import type { ECharts } from 'echarts/core'
import type { KostraQuantity, KostraTable } from '~/utils/kostra'
import { durationLabel, KOSTRA_DURATIONS, KOSTRA_RETURN_PERIODS, KOSTRA_UNITS } from '~/utils/kostra'
import { buildKostraOption, curveColour, kostraHeight, kostraReadoutRows, nearestDurationIndex } from '~/utils/kostra-option'

// The curves of the Heavy-rainfall tool (GH-4500): one depth-duration curve for each return period, drawn by Apache ECharts as SVG
// (`utils/kostra-option.ts` is the option). The legend and the readout are this component's own elements, as in the Explorer's chart:
// a pointer can move onto the readout, and the keyboard does what the pointer does. The chart is one tab stop whose arrow keys step
// through the durations (Home and End to the ends, Escape closes the readout); a tap or a move of the pointer puts the readout at the
// nearest duration. The table beside it holds every value, which is what a screen reader is pointed to.
const props = defineProps<{
  table: KostraTable
  quantity: KostraQuantity
  /** The id of the element that describes the figure (the note that says the table has the same values) */
  describedBy?: string
}>()

const { t } = useI18n()
const formatLanguage = useFormatLanguage()
const { theme } = useChartTheme()

const rootEl = ref<HTMLElement | null>(null)
const chartEl = ref<HTMLElement | null>(null)
const stageEl = ref<HTMLElement | null>(null)
const noticeEl = useTemplateRef<HTMLElement>('chartNotice')

const width = ref(0)
const height = computed(() => kostraHeight(width.value))
/** The duration the crosshair is at, by its place in the table */
const cursor = ref<number | null>(null)
const dismissed = ref(false)
const announcement = ref('')

function measure() {
  const measured = rootEl.value?.clientWidth ?? 0
  // a window that has none to measure (a test's) is a desktop's
  width.value = measured > 0 ? measured : 800
}

const format = (value: number, digits: number) => new Intl.NumberFormat(formatLanguage.value, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value)
const label = (minutes: number) => durationLabel(minutes, t)
const unit = computed(() => KOSTRA_UNITS[props.quantity])

const legend = computed(() => KOSTRA_RETURN_PERIODS.map((years, index) => ({ years, colour: curveColour(index, theme.value.dark) })))

// ---- the readout ---------------------------------------------------------------------------------------------------

/**
 * Where the readout is docked: in the corner the curves leave free, whatever the crosshair is at. That is the upper left for the depth, which
 * rises with the duration, and the upper right for the intensity, which falls. Where the crosshair is under it, it covers the dashed line and
 * no mark: the marks are on the curves, which are low there.
 */
function readoutSide(): 'start' | 'end' {
  return props.quantity === 'depth' ? 'start' : 'end'
}

const readout = computed(() => {
  if (cursor.value === null || dismissed.value)
    return null
  const minutes = KOSTRA_DURATIONS[cursor.value]!
  return {
    title: label(minutes),
    rows: kostraReadoutRows(props.table, props.quantity, cursor.value).map(row => ({
      years: row.years,
      colour: curveColour(row.colourIndex, theme.value.dark),
      text: row.value === null ? t('kostra.noValue') : format(row.value, 1),
    })),
    side: readoutSide(),
  }
})

function sentence(index: number): string {
  const minutes = KOSTRA_DURATIONS[index]!
  const rows = kostraReadoutRows(props.table, props.quantity, index)
    .map(row => `${t('kostra.returnPeriodYears', { count: row.years })}${t('common.colon')} ${row.value === null ? t('kostra.noValue') : format(row.value, 1)}`)
  return `${label(minutes)}${t('common.colon')} ${rows.join('; ')} ${unit.value}`
}

function select(index: number | null, announce = false) {
  if (index !== cursor.value)
    dismissed.value = false
  cursor.value = index
  if (announce && index !== null)
    announcement.value = sentence(index)
}

function indexAt(event: PointerEvent | MouseEvent): number {
  const left = chartEl.value?.getBoundingClientRect().left ?? 0
  return nearestDurationIndex(event.clientX - left, width.value)
}
const onReadout = (event: Event) => event.target instanceof Element && Boolean(event.target.closest('.kostra-readout'))

function onPointerMove(event: PointerEvent) {
  // a finger taps: its readout stays until it is closed or tapped away
  if (event.pointerType === 'touch' || onReadout(event))
    return
  select(indexAt(event))
}
function onPointerLeave(event: PointerEvent) {
  if (event.pointerType === 'touch')
    return
  select(null)
}
function onClick(event: MouseEvent) {
  if (onReadout(event))
    return
  select(indexAt(event))
}
function onKeydown(event: KeyboardEvent) {
  if (event.target !== stageEl.value || event.altKey || event.ctrlKey || event.metaKey)
    return
  const last = KOSTRA_DURATIONS.length - 1
  const at = cursor.value
  let next: number
  switch (event.key) {
    case 'ArrowRight':
      next = at === null ? 0 : Math.min(last, at + (event.shiftKey ? 3 : 1))
      break
    case 'ArrowLeft':
      next = at === null ? last : Math.max(0, at - (event.shiftKey ? 3 : 1))
      break
    case 'Home':
      next = 0
      break
    case 'End':
      next = last
      break
    case 'Escape':
      if (cursor.value !== null)
        dismissed.value = true
      return
    default:
      return
  }
  event.preventDefault()
  // a key that moves the crosshair brings the readout back, also where it is at the duration it was closed at (Escape at the last duration, then End)
  dismissed.value = false
  select(next, true)
}
function onBlur(event: FocusEvent) {
  // the focus left the chart: a readout the keys put there goes with it
  if (!stageEl.value?.contains(event.relatedTarget as Node | null))
    select(null)
}
function closeReadout() {
  dismissed.value = true
  stageEl.value?.focus({ preventScroll: true })
}

// ---- drawing -------------------------------------------------------------------------------------------------------

let echarts: ReturnType<typeof import('~/utils/echarts-loader').loadEcharts> | null = null
let chart: ECharts | null = null
let observer: ResizeObserver | null = null

/** The newest drawing threw (the chart's code did not load, or the drawing failed): the chart area says so, with a Retry */
const renderFailed = ref(false)
const renderFailures = ref(0)
useFocusAfterRetry(renderFailed, noticeEl, stageEl)

async function draw() {
  await nextTick()
  const el = chartEl.value
  if (!el || !width.value)
    return
  echarts ??= (await import('~/utils/echarts-loader')).loadEcharts()
  // the page may have changed under the await
  if (!chartEl.value || chartEl.value !== el)
    return
  if (!chart || chart.getDom() !== el) {
    chart?.dispose()
    chart = echarts.init(el, null, { renderer: 'svg', width: width.value, height: height.value })
  }
  chart.resize({ width: width.value, height: height.value })
  chart.setOption(buildKostraOption({
    table: props.table,
    quantity: props.quantity,
    theme: theme.value,
    width: width.value,
    height: height.value,
    cursor: dismissed.value ? null : cursor.value,
    format,
    durationLabel: label,
  }), { notMerge: true })
  el.querySelector('svg')?.setAttribute('viewBox', `0 0 ${width.value} ${height.value}`)
  el.dataset.drawn = 'true'
  el.dataset.chartScheme = theme.value.dark ? 'dark' : 'light'
}

async function render() {
  try {
    await draw()
    renderFailed.value = false
  }
  catch (error) {
    console.error('The chart could not be drawn', error)
    renderFailed.value = true
    renderFailures.value++
  }
}

watch([() => props.table, () => props.quantity, theme, width, cursor, dismissed, formatLanguage], () => void render())

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
  chart?.dispose()
  chart = null
})

defineExpose({ cursor, select, renderFailed, width })
</script>

<template>
  <div ref="rootEl" class="kostra-chart app-chart" data-testid="kostra-chart">
    <!-- the legend: the return period of each curve, shown as a short line in the curve's colour with its number (the colour is no cue alone) -->
    <div class="kostra-legend" data-testid="kostra-legend">
      <span class="kostra-legend-title">{{ t('kostra.returnPeriodLegend') }}</span>
      <ul class="kostra-legend-items">
        <li v-for="item in legend" :key="item.years" class="kostra-legend-item" :data-years="item.years">
          <span class="kostra-swatch" :style="{ background: item.colour }" aria-hidden="true" />
          {{ item.years }}
        </li>
      </ul>
    </div>

    <!-- what the vertical axis is, in the words of the switch above: the chart has the numbers and this has their name and unit -->
    <p class="kostra-axis-title" data-testid="kostra-axis-title">
      {{ t(`kostra.quantity.${quantity}`) }} ({{ unit }})
    </p>

    <div v-if="renderFailed" ref="chartNotice" class="flex flex-wrap items-center justify-center gap-3 py-8 text-red-600 dark:text-red-400">
      <span :key="renderFailures" role="alert" class="font-medium">{{ t('kostra.chartNotDrawn') }}</span>
      <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" data-testid="kostra-chart-retry" @click="render()" />
    </div>

    <div
      ref="stageEl"
      class="kostra-stage"
      :style="{ height: `${height}px` }"
      tabindex="0"
      role="group"
      :aria-label="t('kostra.chartLabel', { quantity: t(`kostra.quantity.${quantity}`), unit })"
      :aria-describedby="describedBy"
      :inert="renderFailed || undefined"
      data-testid="kostra-stage"
      @pointermove="onPointerMove"
      @pointerleave="onPointerLeave"
      @click="onClick"
      @keydown="onKeydown"
      @focusout="onBlur"
    >
      <div ref="chartEl" class="kostra-plot" />
      <div
        v-if="readout"
        class="kostra-readout"
        :class="readout.side === 'start' ? 'kostra-readout-start' : 'kostra-readout-end'"
        data-testid="kostra-readout"
      >
        <div class="kostra-readout-head">
          <span class="kostra-readout-title" data-testid="kostra-readout-title">{{ readout.title }}</span>
          <UButton
            icon="i-ph-x"
            size="xs"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.close')"
            data-testid="kostra-readout-close"
            @click.stop="closeReadout"
          />
        </div>
        <dl class="kostra-readout-rows">
          <div v-for="row in readout.rows" :key="row.years" class="kostra-readout-row">
            <dt>
              <span class="kostra-swatch" :style="{ background: row.colour }" aria-hidden="true" />
              {{ t('kostra.returnPeriodYears', { count: row.years }) }}
            </dt>
            <dd>{{ row.text }}</dd>
          </div>
        </dl>
      </div>
    </div>
    <p class="sr-only" role="status" aria-live="polite" data-testid="kostra-chart-announcement">
      {{ announcement }}
    </p>
  </div>
</template>

<style>
.kostra-chart {
  min-width: 0;
}
.kostra-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem 0.875rem;
  margin-bottom: 0.5rem;
  font-size: 0.8125rem;
  color: var(--ui-text-muted);
}
.kostra-legend-title {
  font-weight: 600;
  color: var(--ui-text);
}
.kostra-legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem 0.75rem;
  margin: 0;
  padding: 0;
  list-style: none;
  font-variant-numeric: tabular-nums;
}
.kostra-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
/* a short line, as a curve is: 2 px thick, 16 px long */
.kostra-swatch {
  display: inline-block;
  flex: none;
  width: 1rem;
  height: 3px;
  border-radius: 2px;
}
.kostra-axis-title {
  margin-bottom: 0.25rem;
  font-size: 0.8125rem;
  color: var(--ui-text-muted);
}
.kostra-stage {
  position: relative;
  width: 100%;
  border-radius: calc(var(--ui-radius) * 1.5);
  outline-offset: 2px;
  touch-action: pan-y;
}
.kostra-stage:focus-visible {
  outline: 2px solid var(--app-focus-ring, var(--ui-primary));
}
.kostra-plot {
  width: 100%;
  height: 100%;
}
.kostra-readout {
  position: absolute;
  top: 0.5rem;
  z-index: 2;
  min-width: 8.5rem;
  padding: 0.375rem 0.625rem 0.5rem;
  border: 1px solid var(--ui-border-accented);
  border-radius: calc(var(--ui-radius) * 1.5);
  background: var(--ui-bg);
  color: var(--ui-text);
  font-size: 0.8125rem;
  box-shadow: 0 2px 8px rgb(15 23 42 / 0.15);
  font-variant-numeric: tabular-nums;
}
.kostra-readout-start {
  inset-inline-start: 3.25rem;
}
.kostra-readout-end {
  inset-inline-end: 1rem;
}
.kostra-readout-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.125rem;
}
.kostra-readout-title {
  font-weight: 700;
  color: var(--ui-text-highlighted);
}
.kostra-readout-rows {
  margin: 0;
}
.kostra-readout-row {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
}
.kostra-readout-row dt {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  color: var(--ui-text-muted);
}
.kostra-readout-row dd {
  margin: 0;
  font-weight: 600;
}
/* paper is light, whatever the screen shows (main.css scales the chart's SVG to the sheet) */
@media print {
  .kostra-readout {
    display: none;
  }
}
</style>
