<script setup lang="ts">
import type { Station, Value } from '#shared/types/api'
import type { RequestError } from '~/utils/request-error'
import Meteogram from '~/components/Meteogram.vue'
import { meteogramValuesQuery } from '~/utils/meteogram'
import { backendFailure, describeRequestError } from '~/utils/request-error'

// The days ahead at a forecast point, as day cards in the map's panel (GH-3518): the same request as the
// forecast page's, drawn without its chart, which the link under the cards opens.

const props = defineProps<{ station: Station }>()

const { t } = useI18n()

const values = ref<Value[]>([])
const pending = ref(false)
const failure = ref<RequestError | null>(null)
const error = computed(() => failure.value ? describeRequestError(failure.value, t) : null)

// a newer station's answer is the one shown, whichever comes first
let generation = 0

async function load(stationId: string) {
  const mine = ++generation
  pending.value = true
  failure.value = null
  values.value = []
  try {
    const response = await fetch(`/api/values?${new URLSearchParams(meteogramValuesQuery(stationId))}`)
    if (mine !== generation)
      return
    if (!response.ok) {
      failure.value = backendFailure(response.status, response.statusText, await response.json().catch(() => null))
      return
    }
    const body = await response.json()
    if (mine === generation)
      values.value = body.values ?? []
  }
  catch (e: any) {
    if (mine === generation)
      failure.value = e?.message ? { kind: 'text', text: e.message } : { kind: 'requestFailed' }
  }
  finally {
    if (mine === generation)
      pending.value = false
  }
}

watch(() => props.station.station_id, id => void load(id), { immediate: true })
</script>

<template>
  <div :aria-busy="pending">
    <div v-if="pending" class="flex flex-col gap-2" :aria-label="t('meteogram.loading')" role="status">
      <div v-for="day in 4" :key="day" class="h-10 rounded-lg bg-elevated animate-pulse" aria-hidden="true" />
    </div>
    <p v-else-if="error" class="text-sm text-error">
      {{ error }}
    </p>
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
