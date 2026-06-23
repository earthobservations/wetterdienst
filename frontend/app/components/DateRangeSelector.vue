<script setup lang="ts">
import type { DateRange } from '~/types/station-selection-state.type'

const props = defineProps<{
  required: boolean
  resolution?: Resolution
  stationCount?: number
  parameterCount?: number
}>()

const modelValue = defineModel<DateRange>({ required: true })

const { t, locale } = useI18n()

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
      count: estimatedValues.value?.toLocaleString(locale.value),
      max: MAX_VALUES.toLocaleString(locale.value),
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

defineExpose({ isValid, validationError })
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center gap-2">
      <span class="text-sm font-medium">{{ t('dateRange.label') }}</span>
      <UBadge v-if="requiresDateRange" size="xs" color="warning" variant="subtle">
        {{ t('dateRange.required') }}
      </UBadge>
      <UBadge v-else size="xs" color="neutral" variant="subtle">
        {{ t('dateRange.optional') }}
      </UBadge>
    </div>

    <div class="flex gap-4">
      <UFormField :label="t('dateRange.startDate')" class="flex-1" :error="!modelValue.startDate && requiresDateRange ? t('dateRange.required') : undefined">
        <UInput
          v-model="modelValue.startDate"
          type="date"
          class="w-full"
        />
      </UFormField>
      <UFormField :label="t('dateRange.endDate')" class="flex-1" :error="!modelValue.endDate && requiresDateRange ? t('dateRange.required') : undefined">
        <UInput
          v-model="modelValue.endDate"
          type="date"
          class="w-full"
        />
      </UFormField>
    </div>

    <div v-if="isHighResolution && estimatedValues !== null" class="text-sm">
      <span :class="exceedsLimit ? 'text-red-500' : 'text-gray-500'">
        {{ t('dateRange.estimatedValues', { count: estimatedValues.toLocaleString(locale) }) }}
        <span v-if="exceedsLimit"> ({{ t('dateRange.max', { max: MAX_VALUES.toLocaleString(locale) }) }})</span>
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
