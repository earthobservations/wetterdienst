<script setup lang="ts">

// STATE
const provider = useState<string | null>("provider", () => null)
const network = useState<string | null>("network", () => null)
const resolution = useState<string | null>("resolution", () => null)
const dataset = useState<string | null>("dataset", () => null)
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
const { data: providerNetworkCoverage, refresh: refreshNetworkProviderCoverage } = await useFetch(
  "/api/coverage",
  {
    query: {
      provider: provider.value,
      network: network.value
    },
    immediate: false,
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

watch(network, (newValue) => {
  resolution.value = undefined
  dataset.value = undefined
  parameters.value = []
  // Only fetch when network is being set to a value (not when being cleared)
  if (newValue && provider.value) {
    refreshNetworkProviderCoverage()
  }
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

watch(parameters, (newParameters) => {
  parameters.value = [...newParameters]
})


// import type {ParameterSelection} from "~/types/parameter-selection-state.type";

// const props = defineProps<{ modelValue: ParameterSelection }>()
// const emit = defineEmits<{ (e: 'update:modelValue', v: ParameterSelection): void }>()
//
// // local mutable copy
// const parameterSelection = reactive<ParameterSelection>({ ...props.modelValue })
//
// let isUpdating = false
//
// watch(() => props.modelValue, (v) => {
//   if (isUpdating) return
//   Object.assign(parameterSelection, v)
// })
//
// function pushUpdate() {
//   emit('update:modelValue', { ...parameterSelection })
// }

// const providers = computed(() => coverage.value ? Object.keys(coverage.value).sort() : [])
// const networks = computed<string[]>(() => {
//   if (!coverage.value || !parameterSelection.provider) return []
//   return coverage.value[parameterSelection.provider] ?? []
// })
//
// const { data: providerCoverage, refresh: refreshProviderCoverage } = await useFetch(
//   "/api/coverage",
//   {
//     query: {w
//       provider: parameterSelection.provider,
//       network: parameterSelection.network
//     },
//     immediate: false,
//     watch: false
//   }
// )
//
// const resolutions = computed((): string[] => {
//   return providerCoverage.value ? Object.keys(providerCoverage.value) : []
// })
// const datasets = computed((): string[] => {
//   if (!providerCoverage.value || !parameterSelection.resolution) return []
//   return Object.keys(providerCoverage.value[parameterSelection.resolution]).sort()
// })
//
// const parameters = computed<string[]>(() => {
//   if (!providerCoverage.value || !parameterSelection.resolution || !parameterSelection.dataset) return []
//   return providerCoverage.value[parameterSelection.resolution][parameterSelection.dataset]
//     .map((p: any) => p.name)
//     .sort()
// })
//
// watch(() => parameterSelection.provider, () => {
//   isUpdating = true
//   parameterSelection.network = undefined
//   parameterSelection.resolution = undefined
//   parameterSelection.dataset = undefined
//   parameterSelection.parameters = []
//   providerCoverage.value = null
//   pushUpdate()
//   nextTick(() => isUpdating = false)
// })
//
// watch(() => parameterSelection.network, (newValue) => {
//   isUpdating = true
//   parameterSelection.resolution = undefined
//   parameterSelection.dataset = undefined
//   parameterSelection.parameters = []
//   pushUpdate()
//   nextTick(() => isUpdating = false)
//   // Only fetch when network is being set to a value (not when being cleared)
//   if (newValue && parameterSelection.provider) {
//     refreshProviderCoverage()
//   }
// })
//
// watch(() => parameterSelection.resolution, () => {
//   isUpdating = true
//   parameterSelection.dataset = undefined
//   parameterSelection.parameters = []
//   pushUpdate()
//   nextTick(() => isUpdating = false)
// })
//
// watch(() => parameterSelection.dataset, () => {
//   isUpdating = true
//   parameterSelection.parameters = []
//   pushUpdate()
//   nextTick(() => isUpdating = false)
// })
//


</script>

<template>
<div class="flex flex-col gap-4">
  <USelect :model-value="provider" :items="providers" placeholder="Select provider"/>
  <USelect :model-value= "network" :items="networks" placeholder="Select network" :disabled="!provider" />
  <USelect :model-value="resolution" :items="resolutions" placeholder="Select resolution" :disabled="!network" />
  <USelect :model-value="dataset" :items="datasets" placeholder="Select dataset" :disabled="!resolution" />
  <USelect :model-value="parameters" :items="parameters" multiple placeholder="Select parameters" :disabled="!dataset"/>
</div>
</template>