<script setup lang="ts">
import type { RadarLegend } from '~/utils/radar'
import { classLimits, classRange } from '~/utils/radar'

// The legend of the radar's colours (GH-3788): the rate in mm/h each class stands for, as numbers beside its swatch, so the colours
// are never the only way to read them (WCAG 1.4.1). The classes come from the answer (`legend.classes`, lightest first); their words
// are the page's own, in the language of the page, because the answer's labels are English. A screen reader reads each class as a
// sentence ("0.1 to under 0.5 mm/h"), where the eye has the short form ("0.1–0.5") under a heading that names the unit.
const props = defineProps<{ legend: RadarLegend }>()

const { t } = useI18n()
const formatLanguage = useFormatLanguage()

const classes = computed(() => props.legend.classes.map((entry) => {
  const limits = classLimits(entry, formatLanguage.value)
  return {
    key: entry.lower,
    color: entry.color,
    short: classRange(entry, formatLanguage.value),
    long: limits.upper === null ? t('radar.legendOpen', { lower: limits.lower }) : t('radar.legendRange', { lower: limits.lower, upper: limits.upper }),
  }
}))
const none = computed(() => t('radar.legendNone', { limit: classLimits({ lower: props.legend.transparentBelow, upper: null, color: '' }, formatLanguage.value).lower }))
</script>

<template>
  <section class="radar-legend" aria-labelledby="radar-legend-title" data-testid="radar-legend">
    <h2 id="radar-legend-title" class="radar-legend-title">
      {{ t('radar.legendTitle') }}
    </h2>
    <ul class="radar-legend-list">
      <li v-for="entry in classes" :key="entry.key" class="radar-legend-item" data-testid="radar-legend-class">
        <span class="radar-legend-swatch" :style="{ background: entry.color }" aria-hidden="true" />
        <span aria-hidden="true">{{ entry.short }}</span>
        <span class="sr-only">{{ entry.long }}</span>
      </li>
    </ul>
    <p class="radar-legend-none" data-testid="radar-legend-none">
      {{ none }}
    </p>
  </section>
</template>

<style>
.radar-legend {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}
.radar-legend-title {
  font-size: 0.8125rem;
  font-weight: 700;
  color: var(--ui-text-highlighted);
}
.radar-legend-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem 0.875rem;
}
.radar-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.8125rem;
  color: var(--ui-text-toned);
  font-variant-numeric: tabular-nums;
}
/* the swatch has an edge of the neutral's accented tone, so that the palest class stands against the page (WCAG 1.4.11) */
.radar-legend-swatch {
  flex: none;
  width: 1.25rem;
  height: 1rem;
  border-radius: 0.25rem;
  border: 1px solid var(--ui-border-accented);
}
.radar-legend-none {
  font-size: 0.75rem;
  color: var(--ui-text-muted);
}
@media (forced-colors: active) {
  .radar-legend-swatch {
    forced-color-adjust: none;
  }
}
</style>
