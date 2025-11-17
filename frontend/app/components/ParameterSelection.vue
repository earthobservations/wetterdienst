<script setup lang="ts">
interface Selection {
  provider: string | undefined
  network: string | undefined
  resolution: string | undefined
  dataset: string | undefined
  parameters: string[]
}

const props = defineProps<{ modelValue: Selection }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: Selection): void }>()

// local mutable copy
const selection = reactive<Selection>({ ...props.modelValue })

watch(() => props.modelValue, (v) => Object.assign(selection, v))

function pushUpdate() {
  emit('update:modelValue', { ...selection })
}

function setSelection<K extends keyof Selection>(key: K, value: Selection[K]) {
  if (key === 'provider' && selection.provider !== value) {
    selection.provider = value
    selection.network = undefined
    selection.resolution = undefined
    selection.dataset = undefined
    selection.parameters = []
  } else if (key === 'network' && selection.network !== value) {
    selection.network = value
    selection.resolution = undefined
    selection.dataset = undefined
    selection.parameters = []
  } else if (key === 'resolution' && selection.resolution !== value) {
    selection.resolution = value
    selection.dataset = undefined
    selection.parameters = []
  } else if (key === 'dataset' && selection.dataset !== value) {
    selection.dataset = value
    selection.parameters = []
  }
  pushUpdate()
}

const {data: coverage} = await useFetch('/api/coverage')

const providers = computed(() => coverage.value ? Object.keys(coverage.value).sort() : [])
const networks = computed<string[]>(() => {
  if (!coverage.value || !selection.provider) return []
  return coverage.value[selection.provider] ?? []
})
const providerCoverageUrl = computed(() => {
  if (!selection.provider || !selection.network) return null
  return `/api/coverage?provider=${selection.provider}&network=${selection.network}`
})
const { data: providerCoverage, refresh: refreshProviderCoverage } = await useFetch(
  providerCoverageUrl,
  { immediate: false, watch: false }
)

watch(providerCoverageUrl, (url) => {
  if (url) {
    refreshProviderCoverage()
  }
})

const resolutions = computed((): string[] => {
  return providerCoverage.value ? Object.keys(providerCoverage.value) : []
})
const datasets = computed((): string[] => {
  if (!providerCoverage.value || !selection.resolution) return []
  return Object.keys(providerCoverage.value[selection.resolution]).sort()
})

const parameters = computed<string[]>(() => {
  if (!providerCoverage.value || !selection.resolution || !selection.dataset) return []
  return providerCoverage.value[selection.resolution][selection.dataset]
    .map((p: any) => p.name)
    .sort()
})

watch(parameters, (newParameters) => {
  selection.parameters = [...newParameters]
  pushUpdate()
})

</script>

<template>
  <USelect :model-value="selection.provider" :items="providers" placeholder="Select provider" @update:model-value="setSelection('provider', $event)"/>
  <USelect :model-value= "selection.network" :items="networks" placeholder="Select network" @update:model-value="setSelection('network', $event)" :disabled="!selection.provider"/>
  <USelect :model-value="selection.resolution" :items="resolutions" placeholder="Select resolution" @update:model-value="setSelection('resolution', $event)" :disabled="!selection.network"/>
  <USelect :model-value="selection.dataset" :items="datasets" placeholder="Select dataset" @update:model-value="setSelection('dataset', $event)" :disabled="!selection.resolution"/>
  <USelect :model-value="selection.parameters" :items="parameters" multiple placeholder="Select parameters" @update:model-value="(v) => { selection.parameters = v; pushUpdate() }" :disabled="!selection.dataset"/>
</template>