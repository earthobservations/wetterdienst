<script setup lang="ts">
import type { LimitRefusal } from '~/utils/limit-refusal'
import type { FittingWindow } from '~/utils/row-window'
import { formatNumber } from '~/utils/format'

// What the table area says where the server refused the request over one of its limits (GH-3457): the
// numbers, what can be done, and the ways on as buttons, in place of the server's English text. The
// refusal is a state of the table, not a failure: nothing went wrong, the answer is only too big for one
// body.
const props = defineProps<{
  refusal: LimitRefusal
  /** the selection is a point (interpolation, summary): no stations are chosen, and no CSV stream is offered */
  point?: boolean
  stationCount: number
  parameterCount: number
  /** the newest window that fits, where there is one */
  window: FittingWindow | null
  /** the page knows the span of the selection and not even its shortest window fits; false where it cannot tell */
  noWindow?: boolean
  /** whether applying it is still what the page selects: not after the selection moved on */
  canApply: boolean
  /** the streamed CSV of the refused request, where the server streams that many rows */
  csvHref: string | null
  /** the most rows a streamed answer holds, 0 for none */
  maxStreamRows: number
}>()

const emit = defineEmits<{
  apply: [window: FittingWindow]
}>()

const { t, locale } = useI18n()

const number = (value: number) => formatNumber(value, locale.value, 0)

const isStations = computed(() => props.refusal.limit === 'stations')

const stationsText = computed(() => t('dataViewer.limitStationsCount', { count: props.stationCount }))
const parametersText = computed(() => t('dataViewer.limitParametersCount', { count: props.parameterCount }))

const title = computed(() => isStations.value ? t('dataViewer.limitStationsTitle') : t('dataViewer.limitRowsTitle'))

const body = computed(() => isStations.value
  ? t('dataViewer.limitStationsBody', { requested: number(props.refusal.requested), maximum: number(props.refusal.maximum) })
  : t('dataViewer.limitRowsBody', { requested: number(props.refusal.requested), maximum: number(props.refusal.maximum) }))

// what can be done, with the counts of the selection where the page has them
const narrow = computed(() => {
  if (isStations.value)
    return t('dataViewer.limitNarrowStations', { stations: stationsText.value })
  if (props.point)
    return t('dataViewer.limitNarrowPoint', { parameters: parametersText.value })
  return t('dataViewer.limitNarrow', { stations: stationsText.value, parameters: parametersText.value })
})

const applyLabel = computed(() => {
  const window = props.window
  if (!window)
    return ''
  return t('dataViewer.limitApply', {
    span: t(`dataViewer.limitUnit.${window.unit}`, { count: window.count }),
    rows: number(window.rows),
  })
})

// the rows are the cause: no window to offer says so, as the buttons are not there to say it. Said only
// where the page could count the span: without one (no station publishes its record) it cannot tell
const showNoWindow = computed(() => !isStations.value && !props.window && props.noWindow === true)

const headingId = useId()
</script>

<template>
  <section
    class="flex flex-col gap-4 py-8 text-left"
    data-testid="limit-notice"
    :aria-labelledby="headingId"
  >
    <!-- the text is the alert, announced as it appears; the buttons are outside it, so they are not read
         again with it, and stay in the tab order after it -->
    <div role="alert" class="space-y-2">
      <p :id="headingId" class="flex items-start gap-2 font-medium">
        <UIcon name="i-lucide-info" class="mt-0.5 size-5 shrink-0 text-primary-700 dark:text-primary-400" aria-hidden="true" />
        <span>{{ title }}</span>
      </p>
      <p class="text-sm text-gray-700 dark:text-gray-300">
        {{ body }}
      </p>
      <p class="text-sm text-gray-700 dark:text-gray-300">
        {{ narrow }}
      </p>
      <p v-if="showNoWindow" class="text-sm text-gray-700 dark:text-gray-300" data-testid="limit-no-window">
        {{ t('dataViewer.limitNoWindow') }}
      </p>
    </div>

    <div v-if="(window && canApply) || csvHref" class="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
      <UButton
        v-if="window && canApply"
        :label="applyLabel"
        icon="i-lucide-calendar-range"
        color="primary"
        class="h-auto w-full sm:w-auto"
        :ui="{ label: 'whitespace-normal text-left' }"
        data-testid="limit-apply"
        @click="emit('apply', window)"
      />
      <UButton
        v-if="csvHref"
        :label="t('dataViewer.limitDownload')"
        icon="i-lucide-download"
        color="neutral"
        variant="outline"
        :href="csvHref"
        external
        download="values.csv"
        class="h-auto w-full sm:w-auto"
        :ui="{ label: 'whitespace-normal text-left' }"
        data-testid="limit-download"
      />
    </div>
    <p v-if="csvHref" class="text-xs text-gray-600 dark:text-gray-400">
      {{ maxStreamRows ? t('dataViewer.limitDownloadHintMax', { maximum: number(maxStreamRows) }) : t('dataViewer.limitDownloadHint') }}
    </p>
  </section>
</template>
