<script setup lang="ts">
import type { GlossaryEntry } from '~~/shared/types/api'

const { t, locale } = useI18n()
const { parameterLabel } = useParameterLabel()
const { unitTypeLabel } = useUnitTypeLabel()

// Sorting the translated labels with the default comparison orders them by code point, which puts
// German "Ökologie" after "Zenit" and Czech "Čas" last instead of first. A collator for the active
// language puts each where a reader of that language looks for it.
const collator = computed(() => new Intl.Collator(locale.value, { numeric: true }))

// the whole vocabulary in one call -- around 500 entries, small enough to filter in the browser
// and it saves a round trip per keystroke
const { data: glossary, pending } = await useFetch<GlossaryEntry[]>('/api/glossary')

const search = ref('')
const unitType = ref<string | undefined>(undefined)

const unitTypes = computed<string[]>(() =>
  [...new Set((glossary.value ?? []).map(entry => entry.unit_type))],
)
const unitTypeItems = computed(() => [
  { label: t('glossary.allUnitTypes'), value: undefined },
  // by the label the reader sees, not the backend id it is built from
  ...unitTypes.value
    .map(type => ({ label: unitTypeLabel(type), value: type }))
    .sort((a, b) => collator.value.compare(a.label, b.label)),
])

const entries = computed<GlossaryEntry[]>(() => {
  const term = search.value.trim().toLowerCase()
  const matching = (glossary.value ?? []).filter((entry) => {
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
  // the API returns them ordered by raw id, which bears no relation to the order of the labels on
  // screen once those are translated
  return matching.sort((a, b) => collator.value.compare(parameterLabel(a.name), parameterLabel(b.name)))
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
