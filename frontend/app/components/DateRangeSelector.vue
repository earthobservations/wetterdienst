<script setup lang="ts">
import type {Resolution} from '#types/api.types'
import type { DateRange } from '~/types/station-selection-state.type'

const props = defineProps<{
  required: boolean
  resolution?: Resolution
  stationCount?: number
  parameterCount?: number
}>()

const modelValue = defineModel<DateRange>({ required: true })

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

const MAX_VALUES = 100000

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
      return 'Start date is required'
    if (!modelValue.value.endDate)
      return 'End date is required'
  }

  if (modelValue.value.startDate && modelValue.value.endDate) {
    const start = new Date(modelValue.value.startDate)
    const end = new Date(modelValue.value.endDate)
    if (end < start)
      return 'End date must be after start date'
  }

  if (exceedsLimit.value) {
    return `Estimated ${estimatedValues.value?.toLocaleString()} values exceeds limit of ${MAX_VALUES.toLocaleString()}. Please narrow the date range.`
  }

  return null
})

const isValid = computed(() => {
  if (!requiresDateRange.value && !modelValue.value.startDate && !modelValue.value.endDate) {
    return true
  }
  return validationError.value === null
})

defineExpose({ isValid, validationError })
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center gap-2">
      <span class="text-sm font-medium">Date Range</span>
      <UBadge v-if="requiresDateRange" size="xs" color="warning" variant="subtle">
        Required
      </UBadge>
      <UBadge v-else size="xs" color="neutral" variant="subtle">
        Optional
      </UBadge>
    </div>

    <div class="flex gap-4">
      <UFormField label="Start Date" class="flex-1" :error="!modelValue.startDate && requiresDateRange ? 'Required' : undefined">
        <UInput
          v-model="modelValue.startDate"
          type="date"
          class="w-full"
        />
      </UFormField>
      <UFormField label="End Date" class="flex-1" :error="!modelValue.endDate && requiresDateRange ? 'Required' : undefined">
        <UInput
          v-model="modelValue.endDate"
          type="date"
          class="w-full"
        />
      </UFormField>
    </div>

    <div v-if="isHighResolution && estimatedValues !== null" class="text-sm">
      <span :class="exceedsLimit ? 'text-red-500' : 'text-gray-500'">
        Estimated values: {{ estimatedValues.toLocaleString() }}
        <span v-if="exceedsLimit"> (max: {{ MAX_VALUES.toLocaleString() }})</span>
      </span>
    </div>

    <UAlert
      v-if="validationError"
      color="error"
      variant="subtle"
      :title="validationError"
      icon="i-lucide-alert-circle"
    />
  </div>
</template>
