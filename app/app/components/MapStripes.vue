<script setup lang="ts">
import type { StripesValuesResponse } from '#shared/types/api'
import { describeFetchError } from '~/utils/api-error'
import { formatNumber } from '~/utils/format'
import { STRIPES_KIND } from '~/utils/map-tool'
import { stripeColour, stripesMethodNote, stripesMirrorNote, stripesReferenceText, stripesSummaryParams, stripeYears } from '~/utils/stripes'
import { fetchStripes, stripesFetch } from '~/utils/stripes-source'
import { stripesUnitTargets, unitSymbol } from '~/utils/unit-targets'

// The climate stripes of a station, as a band of colour in the map's panel (GH-3650): one stripe a year, drawn in
// plain elements, each in the colour of the class of its year (the stripes page's scale, GH-4157, calculated by the app, GH-4258). The page, which the link under the band opens, has the chart,
// its options and the table of the years. The band is a picture of what the sentence under it says, in words.
//
// A station of NOAA's GHCN daily (`ghcn`, GH-4078) is asked for with its provider and network, and its years are built from the days:
// the line under the sentence says how a day's temperature was made (the midrange of the daily maximum and minimum, no 24-hour mean).
// A station that has no stripes (a 400: too few years with data) is refused by the app (`stripesFromRecord`, as the backend's stripes refused it), which is not a failure of the request but the
// answer, said as "no stripes", and raised as `none` for the card to take its link away; DWD's stations are listed by their having
// stripes, so for them a refusal stays the failure it is.

const props = defineProps<{ stationId: string, stationName: string, ghcn?: boolean }>()
const emit = defineEmits<{ none: [mirrorNote: string] }>()

const { t, locale } = useI18n()

// the unit the app settings choose (GH-3980): in the query, so that a change of it fetches the values again, and in the
// key, so that the values of another unit are not taken for these
const { settings } = useSettings()
const unitTargets = computed(() => JSON.stringify(stripesUnitTargets(STRIPES_KIND, settings.value.units)))

// the stripes are made by the app from the annual values of the API, or of its own server for GHCN's days (GH-4258)
const { data, pending, error, refresh } = useAsyncData(
  computed(() => `map-stripes-${props.ghcn ? 'ghcn-' : ''}${props.stationId}-${unitTargets.value}`),
  () => fetchStripes(stripesFetch, {
    source: props.ghcn ? 'ghcn' : 'dwd',
    kind: STRIPES_KIND,
    station: { station_id: props.stationId, name: props.stationName },
    unitTargets: JSON.parse(unitTargets.value),
  }),
)

/** The stripes could not be made of this station of GHCN daily: it has no stripes (400, or 404, 422), which is no failure to try again */
const refused = computed(() => props.ghcn && [400, 404, 422].includes((error.value as { statusCode?: number } | null)?.statusCode ?? 0))
/** Where the record of a refused station was read from the mirror of NOAA's data on AWS, whose file may be the reason it is too short (GH-4390): the line that says so, else an empty text */
// (the error of `useAsyncData` is an H3 error wrapping the one thrown, which is its `cause`)
const refusedMirrorNote = computed(() => {
  const failure = error.value as { mirror?: StripesValuesResponse['mirror'], cause?: { mirror?: StripesValuesResponse['mirror'] } } | null
  return refused.value ? stripesMirrorNote(failure?.mirror ?? failure?.cause?.mirror, t) : ''
})
watch(refused, (now) => {
  if (now)
    emit('none', refusedMirrorNote.value)
}, { immediate: true })

const years = computed(() => stripeYears(data.value?.values ?? []))
const stripes = computed(() => years.value.map(year => ({
  year: year.year,
  colour: stripeColour(STRIPES_KIND, year.stripeClass),
})))
const unit = computed(() => data.value?.series.unit ? unitSymbol(data.value.series.unit) : '')
const summary = computed(() => years.value.length && data.value
  ? `${t('stripes.summary', stripesSummaryParams(years.value, value => `${formatNumber(value, locale.value, 1)} ${unit.value}`.trim()))} ${stripesReferenceText(data.value.reference, t, value => formatNumber(value, locale.value, 1))}`
  : '')
const methodNote = computed(() => stripesMethodNote(data.value?.series.method, t))
// the days were read from the mirror of NOAA's data on AWS, whose file may end early (GH-4390)
const mirrorNote = computed(() => stripesMirrorNote(data.value?.mirror, t))
const descriptionId = useId()
</script>

<template>
  <div data-testid="map-stripes">
    <div v-if="pending && !years.length" class="h-14 rounded-lg bg-elevated motion-safe:animate-pulse" role="status" :aria-label="t('common.loading')" />
    <template v-else-if="refused">
      <p class="text-sm text-muted" data-testid="map-stripes-refused">
        {{ t('mapTool.stripesNone') }}
      </p>
      <p v-if="refusedMirrorNote" class="mt-1 text-xs text-muted" data-testid="map-stripes-refused-mirror">
        {{ refusedMirrorNote }}
      </p>
    </template>
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
      <!-- how a day's temperature was made, for a station of GHCN daily (no 24-hour mean) -->
      <p v-if="methodNote" class="mt-1 text-xs text-muted" data-testid="map-stripes-method">
        {{ methodNote }}
      </p>
      <!-- the days came from the mirror of NOAA's data on AWS (NCEI did not give the station's file): the most recent may be missing, and the record may end early -->
      <p v-if="mirrorNote" class="mt-1 text-xs text-muted" data-testid="map-stripes-mirror">
        {{ mirrorNote }}
      </p>
      <!-- whose data the band is made of, and what was done to it, from the terms the answer it was made of carries (GH-4255) -->
      <ProviderCredit
        :terms="data?.metadata?.provider"
        :fallback="ghcn ? t('stripes.plotSourceGhcn') : t('stripes.plotSource')"
        class="mt-2" data-testid="map-stripes-credit"
      />
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
