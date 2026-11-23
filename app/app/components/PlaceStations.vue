<script setup lang="ts">
import type { Station } from '#shared/types/api'
import type { PlaceInLink } from '~/utils/place-link'
import type { NearStation } from '~/utils/place-stations'
import { formatDistance } from '~/utils/map-tool'
import { PLACE_REACH_KM, stationForPlace, withinReach } from '~/utils/place-stations'
import { stationShortLabel } from '~/utils/station'

// A place found by its name, in a tool that shows the weather of a station (GH-3791, the Forecast): the place with where it lies, then the stations
// closest to it, each with how far it is and how high it stands (a place has no height of its own, so the heights are compared with the closest
// station's), and the weather of the closest one is shown. Where no station is within reach (`PLACE_REACH_KM`) it says so, names the nearest and does
// not show a forecast as the place's: the reader may still open that station's forecast, which is then called the station's.
const props = defineProps<{
  place: PlaceInLink
  near: NearStation<Station>[]
  /** The stations near the place are being looked up, or could not be */
  state: 'loading' | 'failed' | 'ready'
  /** The id of the station whose weather is shown */
  selectedId?: string
}>()
defineEmits<{ pick: [station: Station] }>()

const { t, locale } = useI18n()
const headingId = useId()

const closest = computed(() => stationForPlace(props.near))
const nearest = computed(() => props.near[0] ?? null)
/** The stations listed: the ones within reach, or the nearest alone where none is (a station 500 km away is no alternative to list) */
const listed = computed(() => closest.value ? props.near.filter(entry => withinReach(entry.distanceKm)) : props.near.slice(0, 1))
const distance = (km: number) => formatDistance(km, locale.value)
const height = (station: Station) => station.elevation == null ? t('place.heightUnknown') : t('place.height', { height: Math.round(station.elevation) })
/** The height against the closest station, in metres with its sign (a unit and a sign are the same in every language) */
const difference = (km: NearStation<Station>) => km.heightDifference == null || km.heightDifference === 0 ? '' : `${km.heightDifference > 0 ? '+' : '−'}${Math.abs(km.heightDifference)} m`
/** Sentence of the live region: what the place got, said once the stations are there */
const summary = computed(() => {
  if (props.state === 'loading')
    return t('place.looking', { place: props.place.name })
  if (props.state === 'failed')
    return t('place.failed')
  // the reader opened the nearest station anyway: its forecast is shown, called the station's and not the place's
  const opened = props.near.find(entry => entry.station.station_id === props.selectedId)
  if (!closest.value && opened)
    return t('place.shownAnyway', { station: stationShortLabel(opened.station), place: props.place.name, distance: distance(opened.distanceKm) })
  if (closest.value)
    return t('place.closest', { station: stationShortLabel(closest.value.station), place: props.place.name, distance: distance(closest.value.distanceKm) })
  return nearest.value
    ? t('place.noneNear', { place: props.place.name, reach: PLACE_REACH_KM, station: stationShortLabel(nearest.value.station), distance: distance(nearest.value.distanceKm) })
    : t('place.noneAtAll', { place: props.place.name })
})
</script>

<template>
  <section :aria-labelledby="headingId" class="flex flex-col gap-3 rounded-lg border border-default p-3" data-testid="place-stations">
    <header class="flex flex-wrap items-baseline gap-x-2">
      <UIcon name="i-ph-map-pin" class="size-4 shrink-0 self-center text-primary-600 dark:text-primary-500" aria-hidden="true" />
      <h3 :id="headingId" class="font-bold" data-testid="place-name">
        {{ place.name }}
      </h3>
      <span v-if="place.region" class="text-sm text-muted" data-testid="place-region">{{ place.region }}</span>
    </header>

    <p class="text-sm" :class="state === 'failed' || (state === 'ready' && !closest) ? 'text-toned' : 'text-muted'" role="status" data-testid="place-summary">
      {{ summary }}
    </p>

    <ul v-if="state === 'ready' && listed.length" class="flex flex-col divide-y divide-default" :aria-label="t('place.stationsLabel', { place: place.name })" data-testid="place-station-list">
      <li v-for="(entry, index) in listed" :key="entry.station.station_id" class="flex flex-col gap-1 py-2 text-sm" :aria-current="entry.station.station_id === selectedId ? 'true' : undefined">
        <span class="break-words font-medium">
          {{ stationShortLabel(entry.station) }}
          <span v-if="index === 0 && closest" class="ms-1 rounded-sm bg-elevated px-1.5 text-xs font-normal text-toned">{{ t('place.closestTag') }}</span>
        </span>
        {{ ' ' }}
        <span class="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span class="tabular-nums text-muted">{{ distance(entry.distanceKm) }}</span>
          {{ ' ' }}
          <span class="tabular-nums text-muted">{{ height(entry.station) }}<template v-if="difference(entry)"> ({{ difference(entry) }})</template></span>
          {{ ' ' }}
          <UBadge v-if="entry.station.station_id === selectedId" color="primary" variant="subtle" size="md" class="ms-auto">
            {{ t('place.shown') }}
          </UBadge>
          <UButton
            v-else
            size="md"
            color="neutral"
            variant="outline"
            class="ms-auto"
            :label="closest ? t('place.show') : t('place.showAnyway')"
            :aria-label="closest ? t('place.showStation', { station: stationShortLabel(entry.station) }) : t('place.showAnywayStation', { station: stationShortLabel(entry.station), place: place.name, distance: distance(entry.distanceKm) })"
            @click="$emit('pick', entry.station)"
          />
        </span>
      </li>
    </ul>
    <p v-if="state === 'ready' && closest && listed.length > 1" class="text-xs text-muted">
      {{ t('place.heightNote') }}
    </p>
  </section>
</template>
