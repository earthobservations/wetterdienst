<script setup lang="ts">

// STATE
const provider = useState<string | undefined>("provider", () => undefined)
const network = useState<string | undefined>("network", () => undefined)
const resolution = useState<string | undefined>("resolution", () => undefined)
const dataset = useState<string | undefined>("dataset", () => undefined)
const parameters = useState<string[]>("parameters", () => [])

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

// watch to reset provider and network
watch(provider, () => {
  network.value = undefined
  resolution.value = undefined
  dataset.value = undefined
  parameters.value = []
})

watch(network, () => {
  resolution.value = undefined
  dataset.value = undefined
  parameters.value = []
  // Only fetch when network is being set to a value (not when being cleared)
  if (provider.value && network.value) {
    refreshProviderNetworkCoverage()
  }
})

watch(resolution, () => {
  dataset.value = undefined
  parameters.value = []
})

watch(dataset, () => {
  parameters.value = []
})

watch(params, (newParams) => {
  parameters.value = [...newParams]
})

const emit = defineEmits(['update:modelValue'])

watch([provider, network, resolution, dataset, parameters], () => {
  emit('update:modelValue', {
    provider: provider.value,
    network: network.value,
    resolution: resolution.value,
    dataset: dataset.value,
    parameters: parameters.value
  })
})
</script>

<template>
<UContainer class="flex flex-col gap-4">
  <USelect v-model="provider" :items="providers" placeholder="Select provider"/>
  <USelect v-model="network" :items="networks" placeholder="Select network" :disabled="!provider" />
  <USelect v-model="resolution" :items="resolutions" placeholder="Select resolution" :disabled="!network" />
  <USelect v-model="dataset" :items="datasets" placeholder="Select dataset" :disabled="!resolution" />
  <USelect v-model="parameters" :items="params" multiple placeholder="Select parameters" :disabled="!dataset"/>
</UContainer>
</template>