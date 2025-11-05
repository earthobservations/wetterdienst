<script setup lang="ts">
  const { data } = await useAsyncData('coverage', () => $fetch('/api/coverage'))
  const providers = computed<string[]>(() => data.value ? Object.keys(data.value).sort() : [])
  const selectedProvider = useState<string | null>("provider", () => null)
  const networks = computed<string[]>(() => {
      if (!selectedProvider.value || !data.value) return []
      return (data.value as Record<string, string[]>)[selectedProvider.value] ?? []
    }
  )
  const selectedNetwork = useState<string | null>("network", () => networks.value[0])

  watch(selectedProvider, () => {
    selectedNetwork.value = networks.value[0]
  })
</script>
<template>
  <ClientOnly>
    <UCard class="max-w-xl mx-auto">
      <template #header>
        <h1 class="text-xl font-semibold">Explorer</h1>
        <p class="text-xs text-gray-500">Choose a provider and its network.</p>
      </template>
      <div class="flex flex-col gap-5">
        <UFormGroup label="Provider" description="Select the data provider" name="provider">
          <USelect
            v-model="selectedProvider"
            :items="providers"
            :disabled="!providers.length"
            placeholder="Select provider"
            variant="outline"
            color="primary"
          />
        </UFormGroup>
        <UFormGroup label="Network" description="Select a network of the provider" name="network">
          <USelect
            v-model="selectedNetwork"
            :items="networks"
            :disabled="!networks.length"
            placeholder="Select network"
            variant="outline"
            color="primary"
          />
        </UFormGroup>
      </div>
    </UCard>
  </ClientOnly>
</template>