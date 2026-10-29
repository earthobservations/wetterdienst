<script setup lang="ts">
import type { Station } from '#shared/types/api'
import type { Place } from '~/composables/usePlace'
import { useDebounceFn, useEventListener } from '@vueuse/core'
import { PLACE_NETWORK, placeOf } from '~/composables/usePlace'
import { languageSelectItems } from '~/utils/languages'
import { QUESTIONS } from '~/utils/questions'

// The command palette: one field that finds the pages, the questions, the settings of appearance and language, and
// the places (DWD's stations, by `GET /api/stations?name=`) to ask about. Opened by the search button of the header,
// by Ctrl+K or ⌘K anywhere, and by the home page's place button.
//
// It is the ARIA 1.2 combobox with a listbox popup: the focus stays in the field, the arrow keys move the active
// option (`aria-activedescendant`), Enter runs it, Escape closes the dialog, and the dialog (Nuxt UI's modal, Reka's
// focus scope) holds the focus while it is open and gives it back to what had it before. Not Nuxt UI's
// CommandPalette: it puts the field inside the element with `role="listbox"`, as its select menu does, which is the
// `aria-required-children` the accessibility baseline lists for that menu.
const { t, locale, setLocale } = useI18n()
const colorMode = useColorMode()
const router = useRouter()
const { open, scope } = usePalette()
const { setPlace } = usePlace()
const { questionText } = useQuestions()

interface Item {
  id: string
  group: 'questions' | 'pages' | 'places' | 'appearance' | 'language'
  label: string
  description: string
  icon: string
  /** More words it is found by */
  keywords?: string
  run: () => void | Promise<unknown>
}

const query = ref('')
const activeIndex = ref(0)
const input = ref<HTMLInputElement | null>(null)
const listId = useId()
const optionId = (index: number) => `${listId}-option-${index}`

function go(to: string | { path: string, query?: Record<string, string> }) {
  open.value = false
  return router.push(to)
}

const PAGES = [
  { key: 'ask', to: '/', icon: 'i-lucide-message-circle-question', label: 'nav.ask' },
  { key: 'meteogram', to: '/meteogram', icon: 'i-lucide-cloud-sun', label: 'nav.meteogram' },
  { key: 'stripes', to: '/stripes', icon: 'i-lucide-bar-chart-3', label: 'nav.stripes' },
  { key: 'explorer', to: '/explorer', icon: 'i-lucide-compass', label: 'nav.explorer' },
  { key: 'history', to: '/history', icon: 'i-lucide-clock', label: 'nav.history' },
  { key: 'providers', to: '/providers', icon: 'i-lucide-building-2', label: 'nav.providers' },
  { key: 'glossary', to: '/glossary', icon: 'i-lucide-book-open', label: 'nav.glossary' },
  { key: 'api', to: '/api', icon: 'i-lucide-code', label: 'nav.api' },
  { key: 'settings', to: '/settings', icon: 'i-lucide-sliders-horizontal', label: 'settings.title' },
  { key: 'about', to: '/about', icon: 'i-lucide-info', label: 'footer.about' },
  { key: 'support', to: '/support', icon: 'i-lucide-heart', label: 'nav.support' },
  { key: 'impressum', to: '/impressum', icon: 'i-lucide-scale', label: 'footer.legal' },
  { key: 'datenschutz', to: '/datenschutz', icon: 'i-lucide-shield-check', label: 'footer.privacy' },
] as const

const staticItems = computed<Item[]>(() => {
  const current = t('palette.current')
  return [
    ...QUESTIONS.map(question => ({
      id: `question-${question.id}`,
      group: 'questions' as const,
      label: questionText(question.id),
      description: t(`ask.from.${question.id}`),
      icon: question.icon,
      run: () => go({ path: '/', query: { ask: question.id } }),
    })),
    ...PAGES.map(page => ({
      id: `page-${page.key}`,
      group: 'pages' as const,
      label: t(page.label),
      description: t(`palette.pages.${page.key}`),
      icon: page.icon,
      keywords: page.to,
      run: () => go(page.to),
    })),
    ...([['system', 'i-lucide-monitor', 'settings.themeSystem'], ['light', 'i-lucide-sun', 'settings.themeLight'], ['dark', 'i-lucide-moon', 'settings.themeDark']] as const)
      .map(([mode, icon, label]) => ({
        id: `theme-${mode}`,
        group: 'appearance' as const,
        label: `${t('settings.theme')}: ${t(label)}`,
        description: colorMode.preference === mode ? current : '',
        icon,
        run: () => {
          colorMode.preference = mode
          open.value = false
        },
      })),
    ...languageSelectItems().map(language => ({
      id: `language-${language.value}`,
      group: 'language' as const,
      label: `${t('settings.language')}: ${language.label}`,
      description: language.value === locale.value ? current : '',
      icon: 'i-lucide-languages',
      keywords: language.value,
      run: async () => {
        open.value = false
        await setLocale(language.value as typeof locale.value)
      },
    })),
  ]
})

// ---------------------------------------------------------------------------------------- places, from the backend

const places = ref<Place[]>([])
const placesStatus = ref<'idle' | 'loading' | 'failed'>('idle')
let placeTurn = 0

const searchPlaces = useDebounceFn(async (text: string) => {
  const turn = ++placeTurn
  try {
    const response = await $fetch<{ stations: Station[] }>('/api/stations', { query: { ...PLACE_NETWORK, name: text }, ...RETRY_TRANSIENT })
    if (turn !== placeTurn)
      return
    // a station that stopped reporting years ago has no recent weather to ask about
    const recent = Date.now() - 2 * 365 * 86_400_000
    places.value = (response.stations ?? [])
      .filter(station => !station.end_timestamp || Date.parse(station.end_timestamp) > recent)
      .map(placeOf)
      .filter((place): place is Place => place !== null)
    placesStatus.value = 'idle'
  }
  catch {
    if (turn === placeTurn)
      placesStatus.value = 'failed'
  }
}, 250)

watch(query, (text) => {
  const trimmed = text.trim()
  if (trimmed.length < 2) {
    placeTurn++
    places.value = []
    placesStatus.value = 'idle'
    return
  }
  placesStatus.value = 'loading'
  void searchPlaces(trimmed)
})

const placeItems = computed<Item[]>(() => places.value.map(place => ({
  id: `place-${place.id}`,
  group: 'places' as const,
  label: place.name,
  description: [place.region, t('palette.askAbout')].filter(Boolean).join(' · '),
  icon: 'i-lucide-map-pin',
  run: () => {
    setPlace(place)
    return go({ path: '/', query: { place: place.id } })
  },
})))

// --------------------------------------------------------------------------------------------------- the results

/** Lower case and without accents, so that "zurich" finds "Zürich" and "muenchen" is still typed as one */
function fold(text: string): string {
  return text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
}

const results = computed<Item[]>(() => {
  const words = fold(query.value).split(/\s+/).filter(Boolean)
  const own = scope.value === 'place' ? [] : staticItems.value
  const matching = words.length
    ? own.filter((item) => {
        const haystack = fold(`${item.label} ${item.description} ${item.keywords ?? ''}`)
        return words.every(word => haystack.includes(word))
      })
    : own
  // places first once there are any: a name typed is most often a place
  return [...placeItems.value, ...matching]
})

const GROUP_LABEL = computed(() => ({
  questions: t('palette.groups.questions'),
  pages: t('palette.groups.pages'),
  places: t('palette.groups.places'),
  appearance: t('settings.theme'),
  language: t('settings.language'),
}))

const groups = computed(() => {
  const order: Item['group'][] = ['places', 'questions', 'pages', 'appearance', 'language']
  let index = 0
  const indexed = results.value.map(item => ({ item, index: index++ }))
  return order
    .map(group => ({ group, label: GROUP_LABEL.value[group], entries: indexed.filter(entry => entry.item.group === group) }))
    .filter(group => group.entries.length)
})

watch(results, () => {
  activeIndex.value = 0
})

const status = computed(() => {
  if (placesStatus.value === 'loading')
    return t('palette.searchingPlaces')
  if (placesStatus.value === 'failed')
    return t('palette.placesFailed')
  if (!results.value.length)
    return query.value.trim() ? t('palette.none') : t('palette.placeHint')
  return t('palette.results', { count: results.value.length })
})

// ------------------------------------------------------------------------------------------------- the keyboard

function move(by: number) {
  const count = results.value.length
  if (!count)
    return
  activeIndex.value = (activeIndex.value + by + count) % count
  nextTick(() => document.getElementById(optionId(activeIndex.value))?.scrollIntoView({ block: 'nearest' }))
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
  else if (event.key === 'PageDown') {
    event.preventDefault()
    move(Math.min(5, results.value.length - 1 - activeIndex.value) || 0)
  }
  else if (event.key === 'PageUp') {
    event.preventDefault()
    move(-Math.min(5, activeIndex.value))
  }
  else if (event.key === 'Enter') {
    const item = results.value[activeIndex.value]
    if (item) {
      event.preventDefault()
      void item.run()
    }
  }
}

// Ctrl+K and ⌘K, anywhere: open (or close) the palette. Not while another dialog holds the focus, which would leave
// two modal dialogs open at once.
useEventListener(document, 'keydown', (event: KeyboardEvent) => {
  if (event.key.toLowerCase() !== 'k' || !(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey)
    return
  if (!open.value && document.activeElement?.closest('[role="dialog"]'))
    return
  event.preventDefault()
  if (!open.value)
    scope.value = 'all'
  open.value = !open.value
})

watch(open, (isOpen) => {
  if (!isOpen)
    return
  query.value = ''
  activeIndex.value = 0
})

const placeholder = computed(() => scope.value === 'place' ? t('palette.placeholderPlace') : t('palette.placeholder'))
const shortcut = computed(() => import.meta.client && /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘K' : 'Ctrl K')
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('palette.title')"
    :description="t('palette.description')"
    :ui="{ content: 'sm:max-w-2xl sm:top-[10vh] sm:translate-y-0 max-h-[100dvh] sm:max-h-[80vh] flex flex-col overflow-hidden', overlay: 'bg-elevated/70 dark:bg-gray-950/70' }"
    :content="{ onOpenAutoFocus: (event: Event) => { event.preventDefault(); input?.focus() } }"
  >
    <template #content>
      <div class="flex items-center gap-2 border-b border-default px-3 sm:px-4">
        <UIcon name="i-lucide-search" class="size-5 shrink-0 text-muted" />
        <input
          ref="input"
          v-model="query"
          type="text"
          role="combobox"
          :aria-label="t('palette.inputLabel')"
          aria-autocomplete="list"
          :aria-expanded="results.length > 0"
          :aria-controls="listId"
          :aria-activedescendant="results.length ? optionId(activeIndex) : undefined"
          :placeholder="placeholder"
          autocomplete="off"
          autocapitalize="off"
          spellcheck="false"
          class="palette-input min-w-0 flex-1 bg-transparent py-4 text-base text-highlighted placeholder:text-dimmed"
          data-testid="palette-input"
          @keydown="onKeydown"
        >
        <span class="app-kbd hidden sm:inline-flex" aria-hidden="true">Esc</span>
        <UButton
          icon="i-lucide-x"
          color="neutral"
          variant="ghost"
          :aria-label="t('common.close')"
          @click="open = false"
        />
      </div>

      <div
        :id="listId"
        role="listbox"
        :aria-label="t('palette.resultsLabel')"
        class="palette-list flex-1 overflow-y-auto overscroll-contain p-2"
        :class="{ hidden: !results.length }"
      >
        <div
          v-for="group in groups"
          :key="group.group"
          role="group"
          :aria-labelledby="`${listId}-group-${group.group}`"
          class="pb-2"
        >
          <div :id="`${listId}-group-${group.group}`" role="presentation" class="px-3 pt-2 pb-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {{ group.label }}
          </div>
          <div
            v-for="entry in group.entries"
            :id="optionId(entry.index)"
            :key="entry.item.id"
            role="option"
            :aria-selected="entry.index === activeIndex"
            class="palette-option flex items-center gap-3 rounded-lg px-3 py-2 cursor-pointer"
            :data-testid="entry.item.id"
            @mousemove="activeIndex = entry.index"
            @click="entry.item.run()"
          >
            <UIcon :name="entry.item.icon" class="size-5 shrink-0 text-muted palette-option__icon" />
            <span class="min-w-0 flex-1">
              <span class="block font-medium text-highlighted break-words">{{ entry.item.label }}</span>
              <span v-if="entry.item.description" class="block text-sm text-muted break-words">{{ entry.item.description }}</span>
            </span>
            <UIcon v-if="entry.index === activeIndex" name="i-lucide-corner-down-left" class="size-4 shrink-0 text-muted" />
          </div>
        </div>
      </div>

      <div class="flex items-center justify-between gap-3 border-t border-default px-4 py-2 text-xs text-muted">
        <p role="status" data-testid="palette-status">
          {{ status }}
        </p>
        <p class="hidden sm:flex items-center gap-1.5" aria-hidden="true">
          <span class="app-kbd">↑</span><span class="app-kbd">↓</span>
          <span class="app-kbd">↵</span>
          <span class="app-kbd">{{ shortcut }}</span>
        </p>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
/* the field draws no box of its own inside the palette: the palette's edge is its edge, and the focus is shown by
   the active option and by this underline of the field, 3:1 and more against the panel */
.palette-input:focus-visible {
  outline: none;
  box-shadow: inset 0 -2px 0 var(--app-focus-ring);
}
.palette-option[aria-selected="true"] {
  background: var(--ui-color-primary-50);
  box-shadow: inset 3px 0 0 var(--ui-color-primary-700);
}
.dark .palette-option[aria-selected="true"] {
  background: color-mix(in oklab, var(--ui-color-primary-300) 16%, var(--ui-bg));
  box-shadow: inset 3px 0 0 var(--ui-color-primary-300);
}
.palette-option[aria-selected="true"] .palette-option__icon {
  color: var(--ui-color-primary-700);
}
.dark .palette-option[aria-selected="true"] .palette-option__icon {
  color: var(--ui-color-primary-300);
}
@media (forced-colors: active) {
  .palette-option[aria-selected="true"],
  .dark .palette-option[aria-selected="true"] {
    forced-color-adjust: none;
    background: Highlight;
    color: HighlightText;
    box-shadow: none;
  }
  .palette-option[aria-selected="true"] *,
  .dark .palette-option[aria-selected="true"] .palette-option__icon {
    color: HighlightText;
  }
}
</style>
