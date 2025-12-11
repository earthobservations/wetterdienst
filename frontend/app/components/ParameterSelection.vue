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
}>()

const emit = defineEmits(['update:modelValue'])

// STATE
const provider = ref<string | undefined>(undefined)
const network = ref<string | undefined>(undefined)
const resolution = ref<string | undefined>(undefined)
const dataset = ref<string | undefined>(undefined)
const parameters = ref<string[]>([])

// Track if we're in initialization phase to skip reset watchers
const isInitializing = ref(true)

// fetch coverage data
const {data: coverage} = await useFetch('/api/coverage')

// EXPECTING
const providers = computed(() => coverage.value ? Object.keys(coverage.value).sort() : [])
const networks = computed<string[]>(() => {
  if (!provider.value) return []
  return coverage.value[provider.value] ?? []
})

// provider-network coverage
const { data: providerNetworkCoverage, refresh: refreshProviderNetworkCoverage } = await useFetch(
    "/api/coverage",
    {
      query: computed(() => ({
        provider: provider.value,
        network: network.value
      })),
      immediate: false,
      watch: false
    }
)

const resolutions = computed((): string[] => {
  return providerNetworkCoverage.value ? Object.keys(providerNetworkCoverage.value) : []
})
const datasets = computed((): string[] => {
  if (!providerNetworkCoverage.value || !resolution.value) return []
  return Object.keys(providerNetworkCoverage.value[resolution.value]).sort()
})
const params = computed<string[]>(() => {
  if (!providerNetworkCoverage.value || !resolution.value || !dataset.value) return []
  return providerNetworkCoverage.value[resolution.value][dataset.value]
    .map((p: any) => p.name)
    .sort()
})

// Initialize from query params and validate step by step
const initializeFromProps = async () => {
  const initial = props.modelValue
  if (!initial) {
    isInitializing.value = false
    return
  }

  // Step 1: Validate provider
  if (initial.provider && providers.value.includes(initial.provider)) {
    provider.value = initial.provider
  } else {
    isInitializing.value = false
    emitUpdate()
    return
  }

  // Step 2: Validate network
  if (initial.network && networks.value.includes(initial.network)) {
    network.value = initial.network
    // Fetch provider-network coverage for next steps
    await refreshProviderNetworkCoverage()
  } else {
    isInitializing.value = false
    emitUpdate()
    return
  }

  // Step 3: Validate resolution
  if (initial.resolution && resolutions.value.includes(initial.resolution)) {
    resolution.value = initial.resolution
  } else {
    isInitializing.value = false
    emitUpdate()
    return
  }

  // Step 4: Validate dataset
  if (initial.dataset && datasets.value.includes(initial.dataset)) {
    dataset.value = initial.dataset
  } else {
    isInitializing.value = false
    emitUpdate()
    return
  }

  // Step 5: Validate parameters - keep only valid ones
  // Need to wait for next tick so params computed updates after dataset is set
  await nextTick()

  if (initial.parameters?.length) {
    const validParams = initial.parameters.filter(p => params.value.includes(p))
    parameters.value = validParams.length > 0 ? validParams : [...params.value]
  } else {
    // Select all parameters by default
    parameters.value = [...params.value]
  }

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
  if (isInitializing.value) return
  network.value = undefined
  resolution.value = undefined
  dataset.value = undefined
  parameters.value = []
})

watch(network, () => {
  if (isInitializing.value) return
  resolution.value = undefined
  dataset.value = undefined
  parameters.value = []
  // Only fetch when network is being set to a value (not when being cleared)
  if (provider.value && network.value) {
    refreshProviderNetworkCoverage()
  }
})

watch(resolution, () => {
  if (isInitializing.value) return
  dataset.value = undefined
  parameters.value = []
})

watch(dataset, (newDataset, oldDataset) => {
  if (isInitializing.value) return
  // Only auto-select parameters when user changes dataset (not during init)
  // params is computed and updates synchronously when dataset changes
  if (newDataset && newDataset !== oldDataset) {
    // Use nextTick to ensure params computed has updated
    nextTick(() => {
      if (!isInitializing.value) {
        parameters.value = [...params.value]
      }
    })
  }
})

const emitUpdate = () => {
  emit('update:modelValue', {
    provider: provider.value,
    network: network.value,
    resolution: resolution.value,
    dataset: dataset.value,
    parameters: parameters.value
  })
}

watch([provider, network, resolution, dataset, parameters], () => {
  if (isInitializing.value) return
  emitUpdate()
})
</script>

<template>
<UCard>
  <template #header>
    Select Parameters
  </template>
  <UContainer class="flex flex-col gap-4">
    <USelect v-model="provider" :items="providers" placeholder="Select provider"/>
    <USelect v-model="network" :items="networks" placeholder="Select network" :disabled="!provider" />
    <USelect v-model="resolution" :items="resolutions" placeholder="Select resolution" :disabled="!network" />
    <USelect v-model="dataset" :items="datasets" placeholder="Select dataset" :disabled="!resolution" />
    <USelect v-model="parameters" :items="params" multiple placeholder="Select parameters" :disabled="!dataset"/>
  </UContainer>
</UCard>
</template>