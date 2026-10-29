<script setup lang="ts">
import type { Station } from '#shared/types/api'

// The search of the whole app (GH-3518): the pages, each with what it is for; the appearance and the language; and
// the places a forecast is made for. Opened by the search button of the header, the search field of the home page,
// and Ctrl+K (⌘K on a Mac) on every page.
//
// It is the ARIA combobox pattern with a listbox popup (WAI-ARIA APG, "editable combobox with list autocomplete"):
// the focus stays in the field, the arrow keys move the option that `aria-activedescendant` names, Enter takes it.
// The dialog around it (Reka's, through UModal) keeps the focus inside it, closes on Escape and gives the focus back
// to what had it. Written for the app rather than Nuxt UI's UCommandPalette, which puts its search field inside the
// element with `role="listbox"`, the violation the station picker already has (ACCESSIBILITY.md).

const { open } = usePalette()
const { t, locale, setLocale } = useI18n()
const colorMode = useColorMode()
const router = useRouter()
const { pages } = useSiteNav()

const baseId = useId()
const inputId = `${baseId}-input`
const listboxId = `${baseId}-listbox`
const optionId = (index: number) => `${baseId}-option-${index}`

const input = ref<HTMLInputElement | null>(null)
const query = ref('')
const active = ref(0)

// the narrow layout takes the whole screen, where a keyboard on screen would hide half of a centred box
const wide = useMediaQuery('(min-width: 640px)')

type Group = 'pages' | 'actions' | 'places'
interface Entry {
  group: Group
  /** What the option says, in the language of the page */
  label: string
  /** A language's own name, said in that language (WCAG 3.1.2) */
  native?: { text: string, lang: string }
  /** One line under the label */
  detail: string
  icon: string
  /** More words the option is found by */
  keywords?: string
  run: () => void
}

function close() {
  open.value = false
}

function go(to: string) {
  close()
  void router.push(to)
}

const themes = computed(() => [
  { value: 'system', label: t('settings.themeSystem'), icon: 'i-lucide-monitor' },
  { value: 'light', label: t('settings.themeLight'), icon: 'i-lucide-sun' },
  { value: 'dark', label: t('settings.themeDark'), icon: 'i-lucide-moon' },
])

// a language is also found by its name in the language of the page ("German" finds Deutsch)
const languageNames = computed(() => {
  try {
    return new Intl.DisplayNames([locale.value], { type: 'language' })
  }
  catch {
    return null
  }
})

const pageEntries = computed<Entry[]>(() => pages.value.map(page => ({
  group: 'pages',
  label: page.label,
  detail: page.purpose,
  icon: page.icon,
  keywords: page.to,
  run: () => go(page.to),
})))

const actionEntries = computed<Entry[]>(() => [
  ...themes.value.map(theme => ({
    group: 'actions' as const,
    label: t('palette.themeOption', { theme: theme.label }),
    detail: colorMode.preference === theme.value ? t('palette.current') : t('palette.themeDetail'),
    icon: theme.icon,
    keywords: theme.value,
    run: () => {
      colorMode.preference = theme.value
      close()
    },
  })),
  ...LANGUAGES.map(language => ({
    group: 'actions' as const,
    label: t('palette.languageOption', { language: language.name }),
    // Hamburgisch is German as Hamburg speaks it (the locale's language is de-DE, nuxt.config.ts)
    native: { text: language.name, lang: language.value === 'de-hh' ? 'de' : language.value },
    detail: locale.value === language.value ? t('palette.current') : t('palette.languageDetail'),
    icon: 'i-lucide-languages',
    keywords: `${language.value} ${languageNames.value?.of(language.value.split('-')[0]!) ?? ''}`,
    run: () => {
      close()
      void setLocale(language.value as typeof locale.value)
    },
  })),
])

// The places: the stations of the DWD's MOSMIX forecast, the list the forecast page searches, asked for once, when a
// query is long enough to search it, and kept for the visit.
const MIN_PLACE_QUERY = 2
const MAX_PLACES = 8
const stations = useState<Station[] | null>('command-palette-stations', () => null)
const placesState = ref<'idle' | 'loading' | 'failed'>('idle')

async function loadPlaces() {
  if (stations.value || placesState.value === 'loading')
    return
  placesState.value = 'loading'
  try {
    const answer = await $fetch<{ stations: Station[] }>('/api/stations', {
      query: { provider: 'dwd', network: 'mosmix', parameters: 'hourly/large', all: 'true' },
      ...RETRY_TRANSIENT,
    })
    stations.value = answer.stations ?? []
    placesState.value = 'idle'
  }
  catch {
    placesState.value = 'failed'
  }
}

const words = computed(() => searchable(query.value).split(/\s+/).filter(Boolean))

watch(words, (current) => {
  if (current.join(' ').length >= MIN_PLACE_QUERY)
    void loadPlaces()
})

const placeEntries = computed<Entry[]>(() => {
  const wanted = words.value
  if (wanted.join(' ').length < MIN_PLACE_QUERY || !stations.value)
    return []
  const found: Array<{ station: Station, rank: number }> = []
  for (const station of stations.value) {
    if (!station.name)
      continue
    const name = searchable(station.name)
    const haystack = `${name} ${station.station_id}`
    if (!wanted.every(word => haystack.includes(word)))
      continue
    found.push({ station, rank: name.startsWith(wanted[0]!) || station.station_id === wanted[0] ? 0 : 1 })
  }
  return found
    .sort((a, b) => a.rank - b.rank || a.station.name!.localeCompare(b.station.name!))
    .slice(0, MAX_PLACES)
    .map(({ station }) => ({
      group: 'places' as const,
      label: station.name!,
      detail: t('palette.placeDetail', { id: station.station_id }),
      icon: 'i-lucide-map-pin',
      run: () => go(`/meteogram?station=${encodeURIComponent(station.station_id)}`),
    }))
})

/** How well an entry matches: every word of the query is in it; one whose label starts with the query comes first */
function rank(entry: Entry): number {
  const wanted = words.value
  if (!wanted.length)
    return 1
  const label = searchable(entry.label)
  const haystack = `${label} ${searchable(entry.detail)} ${searchable(entry.keywords ?? '')}`
  if (!wanted.every(word => haystack.includes(word)))
    return 0
  if (label.startsWith(wanted.join(' ')))
    return 3
  return wanted.every(word => label.includes(word)) ? 2 : 1
}

function matching(entries: Entry[]): Entry[] {
  return entries
    .map(entry => ({ entry, score: rank(entry) }))
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score)
    .map(({ entry }) => entry)
}

const groups = computed(() => [
  { key: 'pages' as const, label: t('palette.groupPages'), entries: matching(pageEntries.value) },
  { key: 'actions' as const, label: t('palette.groupActions'), entries: matching(actionEntries.value) },
  { key: 'places' as const, label: t('palette.groupPlaces'), entries: placeEntries.value },
].filter(group => group.entries.length))

/** The options in the order the arrow keys walk them, each with its index */
const flat = computed(() => groups.value.flatMap(group => group.entries))
const indexed = computed(() => {
  let index = 0
  return groups.value.map(group => ({ ...group, entries: group.entries.map(entry => ({ entry, index: index++ })) }))
})

const placesSearched = computed(() => words.value.join(' ').length >= MIN_PLACE_QUERY)

// what a screen reader is told as the list changes: the count, or that there is nothing (WCAG 4.1.3)
const status = computed(() => {
  if (!query.value.trim())
    return ''
  if (placesSearched.value && placesState.value === 'loading')
    return t('palette.placesLoading')
  return flat.value.length ? t('palette.results', { count: flat.value.length }) : t('palette.noResults')
})

watch(query, () => {
  active.value = 0
})

// the option the keys move to is scrolled into the list's view
watch(active, async (index) => {
  await nextTick()
  document.getElementById(optionId(index))?.scrollIntoView({ block: 'nearest' })
})

watch(open, (isOpen) => {
  if (isOpen) {
    query.value = ''
    active.value = 0
  }
})

function move(step: number) {
  const count = flat.value.length
  if (!count)
    return
  active.value = (active.value + step + count) % count
}

function onKeydown(event: KeyboardEvent) {
  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      move(1)
      break
    case 'ArrowUp':
      event.preventDefault()
      move(-1)
      break
    case 'PageDown':
      event.preventDefault()
      active.value = Math.max(0, Math.min(active.value + 5, flat.value.length - 1))
      break
    case 'PageUp':
      event.preventDefault()
      active.value = Math.max(0, active.value - 5)
      break
    case 'Enter': {
      const entry = flat.value[active.value]
      if (entry) {
        event.preventDefault()
        entry.run()
      }
      break
    }
  }
}

// the field takes the focus when the dialog opens, not the dialog's close button, which comes first in its order
function focusInput(event: Event) {
  event.preventDefault()
  input.value?.focus()
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('palette.title')"
    :description="t('palette.description')"
    :fullscreen="!wide"
    :content="{ onOpenAutoFocus: focusInput }"
    :ui="{
      content: wide ? 'max-w-2xl sm:top-[10dvh] sm:translate-y-0 sm:max-h-[80dvh]' : '',
      header: 'pb-0 sm:pb-0 border-0',
      body: 'p-0 sm:p-0 flex flex-col min-h-0',
      description: 'sr-only',
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
      <div class="px-4 sm:px-6 pt-3 pb-4">
        <label :for="inputId" class="block font-semibold mb-1.5">
          {{ t('palette.label') }}
        </label>
        <div class="relative">
          <UIcon name="i-lucide-search" class="absolute start-3 top-1/2 -translate-y-1/2 size-5 text-muted pointer-events-none" />
          <input
            :id="inputId"
            ref="input"
            v-model="query"
            type="text"
            role="combobox"
            autocomplete="off"
            autocapitalize="off"
            spellcheck="false"
            aria-autocomplete="list"
            :aria-expanded="flat.length > 0"
            :aria-controls="flat.length ? listboxId : undefined"
            :aria-activedescendant="flat.length ? optionId(active) : undefined"
            :aria-describedby="`${baseId}-hint`"
            class="w-full rounded-md border-2 border-(--ui-border-accented) bg-default ps-11 pe-3 py-3 text-lg text-highlighted placeholder:text-dimmed"
            :placeholder="t('palette.placeholder')"
            @keydown="onKeydown"
          >
        </div>
      </div>

      <!-- the list scrolls in its own box, which the keyboard reaches too (WCAG 2.1.1): the arrow keys in the field move
           through the options and scroll them into view, and Tab to the box lets the keys scroll it as it is -->
      <div class="app-inset-focus flex-1 min-h-0 overflow-y-auto border-t border-default" tabindex="0" data-testid="palette-results">
        <div
          v-if="flat.length"
          :id="listboxId"
          role="listbox"
          :aria-label="t('palette.resultsLabel')"
          class="py-2"
        >
          <div
            v-for="group in indexed"
            :key="group.key"
            role="group"
            :aria-labelledby="`${baseId}-group-${group.key}`"
            class="pb-2"
          >
            <div :id="`${baseId}-group-${group.key}`" role="presentation" class="px-4 sm:px-6 pt-2 pb-1 text-sm font-bold text-muted">
              {{ group.label }}
            </div>
            <div
              v-for="{ entry, index } in group.entries"
              :id="optionId(index)"
              :key="index"
              role="option"
              :aria-selected="index === active"
              class="flex items-start gap-3 px-4 sm:px-6 py-2.5 cursor-pointer"
              :class="index === active
                ? 'bg-brand-50 dark:bg-ink-800 shadow-[inset_4px_0_0_var(--ui-primary)]'
                : ''"
              @mousedown.prevent
              @mousemove="active = index"
              @click="entry.run()"
            >
              <UIcon :name="entry.icon" class="size-5 shrink-0 mt-0.5 text-toned" />
              <span class="min-w-0 flex-1">
                <span v-if="entry.native" class="block font-semibold text-highlighted break-words">
                  <i18n-t keypath="palette.languageOption" tag="span" scope="global">
                    <template #language>
                      <span :lang="entry.native.lang">{{ entry.native.text }}</span>
                    </template>
                  </i18n-t>
                </span>
                <span v-else class="block font-semibold text-highlighted break-words">{{ entry.label }}</span>
                <span class="block text-sm text-muted break-words">{{ entry.detail }}</span>
              </span>
              <UIcon v-if="index === active" name="i-lucide-corner-down-left" class="size-4 shrink-0 mt-1 text-toned" />
            </div>
          </div>
        </div>
        <p v-else-if="query.trim()" class="px-4 sm:px-6 py-6 text-muted">
          {{ placesSearched && placesState === 'loading' ? t('palette.placesLoading') : t('palette.noResults') }}
        </p>
        <p v-if="placesSearched && placesState === 'failed'" class="px-4 sm:px-6 pb-4 text-sm text-error">
          {{ t('palette.placesFailed') }}
        </p>
      </div>

      <p :id="`${baseId}-hint`" class="px-4 sm:px-6 py-3 border-t border-default text-sm text-muted">
        {{ t('palette.hint') }}
      </p>
      <p class="sr-only" role="status" aria-live="polite">
        {{ status }}
      </p>
    </template>
  </UModal>
</template>
