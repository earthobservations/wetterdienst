<script setup lang="ts">
import type { ProviderNetworkCoverageResponse, Station, Value } from '#shared/types/api'
import type { Bar, RainAnswer, SummerAnswer, TemperatureSource, WindAnswer } from '~/utils/answers'
import type { QuestionId } from '~/utils/questions'
import { DateTime } from 'luxon'
import tzLookup from 'tz-lookup'
import { hourlyNetworks, hourlyTemperatureIn, lastSummer, rainTomorrow, windOnDay, windWindow } from '~/utils/answers'
import { describeFetchError } from '~/utils/api-error'
import { flagEmoji } from '~/utils/country'
import { formatNumber } from '~/utils/format'
import { QUESTIONS } from '~/utils/questions'

// The answer to one of the home page's questions, worked out from what the backend answers, with the chart that
// backs it and the way into the tool that holds the data, filled in. Nothing is said that the data does not say:
// where it has no answer (a forecast that does not reach tomorrow, a station with too few summers), the panel says so.
const props = defineProps<{
  question: QuestionId
  /** The day of the wind question, `YYYY-MM-DD` */
  day: string
}>()
const emit = defineEmits<{ 'update:day': [day: string] }>()

const { t, locale } = useI18n()
const { place } = usePlace()
const { questionText, dayText } = useQuestions()
const { data: providerList } = useProviders()

const meta = computed(() => QUESTIONS.find(entry => entry.id === props.question)!)
const heading = ref<HTMLElement | null>(null)
defineExpose({ focus: () => heading.value?.focus() })

type Status = 'loading' | 'ready' | 'empty' | 'error'
const status = ref<Status>('loading')
const failure = ref('')

const rain = ref<{ answer: RainAnswer | null, point: Station } | null>(null)
const summer = ref<SummerAnswer | null>(null)
const wind = ref<WindAnswer | null>(null)
const sources = ref<TemperatureSource[]>([])

const number = (value: number, digits = 1) => formatNumber(value, locale.value, digits)
const percent = (value: number) => new Intl.NumberFormat(locale.value, { style: 'percent', maximumFractionDigits: 0 }).format(value)
const today = () => DateTime.now()

const VALUE_OPTIONS = { shape: 'long', humanize: 'true', convert_units: 'true' } as const

async function values(query: Record<string, string>): Promise<Value[]> {
  const response = await $fetch<{ values: Value[] }>('/api/values', { query: { ...VALUE_OPTIONS, ...query }, ...RETRY_TRANSIENT })
  return response.values ?? []
}

async function answerRain() {
  const near = await $fetch<{ stations: Station[] }>('/api/stations', {
    query: { provider: 'dwd', network: 'mosmix', parameters: 'hourly/large', latitude: place.value.latitude, longitude: place.value.longitude, rank: 1 },
    ...RETRY_TRANSIENT,
  })
  const point = near.stations?.[0]
  if (!point)
    return 'empty'
  const readings = await values({
    provider: 'dwd',
    network: 'mosmix',
    parameters: 'hourly/large/rr1c,hourly/large/r101',
    stations: point.station_id,
    unit_targets: JSON.stringify({ precipitation: 'millimeter', fraction: 'decimal' }),
  })
  const answer = rainTomorrow(readings, tzLookup(place.value.latitude, place.value.longitude), today())
  rain.value = { answer, point }
  return answer ? 'ready' : 'empty'
}

async function answerSummer() {
  const readings = await values({
    provider: 'dwd',
    network: 'observation',
    parameters: 'monthly/climate_summary/temperature_air_mean_2m',
    stations: place.value.id,
    unit_targets: JSON.stringify({ temperature: 'degree_celsius' }),
  })
  summer.value = lastSummer(readings, today())
  return summer.value ? 'ready' : 'empty'
}

async function answerWind() {
  const { from, to } = windWindow(props.day, today())
  const readings = await values({
    provider: 'dwd',
    network: 'observation',
    parameters: 'daily/climate_summary/wind_gust_max,daily/climate_summary/wind_speed_mean',
    stations: place.value.id,
    timestamp: `${from}/${to}`,
    unit_targets: JSON.stringify({ speed: 'meter_per_second' }),
  })
  wind.value = windOnDay(readings, props.day)
  return wind.value ? 'ready' : 'empty'
}

async function answerDownload() {
  const providers = providerList.value?.providers ?? (await $fetch<{ providers: any[] }>('/api/providers', RETRY_TRANSIENT)).providers
  const candidates = hourlyNetworks(providers)
  const found = await Promise.all(candidates.map(async ({ provider, network }) => {
    try {
      const coverage = await $fetch<ProviderNetworkCoverageResponse>('/api/coverage', { query: { provider: provider.provider, network, resolutions: 'hourly' }, ...RETRY_TRANSIENT })
      const hit = hourlyTemperatureIn(coverage)
      return hit ? { provider: provider.provider, name: provider.name_short, countryCode: provider.country_code, network, ...hit } : null
    }
    catch {
      // a network whose coverage could not be read is left out of the list, not guessed at
      return null
    }
  }))
  const collator = new Intl.Collator(locale.value)
  sources.value = found.filter((source): source is TemperatureSource => source !== null)
    // the place's own service first, the rest by name
    .sort((a, b) => Number(b.provider === 'dwd') - Number(a.provider === 'dwd') || collator.compare(a.name, b.name))
  return sources.value.length ? 'ready' : 'empty'
}

const ANSWER: Record<QuestionId, () => Promise<Status>> = {
  rain: answerRain,
  summer: answerSummer,
  wind: answerWind,
  download: answerDownload,
}

// the last request wins: a question or place changed while one was under way discards its answer
let asked = 0
async function ask() {
  const turn = ++asked
  status.value = 'loading'
  failure.value = ''
  try {
    const result = await ANSWER[props.question]()
    if (turn === asked)
      status.value = result
  }
  catch (error) {
    if (turn !== asked)
      return
    failure.value = describeFetchError(error)
    status.value = 'error'
  }
}

watch(() => [props.question, place.value.id, props.question === 'wind' ? props.day : ''], ask, { immediate: true })

// ------------------------------------------------------------------------------------------------- what is said

const verdict = computed(() => {
  switch (props.question) {
    case 'rain': return rain.value?.answer ? t(`ask.rain.${rain.value.answer.verdict}`) : ''
    case 'summer': return summer.value
      ? t(`ask.summer.${summer.value.verdict}`, { anomaly: number(Math.abs(summer.value.anomaly)) })
      : ''
    case 'wind': return wind.value ? t(`ask.wind.${wind.value.verdict}`) : ''
    case 'download': return t('ask.download.answer', { count: sources.value.length })
  }
  return ''
})

const details = computed<string[]>(() => {
  if (props.question === 'rain' && rain.value?.answer) {
    const answer = rain.value.answer
    const lines = [t('ask.rain.total', { amount: number(answer.total) })]
    if (answer.wettest) {
      const next = (answer.wettest.hour + 1) % 24
      lines.push(t('ask.rain.wettest', { from: String(answer.wettest.hour).padStart(2, '0'), to: String(next).padStart(2, '0'), amount: number(answer.wettest.amount) }))
    }
    if (answer.maxChance !== null)
      lines.push(t('ask.rain.chance', { chance: percent(answer.maxChance) }))
    return lines
  }
  if (props.question === 'summer' && summer.value) {
    const answer = summer.value
    return [
      t('ask.summer.detail', { year: answer.year, mean: number(answer.mean), from: answer.normalFrom, to: answer.normalTo, normal: number(answer.normal) }),
      t('ask.summer.rank', { rank: answer.rank, count: answer.summers, first: answer.bars[0]?.label ?? '' }),
    ]
  }
  if (props.question === 'wind' && wind.value) {
    const answer = wind.value
    const lines: string[] = []
    if (answer.mean !== null)
      lines.push(t('ask.wind.mean', { speed: number(answer.mean), force: answer.beaufort ?? 0 }))
    if (answer.gust !== null)
      lines.push(t('ask.wind.gust', { speed: number(answer.gust), force: answer.gustBeaufort ?? 0 }))
    if (answer.around)
      lines.push(t('ask.wind.context', { stronger: answer.stronger, around: answer.around }))
    return lines
  }
  if (props.question === 'download')
    return [t('ask.download.detail')]
  return []
})

const emptyText = computed(() => {
  switch (props.question) {
    case 'rain': return t('ask.rain.none', { name: rain.value?.point.name ?? place.value.name })
    case 'summer': return t('ask.summer.none')
    case 'wind': return t('ask.wind.none', { day: dayText(props.day, true) })
    case 'download': return t('ask.download.none')
  }
  return ''
})

/** Who the data is from, in the words its licence asks for */
const attribution = computed(() => providerList.value?.providers.find(provider => provider.provider === 'dwd')?.attribution ?? 'Deutscher Wetterdienst')

const pointLine = computed(() => {
  const point = rain.value?.point
  if (!point)
    return ''
  const distance = (point as Station & { distance?: number }).distance
  return distance === undefined
    ? t('ask.rain.pointNoDistance', { name: point.name ?? point.station_id, place: place.value.name })
    : t('ask.rain.point', { name: point.name ?? point.station_id, place: place.value.name, distance: number(distance) })
})

// the chart's bars and caption
const chart = computed<{ bars: Bar[], caption: string, unit: string, diverging?: boolean, every: number, rowLabel?: (bar: Bar) => string } | null>(() => {
  if (props.question === 'rain' && rain.value?.answer)
    return { bars: rain.value.answer.hours, caption: t('ask.rain.chart', { unit: 'mm' }), unit: 'mm', every: 3, rowLabel: bar => `${bar.label}:00` }
  if (props.question === 'summer' && summer.value) {
    return {
      bars: summer.value.bars,
      caption: t('ask.summer.chart', { from: summer.value.normalFrom, to: summer.value.normalTo, unit: '°C' }),
      unit: '°C',
      diverging: true,
      every: 10,
    }
  }
  if (props.question === 'wind' && wind.value) {
    return {
      bars: wind.value.bars.map(bar => ({ ...bar, label: DateTime.fromISO(bar.key).toFormat('d') })),
      caption: t(wind.value.barsAreGusts ? 'ask.wind.chartGust' : 'ask.wind.chartMean', { unit: 'm/s' }),
      unit: 'm/s',
      every: 7,
      rowLabel: bar => dayText(bar.key, true),
    }
  }
  return null
})

// ------------------------------------------------------------------------------------- the tools, filled in

function explorerLink(query: Record<string, string>) {
  return { path: '/explorer', query: { mode: 'station', ...query } }
}

const actions = computed(() => {
  const id = place.value.id
  switch (props.question) {
    case 'rain':
      return rain.value?.point ? [{ label: t('ask.rain.open'), to: { path: '/meteogram', query: { station: rain.value.point.station_id } }, icon: 'i-lucide-cloud-sun' }] : []
    case 'summer':
      return [
        { label: t('ask.summer.open'), to: explorerLink({ provider: 'dwd', network: 'observation', resolution: 'monthly', dataset: 'climate_summary', parameters: 'temperature_air_mean_2m', stations: id }), icon: 'i-lucide-table' },
        { label: t('ask.summer.stripes'), to: { path: '/stripes', query: { kind: 'temperature', station: id } }, icon: 'i-lucide-bar-chart-3', secondary: true },
      ]
    case 'wind': {
      const { from, to } = windWindow(props.day, today())
      return [{ label: t('ask.wind.open'), to: explorerLink({ provider: 'dwd', network: 'observation', resolution: 'daily', dataset: 'climate_summary', parameters: 'wind_gust_max,wind_speed_mean', stations: id, startDate: from, endDate: to }), icon: 'i-lucide-table' }]
    }
    case 'download':
      return [{ label: t('ask.download.api'), to: '/api', icon: 'i-lucide-code', secondary: true }]
  }
  return []
})

function sourceLink(source: TemperatureSource) {
  return explorerLink({
    provider: source.provider,
    network: source.network,
    resolution: 'hourly',
    dataset: source.dataset,
    parameters: source.parameter,
    // the place's station, where the service is the place's own
    ...(source.provider === 'dwd' && source.network === 'observation' ? { stations: place.value.id } : {}),
  })
}

const maxDay = computed(() => today().minus({ days: 1 }).toISODate()!)
function onDay(value: unknown) {
  const day = String(value ?? '')
  if (/^\d{4}-\d{2}-\d{2}$/.test(day) && day <= maxDay.value)
    emit('update:day', day)
}
</script>

<template>
  <section class="answer rounded-2xl border border-default bg-default p-5 sm:p-7" aria-labelledby="answer-heading" data-testid="answer">
    <div class="flex items-start gap-4">
      <AskTile :icon="meta.icon" :tone="meta.tone" size="md" />
      <div class="min-w-0 flex-1">
        <p class="text-sm font-medium text-muted">
          {{ t(`ask.from.${question}`) }}
        </p>
        <h2 id="answer-heading" ref="heading" tabindex="-1" class="text-xl sm:text-2xl font-bold leading-snug break-words focus:outline-none">
          {{ questionText(question, day) }}
        </h2>
      </div>
    </div>

    <div v-if="question === 'wind'" class="mt-4 flex flex-wrap items-center gap-2">
      <label for="answer-day" class="text-sm font-medium">{{ t('ask.wind.dayLabel') }}</label>
      <UInput id="answer-day" type="date" :model-value="day" :max="maxDay" class="w-44" @update:model-value="onDay" />
    </div>

    <!-- what a screen reader is told when the answer has come: the verdict, not the whole panel -->
    <p class="sr-only" role="status">
      {{ status === 'ready' ? verdict : status === 'empty' ? emptyText : '' }}
    </p>
    <div class="mt-5">
      <div v-if="status === 'loading'" role="status" class="space-y-3">
        <p class="flex items-center gap-2 text-muted">
          <UIcon name="i-lucide-loader-circle" class="size-5 animate-spin text-primary" />
          {{ t('ask.working') }}
        </p>
        <div class="h-8 w-2/3 rounded-md bg-elevated animate-pulse" aria-hidden="true" />
        <div class="h-36 rounded-md bg-elevated animate-pulse" aria-hidden="true" />
      </div>

      <UAlert
        v-else-if="status === 'error'"
        color="error"
        variant="subtle"
        icon="i-lucide-alert-circle"
        :title="t('ask.failed')"
        :description="failure"
        :actions="[{ label: t('common.retry'), onClick: () => ask() }]"
      />

      <p v-else-if="status === 'empty'" class="flex items-start gap-2 text-toned">
        <UIcon name="i-lucide-circle-help" class="size-5 shrink-0 mt-0.5 text-muted" />
        {{ emptyText }}
      </p>

      <div v-else class="space-y-5">
        <div>
          <p class="font-bold text-highlighted" :class="question === 'download' ? 'text-xl sm:text-2xl' : 'text-2xl sm:text-3xl'" data-testid="answer-verdict">
            {{ verdict }}
          </p>
          <p v-for="line in details" :key="line" class="mt-1.5 text-toned">
            {{ line }}
          </p>
        </div>

        <AnswerBars
          v-if="chart"
          :bars="chart.bars"
          :caption="chart.caption"
          :unit="chart.unit"
          :diverging="chart.diverging"
          :every="chart.every"
          :row-label="chart.rowLabel"
          :tone="meta.tone"
        />

        <ul v-if="question === 'download'" class="grid gap-2 sm:grid-cols-2" data-testid="answer-sources">
          <li v-for="source in sources" :key="`${source.provider}/${source.network}`">
            <NuxtLink
              :to="sourceLink(source)"
              class="flex items-center gap-3 rounded-lg border border-default px-3 py-2.5 hover:bg-elevated transition-colors"
            >
              <span class="text-xl leading-none" aria-hidden="true">{{ flagEmoji(source.countryCode) }}</span>
              <span class="min-w-0 flex-1">
                <span class="block font-semibold text-highlighted">{{ source.name }}</span>
                <span class="block text-xs text-muted break-words">{{ source.network }} · {{ source.dataset }}<template v-if="source.provider === 'dwd' && source.network === 'observation'"> · <span class="font-medium text-primary">{{ place.name }}</span></template></span>
              </span>
              <UIcon name="i-lucide-arrow-right" class="size-4 shrink-0 text-muted" />
            </NuxtLink>
          </li>
        </ul>

        <p v-if="question === 'rain' && pointLine" class="text-sm text-muted">
          {{ pointLine }}
        </p>
        <p v-if="question !== 'download'" class="text-sm text-muted">
          {{ attribution }}
        </p>
      </div>
    </div>

    <div v-if="actions.length && status !== 'loading'" class="mt-6 flex flex-wrap gap-2">
      <UButton
        v-for="action in actions"
        :key="action.label"
        :to="action.to"
        :icon="action.icon"
        :variant="'secondary' in action && action.secondary ? 'outline' : 'solid'"
        :color="'secondary' in action && action.secondary ? 'neutral' : 'primary'"
        trailing-icon="i-lucide-arrow-right"
        size="lg"
      >
        {{ action.label }}
      </UButton>
    </div>
  </section>
</template>
