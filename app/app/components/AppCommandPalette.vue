<script setup lang="ts">
import type { Station } from '#shared/types/api'
import type { PlacedStation } from '~/utils/atlas'
import { FORECAST_STATIONS_QUERY, placed, searchStations } from '~/utils/atlas'
import { LANGUAGES } from '~/utils/languages'

// The search of the whole app (GH-3518): its pages, each with what it is for, the appearance and the language,
// and the forecast points by name or id, which open on the map. A dialog that keeps the focus, with the WAI-ARIA
// combobox pattern inside it: the field is the combobox, the results its listbox, the arrow keys move the
// active option (aria-activedescendant) while the focus stays in the field, Enter takes it, Escape closes the
// dialog and the focus goes back to where it was (the header's button, or wherever Ctrl+K was pressed).

const open = defineModel<boolean>('open', { default: false })

const { t, setLocale } = useI18n()
const colorMode = useColorMode()

interface Entry {
  id: string
  group: 'pages' | 'appearance' | 'language' | 'stations'
  label: string
  description: string
  icon: string
  /** The language the label is written in, where it is not the page's: the names of the languages */
  lang?: string
  /** Words beside the label and the description that find the entry */
  keywords?: string
  run: () => void | Promise<void>
}

const query = ref('')
const active = ref(0)
const input = ref<HTMLInputElement | null>(null)
const listbox = useId()
const optionId = (index: number) => `${listbox}-option-${index}`

function go(path: string | { path: string, query: Record<string, string> }) {
  return () => {
    open.value = false
    void navigateTo(path)
  }
}

const pages = computed<Entry[]>(() => [
  { id: 'map', label: t('nav.map'), description: t('palette.purposeMap'), icon: 'i-lucide-map', to: '/' },
  { id: 'meteogram', label: t('nav.meteogram'), description: t('meteogram.subtitle'), icon: 'i-lucide-cloud-sun', to: '/meteogram' },
  { id: 'stripes', label: t('nav.stripes'), description: t('stripes.subtitle'), icon: 'i-lucide-chart-column-big', to: '/stripes' },
  { id: 'explorer', label: t('nav.explorer'), description: t('explorer.subtitle'), icon: 'i-lucide-table-2', to: '/explorer' },
  { id: 'history', label: t('nav.history'), description: t('history.subtitle'), icon: 'i-lucide-history', to: '/history' },
  { id: 'api', label: t('nav.api'), description: t('api.subtitle'), icon: 'i-lucide-code', to: '/api' },
  { id: 'providers', label: t('nav.providers'), description: t('providers.subtitle'), icon: 'i-lucide-building-2', to: '/providers' },
  { id: 'glossary', label: t('nav.glossary'), description: t('glossary.subtitle'), icon: 'i-lucide-book-open', to: '/glossary' },
  { id: 'settings', label: t('common.settings'), description: t('settings.subtitle'), icon: 'i-lucide-settings-2', to: '/settings' },
  { id: 'about', label: t('footer.about'), description: t('about.subtitle'), icon: 'i-lucide-info', to: '/about' },
  { id: 'support', label: t('nav.support'), description: t('palette.purposeSupport'), icon: 'i-lucide-heart', to: '/support' },
  { id: 'impressum', label: t('footer.legal'), description: t('palette.purposeLegal'), icon: 'i-lucide-scale', to: '/impressum' },
  { id: 'datenschutz', label: t('footer.privacy'), description: t('palette.purposePrivacy'), icon: 'i-lucide-shield', to: '/datenschutz' },
].map(page => ({ id: `page-${page.id}`, group: 'pages' as const, label: page.label, description: page.description, icon: page.icon, keywords: page.to, run: go(page.to) })))

const appearance = computed<Entry[]>(() => [
  { value: 'light', label: t('settings.themeLight'), icon: 'i-lucide-sun' },
  { value: 'dark', label: t('settings.themeDark'), icon: 'i-lucide-moon' },
  { value: 'system', label: t('settings.themeSystem'), icon: 'i-lucide-monitor' },
].map(mode => ({
  id: `appearance-${mode.value}`,
  group: 'appearance' as const,
  label: mode.label,
  description: t('settings.theme'),
  icon: mode.icon,
  keywords: `${mode.value} theme`,
  run: () => {
    colorMode.preference = mode.value
    open.value = false
  },
})))

const languages = computed<Entry[]>(() => LANGUAGES.map(language => ({
  id: `language-${language.value}`,
  group: 'language' as const,
  label: language.name,
  lang: language.value === 'de-hh' ? 'nds' : language.value,
  description: t('settings.language'),
  icon: 'i-lucide-languages',
  keywords: language.value,
  run: async () => {
    open.value = false
    await setLocale(language.value as Parameters<typeof setLocale>[0])
  },
})))

// The forecast points, asked for the first time a query is long enough to look for one; the map's own list
let forecastPoints: Promise<PlacedStation[]> | null = null
const points = shallowRef<PlacedStation[]>([])
const pointsFailed = ref(false)
function loadPoints() {
  forecastPoints ??= $fetch<{ stations: Station[] }>('/api/stations', { query: FORECAST_STATIONS_QUERY, ...RETRY_TRANSIENT })
    .then(answer => placed(answer.stations ?? []))
  forecastPoints.then((list) => {
    points.value = list
    pointsFailed.value = false
  }, () => {
    forecastPoints = null
    pointsFailed.value = true
  })
}

const stations = computed<Entry[]>(() => query.value.trim().length < 2
  ? []
  : searchStations(points.value, query.value, 8).map(station => ({
      id: `station-${station.station_id}`,
      group: 'stations' as const,
      label: station.name ?? station.station_id,
      description: `${t('stripes.station')} ${station.station_id}`,
      icon: 'i-lucide-map-pin',
      run: go({ path: '/', query: { station: station.station_id } }),
    })))

watch(query, (text) => {
  active.value = 0
  if (text.trim().length >= 2 && !points.value.length)
    loadPoints()
})

const fold = (text: string) => text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
function matches(entry: Entry, words: string[]) {
  const haystack = fold(`${entry.label} ${entry.description} ${entry.keywords ?? ''}`)
  return words.every(word => haystack.includes(word))
}

/** What the list shows: everything that holds every word of the query, by group; with no query, the pages and the appearance */
const results = computed<Entry[]>(() => {
  const words = fold(query.value).split(/\s+/).filter(Boolean)
  if (!words.length)
    return [...pages.value, ...appearance.value]
  return [
    ...[...pages.value, ...appearance.value, ...languages.value].filter(entry => matches(entry, words)),
    ...stations.value,
  ]
})

const groupTitles = computed(() => ({
  pages: t('palette.groupPages'),
  appearance: t('settings.theme'),
  language: t('settings.language'),
  stations: t('palette.groupStations'),
}))
const groups = computed(() => {
  const out: Array<{ key: Entry['group'], title: string, entries: Array<{ entry: Entry, index: number }> }> = []
  results.value.forEach((entry, index) => {
    let group = out.find(candidate => candidate.key === entry.group)
    if (!group)
      out.push(group = { key: entry.group, title: groupTitles.value[entry.group], entries: [] })
    group.entries.push({ entry, index })
  })
  return out
})

const activeId = computed(() => results.value.length ? optionId(active.value) : undefined)

function move(step: number) {
  const count = results.value.length
  if (!count)
    return
  active.value = (active.value + step + count) % count
  void nextTick(() => document.getElementById(optionId(active.value))?.scrollIntoView({ block: 'nearest' }))
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    move(1)
  }
  else if (event.key === 'ArrowUp') {
    event.preventDefault()
    move(-1)
  }
  else if (event.key === 'Home' && results.value.length) {
    event.preventDefault()
    active.value = 0
    move(0)
  }
  else if (event.key === 'End' && results.value.length) {
    event.preventDefault()
    active.value = results.value.length - 1
    move(0)
  }
  else if (event.key === 'Enter') {
    event.preventDefault()
    void results.value[active.value]?.run()
  }
}

// a fresh search each time it opens
watch(open, (isOpen) => {
  if (isOpen) {
    query.value = ''
    active.value = 0
  }
})

/** What a screen reader is told after a keystroke: how many results there are */
const status = computed(() => {
  if (!query.value.trim())
    return ''
  return results.value.length ? t('palette.results', { count: results.value.length }) : t('palette.noResults', { query: query.value.trim() })
})
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('palette.title')"
    :close="false"
    :ui="{
      content: 'sm:max-w-xl top-[8vh] translate-y-0 sm:top-[12vh]',
      header: 'sr-only',
      body: 'p-0 sm:p-0',
    }"
  >
    <template #body>
      <div class="palette">
        <div class="palette-field">
          <UIcon name="i-lucide-search" class="size-5 shrink-0 text-muted" />
          <input
            ref="input"
            v-model="query"
            type="text"
            class="palette-input"
            role="combobox"
            aria-expanded="true"
            aria-autocomplete="list"
            :aria-controls="listbox"
            :aria-activedescendant="activeId"
            :aria-label="t('palette.title')"
            :placeholder="t('palette.placeholder')"
            autocomplete="off"
            autocapitalize="off"
            spellcheck="false"
            autofocus
            @keydown="onKeydown"
          >
          <UButton :label="t('common.close')" color="neutral" variant="outline" size="xs" class="shrink-0" @click="open = false">
            <template #trailing>
              <kbd class="palette-kbd" aria-hidden="true">Esc</kbd>
            </template>
          </UButton>
        </div>

        <p class="sr-only" role="status">
          {{ status }}
        </p>

        <ul :id="listbox" role="listbox" :aria-label="t('palette.title')" class="palette-list">
          <li v-for="group in groups" :key="group.key" role="group" :aria-labelledby="`${listbox}-${group.key}`">
            <span :id="`${listbox}-${group.key}`" class="palette-group" role="presentation">{{ group.title }}</span>
            <ul role="presentation">
              <li
                v-for="{ entry, index } in group.entries"
                :id="optionId(index)"
                :key="entry.id"
                role="option"
                class="palette-option"
                :aria-selected="index === active"
                @click="entry.run()"
                @mousemove="active = index"
              >
                <UIcon :name="entry.icon" class="size-5 shrink-0 palette-icon" />
                <span class="min-w-0">
                  <span class="block font-semibold text-highlighted" :lang="entry.lang">{{ entry.label }}</span>
                  <span class="block text-sm text-muted truncate">{{ entry.description }}</span>
                </span>
              </li>
            </ul>
          </li>
        </ul>
        <p v-if="!results.length" class="palette-empty">
          {{ t('palette.noResults', { query: query.trim() }) }}
        </p>
        <p v-if="pointsFailed" class="palette-empty">
          {{ t('atlas.stationsFailed') }}
        </p>

        <p class="palette-hint" aria-hidden="true">
          <span><kbd class="palette-kbd">↑</kbd> <kbd class="palette-kbd">↓</kbd></span>
          <span><kbd class="palette-kbd">↵</kbd></span>
          <span>{{ t('palette.hint') }}</span>
        </p>
      </div>
    </template>
  </UModal>
</template>

<style>
.palette {
  display: flex;
  flex-direction: column;
  max-height: min(70vh, 36rem);
}
.palette-field {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--ui-border);
}
.palette-input {
  flex: 1;
  min-width: 0;
  min-height: 2.25rem;
  background: transparent;
  color: var(--ui-text-highlighted);
  font-size: 1.0625rem;
}
.palette-input::placeholder {
  color: var(--ui-text-dimmed);
}
.palette-list {
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 0.375rem;
}
.palette-group {
  display: block;
  padding: 0.625rem 0.75rem 0.25rem;
  color: var(--ui-text-muted);
  font-size: 0.8125rem;
  font-weight: 600;
}
.palette-option {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-height: 2.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: calc(var(--ui-radius) * 1.5);
  cursor: pointer;
}
.palette-option[aria-selected="true"] {
  background: var(--ui-bg-elevated);
  box-shadow: inset 3px 0 0 var(--ui-color-primary-700);
}
.dark .palette-option[aria-selected="true"] {
  box-shadow: inset 3px 0 0 var(--color-sun);
}
@media (forced-colors: active) {
  .palette-option[aria-selected="true"] {
    outline: 2px solid Highlight;
    outline-offset: -2px;
  }
}
.palette-icon {
  color: var(--ui-color-primary-600);
}
.dark .palette-icon {
  color: var(--ui-color-primary-400);
}
.palette-empty {
  padding: 1rem 1.25rem;
  color: var(--ui-text-muted);
  font-size: 0.875rem;
}
.palette-hint {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-top: 1px solid var(--ui-border);
  color: var(--ui-text-muted);
  font-size: 0.75rem;
}
.palette-kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.375rem;
  padding: 0 0.3125rem;
  border: 1px solid var(--ui-border-accented);
  border-radius: 0.25rem;
  background: var(--ui-bg-muted);
  color: var(--ui-text-toned);
  font: 600 0.6875rem/1.25rem var(--font-sans);
}
</style>
