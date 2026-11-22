<script setup lang="ts">
import type { CoverageParameter, ProviderNetworkCoverageResponse, Station, Value, ValuesResponse } from '#shared/types/api'
import type { CompareDescription } from '~/utils/compare-export'
import type { ComparePeriod, CompareReading, CompareResolution, CompareRow, CompareState, CompareSummary, SideKind } from '~/utils/compare-model'
import type { ExplorerSeries } from '~/utils/explorer-model'
import ExplorerChart from '~/components/ExplorerChart.vue'
import ProviderCredit from '~/components/ProviderCredit.vue'
import StationSelection from '~/components/StationSelection.vue'
import { API_FETCH } from '~/utils/api-answer'
import { describeFetchError } from '~/utils/api-error'
import { compareToCsv, compareToJson } from '~/utils/compare-export'
import {
  alignPeriods,
  alignStations,
  chartPoints,
  COMPARE_SOURCE,
  isCompareResolution,
  isTotal,
  MAX_STEPS,
  periodLength,
  periodOfFields,
  readingsOf,
  requestWindow,
  sideKindOf,
  sidesDiffer,
  suggestedPeriods,
  summarize,
  valueText,
} from '~/utils/compare-model'
import { processingNote } from '~/utils/processing-note'
import { creditLines, termsOfProvider } from '~/utils/provider-credit'
import { requestUnitTargets } from '~/utils/unit-targets'

// The Compare tool (GH-4296): two stations over one period, or one station over two periods, for one parameter, in one chart and one table
// with the difference (side B minus side A). What the sides are, how they are aligned, what is refused and how the address holds the
// comparison is `utils/compare-model.ts`; this draws it, in the two columns every tool has: the choices, and what comes of them.

const props = defineProps<{
  /** The ids of the stations a link names, which the pickers restore */
  initialStationIds: string[]
  /** A link that names a whole comparison opens it, as a link to a table does elsewhere in the app */
  fromLink?: boolean
}>()

const state = defineModel<CompareState>({ required: true })

const { t } = useI18n()
const formatLanguage = useFormatLanguage()
const { parameterLabel } = useParameterLabel()
const { settings: appSettings } = useSettings()
const { data: providerList } = useProviders()
const toast = useToast()

// -- what is compared --------------------------------------------------------------------------------------------------

const resolution = computed(() => state.value.resolution)
const parameter = computed(() => state.value.parameter ?? '')

// The parameters of the daily and the monthly climate summary of DWD's observations, as the backend's coverage lists them (the one request
// the glossary-free form needs); a failure is told, with a retry, and leaves the form as it is
const { data: coverage, status: coverageStatus, refresh: refreshCoverage } = useFetch<ProviderNetworkCoverageResponse>('/api/coverage', {
  key: 'compare-coverage',
  query: { provider: COMPARE_SOURCE.provider, network: COMPARE_SOURCE.network },
  ...API_FETCH,
})
const coverageFailed = computed(() => coverageStatus.value === 'error')
const parameterNames = computed<string[]>(() =>
  (coverage.value?.[resolution.value]?.datasets[COMPARE_SOURCE.dataset]?.parameters ?? []).map((item: CoverageParameter) => item.name).sort())
const { resolutionLabel } = useParameterLabel()
const resolutionItems = computed(() => COMPARE_SOURCE.resolutions.map(name => ({ value: name, label: resolutionLabel(name) })))
const parameterItems = computed(() => parameterNames.value.map(name => ({ value: name, label: parameterLabel(name) })))

// the parameter the form starts with: the mean air temperature, where the dataset has it; a link's own is never written over
watch(parameterNames, (names) => {
  if (!state.value.parameter && names.includes('temperature_air_mean_2m'))
    state.value = { ...state.value, parameter: 'temperature_air_mean_2m' }
}, { immediate: true })

function setResolution(value: unknown) {
  if (isCompareResolution(value) && value !== state.value.resolution)
    state.value = { ...state.value, resolution: value, parameter: undefined }
}
function setParameter(value: unknown) {
  state.value = { ...state.value, parameter: typeof value === 'string' && value ? value : undefined }
}

/** What the station pickers ask the list of stations for: the dataset, and the parameter that must be there */
const parameterSelection = computed(() => ({
  provider: COMPARE_SOURCE.provider,
  network: COMPARE_SOURCE.network,
  resolution: resolution.value,
  dataset: COMPARE_SOURCE.dataset,
  parameters: parameter.value ? [parameter.value] : [],
}))

const stepWord = computed(() => t(resolution.value === 'monthly' ? 'compare.stepMonths' : 'compare.stepDays'))
const byOptions = computed(() => [
  { value: 'stations' as const, label: t('compare.byStations'), icon: 'i-ph-map-pin' },
  { value: 'periods' as const, label: t('compare.byPeriods'), icon: 'i-ph-calendar-blank' },
])

function setBy(by: CompareState['by']) {
  if (state.value.by === by)
    return
  state.value = { ...state.value, by, idB: by === 'periods' ? undefined : state.value.idB }
}

// -- the sides the reader chooses ---------------------------------------------------------------------------------------

// The stations as the pickers hold them: their names are what the chart and the table call a side
const pickedA = ref<Station>()
const pickedB = ref<Station>()
const idsFromLink = computed(() => props.initialStationIds)

const pickerTouched = { A: false, B: false }
function pick(side: 'A' | 'B', stations: Station[]) {
  const station = stations[0]
  if (side === 'A')
    pickedA.value = station
  else
    pickedB.value = station
  const id = station?.station_id
  // a picker that has not restored the link's station yet answers with none: the id of the link stays until a station is chosen
  if (!station && (side === 'A' ? state.value.idA : state.value.idB) && !pickerTouched[side])
    return
  pickerTouched[side] = true
  state.value = side === 'A' ? { ...state.value, idA: id } : { ...state.value, idB: id }
}

// another resolution is another list of stations: the stations of the one before are gone
let lastResolution = state.value.resolution
watch(resolution, (now) => {
  if (now === lastResolution)
    return
  lastResolution = now
  pickedA.value = undefined
  pickedB.value = undefined
  state.value = { ...state.value, idA: undefined, idB: undefined }
  clearResult()
})

// The fields start with a period, so that a comparison is a choice of stations away: the last complete month, and for two periods the
// same one a year before. Only an empty pair is filled; what a link or the reader has put in is never written over
watch([() => state.value.by, resolution], () => {
  if (!['daily', 'monthly'].includes(resolution.value))
    return
  const { latest, yearBefore } = suggestedPeriods(resolution.value)
  const s = state.value
  const empty = (fields: { start?: string, end?: string }) => !fields.start && !fields.end
  if (s.by === 'stations' && empty(s.period))
    state.value = { ...s, period: { start: latest.start, end: latest.end } }
  else if (s.by === 'periods' && empty(s.periodA) && empty(s.periodB))
    state.value = { ...s, periodA: { start: yearBefore.start, end: yearBefore.end }, periodB: { start: latest.start, end: latest.end } }
}, { immediate: true })

function setField(which: 'period' | 'periodA' | 'periodB', end: 'start' | 'end', value: unknown) {
  state.value = { ...state.value, [which]: { ...state.value[which], [end]: typeof value === 'string' && value ? value : undefined } }
}

const stationA = computed(() => pickedA.value ?? (state.value.idA ? { station_id: state.value.idA, name: state.value.idA } as Station : undefined))
const stationB = computed(() => pickedB.value ?? (state.value.idB ? { station_id: state.value.idB, name: state.value.idB } as Station : undefined))
const nameOf = (station: Station | undefined) => station ? (station.name && station.name !== station.station_id ? `${station.name} (${station.station_id})` : station.station_id) : ''

function formatNumberText(value: number) {
  return new Intl.NumberFormat(formatLanguage.value).format(value)
}

// What is wrong with the choices, said where the reader is choosing: a period that ends before it starts, one longer than a comparison
// holds, two stations that are one
function periodProblem(fields: { start?: string, end?: string }): string | null {
  if (!fields.start || !fields.end)
    return null
  const period = periodOfFields(fields)
  if (!period)
    return t('dateRange.errEndAfterStart')
  const steps = periodLength(period, resolution.value)
  if (steps > MAX_STEPS[resolution.value])
    return t('compare.periodTooLong', { max: formatNumberText(MAX_STEPS[resolution.value]), unit: stepWord.value })
  return null
}
const problems = computed(() => ({
  period: periodProblem(state.value.period),
  periodA: periodProblem(state.value.periodA),
  periodB: periodProblem(state.value.periodB),
  stations: state.value.by === 'stations' && state.value.idA && state.value.idA === state.value.idB ? t('compare.sameStation') : null,
}))

const ready = computed(() => {
  const s = state.value
  if (!s.parameter)
    return false
  if (Object.values(problems.value).some(Boolean))
    return false
  if (s.by === 'stations')
    return !!s.idA && !!s.idB && !!periodOfFields(s.period)
  return !!s.idA && !!periodOfFields(s.periodA) && !!periodOfFields(s.periodB)
})

// -- the request --------------------------------------------------------------------------------------------------------

interface Answer {
  rows: Value[]
  metadata: { parameters?: { name: string, unit?: string | null, aggregation?: string | null, timestamp_position?: string | null }[] | null } | null
}

/** One side's request: the same query for either, differing in the stations and the window; the units are the app settings' (GH-3878) */
function queryFor(stations: string, window: { start: string, end: string }): Record<string, string> {
  const selection = parameterSelection.value
  return {
    provider: selection.provider!,
    network: selection.network!,
    parameters: `${selection.resolution}/${selection.dataset}/${parameter.value}`,
    stations,
    timestamp: (({ start, end }) => `${start}/${end}`)(requestWindow(window, resolution.value)),
    shape: 'long',
    humanize: 'true',
    skip_empty: 'false',
    // a day with no value is a row with none, so that the table says it was missing
    drop_nulls: 'false',
    with_metadata: 'true',
    convert_units: String(appSettings.value.convertUnits),
    unit_targets: JSON.stringify(requestUnitTargets(appSettings.value.units)),
  }
}

async function requestValues(query: Record<string, string>, signal: AbortSignal): Promise<Answer> {
  const answer = await $fetch<ValuesResponse & { metadata?: Answer['metadata'] }>('/api/values', { query, signal, ...API_FETCH })
  return { rows: answer.values ?? [], metadata: answer.metadata ?? null }
}

/** Everything the table, the chart and the files are made of: the request that was answered, and nothing of the selection since */
interface Result {
  /** The choices it was asked with (`choiceKey`) */
  key: string
  /** Period A as it was asked, which the chart of two periods takes its dates from */
  periodA: ComparePeriod | undefined
  by: CompareState['by']
  resolution: CompareResolution
  parameter: string
  provider: string
  unit: string
  aggregation: string | null
  names: { a: string, b: string }
  /** The period of each side as it was asked, `YYYY-MM-DD/YYYY-MM-DD` */
  windows: { a: string, b: string }
  rows: CompareRow[]
  summary: CompareSummary
  /** Why the sides cannot be subtracted, where they cannot: no rows then */
  refused: ReturnType<typeof sidesDiffer>
  /** The sides' own periods, for the note of two periods of unequal length */
  lengths: { a: number, b: number }
}

const status = ref<'idle' | 'loading' | 'error' | 'done'>('idle')
const result = shallowRef<Result | null>(null)
const failure = ref('')
let controller: AbortController | null = null

function clearResult() {
  controller?.abort()
  controller = null
  result.value = null
  failure.value = ''
  status.value = 'idle'
}

function kindOf(answer: Answer, rows: Value[]): SideKind {
  return sideKindOf(parameter.value, answer.metadata?.parameters, rows)
}

/** What a request is made of, as the reader chose it: the table is outdated once this is another */
function choiceKey(): string {
  const s = state.value
  const sides = s.by === 'stations'
    ? [s.idA, s.idB, periodOfFields(s.period)]
    : [s.idA, periodOfFields(s.periodA), periodOfFields(s.periodB)]
  return JSON.stringify([s.by, parameter.value, resolution.value, sides])
}

async function fetchComparison() {
  if (!ready.value)
    return
  controller?.abort()
  const mine = new AbortController()
  controller = mine
  status.value = 'loading'
  failure.value = ''
  const s = state.value
  const res = resolution.value
  const key = choiceKey()
  let periodA: ComparePeriod | undefined
  try {
    let rows: CompareRow[]
    let kinds: [SideKind, SideKind]
    let unit: string | null
    let aggregation: string | null
    let lengths: { a: number, b: number }
    let windows: { a: string, b: string }
    let names: { a: string, b: string }
    if (s.by === 'stations') {
      const period = periodOfFields(s.period)!
      const answer = await requestValues(queryFor(`${s.idA},${s.idB}`, period), mine.signal)
      const own = (id: string) => answer.rows.filter(row => row.station_id === id)
      rows = alignStations(readingsOf(answer.rows, s.idA!, res) as CompareReading[], readingsOf(answer.rows, s.idB!, res) as CompareReading[], period, res)
      kinds = [kindOf(answer, own(s.idA!)), kindOf(answer, own(s.idB!))]
      unit = kinds[0].unit
      aggregation = kinds[0].aggregation
      const length = periodLength(period, res)
      lengths = { a: length, b: length }
      windows = { a: `${period.start}/${period.end}`, b: `${period.start}/${period.end}` }
      names = { a: nameOf(stationA.value), b: nameOf(stationB.value) }
    }
    else {
      const a = periodOfFields(s.periodA)!
      const b = periodOfFields(s.periodB)!
      periodA = a
      const [answerA, answerB] = await Promise.all([requestValues(queryFor(s.idA!, a), mine.signal), requestValues(queryFor(s.idA!, b), mine.signal)])
      rows = alignPeriods(readingsOf(answerA.rows, null, res), a, readingsOf(answerB.rows, null, res), b, res)
      kinds = [kindOf(answerA, answerA.rows), kindOf(answerB, answerB.rows)]
      unit = kinds[0].unit
      aggregation = kinds[0].aggregation
      lengths = { a: periodLength(a, res), b: periodLength(b, res) }
      windows = { a: `${a.start}/${a.end}`, b: `${b.start}/${b.end}` }
      names = { a: `${a.start} – ${a.end}`, b: `${b.start} – ${b.end}` }
    }
    if (mine.signal.aborted)
      return
    const refused = sidesDiffer(kinds[0], kinds[1])
    const shown = refused ? [] : rows
    result.value = {
      key,
      periodA,
      by: s.by,
      resolution: res,
      parameter: parameter.value,
      provider: COMPARE_SOURCE.provider,
      unit: unit ?? '',
      aggregation,
      names,
      windows,
      rows: shown,
      summary: summarize(shown),
      refused,
      lengths,
    }
    status.value = 'done'
  }
  catch (error) {
    if (mine.signal.aborted)
      return
    failure.value = describeFetchError(error)
    result.value = null
    status.value = 'error'
    toast.add({ title: t('dataViewer.fetchErrorToastTitle'), description: failure.value, color: 'error' })
  }
}

onBeforeUnmount(() => controller?.abort())

// A link that names the whole comparison opens it once the choices are valid (the pickers have restored the stations, the dataset is
// known), as a link to a table elsewhere shows it: a comparison is what the link was shared for
let openedFromLink = !props.fromLink
function openFromLink() {
  if (openedFromLink || !ready.value)
    return
  // the pickers have restored the stations: their names are what a side is called
  if (!pickedA.value || (state.value.by === 'stations' && !pickedB.value))
    return
  openedFromLink = true
  void fetchComparison()
}
watch([ready, pickedA, pickedB], openFromLink, { immediate: true })

// What the choices are now is not what the table says once they differ: the table is told so, and Show asks again
const outdated = computed(() => status.value === 'done' && result.value !== null && result.value.key !== choiceKey())

// -- what the table and the chart show ---------------------------------------------------------------------------------

const unitText = computed(() => result.value?.unit ? ` ${result.value.unit}` : '')
const total = computed(() => isTotal(result.value?.aggregation))
const fmt = (value: number | null, signed = false) => value === null ? '' : valueText(value, formatLanguage.value, signed)
const stepsUnit = computed(() => t(result.value?.resolution === 'monthly' ? 'compare.stepMonths' : 'compare.stepDays'))

/** The label of a row's step: the day, or the month */
const dateOf = (date: string | null) => date === null ? '' : result.value?.resolution === 'monthly' ? date.slice(0, 7) : date

const alignmentNote = computed(() => {
  const r = result.value
  if (!r)
    return ''
  if (r.by === 'stations')
    return t(r.resolution === 'monthly' ? 'compare.alignMonthsStations' : 'compare.alignDaysStations')
  const text = t(r.resolution === 'monthly' ? 'compare.alignMonthsPeriods' : 'compare.alignDaysPeriods')
  if (r.lengths.a === r.lengths.b)
    return text
  const shorter = Math.min(r.lengths.a, r.lengths.b)
  const longer = Math.max(r.lengths.a, r.lengths.b)
  return `${text} ${t('compare.alignUnequal', { shorter: r.lengths.a < r.lengths.b ? 'A' : 'B', count: shorter, rest: longer - shorter, unit: stepsUnit.value })}`
})

const refusedText = computed(() => result.value?.refused ? t('compare.differs', { reason: t(`compare.reason.${result.value.refused}`) }) : '')

const series = computed((): ExplorerSeries[] => {
  const r = result.value
  if (!r || r.refused)
    return []
  const points = chartPoints(r.rows, r.by, r.periodA, r.resolution)
  const out: ExplorerSeries[] = []
  const common = { kind: 'values' as const, resolution: r.resolution }
  if (points.a.y.some(y => y !== null))
    out.push({ id: 'compare-a', name: `A · ${r.names.a}`, colorIndex: 0, ...common, x: points.a.x, y: points.a.y })
  if (points.b.y.some(y => y !== null))
    out.push({ id: 'compare-b', name: `B · ${r.names.b}`, colorIndex: 2, ...common, look: { dashed: true, symbol: 'rect' }, x: points.b.x, y: points.b.y })
  return out
})

const chartLabel = computed(() => result.value ? t('compare.chartLabel', { parameter: parameterLabel(result.value.parameter), a: result.value.names.a, b: result.value.names.b }) : '')
const captionText = computed(() => result.value ? t('compare.tableCaption', { parameter: parameterLabel(result.value.parameter), a: result.value.names.a, b: result.value.names.b, unit: result.value.unit }) : '')
const noValues = computed(() => !!result.value && !result.value.refused && result.value.summary.compared === 0)

const differenceTitle = computed(() => t('compare.colDifference', { unit: result.value?.unit ?? '' }))

// -- the download -----------------------------------------------------------------------------------------------------

const terms = computed(() => termsOfProvider(providerList.value?.providers, result.value?.provider ?? COMPARE_SOURCE.provider))

function download(format: 'csv' | 'json') {
  const r = result.value
  if (!r || r.refused)
    return
  const note = processingNote(t, false)
  const description: CompareDescription = {
    by: r.by,
    parameter: r.parameter,
    resolution: r.resolution,
    unit: r.unit,
    aggregation: r.aggregation,
    sides: { a: { name: r.names.a, period: r.windows.a }, b: { name: r.names.b, period: r.windows.b } },
    alignment: r.by === 'stations' ? 'calendar' : 'position-in-period',
    difference: 'B - A',
  }
  const credit = creditLines(terms.value, (name, url) => t('credit.licence', { name, url }), note)
  const content = format === 'csv'
    ? compareToCsv(r.rows, description, [...credit, t('compare.fileSides', { a: r.names.a, b: r.names.b }), alignmentNote.value, total.value ? t('compare.noteTotal') : ''])
    : compareToJson(r.rows, description, r.summary, {
        ...(terms.value ? { provider: { attribution: terms.value.attribution || null, license: terms.value.license ? { name: terms.value.license.name, url: terms.value.license.url } : null } } : {}),
        processing_note: note,
      })
  const url = URL.createObjectURL(new Blob([content], { type: 'application/octet-stream' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `compare.${format}`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
  toast.add({ title: t('dataViewer.downloaded'), description: t('dataViewer.downloadedValues', { format: format.toUpperCase() }), color: 'success' })
}

const downloadItems = computed(() => [[
  { label: 'CSV', disabled: !result.value || !!result.value.refused, onSelect: () => download('csv') },
  { label: 'JSON', disabled: !result.value || !!result.value.refused, onSelect: () => download('json') },
]])

const loading = computed(() => status.value === 'loading')
const chartNoteId = useId()
const headingId = useId()
</script>

<template>
  <ToolWorkbench data-testid="compare">
    <template #setup>
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-ph-scales" class="text-primary-600 dark:text-primary-500 shrink-0" />
            <h2 :id="headingId" class="text-lg font-bold">
              {{ t('compare.title') }}
            </h2>
          </div>
        </template>
        <div class="space-y-6">
          <FittingButtonGroup role="group" :aria-label="t('compare.byLabel')">
            <UButton
              v-for="option in byOptions"
              :key="option.value"
              :icon="option.icon"
              :label="option.label"
              color="neutral"
              :variant="state.by === option.value ? 'solid' : 'ghost'"
              :aria-pressed="state.by === option.value"
              size="sm"
              :data-testid="`compare-by-${option.value}`"
              @click="setBy(option.value)"
            />
          </FittingButtonGroup>

          <!-- the measure: DWD's observations, the daily or the monthly climate summary (approach C of GH-3789) -->
          <div class="grid gap-4 sm:grid-cols-2">
            <UFormField :label="t('parameterSelection.resolutionLabel')">
              <USelect :model-value="state.resolution" :items="resolutionItems" class="w-full" data-testid="compare-resolution" @update:model-value="setResolution" />
            </UFormField>
            <UFormField :label="t('dataViewer.statParameter')">
              <USelectMenu
                :model-value="state.parameter"
                :items="parameterItems"
                value-key="value"
                :placeholder="t('compare.selectParameter')"
                :disabled="!parameterItems.length"
                :loading="coverageStatus === 'pending'"
                class="w-full"
                data-testid="compare-parameter"
                @update:model-value="setParameter"
              />
            </UFormField>
          </div>
          <UAlert
            v-if="coverageFailed"
            color="error"
            variant="subtle"
            icon="i-ph-warning-circle"
            :title="t('parameterSelection.backendUnreachable')"
            :actions="[{ label: t('common.retry'), icon: 'i-ph-arrow-clockwise', color: 'neutral', variant: 'outline', size: 'sm', onClick: () => refreshCoverage() }]"
          />

          <template v-if="state.by === 'stations'">
            <div class="grid gap-6 md:grid-cols-2">
              <StationSelection
                :model-value="{ stations: pickedA ? [pickedA] : [] }"
                :parameter-selection="parameterSelection"
                :initial-station-ids="idsFromLink.slice(0, 1)"
                :label="t('compare.stationA')"
                fetch-key="compare-stations-a"
                tool="explorer"
                data-testid="compare-station-a"
                @update:model-value="pick('A', $event.stations)"
              />
              <StationSelection
                :model-value="{ stations: pickedB ? [pickedB] : [] }"
                :parameter-selection="parameterSelection"
                :initial-station-ids="idsFromLink.slice(1, 2)"
                :label="t('compare.stationB')"
                fetch-key="compare-stations-b"
                tool="explorer"
                data-testid="compare-station-b"
                @update:model-value="pick('B', $event.stations)"
              />
            </div>
            <p v-if="problems.stations" class="text-sm text-red-600 dark:text-red-400" role="alert">
              {{ problems.stations }}
            </p>
            <div role="group" :aria-labelledby="`${headingId}-period`" class="space-y-2">
              <span :id="`${headingId}-period`" class="text-sm font-medium">{{ t('compare.period') }}</span>
              <div class="flex flex-wrap gap-4">
                <UFormField :label="t('compare.start')" class="flex-1">
                  <UInput :model-value="state.period.start" type="date" class="w-full" data-testid="compare-period-start" @update:model-value="setField('period', 'start', $event)" />
                </UFormField>
                <UFormField :label="t('compare.end')" class="flex-1">
                  <UInput :model-value="state.period.end" type="date" class="w-full" data-testid="compare-period-end" @update:model-value="setField('period', 'end', $event)" />
                </UFormField>
              </div>
              <p v-if="problems.period" class="text-sm text-red-600 dark:text-red-400" role="alert">
                {{ problems.period }}
              </p>
            </div>
          </template>
          <template v-else>
            <StationSelection
              :model-value="{ stations: pickedA ? [pickedA] : [] }"
              :parameter-selection="parameterSelection"
              :initial-station-ids="idsFromLink.slice(0, 1)"
              :label="t('compare.station')"
              fetch-key="compare-stations-a"
              tool="explorer"
              data-testid="compare-station-a"
              @update:model-value="pick('A', $event.stations)"
            />
            <div class="grid gap-6 md:grid-cols-2">
              <div role="group" :aria-labelledby="`${headingId}-a`" class="space-y-2">
                <span :id="`${headingId}-a`" class="text-sm font-medium">{{ t('compare.periodA') }}</span>
                <div class="flex flex-wrap gap-4">
                  <UFormField :label="t('compare.start')" class="flex-1">
                    <UInput :model-value="state.periodA.start" type="date" class="w-full" data-testid="compare-period-a-start" @update:model-value="setField('periodA', 'start', $event)" />
                  </UFormField>
                  <UFormField :label="t('compare.end')" class="flex-1">
                    <UInput :model-value="state.periodA.end" type="date" class="w-full" data-testid="compare-period-a-end" @update:model-value="setField('periodA', 'end', $event)" />
                  </UFormField>
                </div>
                <p v-if="problems.periodA" class="text-sm text-red-600 dark:text-red-400" role="alert">
                  {{ problems.periodA }}
                </p>
              </div>
              <div role="group" :aria-labelledby="`${headingId}-b`" class="space-y-2">
                <span :id="`${headingId}-b`" class="text-sm font-medium">{{ t('compare.periodB') }}</span>
                <div class="flex flex-wrap gap-4">
                  <UFormField :label="t('compare.start')" class="flex-1">
                    <UInput :model-value="state.periodB.start" type="date" class="w-full" data-testid="compare-period-b-start" @update:model-value="setField('periodB', 'start', $event)" />
                  </UFormField>
                  <UFormField :label="t('compare.end')" class="flex-1">
                    <UInput :model-value="state.periodB.end" type="date" class="w-full" data-testid="compare-period-b-end" @update:model-value="setField('periodB', 'end', $event)" />
                  </UFormField>
                </div>
                <p v-if="problems.periodB" class="text-sm text-red-600 dark:text-red-400" role="alert">
                  {{ problems.periodB }}
                </p>
              </div>
            </div>
          </template>

          <div class="flex flex-col sm:flex-row gap-2">
            <UButton :label="t('common.fetch')" icon="i-ph-play" color="primary" :disabled="!ready || loading" class="w-full" data-testid="compare-fetch" @click="fetchComparison" />
            <UButton :label="t('common.clear')" icon="i-ph-x" variant="outline" class="w-full" @click="clearResult" />
          </div>
        </div>
      </UCard>
    </template>

    <!-- the result: the chart and the table are two views of the same numbers, and the table is the chart's alternative -->
    <template #result>
      <ToolPlaceholder v-if="status === 'idle'" tool="compare" />
      <UCard v-else data-testid="compare-result">
        <p v-if="loading" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400" role="status">
          <UIcon name="i-ph-circle-notch" class="animate-spin shrink-0" />
          {{ t('common.loading') }}
        </p>
        <div v-else-if="status === 'error'" class="flex flex-col items-center justify-center gap-1 py-8 text-center text-red-600 dark:text-red-400" role="alert">
          <span class="font-medium">{{ t('dataViewer.fetchError') }}</span>
          <span class="text-sm">{{ failure }}</span>
        </div>
        <template v-else-if="result">
          <UAlert v-if="result.refused" color="neutral" variant="subtle" icon="i-ph-warning" :title="refusedText" data-testid="compare-refused" />
          <template v-else>
            <p v-if="outdated" class="mb-3 text-sm text-gray-600 dark:text-gray-400" role="status" data-testid="compare-outdated">
              {{ t('compare.outdated') }}
            </p>
            <!-- the numbers, as a sentence a screen reader reads where it lands: what was compared and how far apart the sides are -->
            <div class="space-y-1 mb-4" role="status" data-testid="compare-summary">
              <p class="text-sm">
                {{ t('compare.summaryCompared', { compared: result.summary.compared, rows: result.summary.rows, unit: stepsUnit }) }}
              </p>
              <p v-if="noValues" class="text-sm text-gray-600 dark:text-gray-400">
                {{ t('compare.noValues') }}
              </p>
              <template v-else>
                <p class="text-sm font-medium" data-testid="compare-mean">
                  {{ t('compare.summaryMean', { a: fmt(result.summary.meanA), b: fmt(result.summary.meanB), difference: fmt(result.summary.meanDifference, true), unit: result.unit }) }}
                </p>
                <p v-if="total" class="text-sm font-medium" data-testid="compare-sum">
                  {{ t('compare.summarySum', { a: fmt(result.summary.sumA), b: fmt(result.summary.sumB), difference: fmt(result.summary.sumDifference, true), unit: result.unit }) }}
                </p>
              </template>
            </div>

            <div v-if="series.length" class="py-2">
              <ExplorerChart :series="series" :large="false" :height="360" camera-file="compare" :label="chartLabel" :described-by="chartNoteId" />
            </div>
            <p :id="chartNoteId" class="text-sm text-gray-600 dark:text-gray-400 mb-4" data-testid="compare-chart-note">
              {{ t('compare.chartAlternative') }} {{ alignmentNote }}
            </p>

            <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
              <h3 class="text-sm font-semibold">
                {{ t('compare.tableTitle') }}
              </h3>
              <UDropdownMenu :items="downloadItems" :modal="false">
                <UButton size="xs" variant="ghost" icon="i-ph-download-simple" :aria-label="t('dataViewer.download')" data-testid="compare-download" />
              </UDropdownMenu>
            </div>
            <!-- a region that scrolls is reachable by keyboard and named (WCAG 2.1.1, axe scrollable-region-focusable) -->
            <div class="overflow-auto max-h-[28rem] border border-default rounded-md" role="region" tabindex="0" :aria-label="t('compare.tableTitle')">
              <table class="w-full text-sm border-collapse" data-testid="compare-table">
                <caption class="sr-only">
                  {{ captionText }}
                </caption>
                <thead class="sticky top-0 bg-default">
                  <tr class="text-left">
                    <th scope="col" class="py-1 px-2 font-semibold">
                      {{ t(result.resolution === 'monthly' ? 'compare.colMonth' : 'compare.colDay') }}
                    </th>
                    <th scope="col" class="py-1 px-2 font-semibold">
                      {{ t('compare.colDateA') }}
                    </th>
                    <th scope="col" class="py-1 px-2 font-semibold">
                      {{ t('compare.colDateB') }}
                    </th>
                    <th scope="col" class="py-1 px-2 font-semibold text-right">
                      {{ t('compare.colA', { unit: result.unit }) }}
                    </th>
                    <th scope="col" class="py-1 px-2 font-semibold text-right">
                      {{ t('compare.colB', { unit: result.unit }) }}
                    </th>
                    <th scope="col" class="py-1 px-2 font-semibold text-right">
                      {{ differenceTitle }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in result.rows" :key="row.step" class="border-t border-default" data-testid="compare-row">
                    <th scope="row" class="py-1 px-2 font-normal text-left tabular-nums">
                      {{ row.step }}
                    </th>
                    <td class="py-1 px-2 tabular-nums whitespace-nowrap">
                      {{ dateOf(row.dateA) }}
                    </td>
                    <td class="py-1 px-2 tabular-nums whitespace-nowrap">
                      {{ dateOf(row.dateB) }}
                    </td>
                    <td class="py-1 px-2 text-right tabular-nums">
                      {{ fmt(row.a) }}
                    </td>
                    <td class="py-1 px-2 text-right tabular-nums">
                      {{ fmt(row.b) }}
                    </td>
                    <td class="py-1 px-2 text-right tabular-nums font-medium">
                      {{ fmt(row.difference, true) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="mt-3 space-y-1 text-sm text-gray-600 dark:text-gray-400">
              <p data-testid="compare-difference-note">
                {{ t('compare.noteDifference', { unit: unitText.trim() || '–' }) }} {{ total ? t('compare.noteTotal') : '' }}
              </p>
            </div>
            <!-- whose data it is and what was done to it, for both sides (GH-4255): both come from the same provider -->
            <div class="mt-3 px-1" data-testid="compare-credit">
              <p class="text-xs text-muted mb-1">
                {{ t('compare.creditBoth') }}
              </p>
              <ProviderCredit :provider="result.provider" data-testid="explorer-credit" />
            </div>
          </template>
        </template>
      </UCard>
    </template>
  </ToolWorkbench>
</template>
