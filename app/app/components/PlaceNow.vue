<script setup lang="ts">
import type { CurrentConditions, HourConditions, Place, ValueRow } from '~/utils/place'
import type { WeatherKind } from '~/utils/weather-kind'
import { describeFetchError } from '~/utils/api-error'
import { formatNumber } from '~/utils/format'
import { METEOGRAM_VALUES_SETTINGS } from '~/utils/meteogram'
import { currentConditions, placeName, skyPhase, temperatureColor } from '~/utils/place'

/**
 * The weather at the place now and in the hours ahead (GH-3518), from its MOSMIX forecast: the temperature,
 * the weather in words, the wind and the rain of the next six hours, and every second hour of the next
 * twelve. The edge of the card takes the colour of the temperature, and the sky of the page its weather.
 */
const props = defineProps<{
  place: Readonly<Place>
}>()
const emit = defineEmits<{
  forget: []
}>()

const { t, locale, localeProperties } = useI18n()
const { rememberWeather } = usePlace()

// the parameters the card shows, of the same dataset and in the same units as the forecast page
const PARAMETERS = ['ttt', 'ww', 'n', 'ff', 'rr1c']
// by the place's id alone: the place is a new object whenever its weather is remembered, which is no new request
const placeId = computed(() => props.place.id)
const query = computed(() => ({
  provider: 'dwd',
  network: 'mosmix',
  parameters: PARAMETERS.map(p => `hourly/large/${p}`).join(','),
  stations: placeId.value,
  ...METEOGRAM_VALUES_SETTINGS,
}))
const { data, status, error, refresh } = useFetch<{ values: ValueRow[] }>('/api/values', {
  query,
  key: computed(() => `place-now-${placeId.value}`),
  ...RETRY_TRANSIENT,
})

const now = useNow({ interval: 5 * 60 * 1000 })
const conditions = computed<CurrentConditions | null>(() => data.value?.values ? currentConditions(data.value.values, now.value) : null)

watch(conditions, (c) => {
  if (c)
    rememberWeather(props.place.id, c.sky)
}, { immediate: true })

// the times in the place's own time zone; tz-lookup is loaded with the card, and until it is the browser's zone is used
const timeZone = ref<string | undefined>()
watch(placeId, async () => {
  try {
    const { default: tzLookup } = await import('tz-lookup')
    timeZone.value = tzLookup(props.place.latitude, props.place.longitude)
  }
  catch {
    timeZone.value = undefined
  }
}, { immediate: true })
function time(at: Date) {
  return new Intl.DateTimeFormat(localeProperties.value.language ?? locale.value, { hour: '2-digit', minute: '2-digit', timeZone: timeZone.value }).format(at)
}

const ICONS: Record<WeatherKind, string> = {
  thunderstorm: 'i-lucide-cloud-lightning',
  rain: 'i-lucide-cloud-rain',
  snow: 'i-lucide-cloud-snow',
  sleet: 'i-lucide-cloud-hail',
  drizzle: 'i-lucide-cloud-drizzle',
  fog: 'i-lucide-cloud-fog',
  wind: 'i-lucide-wind',
  dust: 'i-lucide-tornado',
  blowingSnow: 'i-lucide-snowflake',
  cloudy: 'i-lucide-cloud',
  partlyCloudy: 'i-lucide-cloud-sun',
  clear: 'i-lucide-sun',
}
function kindOf(hour: HourConditions): WeatherKind {
  if (hour.kind)
    return hour.kind
  return hour.sky === 'clear' ? 'clear' : hour.sky === 'partly' ? 'partlyCloudy' : 'cloudy'
}
function iconOf(hour: HourConditions) {
  const kind = kindOf(hour)
  const night = skyPhase(props.place.latitude, props.place.longitude, hour.at) === 'night'
  if (night && kind === 'clear')
    return 'i-lucide-moon'
  if (night && kind === 'partlyCloudy')
    return 'i-lucide-cloud-moon'
  return ICONS[kind]
}
function words(hour: HourConditions) {
  return t(`meteogram.chart.weather.${kindOf(hour)}`)
}
function degrees(value: number | null) {
  return value === null ? '–' : `${formatNumber(Math.round(value), locale.value, 0)}°`
}

const edge = computed(() => ({ '--wd-temp': temperatureColor(conditions.value?.temperature ?? null) }))
const failure = computed(() => error.value ? describeFetchError(error.value) : '')
const loading = computed(() => status.value === 'pending' && !data.value)
const headingId = useId()
</script>

<template>
  <section :aria-labelledby="headingId" class="wd-surface overflow-hidden rounded-xl bg-default shadow-(--shadow-card) ring ring-default">
    <div class="wd-temp-edge h-1.5" :style="edge" aria-hidden="true" />
    <div class="flex flex-wrap items-start justify-between gap-4 p-5 sm:p-6">
      <div class="min-w-0">
        <p class="flex items-center gap-1.5 text-sm font-semibold text-toned">
          <UIcon name="i-lucide-map-pin" class="size-4 shrink-0 text-ember" />
          {{ t('home.now') }}<template v-if="conditions">
            · {{ time(conditions.at) }}
          </template>
        </p>
        <h2 :id="headingId" class="mt-1 text-2xl font-extrabold tracking-tight text-highlighted break-words sm:text-3xl">
          {{ placeName(place.name) }}
        </h2>
      </div>
      <UButton
        :label="t('home.placeForget')"
        icon="i-lucide-x"
        color="neutral"
        variant="ghost"
        size="sm"
        @click="emit('forget')"
      />
    </div>

    <div v-if="loading" class="px-5 pb-6 sm:px-6" role="status" :aria-label="t('common.loading')" aria-busy="true">
      <div class="h-16 w-48 animate-pulse rounded-lg bg-elevated" aria-hidden="true" />
    </div>
    <div v-else-if="failure" class="flex flex-wrap items-center gap-3 px-5 pb-6 sm:px-6" role="alert">
      <p class="text-sm text-error">
        <span class="font-semibold">{{ t('common.requestFailed') }}:</span> {{ failure }}
      </p>
      <UButton :label="t('common.retry')" icon="i-lucide-rotate-cw" size="sm" color="neutral" variant="outline" @click="refresh()" />
    </div>
    <p v-else-if="!conditions" class="px-5 pb-6 text-sm text-muted sm:px-6">
      {{ t('home.nowUnavailable') }}
    </p>
    <template v-else>
      <div class="flex flex-wrap items-center gap-x-6 gap-y-3 px-5 pb-5 sm:px-6">
        <UIcon :name="iconOf(conditions)" class="size-16 shrink-0 text-brand-600 dark:text-brand-300" />
        <p class="text-6xl font-extrabold leading-none tracking-tight tabular-nums text-highlighted">
          {{ degrees(conditions.temperature) }}<span class="sr-only">C</span>
        </p>
        <div class="min-w-0">
          <p class="text-lg font-semibold text-highlighted">
            {{ words(conditions) }}
          </p>
          <dl class="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-toned">
            <div class="flex gap-1">
              <dt>{{ t('home.wind') }}:</dt>
              <dd class="tabular-nums">
                {{ conditions.windSpeed === null ? '–' : `${formatNumber(conditions.windSpeed, locale, 0)} m/s` }}
              </dd>
            </div>
            <div class="flex gap-1">
              <dt>{{ t('home.rainNext6h') }}:</dt>
              <dd class="tabular-nums">
                {{ conditions.precipitationNext6h === null ? '–' : `${formatNumber(conditions.precipitationNext6h, locale, 1)} mm` }}
              </dd>
            </div>
          </dl>
        </div>
      </div>
      <div v-if="conditions.next.length" class="border-t border-default px-5 py-4 sm:px-6">
        <h3 class="mb-2 text-xs font-bold uppercase tracking-wider text-muted">
          {{ t('home.nextHours') }}
        </h3>
        <ol class="grid grid-cols-3 gap-2 sm:grid-cols-6">
          <li v-for="hour in conditions.next" :key="hour.at.getTime()" class="flex flex-col items-center gap-1 rounded-lg bg-muted px-2 py-2 text-center">
            <span class="text-xs font-semibold text-toned tabular-nums">{{ time(hour.at) }}</span>
            <UIcon :name="iconOf(hour)" class="size-6 text-brand-600 dark:text-brand-300" />
            <span class="sr-only">{{ words(hour) }}</span>
            <span class="font-bold tabular-nums text-highlighted">{{ degrees(hour.temperature) }}</span>
          </li>
        </ol>
      </div>
      <p class="border-t border-default px-5 py-3 text-xs text-muted sm:px-6">
        {{ t('home.forecastSource', { id: place.id }) }}
      </p>
    </template>
  </section>
</template>
