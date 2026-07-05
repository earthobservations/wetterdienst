<script setup lang="ts">
// Accept initial values from parent via v-model
const props = defineProps<{
  modelValue?: {
    provider?: string
    network?: string
    resolution?: string
    dataset?: string
    parameters?: string[]
  }
  showParameters?: boolean
}>()

const emit = defineEmits(['update:modelValue'])

const { t } = useI18n()
const { parameterLabel, resolutionLabel, datasetLabel } = useParameterLabel()

// STATE
const provider = ref<string | undefined>(undefined)
const network = ref<string | undefined>(undefined)
const resolution = ref<string | undefined>(undefined)
const dataset = ref<string | undefined>(undefined)
const parameters = ref<string[]>([])

// Track if we're in initialization phase to skip reset watchers
const isInitializing = ref(true)

// fetch coverage data
const { data: coverage } = await useFetch<CoverageResponse>('/api/coverage')

// EXPECTING
const providers = computed(() => coverage.value ? Object.keys(coverage.value).sort() : [])
const networks = computed<string[]>(() => {
  if (!provider.value || !coverage.value)
    return []
  return coverage.value[provider.value] ?? []
})

// provider-network coverage
const { data: providerNetworkCoverage, pending: networkCoveragePending, refresh: refreshProviderNetworkCoverage } = await useFetch<ProviderNetworkCoverageResponse>(
  '/api/coverage',
  {
    query: computed(() => ({
      provider: provider.value,
      network: network.value,
    })),
    immediate: false,
    watch: false,
  },
)

const resolutions = computed((): string[] => {
  return providerNetworkCoverage.value ? Object.keys(providerNetworkCoverage.value) : []
})
const datasets = computed((): string[] => {
  if (!providerNetworkCoverage.value || !resolution.value)
    return []
  const resolutionData = providerNetworkCoverage.value[resolution.value as Resolution]
  return resolutionData ? Object.keys(resolutionData).sort() : []
})
const params = computed<string[]>(() => {
  if (!providerNetworkCoverage.value || !resolution.value || !dataset.value)
    return []
  const resolutionData = providerNetworkCoverage.value[resolution.value as Resolution]
  if (!resolutionData)
    return []
  const datasetParams = resolutionData[dataset.value]
  if (!datasetParams)
    return []
  return datasetParams
    .map((p: CoverageParameter) => p.name)
    .sort()
})

// Friendly, locale-aware labels for the select menus (value stays the raw backend id).
const resolutionItems = computed(() => resolutions.value.map(r => ({ label: resolutionLabel(r), value: r })))
const datasetItems = computed(() => datasets.value.map(d => ({ label: datasetLabel(d), value: d })))
const paramItems = computed(() => params.value.map(p => ({ label: parameterLabel(p), value: p })))

// Beginner-friendly starting point used when the Explorer is opened without any
// existing selection (no URL query): DWD observation, daily climate summary,
// mean 2 m air temperature. Gives newcomers a working example to tweak.
const PRESELECTION = {
  provider: 'dwd',
  network: 'observation',
  resolution: 'daily',
  dataset: 'climate_summary',
  parameters: ['temperature_air_mean_2m'],
}

// Initialize from query params and validate step by step
async function initializeFromProps() {
  const initial = props.modelValue?.provider ? props.modelValue : PRESELECTION

  // Step 1: Validate provider
  if (initial.provider && providers.value.includes(initial.provider)) {
    provider.value = initial.provider
  }
  else {
    isInitializing.value = false
    emitUpdate()
    return
  }

  // Step 2: Validate network
  if (initial.network && networks.value.includes(initial.network)) {
    network.value = initial.network
    // Fetch provider-network coverage for next steps
    await refreshProviderNetworkCoverage()
  }
  else {
    isInitializing.value = false
    emitUpdate()
    return
  }

  // Step 3: Validate resolution
  if (initial.resolution && resolutions.value.includes(initial.resolution)) {
    resolution.value = initial.resolution as Resolution
  }
  else {
    isInitializing.value = false
    emitUpdate()
    return
  }

  // Step 4: Validate dataset
  if (initial.dataset && datasets.value.includes(initial.dataset)) {
    dataset.value = initial.dataset
  }
  else {
    isInitializing.value = false
    emitUpdate()
    return
  }

  // Step 5: Validate parameters - keep only valid ones
  // Need to wait for next tick so params computed updates after dataset is set
  await nextTick()

  if (initial.parameters?.length) {
    const validParams = initial.parameters.filter(p => params.value.includes(p))
    parameters.value = validParams
  }
  // Don't auto-select all parameters by default

  // Wait another tick to ensure watchers have processed before turning off initialization mode
  await nextTick()
  isInitializing.value = false
  emitUpdate()
}

// Run initialization on mount
onMounted(() => {
  initializeFromProps()
})

// watch to reset provider and network
watch(provider, () => {
  if (isInitializing.value)
    return
  network.value = undefined
  resolution.value = undefined
  dataset.value = undefined
  parameters.value = []
})

watch(network, () => {
  if (isInitializing.value)
    return
  resolution.value = undefined
  dataset.value = undefined
  parameters.value = []
  // Only fetch when network is being set to a value (not when being cleared)
  if (provider.value && network.value) {
    refreshProviderNetworkCoverage()
  }
})

watch(resolution, () => {
  if (isInitializing.value)
    return
  dataset.value = undefined
  parameters.value = []
})

watch(dataset, () => {
  if (isInitializing.value)
    return
  // Clear parameters when dataset changes
  parameters.value = []
})

function selectAllParameters() {
  parameters.value = [...params.value]
}

function clearParameters() {
  parameters.value = []
}

const allSelected = computed(() => parameters.value.length === params.value.length && params.value.length > 0)

// The first enabled-but-empty field in the chain — the one a newcomer should
// fill next. Used to visually highlight that single field (see `needs-input`).
// Returns null once every step has a value, so nothing pulses unnecessarily.
const activeField = computed<'provider' | 'network' | 'resolution' | 'dataset' | 'parameters' | null>(() => {
  if (isInitializing.value)
    return null
  if (!provider.value)
    return 'provider'
  if (!network.value)
    return 'network'
  if (!resolution.value)
    return 'resolution'
  if (!dataset.value)
    return 'dataset'
  if (parameters.value.length === 0)
    return 'parameters'
  return null
})

function emitUpdate() {
  emit('update:modelValue', {
    provider: provider.value,
    network: network.value,
    resolution: resolution.value,
    dataset: dataset.value,
    parameters: parameters.value,
  })
}

watch([provider, network, resolution, dataset, parameters], () => {
  if (isInitializing.value)
    return
  emitUpdate()
})
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon name="i-lucide-database" class="text-primary-500 shrink-0" />
        <h2 class="text-lg font-bold">
          {{ t('parameterSelection.title') }}
        </h2>
      </div>
    </template>
    <UContainer class="flex flex-col gap-4">
      <UFormField :label="t('parameterSelection.providerLabel')">
        <USelect v-model="provider" :items="providers" :placeholder="t('parameterSelection.selectProvider')" class="w-full" :class="{ 'needs-input': activeField === 'provider' }" />
      </UFormField>
      <UFormField :label="t('parameterSelection.networkLabel')">
        <USelect v-model="network" :items="networks" :placeholder="t('parameterSelection.selectNetwork')" :disabled="!provider" class="w-full" :class="{ 'needs-input': activeField === 'network' }" />
      </UFormField>
      <UFormField :label="t('parameterSelection.resolutionLabel')">
        <USelect v-model="resolution" :items="resolutionItems" :placeholder="t('parameterSelection.selectResolution')" :disabled="!network || networkCoveragePending" class="w-full" :class="{ 'needs-input': activeField === 'resolution' }" />
      </UFormField>
      <UFormField :label="t('parameterSelection.datasetLabel')">
        <USelect v-model="dataset" :items="datasetItems" :placeholder="t('parameterSelection.selectDataset')" :disabled="!resolution || networkCoveragePending" class="w-full" :class="{ 'needs-input': activeField === 'dataset' }" />
      </UFormField>
      <UFormField v-if="props.showParameters !== false" :label="t('parameterSelection.parametersLabel')">
        <div class="flex gap-2 items-center min-w-0">
          <USelectMenu v-model="parameters" :items="paramItems" value-key="value" multiple :placeholder="t('parameterSelection.selectParameters')" :disabled="!dataset" class="flex-1 min-w-0 overflow-hidden" :class="{ 'needs-input': activeField === 'parameters' }" />
          <UButton
            v-if="dataset && !allSelected"
            size="xs"
            variant="ghost"
            color="neutral"
            icon="i-lucide-check-check"
            @click="selectAllParameters"
          >
            {{ t('common.all') }}
          </UButton>
          <UButton
            v-if="dataset && parameters.length > 0"
            size="xs"
            variant="ghost"
            color="neutral"
            icon="i-lucide-x"
            @click="clearParameters"
          >
            {{ t('parameterSelection.clear') }}
          </UButton>
        </div>
      </UFormField>
    </UContainer>
  </UCard>
</template>
