<script setup lang="ts">
import type { GlossaryEntry } from '~~/shared/types/api'

const { t } = useI18n()
const { parameterLabel } = useParameterLabel()

// the whole vocabulary in one call -- around 500 entries, small enough to filter in the browser
// and it saves a round trip per keystroke
const { data: glossary, pending } = await useFetch<GlossaryEntry[]>('/api/glossary')

const search = ref('')
const unitType = ref<string | undefined>(undefined)

const unitTypes = computed<string[]>(() =>
  [...new Set((glossary.value ?? []).map(entry => entry.unit_type))].sort(),
)
const unitTypeItems = computed(() => [
  { label: t('glossary.allUnitTypes'), value: undefined },
  ...unitTypes.value.map(type => ({ label: type.replace(/_/g, ' '), value: type })),
])

const entries = computed<GlossaryEntry[]>(() => {
  const term = search.value.trim().toLowerCase()
  return (glossary.value ?? []).filter((entry) => {
    if (unitType.value && entry.unit_type !== unitType.value)
      return false
    if (!term)
      return true
    // match the id, the friendly label and the description, so searching either
    // "sunshine" or "Sonnenschein" finds the same entry
    return entry.name.toLowerCase().includes(term)
      || parameterLabel(entry.name).toLowerCase().includes(term)
      || entry.description.toLowerCase().includes(term)
  })
})
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6 space-y-6">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold mb-4">
        {{ t('glossary.title') }}
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('glossary.subtitle') }}
      </p>
    </div>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-book-open" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('glossary.parametersTitle') }}
          </h2>
        </div>
      </template>

      <div class="flex flex-col sm:flex-row gap-2 mb-4">
        <UInput
          v-model="search"
          icon="i-lucide-search"
          :placeholder="t('glossary.searchPlaceholder')"
          class="flex-1"
        />
        <USelect
          v-model="unitType"
          :items="unitTypeItems"
          value-key="value"
          :placeholder="t('glossary.allUnitTypes')"
          class="sm:w-56"
        />
      </div>

      <UEmpty v-if="pending" loading :title="t('glossary.loading')" />
      <UEmpty
        v-else-if="!entries.length"
        icon="i-lucide-book-open"
        :title="t('glossary.noResults')"
      />
      <div v-else class="space-y-4">
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {{ t('glossary.count', { count: entries.length, total: glossary?.length ?? 0 }) }}
        </p>
        <div
          v-for="entry in entries"
          :key="entry.name"
          class="border-t border-gray-200 dark:border-gray-800 pt-3 first:border-t-0 first:pt-0"
        >
          <div class="flex items-baseline justify-between gap-3 flex-wrap">
            <span class="font-medium">{{ parameterLabel(entry.name) }}</span>
            <span class="text-xs font-mono text-gray-500 dark:text-gray-400">{{ entry.unit_symbol || entry.unit }}</span>
          </div>
          <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
            {{ entry.description }}
          </p>
          <p class="text-xs font-mono text-gray-400 dark:text-gray-500 mt-1">
            {{ entry.name }}
          </p>
        </div>
      </div>
    </UCard>
  </UContainer>
</template>
