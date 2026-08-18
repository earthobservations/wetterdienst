<script setup lang="ts">
import type { Station } from '#shared/types/api'

const props = defineProps<{
  modelValue?: Station | null
}>()

const emit = defineEmits<{
  'update:modelValue': [station: Station | null]
}>()

const { t } = useI18n()

const { data, pending } = useFetch<{ stations: Station[] }>('/api/stations', {
  query: {
    provider: 'dwd',
    network: 'mosmix',
    parameters: 'hourly/large',
    all: 'true',
  },
  default: () => ({ stations: [] }),
})

interface StationItem { label: string, value: string, station: Station }

const stationItems = computed<StationItem[]>(() =>
  (data.value?.stations ?? []).map(s => ({
    label: s.state ? `${s.name} (${s.station_id}) — ${s.state}` : `${s.name} (${s.station_id})`,
    value: s.station_id,
    station: s,
  })),
)

const selectedItem = computed({
  get: (): StationItem | undefined =>
    props.modelValue
      ? stationItems.value.find(i => i.value === props.modelValue?.station_id)
      : undefined,
  set: (item: StationItem | undefined) => {
    emit('update:modelValue', item?.station ?? null)
  },
})
</script>

<template>
  <div class="flex items-center gap-2">
    <USelectMenu
      v-model="selectedItem"
      :items="stationItems"
      :loading="pending"
      searchable
      virtualize
      color="primary"
      class="w-full"
      :class="{ 'needs-input': !modelValue }"
      :placeholder="t('common.stationSearch')"
    />
    <UButton
      v-if="modelValue"
      color="neutral"
      variant="ghost"
      icon="i-lucide-x"
      size="sm"
      @click="emit('update:modelValue', null)"
    />
  </div>
</template>
