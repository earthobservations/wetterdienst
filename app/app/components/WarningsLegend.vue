<script setup lang="ts">
import { LEVEL_STYLES, WARNING_LEVELS } from '~/utils/warnings'

// The legend of the warnings' outlines (GH-4295), in the layers panel under the legend of the dots: the four levels of DWD and its
// preliminary information, each with a swatch drawn as the map draws it (the fill, and an edge that is dotted, dashed, solid, a double line or dash-dotted) and
// its name in words with its number, so that the level is never told by colour alone (WCAG 1.4.1). The labels follow the language of the page as it changes.

const { t } = useI18n()
const entries = computed(() => [
  ...WARNING_LEVELS.map(level => ({ key: String(level), style: LEVEL_STYLES[level], label: `${t('warnings.levelOf', { level })} · ${t(`warnings.level.${level}`)}` })),
  { key: 'preliminary', style: LEVEL_STYLES.preliminary, label: t('warnings.level.preliminary') },
])
</script>

<template>
  <div class="warnings-legend-box">
    <ul class="map-legend warnings-legend" data-testid="warnings-legend">
      <li v-for="entry in entries" :key="entry.key" data-testid="warnings-legend-entry">
        <svg class="warnings-swatch" viewBox="0 0 32 18" width="32" height="18" aria-hidden="true" focusable="false">
          <rect x="3" y="3" width="26" height="12" rx="2" :fill="entry.style.fill" :fill-opacity="Math.min(1, entry.style.fillOpacity + 0.3)" :stroke="entry.style.edge" :stroke-width="Math.min(entry.style.weight, 5)" :stroke-dasharray="entry.style.dashArray ?? undefined" />
          <rect v-if="entry.style.double" x="3" y="3" width="26" height="12" rx="2" fill="none" stroke="#ffffff" stroke-width="1.5" />
        </svg>
        {{ entry.label }}
      </li>
    </ul>
    <p class="mt-2 text-xs text-muted" data-testid="warnings-legend-health">
      {{ t('warnings.legendHealth') }}
    </p>
  </div>
</template>

<style>
.warnings-swatch {
  flex: none;
  /* the map is a light surface in both colour schemes: the swatch has its own, so that its edge is seen against the navy of the panel at night */
  padding: 1px;
  border-radius: 3px;
  background: #ffffff;
}
</style>
