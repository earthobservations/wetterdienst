<script setup lang="ts">
import type { Station } from '~/shared/types/api'
import { ref, watch, nextTick, computed, onUnmounted } from 'vue'

const props = defineProps<{
  modelValue?: Station | null
}>()

const emit = defineEmits<{
  'update:modelValue': [station: Station | null]
}>()

const query = ref('')
const results = ref<Station[]>([])
const loading = ref(false)
const showResults = ref(false)
const noResults = ref(false)

const MAX_RESULTS = 20

// Fixed MOSMIX params – user never needs to see or touch these
const SEARCH_PARAMS = {
  provider: 'dwd',
  network: 'mosmix',
  parameters: 'hourly/large',
}

let debounceTimer: ReturnType<typeof setTimeout> | null = null

async function doSearch(q: string) {
  loading.value = true
  noResults.value = false
  try {
    // Numeric-only input → treat as station ID for an exact lookup
    const isId = /^\d+$/.test(q)
    const queryParams: Record<string, string | number | boolean> = { ...SEARCH_PARAMS }
    if (isId) {
      queryParams.station = q
    }
    else {
      queryParams.name = q
      queryParams.name_threshold = 0.6
    }

    const res = await $fetch<{ stations: Station[] }>('/api/stations', { query: queryParams })
    results.value = (res.stations ?? []).slice(0, MAX_RESULTS)
    showResults.value = results.value.length > 0
    noResults.value = results.value.length === 0
  }
  catch {
    results.value = []
    showResults.value = false
  }
  finally {
    loading.value = false
  }
}

watch(query, (q) => {
  if (debounceTimer)
    clearTimeout(debounceTimer)

  if (!q || q.length < 2) {
    results.value = []
    showResults.value = false
    noResults.value = false
    return
  }

  debounceTimer = setTimeout(() => doSearch(q), 400)
})

function select(station: Station) {
  emit('update:modelValue', station)
  query.value = ''
  results.value = []
  showResults.value = false
  noResults.value = false
}

function clear() {
  emit('update:modelValue', null)
  query.value = ''
  results.value = []
  showResults.value = false
  noResults.value = false
}

// Repositioning portal so dropdown cannot be clipped by sibling frames
const wrapperRef = ref<HTMLDivElement | null>(null)
const anchorRef = ref<HTMLDivElement | null>(null)
const portalVisible = ref(false)
// Very high z-index and pointer-events enabled so the portal always appears above chart frames
const dropdownStyle = ref<Record<string, string>>({ position: 'fixed', left: '0px', top: '0px', width: '200px', zIndex: '2147483647', pointerEvents: 'auto' })

const shouldShowPortal = computed(() => showResults.value && results.value.length > 0)

function updateDropdownPosition() {
  const anchor = anchorRef.value ?? wrapperRef.value
  if (!anchor)
    return
  const rect = anchor.getBoundingClientRect()
  const top = rect.bottom + 6
  const left = rect.left
  const width = rect.width
  dropdownStyle.value.top = `${top}px`
  dropdownStyle.value.left = `${left}px`
  dropdownStyle.value.width = `${width}px`
}

function onDocumentMousedown(e: MouseEvent) {
  const target = e.target as Element | null
  if (!target) {
    showResults.value = false
    return
  }
  // Keep open if click was inside the search wrapper or inside the teleported portal
  if (wrapperRef.value && wrapperRef.value.contains(target))
    return
  if (target.closest('[data-station-portal]'))
    return
  showResults.value = false
}

function onEscape(e: KeyboardEvent) {
  if (e.key === 'Escape')
    showResults.value = false
}

watch(shouldShowPortal, async (v) => {
  if (v) {
    await nextTick()
    updateDropdownPosition()
    portalVisible.value = true
    document.addEventListener('mousedown', onDocumentMousedown)
    document.addEventListener('keydown', onEscape)
    window.addEventListener('resize', updateDropdownPosition)
    window.addEventListener('scroll', updateDropdownPosition, true)
  }
  else {
    portalVisible.value = false
    document.removeEventListener('mousedown', onDocumentMousedown)
    document.removeEventListener('keydown', onEscape)
    window.removeEventListener('resize', updateDropdownPosition)
    window.removeEventListener('scroll', updateDropdownPosition, true)
  }
})

watch(results, (r) => {
  if (showResults.value && r.length > 0) {
    void nextTick().then(updateDropdownPosition)
  }
})

onUnmounted(() => {
  document.removeEventListener('mousedown', onDocumentMousedown)
  document.removeEventListener('keydown', onEscape)
  window.removeEventListener('resize', updateDropdownPosition)
  window.removeEventListener('scroll', updateDropdownPosition, true)
})
</script>

<template>
  <div ref="wrapperRef" class="relative">
    <!-- Selected station badge -->
    <div v-if="modelValue" class="flex items-center gap-2 mb-3">
      <UBadge size="lg" variant="subtle" class="text-sm font-medium py-1 px-3">
        {{ modelValue.name }}
        <span class="text-gray-400 ml-1">({{ modelValue.station_id }})</span>
        <span
          class="ml-2 cursor-pointer text-gray-500 hover:text-red-500 font-bold"
          tabindex="0"
          role="button"
          @click="clear"
          @keydown.enter="clear"
        >×</span>
      </UBadge>
    </div>

    <!-- Search input -->
    <div ref="anchorRef">
      <UInput
        v-model="query"
        :placeholder="modelValue ? 'Search for a different station…' : 'Search by name or station ID (e.g. München, 10738)'"
        class="w-full"
        :loading="loading"
        icon="i-lucide-search"
        @focus="showResults = results.length > 0"
      />
    </div>

    <!-- Hint text -->
    <p class="text-xs text-gray-400 mt-1">
      Type ≥ 2 characters to search. Use a numeric ID for an exact lookup.
    </p>

    <!-- Results dropdown teleported so it can't be clipped by sibling frames -->
    <teleport to="body">
      <div v-if="portalVisible" data-station-portal :style="dropdownStyle" class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl max-h-72 overflow-y-auto">
        <div v-for="station in results" :key="station.station_id">
          <button
            class="w-full text-left px-4 py-2 hover:bg-primary-50 dark:hover:bg-primary-950 text-sm transition-colors"
            tabindex="0"
            @mousedown.prevent="select(station)"
            @keydown.enter="select(station)"
          >
            <span class="font-medium">{{ station.name }}</span>
            <span class="text-gray-400 ml-2 text-xs">{{ station.station_id }}</span>
            <span v-if="station.state" class="text-gray-400 ml-2 text-xs">— {{ station.state }}</span>
            <span v-if="station.latitude && station.longitude" class="text-gray-300 ml-2 text-xs">
              {{ station.latitude.toFixed(2) }}°N {{ station.longitude.toFixed(2) }}°E
            </span>
          </button>
        </div>
      </div>
    </teleport>

    <!-- No results notice -->
    <p
      v-if="!loading && noResults && query.length >= 2"
      class="text-sm text-gray-500 mt-2"
    >
      No stations found for "{{ query }}"
    </p>
  </div>
</template>
