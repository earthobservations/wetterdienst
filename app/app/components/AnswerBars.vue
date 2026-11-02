<script setup lang="ts">
import type { Bar } from '~/utils/answers'
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
  /** Which labels to write under the axis: every n-th */
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
const axisTop = computed(() => `${format(top.value)} ${props.unit}`)
const axisBottom = computed(() => props.diverging ? `${format(bottom.value)} ${props.unit}` : `0 ${props.unit}`)
const showLabel = (index: number) => index % props.every === 0
</script>

<template>
  <figure class="answer-bars" :data-emphasis="emphasis" :aria-labelledby="`${id}-caption`">
    <figcaption :id="`${id}-caption`" class="mb-3 text-sm font-semibold text-highlighted">
      {{ caption }}
    </figcaption>
    <div class="flex gap-2" aria-hidden="true">
      <div class="flex min-w-10 shrink-0 flex-col justify-between py-0.5 text-right text-xs text-muted">
        <span>{{ axisTop }}</span>
        <span>{{ axisBottom }}</span>
      </div>
      <div class="min-w-0 flex-1">
        <div class="relative flex h-36 items-stretch gap-px sm:gap-0.5">
          <div v-if="diverging" class="absolute inset-x-0 border-t border-default" :style="{ top: `${zero * 100}%` }" />
          <div v-for="bar in bars" :key="bar.key" class="relative min-w-0 flex-1">
            <div
              class="answer-bar absolute inset-x-0 rounded-[2px]"
              :data-highlight="bar.highlight ? 'true' : 'false'"
              :style="barStyle(bar)"
            />
          </div>
        </div>
        <div class="mt-1 flex gap-px text-[0.6875rem] leading-tight text-muted sm:gap-0.5">
          <span v-for="(bar, index) in bars" :key="bar.key" class="min-w-0 flex-1 overflow-visible whitespace-nowrap text-center" :class="{ 'font-bold text-highlighted': bar.highlight }">
            {{ showLabel(index) || bar.highlight ? bar.label : '' }}
          </span>
        </div>
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
