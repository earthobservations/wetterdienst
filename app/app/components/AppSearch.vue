<script setup lang="ts">
import type { Station } from '#shared/types/api'

// The search of the app (GH-3518): a dialog with one field that finds the pages, the two settings that act at once
// (appearance and language) and the forecast stations, whose forecast it opens. Opened by the search button of the
// rail and by Ctrl+K / ⌘K (app.vue).
//
// The ARIA pattern is a combobox with a listbox popup (WAI-ARIA APG, "editable combobox with list autocomplete"): the
// focus stays in the field, the arrow keys move the active option (`aria-activedescendant`), Enter runs it, Escape
// closes the dialog. The dialog is Nuxt UI's (Reka's): it keeps the focus, and gives it back to what had it before.
// Not Nuxt UI's command palette: its field is no combobox (no role, no `aria-controls`, no `aria-expanded`).
const open = defineModel<boolean>('open', { default: false })

const { t, locale, setLocale } = useI18n()
const colorMode = useColorMode()
const route = useRoute()
const router = useRouter()

type Group = 'pages' | 'appearance' | 'language' | 'stations'
type Tile = 'sun' | 'rain' | 'wind' | 'temperature'
interface Entry {
  id: string
  group: Group
  label: string
  description?: string
  icon?: string
  tile?: Tile
  /** an emoji in place of the icon, hidden from assistive technology */
  glyph?: string
  /** the language the label is in, where it is not the page's (a language's own name) */
  lang?: string
  /** the page the reader is on, the appearance and the language in use */
  current?: boolean
  run: () => void | Promise<unknown>
}

const query = ref('')
const activeIndex = ref(0)
const field = ref<HTMLInputElement | null>(null)
const listId = useId()
const optionId = (entry: Entry) => `${listId}-${entry.id}`

/** Lower case, the German umlauts spelled out (MOSMIX writes MUENCHEN) and every other accent dropped */
function fold(text: string): string {
  return text.toLowerCase()
    .replaceAll('ä', 'ae')
    .replaceAll('ö', 'oe')
    .replaceAll('ü', 'ue')
    .replaceAll('ß', 'ss')
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
}
const words = computed(() => fold(query.value).split(/[\s,()]+/).filter(Boolean))
function matches(...texts: Array<string | null | undefined>): boolean {
  const haystack = fold(texts.filter(Boolean).join(' '))
  return words.value.every(word => haystack.includes(word))
}

function go(path: string) {
  return router.push(path)
}

// the pages, each with the line that says what it is for (its subtitle, where it has one)
const pages = computed<Entry[]>(() => [
  { id: 'home', path: '/', label: t('nav.home'), description: t('home.tagline'), icon: 'i-lucide-house' },
  { id: 'meteogram', path: '/meteogram', label: t('nav.meteogram'), description: t('meteogram.subtitle'), icon: 'i-lucide-sun', tile: 'sun' as Tile },
  { id: 'stripes', path: '/stripes', label: t('nav.stripes'), description: t('stripes.subtitle'), icon: 'i-lucide-thermometer', tile: 'temperature' as Tile },
  { id: 'explorer', path: '/explorer', label: t('nav.explorer'), description: t('explorer.subtitle'), icon: 'i-lucide-droplets', tile: 'rain' as Tile },
  { id: 'history', path: '/history', label: t('nav.history'), description: t('history.subtitle'), icon: 'i-lucide-wind', tile: 'wind' as Tile },
  { id: 'providers', path: '/providers', label: t('nav.providers'), description: t('providers.subtitle'), icon: 'i-lucide-building-2' },
  { id: 'glossary', path: '/glossary', label: t('nav.glossary'), description: t('glossary.subtitle'), icon: 'i-lucide-book-open' },
  { id: 'api', path: '/api', label: t('nav.api'), description: t('api.subtitle'), icon: 'i-lucide-code' },
  { id: 'settings', path: '/settings', label: t('settings.title'), description: t('settings.subtitle'), icon: 'i-lucide-settings-2' },
  { id: 'about', path: '/about', label: t('footer.about'), description: t('about.subtitle'), icon: 'i-lucide-info' },
  { id: 'support', path: '/support', label: t('nav.support'), description: t('seo.pages.support'), icon: 'i-lucide-heart' },
  { id: 'impressum', path: '/impressum', label: t('footer.legal'), description: t('palette.purposeLegal'), icon: 'i-lucide-scale' },
  { id: 'datenschutz', path: '/datenschutz', label: t('footer.privacy'), description: t('palette.purposePrivacy'), icon: 'i-lucide-shield' },
].map(({ path, ...page }) => ({
  ...page,
  group: 'pages' as Group,
  current: path === '/' ? route.path === '/' : route.path.startsWith(path),
  run: () => go(path),
})))

const appearance = computed<Entry[]>(() => [
  { value: 'system', label: t('settings.themeSystem'), icon: 'i-lucide-monitor' },
  { value: 'light', label: t('settings.themeLight'), icon: 'i-lucide-sun-medium' },
  { value: 'dark', label: t('settings.themeDark'), icon: 'i-lucide-moon' },
].map(option => ({
  id: `appearance-${option.value}`,
  group: 'appearance' as Group,
  label: option.label,
  description: t('settings.theme'),
  icon: option.icon,
  current: colorMode.preference === option.value,
  run: () => {
    colorMode.preference = option.value
  },
})))

const languages = computed<Entry[]>(() => LANGUAGES.map(language => ({
  id: `language-${language.value}`,
  group: 'language' as Group,
  label: language.name,
  description: t('settings.language'),
  glyph: language.flag,
  // Hamburgisch is Low German, whose tag is nds
  lang: language.value === 'de-hh' ? 'nds' : language.value,
  current: locale.value === language.value,
  run: () => setLocale(language.value as typeof locale.value),
})))

// The forecast stations, the ones the forecast page offers (the same request, `/api/stations` of dwd/mosmix), asked
// for the first time the dialog opens. A station is looked for from the second letter on, and only the first few are
// shown: a list of five thousand is no answer.
const STATION_LIMIT = 8
const { data: stationData, status: stationStatus, execute: loadStations } = useFetch<{ stations: Station[] }>('/api/stations', {
  query: { provider: 'dwd', network: 'mosmix', parameters: 'hourly/large', all: 'true' },
  immediate: false,
  server: false,
  default: () => ({ stations: [] }),
})
watch(open, (isOpen) => {
  if (isOpen && stationStatus.value === 'idle')
    loadStations()
})
const searchingStations = computed(() => words.value.join('').length >= 2)
const stations = computed<Entry[]>(() => {
  if (!searchingStations.value)
    return []
  // a name that begins with what was typed comes before one that only holds it (BERLIN-DAHLEM before DOBERLUG)
  const first = words.value[0] ?? ''
  const found = (stationData.value?.stations ?? [])
    .filter(station => matches(station.name, station.station_id))
    .map(station => ({ station, rank: fold(station.name ?? '').startsWith(first) || station.station_id.startsWith(first) ? 0 : 1 }))
    .sort((a, b) => a.rank - b.rank)
    .slice(0, STATION_LIMIT)
  return found.map(({ station }): Entry => ({
    id: `station-${station.station_id}`,
    group: 'stations',
    label: station.name ?? station.station_id,
    description: `${t('palette.openForecast')} · ${station.station_id}`,
    icon: 'i-lucide-map-pin',
    run: () => go(`/meteogram?station=${encodeURIComponent(station.station_id)}`),
  }))
})
const stationsLoading = computed(() => searchingStations.value && stationStatus.value === 'pending')

const groups = computed(() => {
  const all: Array<{ key: Group, label: string, entries: Entry[] }> = [
    { key: 'pages', label: t('palette.pages'), entries: pages.value.filter(entry => matches(entry.label, entry.description)) },
    { key: 'appearance', label: t('settings.theme'), entries: appearance.value.filter(entry => matches(entry.label, entry.description)) },
    { key: 'language', label: t('settings.language'), entries: languages.value.filter(entry => matches(entry.label, entry.description, entry.lang)) },
    { key: 'stations', label: t('palette.stations'), entries: stations.value },
  ]
  return all.filter(group => group.entries.length)
})
const entries = computed(() => groups.value.flatMap(group => group.entries))
const active = computed(() => entries.value[activeIndex.value])

watch(query, () => {
  activeIndex.value = 0
})
watch(open, (isOpen) => {
  if (isOpen) {
    query.value = ''
    activeIndex.value = 0
  }
})
// the active option is kept in view as the arrow keys move it (the field above it stays: scroll-padding)
watch(active, (entry) => {
  if (!entry || !import.meta.client)
    return
  nextTick(() => document.getElementById(optionId(entry))?.scrollIntoView({ block: 'nearest' }))
})

function move(step: number) {
  const count = entries.value.length
  if (count)
    activeIndex.value = (activeIndex.value + step + count) % count
}

async function run(entry: Entry | undefined) {
  if (!entry)
    return
  open.value = false
  await entry.run()
}

// the dialog would put the focus on its first control, the close button: the field is where the reader types
function focusField(event: Event) {
  event.preventDefault()
  field.value?.focus()
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
  else if (event.key === 'Enter') {
    event.preventDefault()
    run(active.value)
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    :content="{ onOpenAutoFocus: focusField }"
    :title="t('palette.title')"
    :description="t('palette.hint')"
    :ui="{
      content: 'sm:max-w-2xl',
      header: 'px-4 py-3 sm:px-5 bg-muted/60',
      description: 'text-xs',
      body: 'p-0 sm:p-0 scroll-pt-16',
    }"
  >
    <!-- the label in the language of the app, which Nuxt UI's own is only for the two it ships -->
    <template #close="{ ui }">
      <UButton
        icon="i-lucide-x"
        color="neutral"
        variant="ghost"
        :aria-label="t('common.close')"
        :class="ui.close()"
      />
    </template>
    <template #body>
      <div class="sticky top-0 z-10 flex items-center gap-3 border-b border-default bg-default px-4 py-2 sm:px-5">
        <UIcon name="i-lucide-search" class="size-5 shrink-0 text-muted" aria-hidden="true" />
        <input
          ref="field"
          v-model="query"
          type="text"
          role="combobox"
          aria-autocomplete="list"
          :aria-label="t('palette.title')"
          :aria-expanded="entries.length > 0"
          :aria-controls="entries.length ? listId : undefined"
          :aria-activedescendant="active ? optionId(active) : undefined"
          :placeholder="t('palette.placeholder')"
          autocomplete="off"
          spellcheck="false"
          class="min-h-10 w-full min-w-0 rounded-sm bg-transparent px-1 text-base text-highlighted placeholder:text-dimmed"
          @keydown="onKeydown"
        >
      </div>

      <div
        v-if="entries.length"
        :id="listId"
        role="listbox"
        :aria-label="t('palette.title')"
        class="px-2 py-2"
      >
        <div
          v-for="group in groups"
          :key="group.key"
          role="group"
          :aria-labelledby="`${listId}-${group.key}`"
          class="pb-2"
        >
          <div :id="`${listId}-${group.key}`" role="presentation" class="px-3 pb-1 pt-2 text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-muted">
            {{ group.label }}
          </div>
          <div
            v-for="entry in group.entries"
            :id="optionId(entry)"
            :key="entry.id"
            role="option"
            :aria-selected="active?.id === entry.id"
            class="flex min-h-11 cursor-pointer items-center gap-3 rounded-md border-l-[3px] px-3 py-1.5"
            :class="active?.id === entry.id ? 'border-primary bg-primary/10' : 'border-transparent'"
            @mousedown.prevent
            @mousemove="activeIndex = entries.indexOf(entry)"
            @click="run(entry)"
          >
            <span
              class="app-tile size-7"
              :class="entry.tile ? `app-tile--${entry.tile}` : 'app-tile--plain text-muted'"
              aria-hidden="true"
            >
              <span v-if="entry.glyph" class="text-sm leading-none">{{ entry.glyph }}</span>
              <UIcon v-else-if="entry.icon" :name="entry.icon" class="size-4" />
            </span>
            <span class="min-w-0 flex-1">
              <span class="block font-medium text-highlighted" :lang="entry.lang">{{ entry.label }}</span>
              <span v-if="entry.description" class="block text-sm text-muted">{{ entry.description }}</span>
            </span>
            <span v-if="entry.current" class="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-primary">
              <UIcon name="i-lucide-check" class="size-4" aria-hidden="true" />
              {{ t('palette.current') }}
            </span>
          </div>
        </div>
      </div>

      <p v-else-if="!stationsLoading" class="px-5 py-10 text-center text-sm text-muted">
        {{ t('palette.empty') }}
      </p>

      <p v-if="stationsLoading" class="flex items-center gap-2 px-5 pb-4 text-sm text-muted">
        <UIcon name="i-lucide-loader-circle" class="size-4 animate-spin" aria-hidden="true" />
        {{ t('common.loading') }}
      </p>

      <!-- what the list holds now, for a screen reader, which is not told when the options change -->
      <p role="status" class="sr-only">
        {{ t('palette.results', { count: entries.length }) }}
      </p>
    </template>
  </UModal>
</template>
