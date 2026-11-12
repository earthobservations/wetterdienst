<script setup lang="ts">
import type { Bar } from '~/utils/answers'
import { chooseLabels, estimateLabelWidth, labelLeft, PLOT_HEIGHT_REM, valueLabels, yearSteps } from '~/utils/axis-labels'
import { formatNumber } from '~/utils/format'

// The chart that backs an answer (GH-3518): one bar per hour, day or year, the one asked about marked. Bars of HTML, not
// a plotting library: a chart of thirty bars needs no axes to zoom, it reflows with the page and its text, it follows the
// colour scheme with the page's tokens and it prints. The bars are decoration for a reader who sees them (the
// caption says what they show), and "Show the values" opens the numbers as a table, for a screen reader and for
// anyone who wants them exact. The bars are in the colour of action, the logo's blue, and the grey of the hairlines
// for the rest: the four colours of the tiles belong to the tools.
const props = withDefaults(defineProps<{
  bars: Bar[]
  /** What the chart shows, with its unit: the figure's caption */
  caption: string
  unit: string
  /** Bars below zero hang from a line in the middle (differences from a normal) */
  diverging?: boolean
  /** How a bar's label is written in the table, where it differs from the label under the axis */
  rowLabel?: (bar: Bar) => string
  /**
   * Which labels to write under the axis where the bars carry no year: every n-th bar, or a multiple of it where
   * that is too many for the width
   */
  every?: number
  /** All bars in the colour of action (the hours of a day), or only the one asked about (a year among years) */
  emphasis?: 'all' | 'one'
}>(), { diverging: false, every: 1, emphasis: 'all' })

const { t, locale } = useI18n()
const id = useId()

const values = computed(() => props.bars.map(bar => bar.value ?? 0))
const top = computed(() => Math.max(0, ...values.value))
const bottom = computed(() => Math.min(0, ...values.value))
const span = computed(() => (top.value - bottom.value) || 1)
/** Where zero is, from the top of the plot, as a share of its height */
const zero = computed(() => top.value / span.value)

function barStyle(bar: Bar) {
  if (bar.value === null)
    return { height: '0' }
  const size = Math.abs(bar.value) / span.value
  return bar.value >= 0
    ? { height: `${size * 100}%`, bottom: `${(1 - zero.value) * 100}%` }
    : { height: `${size * 100}%`, top: `${zero.value * 100}%` }
}

const format = (value: number | null) => value === null ? '–' : formatNumber(value, locale.value, 1)
const valueAxis = computed(() => valueLabels(top.value, bottom.value, props.diverging).map(label => ({
  ...label,
  text: `${label.value === 0 ? '0' : format(label.value)} ${props.unit}`,
})))

// The labels under the axis are placed by position and chosen by what the width allows: by year where the bars are
// years (round decades, not every n-th bar of a series with gaps), else by place in the series.
const labelRow = useTemplateRef<HTMLElement>('labelRow')
const { width } = useElementSize(labelRow)
const font = ref(11)
onMounted(() => {
  // 0.6875 rem, the size of the labels, in px
  font.value = 0.6875 * (Number.parseFloat(getComputedStyle(document.documentElement).fontSize) || 16)
})

const labelled = computed(() => {
  const byYear = props.bars.length > 0 && props.bars.every(bar => bar.at !== undefined)
  const positions = props.bars.map((bar, index) => bar.at ?? index)
  const steps = byYear
    ? yearSteps(positions)
    : Array.from({ length: Math.max(props.bars.length, 1) }, (_, at) => props.every * (at + 1))
  return chooseLabels({
    positions,
    widths: props.bars.map(bar => estimateLabelWidth(bar.label, font.value)),
    width: width.value,
    steps,
    highlights: props.bars.flatMap((bar, index) => bar.highlight ? [index] : []),
  })
})
const yearLabels = computed(() => labelled.value.map((index) => {
  const bar = props.bars[index]!
  const size = estimateLabelWidth(bar.label, font.value)
  return { bar, style: { left: labelLeft(index, props.bars.length, size), width: `${size}px` } }
}))
</script>

<template>
  <figure class="answer-bars" :data-emphasis="emphasis" :aria-labelledby="`${id}-caption`">
    <figcaption :id="`${id}-caption`" class="mb-3 text-sm font-semibold text-highlighted">
      {{ caption }}
    </figcaption>
    <div class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-2" aria-hidden="true">
      <div class="relative text-right text-xs leading-4 text-muted" :style="{ height: `${PLOT_HEIGHT_REM}rem` }" data-testid="answer-bars-values">
        <!-- the widest label gives the column its width; the labels themselves are placed in the plot's height -->
        <span v-for="label in valueAxis" :key="`size-${label.kind}`" class="invisible block h-0 overflow-hidden whitespace-nowrap">{{ label.text }}</span>
        <span
          v-for="label in valueAxis"
          :key="label.kind"
          class="absolute right-0 whitespace-nowrap"
          :data-kind="label.kind"
          :style="{ top: `${label.rem}rem` }"
        >{{ label.text }}</span>
      </div>
      <div class="relative flex items-stretch gap-px sm:gap-0.5" :style="{ height: `${PLOT_HEIGHT_REM}rem` }" data-testid="answer-bars-plot">
        <div v-if="diverging" class="absolute inset-x-0 border-t border-default" data-testid="answer-bars-zero" :style="{ top: `${zero * 100}%` }" />
        <div v-for="bar in bars" :key="bar.key" class="relative min-w-0 flex-1">
          <div
            class="answer-bar absolute inset-x-0 rounded-[2px]"
            :data-highlight="bar.highlight ? 'true' : 'false'"
            :style="barStyle(bar)"
          />
        </div>
      </div>
      <div />
      <div ref="labelRow" class="relative mt-1 h-4 text-[0.6875rem] leading-tight text-muted" data-testid="answer-bars-labels">
        <span
          v-for="{ bar, style } in yearLabels"
          :key="bar.key"
          class="absolute top-0 whitespace-nowrap text-center"
          :class="{ 'font-bold text-highlighted': bar.highlight }"
          :style="style"
          data-testid="answer-bars-label"
        >{{ bar.label }}</span>
      </div>
    </div>
    <details class="mt-3">
      <summary class="w-fit cursor-pointer rounded-sm text-sm font-medium text-primary">
        {{ t('ask.showValues') }}
      </summary>
      <div class="mt-2 max-h-64 overflow-auto rounded-md border border-default" tabindex="0" role="region" :aria-label="caption">
        <table class="w-full text-sm">
          <thead class="sticky top-0 bg-elevated">
            <tr>
              <th scope="col" class="px-3 py-1.5 text-left font-semibold">
                {{ t('ask.tableWhen') }}
              </th>
              <th scope="col" class="px-3 py-1.5 text-right font-semibold">
                {{ unit }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="bar in bars" :key="bar.key" class="border-t border-default" :class="{ 'font-bold': bar.highlight }">
              <th scope="row" class="px-3 py-1 text-left" :class="bar.highlight ? 'font-bold' : 'font-normal'">
                {{ rowLabel ? rowLabel(bar) : bar.label }}
              </th>
              <td class="px-3 py-1 text-right">
                {{ format(bar.value) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>
  </figure>
</template>

<style scoped>
/* the grey of the fields' edges (3.3:1 on a card), and the colour of action for what is asked about; a hairline
   edge in the page's text colour says it too, so the bar asked about does not rely on colour alone (WCAG 1.4.1) */
.answer-bar {
  background: var(--ui-border-accented);
}
.answer-bars[data-emphasis="all"] .answer-bar,
.answer-bar[data-highlight="true"] {
  background: var(--ui-primary);
}
.answer-bar[data-highlight="true"] {
  box-shadow: 0 0 0 2px var(--ui-text-highlighted);
}
.answer-bars[data-emphasis="all"] .answer-bar[data-highlight="true"] {
  box-shadow: none;
}
@media print {
  .answer-bar {
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
  }
}
@media (forced-colors: active) {
  .answer-bar {
    background: CanvasText;
    forced-color-adjust: none;
  }
}
</style>
