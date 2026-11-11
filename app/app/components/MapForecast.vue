<script setup lang="ts">
import type { Station, Value, ValuesResponse } from '#shared/types/api'
import type { RequestError } from '~/utils/request-error'
import Meteogram from '~/components/Meteogram.vue'
import { meteogramUnitsKey, meteogramValuesQuery } from '~/utils/meteogram'
import { backendFailure, describeRequestError, failureOfError } from '~/utils/request-error'
import { unitsOfAnswer } from '~/utils/units'

// The days ahead at a forecast point, as day rows in the map's panel (GH-3650): the request of the forecast page,
// drawn without its chart. The link under the rows, in the panel, opens the forecast itself.

const props = defineProps<{ station: Station }>()

const { t } = useI18n()

const values = ref<Value[]>([])
// the unit of each parameter of the values, as the answer says (GH-3980)
const units = ref<Record<string, string>>({})

// the unit settings (GH-3980), read at each request: a change while the days are shown fetches them again
const { settings: appSettings } = useSettings()
const unitSettings = computed(() => ({ units: appSettings.value.units, convertUnits: appSettings.value.convertUnits }))
// the day rows show the temperatures, the rain and, for the weather of a day, the cloud cover: no other unit is a reason to ask again
const unitsAsked = computed(() => meteogramUnitsKey(unitSettings.value, ['temperature', 'precipitation', 'fraction']))
const pending = ref(false)
const failure = ref<RequestError | null>(null)
const error = computed(() => failure.value ? describeRequestError(failure.value, t) : null)

// the request that is under way, which a newer station's or a retry ends: only the newest answer is shown
let controller: AbortController | null = null

async function load(stationId: string) {
  controller?.abort()
  const mine = new AbortController()
  controller = mine
  pending.value = true
  failure.value = null
  values.value = []
  try {
    const response = await fetch(`/api/values?${new URLSearchParams(meteogramValuesQuery(stationId, unitSettings.value))}`, { signal: mine.signal })
    if (!response.ok) {
      const failed = backendFailure(response.status, response.statusText, await response.json().catch(() => null))
      if (!mine.signal.aborted)
        failure.value = failed
      return
    }
    const body = await readJsonAnswer<ValuesResponse>('/api/values', response)
    if (!mine.signal.aborted) {
      units.value = unitsOfAnswer(body)
      values.value = body.values ?? []
    }
  }
  catch (e: any) {
    if (!mine.signal.aborted)
      failure.value = failureOfError(e)
  }
  finally {
    if (controller === mine) {
      pending.value = false
      controller = null
    }
  }
}

// the station, or the units: one request for either, or both together; the one under way is ended by the newer
watch([() => props.station.station_id, unitsAsked], ([id]) => void load(id), { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div :aria-busy="pending" data-testid="map-forecast">
    <div v-if="pending" class="flex flex-col gap-2" role="status" :aria-label="t('common.loading')">
      <div v-for="day in 4" :key="day" class="h-10 rounded-lg bg-elevated motion-safe:animate-pulse" aria-hidden="true" />
    </div>
    <div v-else-if="error" class="flex flex-col items-start gap-2">
      <p role="alert" class="text-sm text-error">
        {{ error }}
      </p>
      <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" @click="load(station.station_id)" />
    </div>
    <Meteogram
      v-else-if="values.length"
      :values="values"
      :station-name="station.name"
      :station-coords="{ latitude: station.latitude, longitude: station.longitude }"
      widget
      days-only
      :units="units"
    />
    <p v-else class="text-sm text-muted">
      {{ t('widget.noData') }}
    </p>
  </div>
</template>
