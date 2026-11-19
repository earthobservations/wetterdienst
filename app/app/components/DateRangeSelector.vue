<script setup lang="ts">
import type { DateRange } from '~/types/station-selection-state.type'
import type { FittingWindow } from '~/utils/row-window'
import { formatNumber } from '~/utils/format'
import { HIGH_RESOLUTION_MAX_VALUES } from '~/utils/row-window'

const props = defineProps<{
  required: boolean
  resolution?: Resolution
  stationCount?: number
  parameterCount?: number
  /** the range the page chose for the selection and the user has not touched, which the note says */
  defaultWindow?: FittingWindow | null
}>()

const emit = defineEmits<{
  /** the user typed a date or picked one: what is in the fields is theirs now, not the page's default */
  edited: []
  /** the user cleared the range: the request is for everything, and the page does not choose a range again */
  cleared: []
}>()

const modelValue = defineModel<DateRange>({ required: true })

const { t } = useI18n()
const formatLanguage = useFormatLanguage()

// High resolution thresholds (resolutions that require date filtering)
const HIGH_RESOLUTION_THRESHOLDS: Resolution[] = ['1_minute', '5_minutes', '10_minutes']

const isHighResolution = computed(() => {
  if (!props.resolution)
    return false
  return HIGH_RESOLUTION_THRESHOLDS.includes(props.resolution)
})

const requiresDateRange = computed(() => {
  return props.required || isHighResolution.value
})

// Estimate values based on resolution and date range
const estimatedValues = computed(() => {
  if (!modelValue.value.startDate || !modelValue.value.endDate)
    return null
  if (!props.resolution)
    return null

  const start = new Date(modelValue.value.startDate)
  const end = new Date(modelValue.value.endDate)
  const diffMs = end.getTime() - start.getTime()
  const diffDays = diffMs / (1000 * 60 * 60 * 24)

  if (diffDays < 0)
    return null

  // Values per day based on resolution
  const valuesPerDay: Partial<Record<Resolution, number>> = {
    '1_minute': 1440,
    '5_minutes': 288,
    '10_minutes': 144,
    'hourly': 24,
    'daily': 1,
    'monthly': 1 / 30,
    'annual': 1 / 365,
  }

  const perDay = valuesPerDay[props.resolution] ?? 1
  const stationMultiplier = props.stationCount ?? 1
  const paramMultiplier = props.parameterCount ?? 1

  return Math.round(diffDays * perDay * stationMultiplier * paramMultiplier)
})

// the range the fields hold, as the page's own rule for a high resolution (the server's limit is its own)
const MAX_VALUES = HIGH_RESOLUTION_MAX_VALUES

const exceedsLimit = computed(() => {
  if (!isHighResolution.value)
    return false
  if (estimatedValues.value === null)
    return false
  return estimatedValues.value > MAX_VALUES
})

const validationError = computed(() => {
  if (requiresDateRange.value) {
    if (!modelValue.value.startDate)
      return t('dateRange.errStartRequired')
    if (!modelValue.value.endDate)
      return t('dateRange.errEndRequired')
  }

  if (modelValue.value.startDate && modelValue.value.endDate) {
    const start = new Date(modelValue.value.startDate)
    const end = new Date(modelValue.value.endDate)
    if (end < start)
      return t('dateRange.errEndAfterStart')
  }

  if (exceedsLimit.value) {
    return t('dateRange.errExceedsLimit', {
      count: estimatedValues.value === null ? undefined : formatNumber(estimatedValues.value, formatLanguage.value, 0),
      max: formatNumber(MAX_VALUES, formatLanguage.value, 0),
    })
  }

  return null
})

const isValid = computed(() => {
  if (!requiresDateRange.value && !modelValue.value.startDate && !modelValue.value.endDate) {
    return true
  }
  return validationError.value === null
})

function setDate(field: 'startDate' | 'endDate', value: unknown) {
  modelValue.value[field] = typeof value === 'string' && value ? value : undefined
  emit('edited')
}

// The button goes with the dates it clears, and the focus it held goes to the two fields as a group (named
// "Date Range", which a screen reader says), where a range is typed with the next Tab. Not to the first
// field itself: focusing a date input from script may open its picker on iOS, which nobody asked for (GH-3722)
const fieldsBox = ref<HTMLElement | null>(null)
async function clearRange() {
  modelValue.value.startDate = undefined
  modelValue.value.endDate = undefined
  emit('cleared')
  await nextTick()
  fieldsBox.value?.focus()
}

const labelId = useId()
const noteId = useId()
// something to clear: a range that is required is never empty, and the dates are the page's to fill
const canClear = computed(() => !requiresDateRange.value && !!(modelValue.value.startDate || modelValue.value.endDate))
// the way to ask for everything is said where there is one: not for a range that is required
const note = computed(() => {
  const window = props.defaultWindow
  if (!window)
    return null
  const text = t('dateRange.defaultNote', {
    span: t(`dataViewer.limitUnit.${window.unit}`, { count: window.count }),
    rows: formatNumber(window.rows, formatLanguage.value, 0),
  })
  return canClear.value ? `${text} ${t('dateRange.defaultNoteClear')}` : text
})

// A live region announces text that is put into it, not text that was there when it came: the first station
// mounts this selector with the note already worded, and it was then only the fields' description. So a note
// that is there at the start is written into the status a moment after the status is in the page, which is
// the change a screen reader announces. One that comes later is a change already (GH-3722)
const ANNOUNCE_AFTER_MS = 150
const noteWritten = ref(!note.value)
let announceTimer: ReturnType<typeof setTimeout> | undefined
onMounted(() => {
  if (!noteWritten.value)
    announceTimer = setTimeout(() => { noteWritten.value = true }, ANNOUNCE_AFTER_MS)
})
onBeforeUnmount(() => clearTimeout(announceTimer))

defineExpose({ isValid, validationError })
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center gap-2">
      <span :id="labelId" class="text-sm font-medium">{{ t('dateRange.label') }}</span>
      <UBadge v-if="requiresDateRange" size="xs" color="warning" variant="subtle">
        {{ t('dateRange.required') }}
      </UBadge>
      <UBadge v-else size="xs" color="neutral" variant="subtle">
        {{ t('dateRange.optional') }}
      </UBadge>
    </div>

    <div ref="fieldsBox" role="group" tabindex="-1" :aria-labelledby="labelId" class="flex flex-wrap gap-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--app-focus-ring)">
      <UFormField :label="t('dateRange.startDate')" class="flex-1" :error="!modelValue.startDate && requiresDateRange ? t('dateRange.required') : undefined">
        <UInput
          :model-value="modelValue.startDate"
          type="date"
          class="w-full"
          :aria-describedby="note ? noteId : undefined"
          @update:model-value="setDate('startDate', $event)"
        />
      </UFormField>
      <UFormField :label="t('dateRange.endDate')" class="flex-1" :error="!modelValue.endDate && requiresDateRange ? t('dateRange.required') : undefined">
        <UInput
          :model-value="modelValue.endDate"
          type="date"
          class="w-full"
          :aria-describedby="note ? noteId : undefined"
          @update:model-value="setDate('endDate', $event)"
        />
      </UFormField>
    </div>

    <!-- the page's own choice of range, and why: a status, announced as its text changes (a note that is there
         when the component is mounted, by the first station, is written in after `ANNOUNCE_AFTER_MS`, see
         the script), and the description of both fields. Empty it stays in the accessibility tree
         (`sr-only`, which also takes no space) -->
    <p :id="noteId" role="status" class="text-sm text-gray-600 empty:sr-only dark:text-gray-400" data-testid="default-range-note">
      <template v-if="note && noteWritten">
        {{ note }}
      </template>
    </p>

    <UButton
      v-if="canClear"
      :label="t('dateRange.clear')"
      icon="i-ph-x"
      size="xs"
      color="neutral"
      variant="ghost"
      data-testid="clear-date-range"
      @click="clearRange"
    />

    <div v-if="isHighResolution && estimatedValues !== null" class="text-sm">
      <span :class="exceedsLimit ? 'text-red-600 dark:text-red-400' : 'text-gray-500 dark:text-gray-400'">
        {{ t('dateRange.estimatedValues', { count: formatNumber(estimatedValues, formatLanguage, 0) }) }}
        <span v-if="exceedsLimit"> ({{ t('dateRange.max', { max: formatNumber(MAX_VALUES, formatLanguage, 0) }) }})</span>
      </span>
    </div>

    <UAlert
      v-if="validationError"
      color="error"
      variant="subtle"
      :title="validationError"
      icon="i-ph-warning-circle"
    />
  </div>
</template>
