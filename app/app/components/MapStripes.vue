<script setup lang="ts">
import type { StripesValuesResponse } from '#shared/types/api'
import { describeFetchError } from '~/utils/api-error'
import { formatNumber } from '~/utils/format'
import { STRIPES_KIND } from '~/utils/map-tool'
import { COLOR_MAPS, stripeColour, stripesSummaryParams, stripeYears } from '~/utils/stripes'
import { unitSymbol } from '~/utils/unit-targets'

// The climate stripes of a station, as a band of colour in the map's panel (GH-3650): one stripe a year, drawn in
// plain elements with the stripes page's colour scale. The page, which the link under the band opens, has the chart,
// its options and the table of the years. The band is a picture of what the sentence under it says, in words.

const props = defineProps<{ stationId: string, stationName: string }>()

const { t, locale } = useI18n()

const { data, pending, error, refresh } = useFetch<StripesValuesResponse>('/api/stripes/values', {
  query: computed(() => ({ kind: STRIPES_KIND, station: props.stationId, format: 'json' })),
  key: computed(() => `map-stripes-${props.stationId}`),
  ...API_FETCH,
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
const unit = computed(() => data.value?.series.unit ? unitSymbol(data.value.series.unit) : '')
const summary = computed(() => years.value.length
  ? t('stripes.summary', stripesSummaryParams(years.value, value => `${formatNumber(value, locale.value, 1)} ${unit.value}`.trim()))
  : '')
const descriptionId = useId()
</script>

<template>
  <div data-testid="map-stripes">
    <div v-if="pending && !years.length" class="h-14 rounded-lg bg-elevated motion-safe:animate-pulse" role="status" :aria-label="t('common.loading')" />
    <div v-else-if="error" class="flex flex-col items-start gap-2">
      <p role="alert" class="text-sm text-error">
        {{ describeFetchError(error) }}
      </p>
      <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" @click="refresh()" />
    </div>
    <figure v-else-if="years.length" class="m-0">
      <div class="map-stripes" role="img" :aria-label="t('mapTool.stripesFigure', { name: stationName })" :aria-describedby="descriptionId">
        <span v-for="stripe in stripes" :key="stripe.year" :style="{ background: stripe.colour }" />
      </div>
      <figcaption :id="descriptionId" class="mt-1.5 text-xs text-muted">
        {{ summary }}
      </figcaption>
    </figure>
    <p v-else class="text-sm text-muted">
      {{ t('mapTool.stripesNone') }}
    </p>
  </div>
</template>

<style>
.map-stripes {
  display: flex;
  height: 3.5rem;
  overflow: hidden;
  border-radius: var(--ui-radius);
  /* the edge of the band where its outer stripes are as pale as the panel */
  box-shadow: inset 0 0 0 1px rgb(15 23 42 / 0.12);
}
.map-stripes > span {
  flex: 1 1 0;
  min-width: 0;
}
@media (forced-colors: active) {
  .map-stripes {
    forced-color-adjust: none;
    border: 1px solid CanvasText;
  }
}
</style>
