<script setup lang="ts">
import type { ProviderTerms } from '~/utils/provider-credit'
import { safeHref, termsOfProvider } from '~/utils/provider-credit'

// The credit line of provider data, and directly under it what wetterdienst did to the data (GH-3799, GH-4255): the provider's own
// words (`attribution`) and the licence it publishes under, as a link to its terms, both as `GET /api/providers` lists them, so that
// nothing of a provider's credit is written in the app. Ask the weather, the Explorer, the forecast, the history, the map's panel, the
// widget and the stripes' table all show it, in this one style. `terms` is for a place that holds the answer's own `metadata.provider`
// (the stripes); `fallback` is the line for a provider that states none. Where there is no credit to give, the note is still said.
// A class and a `data-testid` given to it are those of the block.
const props = withDefaults(defineProps<{
  /** The provider's name, as a request calls it (`dwd`): its terms are looked up in the list of providers */
  provider?: string | null
  /** The terms themselves, where the page has them from the answer: used instead of the list's */
  terms?: ProviderTerms | null
  /** The credit line where the provider states none */
  fallback?: string
  /** The values were selected or calculated from the provider's readings (an interpolation, a summary) */
  derived?: boolean
  /** Smaller, for the widget's narrow frame */
  compact?: boolean
}>(), { provider: null, terms: null, fallback: '', derived: false, compact: false })

const { data: providerList } = useProviders()
const resolved = computed(() => props.terms ?? termsOfProvider(providerList.value?.providers, props.provider))
const attribution = computed(() => resolved.value?.attribution || props.fallback)
const licence = computed(() => resolved.value?.license ? { name: resolved.value.license.name, href: safeHref(resolved.value.license.url) } : null)
</script>

<template>
  <div data-testid="provider-credit">
    <p v-if="attribution || licence" :class="compact ? 'text-xs' : 'text-sm'" class="text-muted" data-testid="provider-credit-line">
      <span v-if="attribution">{{ attribution }}</span><template v-if="licence">
        <template v-if="attribution">
          {{ ', ' }}
        </template>
        <a v-if="licence.href" :href="licence.href" target="_blank" rel="noopener" class="underline underline-offset-2" data-testid="provider-credit-licence">{{ licence.name }}</a>
        <span v-else>{{ licence.name }}</span>
      </template>
    </p>
    <ProcessingNote class="mt-1" :derived="derived" :compact="compact" />
  </div>
</template>
