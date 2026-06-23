<script setup lang="ts">
import type { Station } from '#shared/types/api'
import Meteogram from '~/components/Meteogram.vue'

const MOSMIX = {
  provider: 'dwd',
  network: 'mosmix',
  resolution: 'hourly',
  dataset: 'large',
  parameters: ['ttt', 'td', 'ff', 'dd', 'fx1', 'n', 'nl', 'nm', 'nh', 'rr1c', 'ww', 'pppp', 'tx', 'tn'],
}

const { t } = useI18n()
const route = useRoute()
const stationId = computed(() => route.query.station as string | undefined)
const themeParam = computed(() => route.query.theme as string | undefined)

const colorMode = useColorMode()
// Apply theme from query param if provided
watchEffect(() => {
  if (themeParam.value === 'dark' || themeParam.value === 'light')
    colorMode.preference = themeParam.value
})

const station = ref<Station | null>(null)
const values = ref<any[]>([])
const pending = ref(false)
const error = ref<string | null>(null)

async function loadStation(id: string) {
  try {
    const res = await $fetch<{ stations: Station[] }>('/api/stations', {
      query: {
        provider: MOSMIX.provider,
        network: MOSMIX.network,
        parameters: `${MOSMIX.resolution}/${MOSMIX.dataset}`,
        station: id,
      },
    })
    station.value = (res.stations ?? [])[0] ?? null
  }
  catch {
    error.value = t('widget.stationNotFound')
  }
}

async function fetchValues(s: Station) {
  pending.value = true
  error.value = null
  values.value = []
  const params = new URLSearchParams({
    provider: MOSMIX.provider,
    network: MOSMIX.network,
    parameters: MOSMIX.parameters.map(p => `${MOSMIX.resolution}/${MOSMIX.dataset}/${p}`).join(','),
    station: s.station_id,
  })
  try {
    const res = await fetch(`/api/values?${params}`)
    if (!res.ok) {
      error.value = `Backend error ${res.status}`
      return
    }
    const json = await res.json()
    values.value = json.values ?? []
  }
  catch (e: any) {
    error.value = e?.message ?? 'Request failed'
  }
  finally {
    pending.value = false
  }
}

watch(station, (s) => {
  if (s)
    void fetchValues(s)
})

onMounted(async () => {
  if (stationId.value)
    await loadStation(stationId.value)
})
</script>

<template>
  <div class="min-h-screen bg-white dark:bg-gray-950 flex flex-col">
    <!-- Minimal header -->
    <div class="flex items-center justify-between px-4 py-2 border-b border-gray-100 dark:border-gray-800 bg-white/90 dark:bg-gray-950/90 backdrop-blur-sm shrink-0">
      <div class="flex items-center gap-2 min-w-0">
        <img src="/favicon.ico" alt="Wetterdienst" class="w-5 h-5 shrink-0">
        <span class="text-sm font-semibold text-gray-700 dark:text-gray-200 truncate">
          {{ station ? station.name : t('meteogram.title') }}
        </span>
        <span v-if="station" class="text-xs text-gray-400 shrink-0">({{ station.station_id }})</span>
      </div>
      <a
        :href="station ? `/meteogram?station=${station.station_id}` : '/meteogram'"
        target="_blank"
        rel="noopener"
        class="inline-flex items-center gap-1 text-xs text-primary-500 hover:text-primary-600 dark:text-primary-400 dark:hover:text-primary-300 shrink-0 ml-2"
        :title="t('widget.openFull')"
      >
        {{ t('common.open') }}
        <UIcon name="i-lucide-external-link" class="w-3 h-3" />
      </a>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-hidden">
      <i18n-t v-if="!stationId" keypath="widget.noStation" tag="div" class="flex items-center justify-center h-full py-16 text-gray-400 text-sm" scope="global">
        <template #param>
          <code class="mx-1 px-1 bg-gray-100 dark:bg-gray-800 rounded">?station=XXXXX</code>
        </template>
      </i18n-t>

      <div v-else-if="pending" class="flex items-center justify-center gap-2 py-16 text-gray-400 text-sm">
        <UIcon name="i-lucide-loader-circle" class="w-4 h-4 animate-spin text-primary-500" />
        {{ t('widget.loading') }}
      </div>

      <div v-else-if="error" class="flex items-center justify-center py-16 text-red-500 text-sm">
        {{ error }}
      </div>

      <div v-else-if="station && values.length > 0" class="p-3">
        <Meteogram
          :values="values"
          :station-name="station.name"
          :station-coords="{ latitude: station.latitude, longitude: station.longitude }"
          :widget="true"
        />
      </div>

      <div v-else-if="station && !pending" class="flex items-center justify-center py-16 text-gray-400 text-sm">
        {{ t('widget.noData') }}
      </div>
    </div>

    <!-- Attribution footer -->
    <div class="shrink-0 px-4 py-1.5 border-t border-gray-100 dark:border-gray-800 text-center">
      <a
        href="https://github.com/earthobservations/wetterdienst"
        target="_blank"
        rel="noopener"
        class="text-[10px] text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
      >
        {{ t('widget.poweredBy') }}
      </a>
    </div>
  </div>
</template>
