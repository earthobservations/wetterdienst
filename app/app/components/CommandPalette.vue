<script setup lang="ts">
import type { Station } from '#shared/types/api'

// The app's search (GH-3518): the pages, each with what it is for, the appearance and the language, and the forecast
// stations, in one dialog opened by the search button of the rail (or of the narrow layout's bar) and by Ctrl+K / ⌘K.
//
// Built here rather than on Nuxt UI's UCommandPalette, whose field is no combobox and whose list has no name. It is
// the ARIA combobox pattern with a list box: the focus stays in the field, the arrow keys move the option that is
// active (`aria-activedescendant`), Enter takes it. The dialog (Nuxt UI's modal, Reka's dialog) keeps the focus in
// itself, closes on Escape and gives the focus back to what had it before.

const { t, locale, setLocale } = useI18n()
const colorMode = useColorMode()
const { open } = useCommandPalette()

const query = ref('')
const active = ref(0)
const input = ref<HTMLInputElement | null>(null)
const listId = useId()
const optionId = (index: number) => `${listId}-option-${index}`

type Tile = 'sun' | 'rain' | 'wind' | 'heat'
interface Option {
  key: string
  label: string
  description?: string
  icon: string
  tile?: Tile
  /** A language's own name, and the language it is in, which is not the page's (WCAG 3.1.2) */
  languageName?: string
  lang?: string
  current?: boolean
  run: () => unknown
}
interface Group { key: string, label: string, options: Option[] }

function go(to: string) {
  open.value = false
  return navigateTo(to)
}

// The pages, in the rail's order, each with a line that says what it is for
const PAGES: { path: string, key: string, label: string, icon: string, tile?: Tile }[] = [
  { path: '/', key: 'home', label: 'nav.home', icon: 'i-lucide-house' },
  { path: '/meteogram', key: 'meteogram', label: 'nav.meteogram', icon: 'i-lucide-sun', tile: 'sun' },
  { path: '/explorer', key: 'explorer', label: 'nav.explorer', icon: 'i-lucide-compass', tile: 'rain' },
  { path: '/history', key: 'history', label: 'nav.history', icon: 'i-lucide-history', tile: 'wind' },
  { path: '/stripes', key: 'stripes', label: 'nav.stripes', icon: 'i-lucide-thermometer', tile: 'heat' },
  { path: '/providers', key: 'providers', label: 'nav.providers', icon: 'i-lucide-building-2' },
  { path: '/glossary', key: 'glossary', label: 'nav.glossary', icon: 'i-lucide-book-a' },
  { path: '/api', key: 'api', label: 'nav.api', icon: 'i-lucide-code' },
  { path: '/settings', key: 'settings', label: 'common.settings', icon: 'i-lucide-settings-2' },
  { path: '/about', key: 'about', label: 'footer.about', icon: 'i-lucide-info' },
  { path: '/support', key: 'support', label: 'nav.support', icon: 'i-lucide-heart' },
  { path: '/impressum', key: 'impressum', label: 'footer.legal', icon: 'i-lucide-scale' },
  { path: '/datenschutz', key: 'datenschutz', label: 'footer.privacy', icon: 'i-lucide-shield' },
]

const THEMES = [
  { value: 'light', label: 'settings.themeLight', icon: 'i-lucide-sun' },
  { value: 'dark', label: 'settings.themeDark', icon: 'i-lucide-moon' },
  { value: 'system', label: 'settings.themeSystem', icon: 'i-lucide-monitor' },
]

// The forecast stations (DWD MOSMIX), asked for once, the first time the dialog opens: the list the forecast page's
// own picker reads, from the same endpoint
const stations = shallowRef<Station[] | null>(null)
const stationsStatus = ref<'idle' | 'pending' | 'error' | 'success'>('idle')
async function loadStations() {
  if (stationsStatus.value === 'pending' || stationsStatus.value === 'success')
    return
  stationsStatus.value = 'pending'
  try {
    const answer = await $fetch<{ stations: Station[] }>('/api/stations', {
      query: { provider: 'dwd', network: 'mosmix', parameters: 'hourly/large', all: 'true' },
      ...RETRY_TRANSIENT,
    })
    stations.value = answer.stations ?? []
    stationsStatus.value = 'success'
  }
  catch {
    stationsStatus.value = 'error'
  }
}

const groups = computed<Group[]>(() => {
  const words = queryWords(query.value)
  const pages: Option[] = PAGES.map(page => ({
    key: `page:${page.path}`,
    label: t(page.label),
    description: t(`palette.pages.${page.key}`),
    icon: page.icon,
    tile: page.tile,
    run: () => go(page.path),
  })).filter(option => matchesQuery(words, option.label, option.description, option.key))

  const themes: Option[] = THEMES.map(theme => ({
    key: `theme:${theme.value}`,
    label: t('palette.themeAction', { theme: t(theme.label) }),
    icon: theme.icon,
    current: colorMode.preference === theme.value,
    run: () => {
      colorMode.preference = theme.value
      open.value = false
    },
  }))
  const languages: Option[] = LANGUAGES.map(language => ({
    key: `language:${language.value}`,
    label: t('palette.languageAction', { language: language.name }),
    languageName: language.name,
    // the name of each language is in that language; Hamburgisch is a German word
    lang: language.value === 'de-hh' ? 'de' : language.value,
    icon: 'i-lucide-languages',
    current: locale.value === language.value,
    run: async () => {
      open.value = false
      await setLocale(language.value as typeof locale.value)
    },
  }))
  // with nothing typed the actions are the appearance; a language is found by its name or the word for "language"
  const actions = words.length
    ? [...themes, ...languages].filter(option => matchesQuery(words, option.label, option.key))
    : themes

  const found: Option[] = findStations(stations.value ?? [], query.value).map(station => ({
    key: `station:${station.station_id}`,
    label: station.name ?? station.station_id,
    description: [station.region, station.station_id].filter(Boolean).join(' · '),
    icon: 'i-lucide-map-pin',
    tile: 'sun' as Tile,
    run: () => go(`/meteogram?station=${encodeURIComponent(station.station_id)}`),
  }))

  return [
    { key: 'pages', label: t('palette.groupPages'), options: pages },
    { key: 'actions', label: t('palette.groupActions'), options: actions },
    { key: 'stations', label: t('palette.groupStations'), options: found },
  ].filter(group => group.options.length)
})

// The options in the order of the list, each with its index across the groups
const flat = computed(() => groups.value.flatMap(group => group.options))
const indexed = computed(() => {
  let index = 0
  return groups.value.map(group => ({ ...group, options: group.options.map(option => ({ option, index: index++ })) }))
})

const stationsNote = computed(() => {
  if (queryWords(query.value).join(' ').length < STATION_QUERY_MIN)
    return t('palette.stationsHint')
  if (stationsStatus.value === 'pending')
    return t('palette.stationsLoading')
  if (stationsStatus.value === 'error')
    return t('palette.stationsFailed')
  return ''
})

// what a screen reader is told after the list has changed: how many results there are, once the typing has paused
const announced = ref('')
watchDebounced(() => [open.value, flat.value.length], () => {
  announced.value = open.value ? t('palette.resultCount', { count: flat.value.length }) : ''
}, { debounce: 400 })

watch(query, () => {
  active.value = 0
})
watch(open, (isOpen) => {
  if (isOpen) {
    query.value = ''
    active.value = 0
    void loadStations()
  }
})

function scrollToActive() {
  void nextTick(() => document.getElementById(optionId(active.value))?.scrollIntoView({ block: 'nearest' }))
}

function onKeydown(event: KeyboardEvent) {
  const count = flat.value.length
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    if (!count)
      return
    active.value = (active.value + (event.key === 'ArrowDown' ? 1 : count - 1)) % count
    scrollToActive()
  }
  else if (event.key === 'PageDown' || event.key === 'PageUp') {
    event.preventDefault()
    if (!count)
      return
    active.value = event.key === 'PageDown' ? Math.min(count - 1, active.value + 5) : Math.max(0, active.value - 5)
    scrollToActive()
  }
  else if (event.key === 'Enter') {
    event.preventDefault()
    // a key held down past the dialog's opening, or an IME's confirmation, is no choice
    if (event.isComposing)
      return
    void flat.value[active.value]?.run()
  }
}

// Ctrl+K, and ⌘K on an Apple system, from anywhere in the app; again while it is open, it closes
useEventListener(window, 'keydown', (event: KeyboardEvent) => {
  if (event.key.toLowerCase() !== 'k' || event.altKey || event.shiftKey || !(event.ctrlKey || event.metaKey))
    return
  event.preventDefault()
  open.value = !open.value
})

// the field takes the focus when the dialog opens, not the dialog's first button (its close button)
const contentProps = {
  onOpenAutoFocus: (event: Event) => {
    event.preventDefault()
    input.value?.focus()
  },
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('palette.title')"
    :description="t('palette.hint')"
    :content="contentProps"
    :ui="{
      content: 'sm:max-w-2xl sm:top-[12vh] sm:translate-y-0',
      header: 'px-4 sm:px-5 py-3 min-h-0',
      title: 'text-base',
      description: 'text-xs',
      body: 'p-0 sm:p-0',
    }"
  >
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
      <!-- one box scrolls, the field at its top and the list under it: what scrolls holds what takes the focus -->
      <div class="max-h-[min(30rem,65dvh)] overflow-y-auto overscroll-contain">
        <div class="sticky top-0 z-10 bg-default border-b border-default px-4 sm:px-5 py-3">
          <div class="relative">
            <UIcon name="i-lucide-search" class="absolute start-3 top-1/2 -translate-y-1/2 size-5 text-muted" aria-hidden="true" />
            <input
              ref="input"
              v-model="query"
              type="text"
              role="combobox"
              autocomplete="off"
              autocapitalize="off"
              spellcheck="false"
              enterkeyhint="go"
              aria-autocomplete="list"
              :aria-label="t('palette.label')"
              :aria-expanded="flat.length > 0"
              :aria-controls="listId"
              :aria-activedescendant="flat.length ? optionId(active) : undefined"
              :placeholder="t('palette.placeholder')"
              class="palette-field w-full rounded-lg border border-accented bg-default ps-11 pe-3 py-2.5 text-base text-highlighted placeholder:text-dimmed"
              @keydown="onKeydown"
            >
          </div>
        </div>

        <div v-if="flat.length" :id="listId" role="listbox" :aria-label="t('palette.results')" class="p-2">
          <div
            v-for="group in indexed"
            :key="group.key"
            role="group"
            :aria-labelledby="`${listId}-${group.key}`"
            class="mb-1"
          >
            <div :id="`${listId}-${group.key}`" role="presentation" class="px-3 pt-3 pb-1 text-xs font-bold uppercase tracking-wider text-muted">
              {{ group.label }}
            </div>
            <div
              v-for="{ option, index } in group.options"
              :id="optionId(index)"
              :key="option.key"
              role="option"
              :aria-selected="index === active"
              class="palette-option"
              @click="option.run()"
              @pointermove="active = index"
            >
              <span class="app-tile" :data-tile="option.tile" aria-hidden="true">
                <UIcon :name="option.icon" class="size-4" />
              </span>
              <span class="min-w-0 flex-1">
                <span class="block font-medium text-highlighted break-words">
                  <i18n-t v-if="option.lang" keypath="palette.languageAction" tag="span" scope="global">
                    <template #language>
                      <span :lang="option.lang">{{ option.languageName }}</span>
                    </template>
                  </i18n-t>
                  <template v-else>{{ option.label }}</template>
                </span>
                <!-- a pause between the name and the line under it, which the option's accessible name runs together -->
                <span v-if="option.description" class="sr-only">, </span>
                <span v-if="option.description" class="block text-sm text-muted break-words">{{ option.description }}</span>
              </span>
              <span v-if="option.current" class="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                {{ t('palette.current') }}
              </span>
            </div>
          </div>
        </div>
        <p v-else class="px-5 py-6 text-muted">
          {{ t('palette.empty') }}
        </p>

        <p v-if="stationsNote" class="px-5 pb-4 pt-1 text-sm text-muted">
          {{ stationsNote }}
        </p>
      </div>
      <p role="status" class="sr-only">
        {{ announced }}
      </p>
    </template>
  </UModal>
</template>

<style scoped>
/* the field's own focus is the dialog's: the app's ring (main.css) around it */
.palette-option {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-height: 2.75rem;
  padding: 0.5rem 0.75rem 0.5rem calc(0.75rem - 3px);
  border-inline-start: 3px solid transparent;
  border-radius: 0 var(--ui-radius) var(--ui-radius) 0;
  cursor: pointer;
  scroll-margin-top: 5rem;
  scroll-margin-bottom: 0.5rem;
}
/* the active option: a tint and the bar of the rail's current page (a border, which forced colours keep) */
.palette-option[aria-selected='true'] {
  background: var(--ui-bg-elevated);
  border-inline-start-color: var(--ui-primary);
}
.palette-option .app-tile:not([data-tile]) {
  background: var(--ui-bg-accented);
}
@media (forced-colors: active) {
  .palette-option {
    border-inline-start-color: Canvas;
  }
  .palette-option[aria-selected='true'] {
    border-inline-start-color: Highlight;
    outline: 1px solid Highlight;
  }
}
</style>
