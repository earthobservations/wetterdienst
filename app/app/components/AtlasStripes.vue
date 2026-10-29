<script setup lang="ts">
import type { StripesValuesResponse } from '#shared/types/api'
import { describeFetchError } from '~/utils/api-error'
import { STRIPES_KIND } from '~/utils/atlas'
import { COLOR_MAPS, stripeColour, stripeYears } from '~/utils/stripes'

// The climate stripes of a station, as a band of colour in the map's panel (GH-3518): one stripe a year,
// drawn in plain elements with the stripes page's colour scale. The page, which the link under the band
// opens, has the chart, its options and the table of the years.

const props = defineProps<{ stationId: string, stationName: string }>()

const { t } = useI18n()

const { data, pending, error } = useFetch<StripesValuesResponse>('/api/stripes/values', {
  query: computed(() => ({ kind: STRIPES_KIND, station: props.stationId, format: 'json' })),
  key: computed(() => `atlas-stripes-${props.stationId}`),
  ...RETRY_TRANSIENT,
})

const years = computed(() => stripeYears(data.value?.values ?? []))
const range = computed(() => {
  const values = years.value.map(year => year.value)
  return { min: Math.min(...values), max: Math.max(...values) }
})
const stripes = computed(() => years.value.map(year => ({
  year: year.year,
  colour: stripeColour(COLOR_MAPS.temperature, range.value.max > range.value.min ? (year.value - range.value.min) / (range.value.max - range.value.min) : 0.5),
})))
const label = computed(() => years.value.length
  ? t('atlas.stripesFigure', { name: props.stationName, first: years.value[0]!.year, last: years.value[years.value.length - 1]!.year })
  : '')
</script>

<template>
  <div>
    <div v-if="pending && !years.length" class="h-14 rounded-lg bg-elevated animate-pulse" role="status" :aria-label="t('common.loading')" />
    <p v-else-if="error" class="text-sm text-error">
      {{ describeFetchError(error) }}
    </p>
    <figure v-else-if="years.length" class="m-0">
      <div class="atlas-stripes" role="img" :aria-label="label">
        <span v-for="stripe in stripes" :key="stripe.year" :style="{ background: stripe.colour }" />
      </div>
      <figcaption class="mt-1.5 flex justify-between text-xs text-muted tabular" aria-hidden="true">
        <span>{{ years[0]!.year }}</span>
        <span>{{ years[years.length - 1]!.year }}</span>
      </figcaption>
    </figure>
  </div>
</template>

<style>
.atlas-stripes {
  display: flex;
  height: 3.5rem;
  overflow: hidden;
  border-radius: var(--ui-radius);
  /* the edge of the band where its outer stripes are as pale as the panel */
  box-shadow: inset 0 0 0 1px rgb(15 23 42 / 0.08);
}
.atlas-stripes > span {
  flex: 1 1 0;
  min-width: 0;
}
@media (forced-colors: active) {
  .atlas-stripes {
    forced-color-adjust: none;
    border: 1px solid CanvasText;
  }
}
</style>
