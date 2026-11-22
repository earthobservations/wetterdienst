<script setup lang="ts">
import { LEVEL_STYLES, WARNING_LEVELS } from '~/utils/warnings'

// The legend of the warnings' outlines (GH-4295), in the layers panel under the legend of the dots: the four levels of DWD and its
// preliminary information, each with a swatch drawn as the map draws it (the fill, and an edge that is dotted, dashed, solid, heavy or dash-dot) and
// its name in words with its number, so that the level is never told by colour alone (WCAG 1.4.1).

const { t } = useI18n()
const entries = [...WARNING_LEVELS.map(level => ({ key: String(level), style: LEVEL_STYLES[level], label: `${t('warnings.levelOf', { level })} · ${t(`warnings.level.${level}`)}` })), { key: 'preliminary', style: LEVEL_STYLES.preliminary, label: t('warnings.level.preliminary') }]
</script>

<template>
  <ul class="map-legend warnings-legend" data-testid="warnings-legend">
    <li v-for="entry in entries" :key="entry.key" data-testid="warnings-legend-entry">
      <svg class="warnings-swatch" viewBox="0 0 32 18" width="32" height="18" aria-hidden="true" focusable="false">
        <rect x="2" y="2" width="28" height="14" rx="2" :fill="entry.style.fill" :fill-opacity="Math.min(1, entry.style.fillOpacity + 0.3)" :stroke="entry.style.edge" :stroke-width="Math.min(entry.style.weight, 4)" :stroke-dasharray="entry.style.dashArray ?? undefined" />
      </svg>
      {{ entry.label }}
    </li>
  </ul>
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
