<script setup lang="ts">
import type { NetworkKind, Provider } from '#shared/types/api'

const { t, locale } = useI18n()

// the title says which page this is: WCAG 2.4.2, and what a screen reader announces after a navigation
useHead({ title: () => t('providers.title') })
const { networkKindLabel } = useNetworkKindLabel()

// Names are sorted for the language of the page, as the glossary does: "Český" after "Czech" is where
// a Czech reader looks for it, and a code-point sort puts it last.
const collator = computed(() => new Intl.Collator(locale.value, { numeric: true }))

const { data, pending, error, refresh } = useProviders()

const search = ref('')
const kind = ref<NetworkKind | undefined>(undefined)

const kinds = computed<NetworkKind[]>(() => [
  ...new Set((data.value?.providers ?? []).flatMap(provider => provider.networks.map(network => network.kind))),
])
const kindItems = computed(() => [
  { label: t('providers.allKinds'), value: undefined },
  ...kinds.value
    .map(value => ({ label: networkKindLabel(value), value }))
    .sort((a, b) => collator.value.compare(a.label, b.label)),
])

const providers = computed<Provider[]>(() => {
  const term = search.value.trim().toLowerCase()
  return (data.value?.providers ?? [])
    .filter((provider) => {
      if (kind.value && !provider.networks.some(network => network.kind === kind.value))
        return false
      if (!term)
        return true
      // the id a request names, both names, the country and its code: "DWD", "Wetterdienst",
      // "Germany" and "DE" find the same card
      return [provider.provider, provider.name_english, provider.name_local, provider.country, provider.country_code ?? '']
        .some(text => text.toLowerCase().includes(term))
    })
    .sort((a, b) => collator.value.compare(a.name_english, b.name_english))
})

const failure = computed(() => error.value ? describeFetchError(error.value) : '')

function licenceLabel(provider: Provider): string {
  return provider.license ? (provider.license.spdx_id ?? provider.license.name) : t('providers.licenceNone')
}

function parameterCount(provider: Provider): number {
  return provider.networks.reduce((sum, network) => sum + network.parameters, 0)
}
</script>

<template>
  <div class="frame">
    <PageHeader :title="t('providers.title')" :lede="t('providers.subtitle')" />
    <div class="page-body">
      <div class="flex flex-col sm:flex-row gap-2 max-w-3xl">
        <UInput
          v-model="search"
          icon="i-ph-magnifying-glass"
          :placeholder="t('providers.searchPlaceholder')"
          :aria-label="t('providers.searchPlaceholder')"
          class="flex-1"
        />
        <USelect
          v-model="kind"
          :items="kindItems"
          value-key="value"
          :placeholder="t('providers.allKinds')"
          :aria-label="t('providers.kindLabel')"
          class="sm:w-56"
        />
      </div>

      <UAlert
        v-if="failure"
        color="error"
        variant="subtle"
        icon="i-ph-warning-circle"
        :title="t('common.requestFailed')"
        :description="failure"
        :actions="[{ label: t('common.retry'), onClick: () => refresh() }]"
      />
      <UEmpty v-else-if="pending && !data" loading :title="t('common.loading')" />
      <UEmpty
        v-else-if="!providers.length"
        icon="i-ph-buildings"
        :title="t('providers.noResults')"
      />
      <template v-else>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {{ t('providers.shown', { shown: providers.length, count: data?.providers.length ?? 0 }) }}
        </p>
        <ul class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          <li v-for="provider in providers" :key="provider.provider">
            <NuxtLink :to="`/providers/${provider.provider}`" class="group block h-full">
              <UCard
                class="h-full transition-shadow group-hover:ring-2 group-hover:ring-primary"
                :ui="{ body: 'flex flex-col gap-2 h-full' }"
              >
                <div class="flex items-start gap-3">
                  <span class="text-3xl leading-none" aria-hidden="true">{{ flagEmoji(provider.country_code) }}</span>
                  <div class="min-w-0">
                    <h2 class="font-bold break-words">
                      {{ provider.name_english }}
                    </h2>
                    <p v-if="provider.name_local !== provider.name_english" class="text-sm text-gray-600 dark:text-gray-400 break-words">
                      {{ provider.name_local }}
                    </p>
                  </div>
                </div>
                <p class="text-sm text-gray-600 dark:text-gray-400">
                  {{ provider.country_code === null ? t('providers.multinational') : provider.country }}
                </p>
                <p class="text-xs text-gray-500 dark:text-gray-400">
                  {{ t('providers.networksCount', { count: provider.networks.length }) }}
                  ·
                  {{ t('providers.parametersCount', { count: parameterCount(provider) }) }}
                </p>
                <div class="flex flex-wrap gap-1.5 mt-auto pt-1">
                  <UBadge
                    v-for="network in [...new Set(provider.networks.map(n => n.kind))]"
                    :key="network"
                    :label="networkKindLabel(network)"
                    color="neutral"
                    variant="subtle"
                  />
                  <!-- a licence with no SPDX identifier is told by its name, which can be a sentence: cut at
                     the card's edge, and whole in the tooltip and on the provider's page -->
                  <UBadge
                    :label="licenceLabel(provider)"
                    :title="licenceLabel(provider)"
                    color="primary"
                    variant="subtle"
                    icon="i-ph-scales"
                    class="max-w-full"
                    :ui="{ label: 'truncate' }"
                  />
                  <UBadge
                    v-if="provider.networks.some(network => network.auth)"
                    :label="t('providers.keyRequired')"
                    color="neutral"
                    variant="outline"
                    icon="i-ph-key"
                  />
                </div>
              </UCard>
            </NuxtLink>
          </li>
        </ul>
      </template>
    </div>
  </div>
</template>
