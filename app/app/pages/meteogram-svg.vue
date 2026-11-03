<script setup lang="ts">
// PROTOTYPE (GH-3237), reachable by URL only: `MeteogramSvg.vue` beside the page it would replace. Not linked
// from the navigation. `?station=10384` draws that MOSMIX station from the backend; without it the page draws a
// synthetic ten-day forecast (`utils/meteogram-demo.ts`), so that it works with no backend at hand.
// `?bench=15` draws the demo forecast 15 times and writes the median render time to `data-render-stats` on the chart's
// card (the number of the pull request). `?theme=dark|light` as the widget has it.
import type { Station } from '#shared/types/api'
import MeteogramSvg from '~/components/MeteogramSvg.vue'
import { METEOGRAM_VALUES_SETTINGS } from '~/utils/meteogram'
import { demoForecast } from '~/utils/meteogram-demo'

const MOSMIX_PARAMETERS = ['ttt', 'td', 'ff', 'dd', 'fx1', 'n', 'nl', 'nm', 'nh', 'rr1c', 'ww', 'pppp', 'tx', 'tn']

const { t } = useI18n()
useHead({ title: () => `${t('meteogram.title')} (SVG prototype)` })
const route = useRoute()

const colorMode = useColorMode()
watchEffect(() => {
  const theme = route.query.theme
  if (theme === 'dark' || theme === 'light')
    colorMode.preference = theme
})

const DEMO_STATION: Station = {
  station_id: 'DEMO',
  name: 'Hamburg (synthetic data)',
  region: null,
  latitude: 53.63,
  longitude: 10.0,
  elevation: 11,
  start_timestamp: null,
  end_timestamp: null,
}

const station = ref<Station>(DEMO_STATION)
const values = ref<any[]>([])
const failed = ref<string | null>(null)
const usingDemo = computed(() => station.value.station_id === 'DEMO')

function startOfHour() {
  const d = new Date()
  d.setUTCMinutes(0, 0, 0)
  return d.getTime()
}

async function load() {
  const id = route.query.station?.toString()
  if (!id) {
    values.value = demoForecast(startOfHour())
    return
  }
  try {
    const found = await $fetch<{ stations: Station[] }>('/api/stations', {
      query: { provider: 'dwd', network: 'mosmix', parameters: 'hourly/large', stations: id },
    })
    const first = found.stations?.[0]
    if (!first) {
      failed.value = `Station ${id} not found`
      return
    }
    station.value = first
    const params = new URLSearchParams({
      provider: 'dwd',
      network: 'mosmix',
      parameters: MOSMIX_PARAMETERS.map(p => `hourly/large/${p}`).join(','),
      stations: first.station_id,
      ...METEOGRAM_VALUES_SETTINGS,
    })
    const res = await fetch(`/api/values?${params}`)
    if (!res.ok) {
      failed.value = `${res.status} ${res.statusText}`
      return
    }
    values.value = (await res.json()).values ?? []
  }
  catch (e: any) {
    failed.value = e?.message ?? 'Request failed'
  }
}

const card = useTemplateRef<HTMLElement>('card')

async function bench(runs: number) {
  const frames = () => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
  const data = demoForecast(startOfHour())
  // ready: the DOM is patched (a Vue render is synchronous); painted: two animation frames later, which has the
  // browser's layout and paint in it and is quantised to the frame (16.7 ms at 60 Hz)
  const ready: number[] = []
  const painted: number[] = []
  for (let i = 0; i < runs + 2; i++) {
    values.value = []
    await nextTick()
    await frames()
    const t0 = performance.now()
    values.value = data
    await nextTick()
    const t1 = performance.now()
    await frames()
    // the first two runs warm the code up
    if (i >= 2) {
      ready.push(t1 - t0)
      painted.push(performance.now() - t0)
    }
  }
  const median = (list: number[]) => [...list].sort((a, b) => a - b)[Math.floor(list.length / 2)]!
  card.value?.setAttribute('data-render-stats', `runs=${runs} ready=${median(ready).toFixed(1)} painted=${median(painted).toFixed(1)}`)
}

onMounted(async () => {
  await load()
  const runs = Number(route.query.bench)
  if (Number.isFinite(runs) && runs > 0) {
    await nextTick()
    await bench(runs)
  }
})
</script>

<template>
  <UContainer class="mx-auto max-w-4xl px-4 py-6 space-y-6">
    <div class="text-center mb-4">
      <h1 class="text-3xl font-bold mb-4 break-words">
        {{ t('meteogram.title') }} (SVG)
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        Prototype of the forecast chart drawn as SVG without Plotly (GH-3237). Not linked from the app.
      </p>
    </div>

    <UAlert v-if="usingDemo" color="neutral" variant="subtle" icon="i-lucide-flask-conical" title="Synthetic data">
      <template #description>
        The numbers are generated, no readings. Add <code>?station=10384</code> to draw a MOSMIX station from the backend.
      </template>
    </UAlert>
    <UAlert v-if="failed" color="error" variant="subtle" icon="i-lucide-alert-circle" :title="failed" />

    <UCard v-if="values.length">
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-cloud-sun" class="text-primary-500" />
          <span class="text-lg font-bold">{{ station.name }}</span>
          <span class="text-gray-600 dark:text-gray-400 text-sm">({{ station.station_id }})</span>
        </div>
      </template>
      <div ref="card">
        <MeteogramSvg
          :values="values"
          :station-name="station.name"
          :station-coords="{ latitude: station.latitude, longitude: station.longitude }"
        />
      </div>
    </UCard>
  </UContainer>
</template>
