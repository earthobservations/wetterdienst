<script setup lang="ts">
import type { ProviderNetworkCoverageResponse, Station, Value, ValuesResponse } from '#shared/types/api'
import type { Bar, RainAnswer, SummerAnswer, TemperatureSource, WindAnswer } from '~/utils/answers'
import type { QuestionId } from '~/utils/questions'
import { DateTime } from 'luxon'
import tzLookup from 'tz-lookup'
import { hourlyNetworks, hourlyTemperatureIn, lastSummer, RAIN_AMOUNT, RAIN_CHANCE, rainTomorrow, WIND_GUST, WIND_MEAN, windOnDay, windWindow } from '~/utils/answers'
import { describeFetchError } from '~/utils/api-error'
import { flagEmoji } from '~/utils/country'
import { formatNumber } from '~/utils/format'
import { TOOLS } from '~/utils/sections'
import { requestUnitTargets } from '~/utils/unit-targets'
import { unitsOfAnswer, unitText } from '~/utils/units'

// The answer to one of the home page's questions (GH-3518), worked out from what the backend answers, with the chart that
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

type Status = 'loading' | 'ready' | 'empty' | 'error'
const status = ref<Status>('loading')
const failure = ref('')
// a Retry that works takes its notice, and the focus in it, away: the focus goes on to the question's heading
const failureNotice = useTemplateRef<HTMLElement>('failureNotice')
const heading = useTemplateRef<HTMLElement>('heading')
useFocusAfterRetry(() => status.value === 'error', failureNotice, heading)

const rain = ref<{ answer: RainAnswer | null, point: Station } | null>(null)
const summer = ref<SummerAnswer | null>(null)
const wind = ref<WindAnswer | null>(null)
const sources = ref<TemperatureSource[]>([])

const number = (value: number, digits = 1) => formatNumber(value, locale.value, digits)
const percent = (value: number) => new Intl.NumberFormat(locale.value, { style: 'percent', maximumFractionDigits: 0 }).format(value)
const today = () => DateTime.now()

// The units the app settings choose (GH-3980), read at each request: the question's own quantity (rain, millimetres; the
// summer, degrees; the wind, a speed) and whether the values are converted at all. The answer says which unit each
// parameter is in (`with_metadata`), and the sentences, the chart and its table are written in that; what the verdicts
// compare with is judged in canonical units (utils/answers.ts), so a verdict is the same in every unit.
const { settings } = useSettings()
const QUANTITY: Partial<Record<QuestionId, 'precipitation' | 'temperature' | 'speed'>> = { rain: 'precipitation', summer: 'temperature', wind: 'speed' }
/** The unit of the question's quantity the settings choose, and whether they convert: what a change of refetches the answer for */
const unitsAsked = computed(() => {
  const quantity = QUANTITY[props.question]
  return quantity ? JSON.stringify([settings.value.convertUnits, requestUnitTargets(settings.value.units)[quantity]]) : ''
})
const chosen = (quantity: 'precipitation' | 'temperature' | 'speed') => requestUnitTargets(settings.value.units)[quantity]!

async function values(query: Record<string, string>): Promise<{ readings: Value[], units: Record<string, string> }> {
  const response = await $fetch<ValuesResponse>('/api/values', {
    query: { shape: 'long', humanize: 'true', convert_units: String(settings.value.convertUnits), with_metadata: 'true', ...query },
    ...API_FETCH,
  })
  return { readings: response.values ?? [], units: unitsOfAnswer(response) }
}

async function answerRain(): Promise<Status> {
  const near = await $fetch<{ stations: Station[] }>('/api/stations', {
    query: { provider: 'dwd', network: 'mosmix', parameters: 'hourly/large', latitude: place.value.latitude, longitude: place.value.longitude, rank: 1 },
    ...API_FETCH,
  })
  const point = near.stations?.[0]
  if (!point)
    return 'empty'
  // the chance is a probability, which the sentence writes as a percentage whatever the settings' unit for fractions
  // (oktas, say, are no way to write one): asked as a decimal, and read by the unit the answer gives where it is not
  const { readings, units } = await values({
    provider: 'dwd',
    network: 'mosmix',
    parameters: 'hourly/large/rr1c,hourly/large/r101',
    stations: point.station_id,
    unit_targets: JSON.stringify({ precipitation: chosen('precipitation'), fraction: 'decimal' }),
  })
  const answer = rainTomorrow(readings, tzLookup(place.value.latitude, place.value.longitude), today(), { precipitation: units[RAIN_AMOUNT], fraction: units[RAIN_CHANCE] })
  rain.value = { answer, point }
  return answer ? 'ready' : 'empty'
}

async function answerSummer(): Promise<Status> {
  const { readings, units } = await values({
    provider: 'dwd',
    network: 'observation',
    parameters: 'monthly/climate_summary/temperature_air_mean_2m',
    stations: place.value.id,
    unit_targets: JSON.stringify({ temperature: chosen('temperature') }),
  })
  summer.value = lastSummer(readings, today(), units.temperature_air_mean_2m)
  return summer.value ? 'ready' : 'empty'
}

async function answerWind(): Promise<Status> {
  const { from, to } = windWindow(props.day, today())
  const { readings, units } = await values({
    provider: 'dwd',
    network: 'observation',
    parameters: 'daily/climate_summary/wind_gust_max,daily/climate_summary/wind_speed_mean',
    stations: place.value.id,
    timestamp: `${from}/${to}`,
    unit_targets: JSON.stringify({ speed: chosen('speed') }),
  })
  wind.value = windOnDay(readings, props.day, units[WIND_GUST] ?? units[WIND_MEAN])
  return wind.value ? 'ready' : 'empty'
}

async function answerDownload(): Promise<Status> {
  const providers = providerList.value?.providers ?? (await $fetch<{ providers: any[] }>('/api/providers', { query: { datasets: true }, ...API_FETCH })).providers
  const candidates = hourlyNetworks(providers)
  const found = await Promise.all(candidates.map(async ({ provider, network }) => {
    try {
      const coverage = await $fetch<ProviderNetworkCoverageResponse>('/api/coverage', { query: { provider: provider.provider, network, resolutions: 'hourly' }, ...API_FETCH })
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

// the question, the place, the day, or the unit the settings choose for the question: a change of any of them asks again,
// and one under way is followed by the new one, whose answer is the only one shown
watch(() => [props.question, place.value.id, props.question === 'wind' ? props.day : '', unitsAsked.value], ask, { immediate: true })
onBeforeUnmount(() => {
  // an answer that comes after the panel is gone says nothing
  asked++
})

// ------------------------------------------------------------------------------------------------- what is said

const verdict = computed(() => {
  switch (props.question) {
    case 'rain': return rain.value?.answer ? t(`ask.rain.${rain.value.answer.verdict}`) : ''
    case 'summer': return summer.value
      ? t(`ask.summer.${summer.value.verdict}`, { anomaly: number(Math.abs(summer.value.anomaly)), unit: unitText(summer.value.unit) })
      : ''
    case 'wind': return wind.value ? t(`ask.wind.${wind.value.verdict}`) : ''
    case 'download': return t('ask.download.answer', { count: sources.value.length })
  }
  return ''
})

const details = computed<string[]>(() => {
  if (props.question === 'rain' && rain.value?.answer) {
    const answer = rain.value.answer
    const lines = [t('ask.rain.total', { amount: number(answer.total), unit: unitText(answer.unit) })]
    if (answer.wettest) {
      const next = (answer.wettest.hour + 1) % 24
      lines.push(t('ask.rain.wettest', { from: String(answer.wettest.hour).padStart(2, '0'), to: String(next).padStart(2, '0'), amount: number(answer.wettest.amount), unit: unitText(answer.unit) }))
    }
    if (answer.maxChance !== null)
      lines.push(t('ask.rain.chance', { chance: percent(answer.maxChance) }))
    return lines
  }
  if (props.question === 'summer' && summer.value) {
    const answer = summer.value
    return [
      t('ask.summer.detail', { year: answer.year, mean: number(answer.mean), from: answer.normalFrom, to: answer.normalTo, normal: number(answer.normal), unit: unitText(answer.unit) }),
      t('ask.summer.rank', { rank: answer.rank, count: answer.summers, first: answer.bars[0]?.label ?? '' }),
    ]
  }
  if (props.question === 'wind' && wind.value) {
    const answer = wind.value
    const lines: string[] = []
    if (answer.mean !== null)
      lines.push(t('ask.wind.mean', { speed: number(answer.mean), unit: unitText(answer.unit), force: answer.beaufort ?? 0 }))
    if (answer.gust !== null)
      lines.push(t('ask.wind.gust', { speed: number(answer.gust), unit: unitText(answer.unit), force: answer.gustBeaufort ?? 0 }))
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
const chart = computed<{ bars: Bar[], caption: string, unit: string, diverging?: boolean, every?: number, emphasis: 'all' | 'one', rowLabel?: (bar: Bar) => string } | null>(() => {
  if (props.question === 'rain' && rain.value?.answer)
    return { bars: rain.value.answer.hours, caption: t('ask.rain.chart', { unit: unitText(rain.value.answer.unit) }), unit: unitText(rain.value.answer.unit), every: 3, emphasis: 'all', rowLabel: bar => `${bar.label}:00` }
  if (props.question === 'summer' && summer.value) {
    return {
      bars: summer.value.bars,
      caption: t('ask.summer.chart', { from: summer.value.normalFrom, to: summer.value.normalTo, unit: unitText(summer.value.unit) }),
      unit: unitText(summer.value.unit),
      diverging: true,
      emphasis: 'one',
    }
  }
  if (props.question === 'wind' && wind.value) {
    return {
      bars: wind.value.bars.map(bar => ({ ...bar, label: DateTime.fromISO(bar.key).toFormat('d') })),
      caption: t(wind.value.barsAreGusts ? 'ask.wind.chartGust' : 'ask.wind.chartMean', { unit: unitText(wind.value.unit) }),
      unit: unitText(wind.value.unit),
      every: 7,
      emphasis: 'one',
      rowLabel: bar => dayText(bar.key, true),
    }
  }
  return null
})

// ------------------------------------------------------------------------------------- the tools, filled in

function explorerLink(query: Record<string, string>) {
  return { path: '/explorer', query: { mode: 'station', ...query } }
}

/** A link into a tool, which carries the tool's tile (`tool` is a key of `TOOLS`); `api` is a reference page and has none */
interface Action {
  key: string
  label: string
  to: string | { path: string, query: Record<string, string> }
  tool?: typeof TOOLS[number]['key']
}

const actions = computed<Action[]>(() => {
  const id = place.value.id
  switch (props.question) {
    case 'rain':
      return rain.value?.point ? [{ key: 'forecast', label: t('ask.rain.open'), tool: 'forecast', to: { path: '/meteogram', query: { station: rain.value.point.station_id } } }] : []
    case 'summer':
      return [
        { key: 'explorer', label: t('ask.summer.open'), tool: 'explorer', to: explorerLink({ provider: 'dwd', network: 'observation', resolution: 'monthly', dataset: 'climate_summary', parameters: 'temperature_air_mean_2m', stations: id }) },
        { key: 'stripes', label: t('ask.summer.stripes'), tool: 'stripes', to: { path: '/stripes', query: { kind: 'temperature', station: id } } },
      ]
    case 'wind': {
      const { from, to } = windWindow(props.day, today())
      return [{ key: 'explorer', label: t('ask.wind.open'), tool: 'explorer', to: explorerLink({ provider: 'dwd', network: 'observation', resolution: 'daily', dataset: 'climate_summary', parameters: 'wind_gust_max,wind_speed_mean', stations: id, startDate: from, endDate: to }) }]
    }
    case 'download':
      return [{ key: 'api', label: t('ask.download.api'), to: '/api' }]
  }
  return []
})
const toolOf = (action: Action) => TOOLS.find(tool => tool.key === action.tool)

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
  <section class="answer" aria-labelledby="answer-heading" data-testid="answer">
    <header>
      <p class="text-sm font-medium text-muted">
        {{ t(`ask.from.${question}`) }}
      </p>
      <h3 id="answer-heading" ref="heading" tabindex="-1" class="mt-0.5 break-words outline-none text-xl font-bold leading-snug text-highlighted sm:text-2xl">
        {{ questionText(question, day) }}
      </h3>
    </header>

    <div v-if="question === 'wind'" class="mt-4 flex flex-wrap items-center gap-2">
      <label for="answer-day" class="text-sm font-medium">{{ t('ask.wind.dayLabel') }}</label>
      <UInput id="answer-day" type="date" :model-value="day" :max="maxDay" class="w-44" @update:model-value="onDay" />
    </div>

    <!-- what a screen reader is told when the answer has come: the verdict, not the whole panel -->
    <p class="sr-only" role="status" data-testid="answer-status">
      {{ status === 'ready' ? verdict : status === 'empty' ? emptyText : '' }}
    </p>

    <div class="mt-5">
      <div v-if="status === 'loading'" role="status" class="space-y-3">
        <p class="flex items-center gap-2 text-muted">
          <UIcon name="i-ph-circle-notch" class="size-5 animate-spin text-primary" />
          {{ t('ask.working') }}
        </p>
        <div class="h-8 w-2/3 animate-pulse rounded-md bg-elevated" aria-hidden="true" />
        <div class="h-36 animate-pulse rounded-md bg-elevated" aria-hidden="true" />
      </div>

      <div v-else-if="status === 'error'" ref="failureNotice">
        <UAlert
          color="error"
          variant="subtle"
          icon="i-ph-warning-circle"
          :title="t('ask.failed')"
          :description="failure"
          :actions="[{ label: t('common.retry'), onClick: () => ask() }]"
        />
      </div>

      <p v-else-if="status === 'empty'" class="flex items-start gap-2 text-toned">
        <UIcon name="i-ph-question" class="mt-0.5 size-5 shrink-0 text-muted" />
        {{ emptyText }}
      </p>

      <div v-else class="space-y-5">
        <div>
          <p class="font-extrabold text-highlighted" :class="question === 'download' ? 'text-xl sm:text-2xl' : 'text-2xl sm:text-3xl'" data-testid="answer-verdict">
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
          :emphasis="chart.emphasis"
          :row-label="chart.rowLabel"
        />

        <ul v-if="question === 'download'" class="grid gap-2 sm:grid-cols-2" data-testid="answer-sources">
          <li v-for="source in sources" :key="`${source.provider}/${source.network}`">
            <NuxtLink :to="sourceLink(source)" class="answer-source">
              <span class="text-xl leading-none" aria-hidden="true">{{ flagEmoji(source.countryCode) }}</span>
              <span class="min-w-0 flex-1">
                <span class="block font-semibold text-highlighted">{{ source.name }}</span>
                <span class="block break-words text-xs text-muted">{{ source.network }} · {{ source.dataset }}<template v-if="source.provider === 'dwd' && source.network === 'observation'"> · <span class="font-medium text-toned">{{ place.name }}</span></template></span>
              </span>
              <UIcon name="i-ph-arrow-right" class="size-4 shrink-0 text-muted" />
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

    <!-- into the tool that holds the data, with the tool's tile: the colour says which tool it is -->
    <ul v-if="actions.length && status !== 'loading'" class="mt-6 flex flex-wrap gap-2" :aria-label="t('ask.leadsTo')" data-testid="answer-actions">
      <li v-for="action in actions" :key="action.key">
        <NuxtLink :to="action.to" class="answer-action">
          <ToolTile v-if="toolOf(action)" :tile="toolOf(action)!.tile" :icon="toolOf(action)!.icon" size="1.75rem" />
          <UIcon v-else name="i-ph-code" class="size-5 shrink-0 text-toned" />
          <span>{{ action.label }}</span>
          <UIcon name="i-ph-arrow-right" class="size-4 shrink-0" />
        </NuxtLink>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.answer-action {
  display: inline-flex;
  min-height: 2.75rem;
  align-items: center;
  gap: 0.625rem;
  padding: 0.375rem 0.875rem 0.375rem 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--ui-border-accented);
  background: var(--ui-bg);
  font-weight: 600;
  color: var(--ui-text-highlighted);
  transition: border-color 150ms, background-color 150ms;
}
.answer-action:hover {
  border-color: var(--ui-primary);
  background: var(--ui-bg-elevated);
}
.answer-source {
  display: flex;
  min-height: 2.75rem;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 0.75rem;
  border: 1px solid var(--ui-border);
  transition: border-color 150ms, background-color 150ms;
}
.answer-source:hover {
  border-color: var(--ui-border-accented);
  background: var(--ui-bg-elevated);
}
</style>
