<script setup lang="ts">
// Accept initial values from parent via v-model
const props = withDefaults(defineProps<{
  modelValue?: {
    provider?: string
    network?: string
    resolution?: string
    dataset?: string
    parameters?: string[]
    dateRequired?: boolean
    kind?: NetworkKind
  }
  showParameters?: boolean
  /** When set, restricts the provider select to this single value (e.g. Explorer is DWD-observation-only). */
  restrictProvider?: string
  /** When set, restricts the network select to this single value. */
  restrictNetwork?: string
  /** DWD DMO's run, where one is chosen: only the parameters it carries are offered */
  leadTime?: 'short' | 'long'
}>(), {
  showParameters: true,
})

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

// fetch the providers and their networks (`GET /api/providers`, the answer the providers pages share by its key)
//
// Deliberately not awaited. A top-level `await` makes this component's setup async, and with
// `ssr: false` the nearest Suspense boundary is the page itself -- so the Explorer rendered
// nothing at all, not even its own headings, until the backend had answered this request. The
// selects render empty-and-loading instead, and `initializeFromProps()` waits for the answer.
const { data: providerList, status: coverageStatus, refresh: refreshProviders } = useProviders()
// The networks as the selects read them, by provider and then network. What a network has (its
// resolutions, datasets and parameters) is the coverage of that network, asked for when one is chosen.
const coverage = computed<Record<string, Record<string, ProviderNetwork>> | null>(() => {
  if (!providerList.value)
    return null
  return Object.fromEntries(providerList.value.providers.map(p => [p.provider, Object.fromEntries(p.networks.map(n => [n.network, n]))]))
})
// Nothing derived from `coverage` means anything until the request has settled: an empty answer
// and an answer that has not arrived yet are indistinguishable in the data, but not to a reader.
const coverageSettled = computed(() => coverageStatus.value === 'success' || coverageStatus.value === 'error')
const coveragePending = computed(() => !coverageSettled.value)
// A request that failed (the backend is down, a 5xx, an answer that is not the list) says nothing about which
// providers exist: the restriction banners below speak only of an answer that arrived
const coverageFailed = computed(() => coverageStatus.value === 'error')

// Whether the backend accepts the credentials of a network is not part of the list of networks: it
// is a request to the provider, which a list of every provider must not wait for (GH-2564). It is
// asked per network, after the list is on screen, and only a network whose answer is "rejected"
// leaves the selects. Until it answers, and where it cannot (`null`, an error), the network is
// listed: a failure to check is not a rejection (GH-2550, GH-2562).
const rejectedNetworks = ref<Record<string, true>>({})
const networkKey = (providerName: string, networkName: string) => `${providerName}/${networkName}`

// A provider/network is available when it is a timeseries network, and needs no auth or has its
// credentials present and not rejected. A standalone network (`radar`, `alerts`: `dwd/radar`,
// `dwd/alerts`, and any later one) has no stations, resolutions or parameters to select, and its
// coverage is a 404. Only a check that says the credentials are rejected hides a network that has
// them (GH-2641).
const TIMESERIES_KINDS: ReadonlyArray<NetworkKind | undefined> = ['observation', 'forecast', 'derived']
function isAvailable(providerName: string, networkName: string, n: Pick<ProviderNetwork, 'auth' | 'configured'> & { kind?: NetworkKind }) {
  // a missing `kind` is an answer that does not carry it, as the mocks of the tests do
  if (n.kind !== undefined && !TIMESERIES_KINDS.includes(n.kind))
    return false
  return !n.auth || (n.configured && !rejectedNetworks.value[networkKey(providerName, networkName)])
}

// EXPECTING
// These reflect what the backend actually offers -- independent of any
// restriction -- so restriction validity can be checked against reality
// instead of assumed.
const providers = computed(() => {
  const cov = coverage.value
  if (!cov)
    return []
  return Object.keys(cov)
    .filter(p => Object.entries(cov[p] ?? {}).some(([name, n]) => isAvailable(p, name, n)))
    .sort()
})
function networksFor(providerName: string | undefined): string[] {
  const cov = coverage.value
  if (!providerName || !cov)
    return []
  return Object.entries(cov[providerName] ?? {})
    .filter(([name, n]) => isAvailable(providerName, name, n))
    .map(([name]) => name)
}
const networks = computed<string[]>(() => networksFor(provider.value))

// Ask whether the backend accepts the credentials of each network that has them configured, all at
// once and without anything waiting for the answers. A request the page no longer needs is aborted
// when it is left. `retry: 0`: the backend's probe is one bounded attempt, and a failure of the
// request is "could not check" like any other.
const credentialChecks = new AbortController()
onScopeDispose(() => credentialChecks.abort())
const checkedNetworks = new Set<string>()
async function checkCredentials(providerName: string, networkName: string) {
  try {
    const answer = await $fetch<AuthResponse>('/api/auth', {
      query: { provider: providerName, network: networkName },
      retry: 0,
      signal: credentialChecks.signal,
      ...API_ANSWER,
    })
    if (answer.valid === false)
      rejectedNetworks.value = { ...rejectedNetworks.value, [networkKey(providerName, networkName)]: true }
  }
  catch {
    // could not check: not a rejection, so the network stays listed
  }
}
watch(coverage, (cov) => {
  for (const [providerName, networksOfProvider] of Object.entries(cov ?? {})) {
    for (const [networkName, n] of Object.entries(networksOfProvider ?? {})) {
      const key = networkKey(providerName, networkName)
      if (!n.auth || !n.configured || checkedNetworks.has(key))
        continue
      checkedNetworks.add(key)
      checkCredentials(providerName, networkName)
    }
  }
}, { immediate: true })

// A network that turns out to be rejected after it was chosen leaves the selection with it
watch([rejectedNetworks, isInitializing], () => {
  if (isInitializing.value)
    return
  if (network.value && !networks.value.includes(network.value))
    network.value = undefined
  if (provider.value && !providers.value.includes(provider.value))
    provider.value = undefined
})

// A caller-supplied restriction (e.g. History is DWD-observation-only) is only
// as good as the backend actually offering it. Silently falling back to the
// unrestricted list when it doesn't (stale config, auth not set up, etc.)
// would look like the restriction never happened; surfacing it as a visible
// error is safer than a confusingly half-locked form.
const restrictedProviderAvailable = computed(() => !props.restrictProvider || providers.value.includes(props.restrictProvider))
const restrictedNetworkAvailable = computed(() => {
  if (!props.restrictNetwork)
    return true
  if (props.restrictProvider && !restrictedProviderAvailable.value)
    return true // provider error already covers this; don't pile on
  return networksFor(props.restrictProvider ?? provider.value).includes(props.restrictNetwork)
})

// What the selects actually display: the restricted value only when it's
// confirmed available, otherwise nothing (rather than silently showing every
// provider/network as if unrestricted).
const providerItems = computed(() => {
  if (!props.restrictProvider)
    return providers.value
  return restrictedProviderAvailable.value ? [props.restrictProvider] : []
})
const networkItems = computed(() => {
  if (!props.restrictNetwork)
    return networks.value
  return restrictedNetworkAvailable.value ? [props.restrictNetwork] : []
})

// provider-network coverage
const { data: providerNetworkCoverage, pending: networkCoveragePending, refresh: refreshProviderNetworkCoverage } = useFetch<ProviderNetworkCoverageResponse>(
  '/api/coverage',
  {
    query: computed(() => ({
      provider: provider.value,
      network: network.value,
    })),
    immediate: false,
    watch: false,
    ...API_ANSWER,
  },
)

const resolutions = computed((): string[] => {
  return providerNetworkCoverage.value ? Object.keys(providerNetworkCoverage.value) : []
})
const datasets = computed((): string[] => {
  if (!providerNetworkCoverage.value || !resolution.value)
    return []
  const resolutionData = providerNetworkCoverage.value[resolution.value as Resolution]
  return resolutionData ? Object.keys(resolutionData.datasets).sort() : []
})
const parameterDescriptions = computed<Record<string, string>>(() => {
  if (!providerNetworkCoverage.value || !resolution.value || !dataset.value)
    return {}
  const resolutionData = providerNetworkCoverage.value[resolution.value as Resolution]
  const entries = resolutionData?.datasets[dataset.value]?.parameters ?? []
  return Object.fromEntries(entries.map((p: CoverageParameter) => [p.name, p.description ?? '']))
})
// The dataset's parameters a run carries. DWD DMO's coverage names the runs that carry each one, and
// the values refuse a parameter asked for by name that the requested run does not carry (GH-2256);
// a parameter that names none is carried by any
function parametersCarriedBy(leadTime: 'short' | 'long' | undefined): string[] {
  if (!providerNetworkCoverage.value || !resolution.value || !dataset.value)
    return []
  const resolutionData = providerNetworkCoverage.value[resolution.value as Resolution]
  if (!resolutionData)
    return []
  const datasetParams = resolutionData.datasets[dataset.value]?.parameters
  if (!datasetParams)
    return []
  return datasetParams
    .filter((p: CoverageParameter) => !leadTime || !p.lead_times || p.lead_times.includes(leadTime))
    .map((p: CoverageParameter) => p.name)
    .sort()
}
const params = computed<string[]>(() => parametersCarriedBy(props.leadTime))
// the source's own words for the selected resolution and dataset, which `/api/coverage` carries
// since the backend nested its answer; null where the source has none (most resolutions, some
// datasets), and then the hint just disappears
const resolutionDescription = computed<string>(() => {
  if (!providerNetworkCoverage.value || !resolution.value)
    return ''
  return providerNetworkCoverage.value[resolution.value as Resolution]?.description ?? ''
})
const datasetDescription = computed<string>(() => {
  if (!providerNetworkCoverage.value || !resolution.value || !dataset.value)
    return ''
  const resolutionData = providerNetworkCoverage.value[resolution.value as Resolution]
  return resolutionData?.datasets[dataset.value]?.description ?? ''
})

// what the network serves (a forecast's readings lie ahead of today), where the coverage says
const networkKind = computed<NetworkKind | undefined>(() => {
  if (!coverage.value || !provider.value || !network.value)
    return undefined
  return coverage.value[provider.value]?.[network.value]?.kind
})

const dateRequired = computed<boolean>(() => {
  if (!coverage.value || !provider.value || !network.value)
    return false
  return coverage.value[provider.value]?.[network.value]?.date_required === true
})

// Friendly, locale-aware labels for the select menus (value stays the raw backend id).
const resolutionItems = computed(() => resolutions.value.map(r => ({ label: resolutionLabel(r), value: r })))
const datasetItems = computed(() => datasets.value.map(d => ({ label: datasetLabel(d), value: d })))
const paramItems = computed(() => params.value.map(p => ({
  label: parameterLabel(p),
  value: p,
  description: parameterDescriptions.value[p] ?? '',
})))

// Initialize from query params and validate step by step
// What the parent handed over when initialization first ran: a retry of a failed request restores from it, not from
// what the parent holds by then
let initialModel: NonNullable<typeof props.modelValue> = {}

// Where initialization ends, the parent is told the selection it came to. Not where it ran on a failed request: nothing
// could be restored then, and an empty selection would replace the parent's, and the address it writes, for good. The
// parent keeps what it had until a retry is answered.
function emitInitial() {
  if (!coverageFailed.value)
    emitUpdate()
}

async function initializeFromProps() {
  const initial = { ...initialModel }

  // A restricted provider/network overrides anything URL-provided — there's
  // only one valid value, so no point treating a mismatch as "invalid input".
  if (props.restrictProvider && initial.provider !== props.restrictProvider) {
    initial.provider = props.restrictProvider
    initial.network = undefined
    initial.resolution = undefined
    initial.dataset = undefined
    initial.parameters = []
  }
  if (props.restrictNetwork && initial.network !== props.restrictNetwork) {
    initial.network = props.restrictNetwork
    initial.resolution = undefined
    initial.dataset = undefined
    initial.parameters = []
  }

  // Step 1: Validate provider
  if (initial.provider && providers.value.includes(initial.provider)) {
    provider.value = initial.provider
  }
  else {
    isInitializing.value = false
    emitInitial()
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
    emitInitial()
    return
  }

  // Step 3: Validate resolution
  if (initial.resolution && resolutions.value.includes(initial.resolution)) {
    resolution.value = initial.resolution as Resolution
  }
  else {
    isInitializing.value = false
    emitInitial()
    return
  }

  // Step 4: Validate dataset
  if (initial.dataset && datasets.value.includes(initial.dataset)) {
    dataset.value = initial.dataset
  }
  else {
    isInitializing.value = false
    emitInitial()
    return
  }

  // Step 5: Use URL-specified parameters if valid; otherwise auto-select all
  await nextTick()

  if (initial.parameters?.length) {
    const validParams = initial.parameters.filter(p => params.value.includes(p))
    parameters.value = validParams.length ? validParams : [...params.value]
  }
  else {
    parameters.value = [...params.value]
  }

  // Wait another tick to ensure watchers have processed before turning off initialization mode
  await nextTick()
  isInitializing.value = false
  emitInitial()
}

// Initialization needs the coverage answer -- every validation step above reads it -- and that is
// no longer awaited in setup, so mount alone is too early. An error settles it too: initialization
// then falls through to the "nothing valid to restore" branch, exactly as it did when a failed
// fetch left `coverage` null.
//
// Not an `immediate` watcher, which would run this during setup: the answer can already be cached
// (both /explorer and /history mount this component against the same `useFetch` key), and
// `emitUpdate()` firing mid-render mutates the parent's state while it is still rendering.
//
// An initialization that ran on a failed request restricted nothing, restored nothing and told the parent nothing
// (`emitInitial`): it is run again, from what the parent handed over the first time, when the retry is answered.
let initializationStarted = false
let initializedOnFailure = false
function initializeWhenCoverageSettled() {
  if (!coverageSettled.value)
    return
  if (initializationStarted) {
    if (!initializedOnFailure || coverageStatus.value !== 'success')
      return
    isInitializing.value = true
  }
  else {
    initialModel = { ...props.modelValue, parameters: props.modelValue?.parameters ? [...props.modelValue.parameters] : undefined }
  }
  initializationStarted = true
  initializedOnFailure = coverageFailed.value
  initializeFromProps()
}
onMounted(initializeWhenCoverageSettled)
watch(coverageSettled, initializeWhenCoverageSettled)

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

watch(dataset, async () => {
  if (isInitializing.value)
    return
  await nextTick()
  parameters.value = [...params.value]
})

// Another run carries other parameters: the ones it does not carry leave the selection, and a
// selection of every parameter the last run carried, as choosing a dataset makes, becomes every one
// this run carries
watch(() => props.leadTime, (_, previous) => {
  if (isInitializing.value)
    return
  const carriedBefore = parametersCarriedBy(previous)
  if (carriedBefore.length > 0 && carriedBefore.every(p => parameters.value.includes(p)))
    parameters.value = [...params.value]
  else
    parameters.value = parameters.value.filter(p => params.value.includes(p))
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
    dateRequired: dateRequired.value,
    kind: networkKind.value,
  })
}

watch([provider, network, resolution, dataset, parameters, dateRequired, networkKind], () => {
  if (isInitializing.value)
    return
  emitUpdate()
})
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon name="i-ph-database" class="text-primary-600 dark:text-primary-500 shrink-0" />
        <h2 class="text-lg font-bold">
          {{ t('parameterSelection.title') }}
        </h2>
      </div>
    </template>
    <UContainer class="flex flex-col gap-4">
      <!-- only once coverage has settled: while the request is out every provider looks unavailable,
           and flashing "not available from this backend" on each cold load is worse than silence. A request that
           failed says the backend could not be reached, with a retry, and not that the provider is missing.
           Inside the container, with the fields: a root that is as wide as its box with a margin on top of it ran
           past it (8 px past a 320 px window, GH-4037) -->
      <UAlert
        v-if="coverageFailed"
        color="error"
        variant="subtle"
        :title="t('parameterSelection.backendUnreachable')"
        icon="i-ph-warning-circle"
        :actions="[{ label: t('common.retry'), icon: 'i-ph-arrow-clockwise', color: 'neutral', variant: 'outline', size: 'sm', class: 'max-w-full h-auto', ui: { label: 'whitespace-normal text-clip text-left' }, onClick: () => refreshProviders() }]"
      />
      <UAlert
        v-else-if="coverageSettled && restrictProvider && !restrictedProviderAvailable"
        color="error"
        variant="subtle"
        :title="t('parameterSelection.providerRestrictionUnavailable', { provider: restrictProvider })"
        icon="i-ph-warning-circle"
      />
      <UAlert
        v-else-if="coverageSettled && restrictNetwork && !restrictedNetworkAvailable"
        color="error"
        variant="subtle"
        :title="t('parameterSelection.networkRestrictionUnavailable', { network: restrictNetwork })"
        icon="i-ph-warning-circle"
      />
      <UFormField :label="t('parameterSelection.providerLabel')">
        <USelect v-model="provider" :items="providerItems" :placeholder="t('parameterSelection.selectProvider')" :disabled="!!restrictProvider || coveragePending" :loading="coveragePending" class="w-full" :class="{ 'needs-input': activeField === 'provider' }" />
      </UFormField>
      <UFormField :label="t('parameterSelection.networkLabel')">
        <USelect v-model="network" :items="networkItems" :placeholder="t('parameterSelection.selectNetwork')" :disabled="!provider || !!restrictNetwork || coveragePending" :loading="coveragePending" class="w-full" :class="{ 'needs-input': activeField === 'network' }" />
      </UFormField>
      <UFormField :label="t('parameterSelection.resolutionLabel')" :help="resolutionDescription">
        <USelect v-model="resolution" :items="resolutionItems" :placeholder="t('parameterSelection.selectResolution')" :disabled="!network || networkCoveragePending" class="w-full" :class="{ 'needs-input': activeField === 'resolution' }" />
      </UFormField>
      <UFormField :label="t('parameterSelection.datasetLabel')" :help="datasetDescription">
        <USelect v-model="dataset" :items="datasetItems" :placeholder="t('parameterSelection.selectDataset')" :disabled="!resolution || networkCoveragePending" class="w-full" :class="{ 'needs-input': activeField === 'dataset' }" />
      </UFormField>
      <UFormField v-if="props.showParameters !== false" :label="t('parameterSelection.parametersLabel')">
        <div class="flex gap-2 items-center min-w-0">
          <USelectMenu v-model="parameters" :items="paramItems" value-key="value" multiple :placeholder="t('parameterSelection.selectParameters')" :disabled="!dataset" class="flex-1 min-w-0 overflow-hidden" :class="{ 'needs-input': activeField === 'parameters' }">
            <template #item-label="{ item }">
              <span>{{ item.label }}</span>
              <span v-if="item.description" class="block text-xs text-gray-500 dark:text-gray-400 whitespace-normal">
                {{ item.description }}
              </span>
            </template>
          </USelectMenu>
          <UButton
            v-if="dataset && !allSelected"
            size="xs"
            variant="ghost"
            color="neutral"
            icon="i-ph-checks"
            @click="selectAllParameters"
          >
            {{ t('common.all') }}
          </UButton>
          <UButton
            v-if="dataset && parameters.length > 0"
            size="xs"
            variant="ghost"
            color="neutral"
            icon="i-ph-x"
            @click="clearParameters"
          >
            {{ t('parameterSelection.clear') }}
          </UButton>
        </div>
      </UFormField>
    </UContainer>
  </UCard>
</template>
