<script setup lang="ts">
import type { ProviderNetworkCoverageResponse } from '#shared/types/api'

// The resolutions and datasets of one network, with the number of parameters of each: the coverage of
// that network (`GET /api/coverage`), which the list of providers does not carry. It is the one
// answer a reader asks for by opening the list, never one for every network of the page: the
// coverage of a large network is some 100 kilobytes.
const props = defineProps<{
  provider: string
  network: string
}>()

const { t } = useI18n()
const { resolutionLabel, datasetLabel } = useParameterLabel()

const { data, status, error, execute } = useFetch<ProviderNetworkCoverageResponse>('/api/coverage', {
  key: () => `network-coverage/${props.provider}/${props.network}`,
  query: { provider: props.provider, network: props.network },
  immediate: false,
  watch: false,
  ...API_ANSWER,
})

const resolutions = computed(() => Object.entries(data.value ?? {}).map(([name, resolution]) => ({
  name: name as Resolution,
  datasets: Object.entries(resolution?.datasets ?? {}).map(([dataset, content]) => ({ name: dataset, parameters: content.parameters.length })),
})))

const failure = computed(() => error.value ? describeFetchError(error.value) : '')

// Asked for the first time the list is opened, and again only where that failed (Retry)
const open = ref(false)
watch(open, (isOpen) => {
  if (isOpen && status.value === 'idle')
    execute()
})
</script>

<template>
  <UCollapsible v-model:open="open">
    <!-- every network of the page has this button: its name is told to a reader who lists the buttons, and the caret
         shows whether the list is open -->
    <UButton
      icon="i-ph-list-bullets"
      variant="subtle"
      color="neutral"
      trailing-icon="i-ph-caret-down"
      size="sm"
      :ui="{ trailingIcon: `transition-transform duration-200 ${open ? 'rotate-180' : ''}` }"
    >
      {{ t('providers.showDatasets') }}<span class="sr-only"> ({{ network }})</span>
    </UButton>
    <template #content>
      <div class="pt-3">
        <UAlert
          v-if="failure"
          color="error"
          variant="subtle"
          icon="i-ph-warning-circle"
          :title="t('common.requestFailed')"
          :description="failure"
          :actions="[{ label: t('common.retry'), onClick: () => execute() }]"
        />
        <UEmpty v-else-if="status !== 'success'" loading :title="t('common.loading')" />
        <dl v-else class="grid grid-cols-1 sm:grid-cols-[minmax(8rem,12rem)_1fr] gap-x-4 gap-y-2 text-sm">
          <template v-for="resolution in resolutions" :key="resolution.name">
            <dt class="font-medium">
              {{ resolutionLabel(resolution.name) }}
            </dt>
            <dd class="text-gray-600 dark:text-gray-400">
              <ul class="flex flex-wrap gap-x-3 gap-y-1">
                <li
                  v-for="dataset in resolution.datasets"
                  :key="dataset.name"
                  :title="t('providers.parametersCount', { count: dataset.parameters })"
                >
                  {{ datasetLabel(dataset.name) }}
                  <span class="text-xs text-gray-500 dark:text-gray-400">({{ dataset.parameters }})</span>
                </li>
              </ul>
            </dd>
          </template>
        </dl>
      </div>
    </template>
  </UCollapsible>
</template>
