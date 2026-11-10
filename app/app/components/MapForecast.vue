<script setup lang="ts">
import type { Station, Value } from '#shared/types/api'
import type { RequestError } from '~/utils/request-error'
import Meteogram from '~/components/Meteogram.vue'
import { meteogramValuesQuery } from '~/utils/meteogram'
import { backendFailure, describeRequestError, failureOfError } from '~/utils/request-error'

// The days ahead at a forecast point, as day rows in the map's panel (GH-3650): the request of the forecast page,
// drawn without its chart. The link under the rows, in the panel, opens the forecast itself.

const props = defineProps<{ station: Station }>()

const { t } = useI18n()

const values = ref<Value[]>([])
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
    const response = await fetch(`/api/values?${new URLSearchParams(meteogramValuesQuery(stationId))}`, { signal: mine.signal })
    if (!response.ok) {
      const failed = backendFailure(response.status, response.statusText, await response.json().catch(() => null))
      if (!mine.signal.aborted)
        failure.value = failed
      return
    }
    const body = await readJsonAnswer<{ values?: Value[] }>('/api/values', response)
    if (!mine.signal.aborted)
      values.value = body.values ?? []
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

watch(() => props.station.station_id, id => void load(id), { immediate: true })
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
    />
    <p v-else class="text-sm text-muted">
      {{ t('widget.noData') }}
    </p>
  </div>
</template>
