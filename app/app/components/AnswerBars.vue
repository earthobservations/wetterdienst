<script setup lang="ts">
import type { Bar } from '~/utils/answers'
import { formatNumber } from '~/utils/format'

// The chart that backs an answer: one bar per hour, day or year, the one asked about in the colour of its question.
// Bars of HTML, not a plotting library: a chart of thirty bars needs no axes to zoom, it reflows with the page and
// its text, and it prints. The bars are decoration for a reader who sees them; the caption says what they show, and
// "Show the values" opens the numbers as a table, for a screen reader and for anyone who wants them exact.
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
  tone?: 'rain' | 'warmth' | 'wind' | 'sun'
}>(), { diverging: false, every: 1, tone: 'rain' })

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
  <figure class="answer-bars" :class="`answer-bars--${tone}`" :aria-labelledby="`${id}-caption`">
    <figcaption :id="`${id}-caption`" class="text-sm font-semibold text-highlighted mb-3">
      {{ caption }}
    </figcaption>
    <div class="flex gap-2" aria-hidden="true">
      <div class="flex flex-col justify-between text-xs text-muted text-right shrink-0 py-0.5 min-w-10">
        <span>{{ axisTop }}</span>
        <span>{{ axisBottom }}</span>
      </div>
      <div class="flex-1 min-w-0">
        <div class="answer-bars__plot relative h-36 flex items-stretch gap-px sm:gap-0.5">
          <div v-if="diverging" class="absolute inset-x-0 border-t border-default" :style="{ top: `${zero * 100}%` }" />
          <div v-for="bar in bars" :key="bar.key" class="relative flex-1 min-w-0">
            <div
              class="app-bar-fill absolute inset-x-0 rounded-[2px]"
              :data-highlight="bar.highlight ? 'true' : 'false'"
              :style="barStyle(bar)"
            />
          </div>
        </div>
        <div class="flex gap-px sm:gap-0.5 mt-1 text-[0.6875rem] leading-tight text-muted">
          <span v-for="(bar, index) in bars" :key="bar.key" class="flex-1 min-w-0 text-center overflow-visible whitespace-nowrap" :class="{ 'font-bold text-highlighted': bar.highlight }">
            {{ showLabel(index) || bar.highlight ? bar.label : '' }}
          </span>
        </div>
      </div>
    </div>
    <details class="mt-3">
      <summary class="cursor-pointer text-sm font-medium text-primary rounded-sm w-fit">
        {{ t('ask.showValues') }}
      </summary>
      <div class="mt-2 max-h-64 overflow-auto rounded-md border border-default" tabindex="0" role="region" :aria-label="caption">
        <table class="w-full text-sm">
          <thead class="bg-elevated sticky top-0">
            <tr>
              <th scope="col" class="text-left font-semibold px-3 py-1.5">
                {{ t('ask.tableWhen') }}
              </th>
              <th scope="col" class="text-right font-semibold px-3 py-1.5">
                {{ unit }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="bar in bars" :key="bar.key" class="border-t border-default" :class="{ 'font-bold': bar.highlight }">
              <th scope="row" class="text-left font-normal px-3 py-1" :class="{ 'font-bold': bar.highlight }">
                {{ rowLabel ? rowLabel(bar) : bar.label }}
              </th>
              <td class="text-right px-3 py-1">
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
.app-bar-fill {
  background: color-mix(in oklab, var(--ui-text-muted) 45%, transparent);
}
.answer-bars--rain .app-bar-fill[data-highlight="true"],
.answer-bars--rain .app-bar-fill {
  background: var(--color-rain);
}
.answer-bars--warmth .app-bar-fill[data-highlight="true"] {
  background: var(--color-warmth);
}
.answer-bars--wind .app-bar-fill[data-highlight="true"] {
  background: var(--color-wind);
}
.answer-bars--sun .app-bar-fill[data-highlight="true"] {
  background: var(--color-sun);
}
/* the bar asked about stands out by its edge too, not by colour alone (1.4.1) */
.app-bar-fill[data-highlight="true"] {
  box-shadow: 0 0 0 2px var(--ui-text-highlighted);
}
@media print {
  .app-bar-fill {
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
  }
}
</style>
