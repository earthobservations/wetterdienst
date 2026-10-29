<script setup lang="ts">
import type { NetworkKind, ProviderNetwork } from '#shared/types/api'

const { t } = useI18n()
const route = useRoute()
const { networkKindLabel } = useNetworkKindLabel()
const { resolutionLabel, datasetLabel } = useParameterLabel()

const { data, pending, error, refresh } = useProviders()

const id = computed(() => String(route.params.provider ?? '').toLowerCase())
const provider = computed(() => data.value?.providers.find(candidate => candidate.provider === id.value))
const failure = computed(() => error.value ? describeFetchError(error.value) : '')

// the title says which provider this is (WCAG 2.4.2), once the provider is known
useHead({ title: () => provider.value?.name_english })

// the networks that have stations and values, which the explorer can be opened on
const TIMESERIES: NetworkKind[] = ['observation', 'forecast', 'derived']

function explorerLink(network: ProviderNetwork): string {
  return `/explorer?provider=${encodeURIComponent(id.value)}&network=${encodeURIComponent(network.network)}`
}

// the station history is a DWD observation page (it restricts itself to the network)
function hasHistory(network: ProviderNetwork): boolean {
  return id.value === 'dwd' && network.network === 'observation'
}

// The Clipboard API exists only in a secure context, so the button is there where it works. A browser
// that refuses the write (no permission, no focus) is left as it was: there is nothing a notice could
// ask the reader to do about it.
const canCopy = typeof navigator !== 'undefined' && !!navigator.clipboard?.writeText
const copied = ref(false)
let copiedTimer: ReturnType<typeof setTimeout> | undefined
async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text)
  }
  catch {
    return
  }
  copied.value = true
  clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => copied.value = false, 2000)
}
onBeforeUnmount(() => clearTimeout(copiedTimer))
</script>

<template>
  <AppPage width="wide">
    <UButton
      to="/providers"
      variant="link"
      icon="i-lucide-arrow-left"
      :label="t('providers.back')"
      class="-ml-2.5"
    />

    <UAlert
      v-if="failure"
      color="error"
      variant="subtle"
      icon="i-lucide-alert-circle"
      :title="t('common.requestFailed')"
      :description="failure"
      :actions="[{ label: t('common.retry'), onClick: () => refresh() }]"
    />
    <UEmpty v-else-if="pending && !data" loading :title="t('common.loading')" />
    <UEmpty
      v-else-if="!provider"
      icon="i-lucide-building-2"
      :title="t('providers.notFound', { provider: id })"
    />
    <template v-else>
      <div class="flex items-start gap-4">
        <span class="text-5xl leading-none" aria-hidden="true">{{ flagEmoji(provider.country_code) }}</span>
        <div class="min-w-0">
          <h1 class="text-3xl sm:text-4xl font-bold tracking-tight text-highlighted break-words">
            {{ provider.name_english }}
          </h1>
          <p v-if="provider.name_local !== provider.name_english" class="text-lg text-gray-600 dark:text-gray-400 break-words">
            {{ provider.name_local }}
          </p>
          <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {{ provider.country_code === null ? t('providers.multinational') : provider.country }}
            ·
            <code>{{ provider.provider }}</code>
          </p>
        </div>
      </div>

      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-scale" class="text-primary-500 shrink-0" />
            <h2 class="text-lg font-bold">
              {{ t('providers.licenceTitle') }}
            </h2>
          </div>
        </template>
        <dl class="space-y-4">
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-gray-400">
              {{ t('providers.licence') }}
            </dt>
            <dd v-if="provider.license" class="flex flex-wrap items-center gap-2">
              <NuxtLink
                :to="provider.license.url"
                external
                target="_blank"
                class="text-primary-700 dark:text-primary-400 underline hover:no-underline"
              >
                {{ provider.license.name }}
              </NuxtLink>
              <UBadge v-if="provider.license.spdx_id" :label="provider.license.spdx_id" color="neutral" variant="subtle" />
            </dd>
            <dd v-else>
              {{ t('providers.licenceNone') }}
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-gray-400">
              {{ t('providers.attribution') }}
            </dt>
            <dd v-if="provider.attribution" class="flex flex-wrap items-center gap-2">
              <q class="break-words">{{ provider.attribution }}</q>
              <UButton
                v-if="canCopy"
                :icon="copied ? 'i-lucide-check' : 'i-lucide-copy'"
                :label="copied ? t('providers.copied') : t('providers.copy')"
                color="neutral"
                variant="ghost"
                size="xs"
                @click="copy(provider.attribution)"
              />
            </dd>
            <dd v-else>
              {{ t('providers.attributionNone') }}
            </dd>
          </div>
        </dl>
      </UCard>

      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-network" class="text-primary-500 shrink-0" />
            <h2 class="text-lg font-bold">
              {{ t('providers.networksTitle') }}
            </h2>
          </div>
        </template>
        <ul class="space-y-6">
          <li
            v-for="network in provider.networks"
            :key="network.network"
            class="border-t border-gray-200 dark:border-gray-800 pt-4 first:border-t-0 first:pt-0 space-y-3"
          >
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="font-bold">
                <code>{{ network.network }}</code>
              </h3>
              <UBadge :label="networkKindLabel(network.kind)" color="neutral" variant="subtle" />
              <UBadge
                v-if="network.auth"
                :label="t('providers.keyRequired')"
                color="neutral"
                variant="outline"
                icon="i-lucide-key-round"
              />
              <UBadge
                v-if="network.date_required"
                :label="t('providers.dateRequired')"
                color="neutral"
                variant="outline"
                icon="i-lucide-calendar"
              />
            </div>
            <p class="text-sm text-gray-600 dark:text-gray-400">
              {{ network.copyright }}
              ·
              <NuxtLink
                :to="network.url"
                external
                target="_blank"
                class="text-primary-700 dark:text-primary-400 underline hover:no-underline break-all"
              >
                {{ t('providers.source') }}
              </NuxtLink>
            </p>

            <template v-if="network.resolutions.length">
              <p class="text-xs text-gray-500 dark:text-gray-400">
                {{ t('providers.parametersCount', { count: network.parameters }) }}
              </p>
              <dl class="grid grid-cols-1 sm:grid-cols-[minmax(8rem,12rem)_1fr] gap-x-4 gap-y-2 text-sm">
                <template v-for="resolution in network.resolutions" :key="resolution.name">
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
            </template>
            <p v-else class="text-sm text-gray-500 dark:text-gray-400">
              {{ t('providers.noResolutions') }}
            </p>

            <div class="flex flex-wrap gap-2">
              <UButton
                v-if="TIMESERIES.includes(network.kind)"
                :to="explorerLink(network)"
                icon="i-lucide-compass"
                :label="t('providers.openExplorer')"
                size="sm"
              />
              <UButton
                v-if="hasHistory(network)"
                to="/history"
                icon="i-lucide-clock"
                :label="t('history.title')"
                color="neutral"
                variant="outline"
                size="sm"
              />
            </div>
          </li>
        </ul>
      </UCard>
    </template>
  </AppPage>
</template>
