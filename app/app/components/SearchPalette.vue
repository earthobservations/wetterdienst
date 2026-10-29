<script setup lang="ts">
import type { Station } from '#shared/types/api'
import { LANGUAGES } from '~/utils/languages'

// The search of the app (GH-3518): one field for the pages, the appearance and the language, and the stations of the
// forecast, as an almanac's index. Opened by the masthead's button and by Ctrl+K / ⌘K from anywhere.
//
// The ARIA combobox pattern with a listbox popup (WAI-ARIA APG, "editable combobox with list autocomplete"): the
// field is the combobox and keeps the focus; the arrow keys move the highlighted option, which the field names by
// `aria-activedescendant`; Enter takes it. The options are grouped as the APG's grouped listbox is (`role="group"`
// named by a `role="presentation"` label). The dialog (Reka's, through UModal) holds the focus, closes on Escape and
// gives the focus back to what opened it. Nuxt UI's own command palette puts its field inside the listbox, which
// breaks `aria-required-children` (see the station picker in ACCESSIBILITY.md), so this is the app's own.

const open = defineModel<boolean>('open', { default: false })

const { t, locale, setLocale } = useI18n()
const colorMode = useColorMode()
const route = useRoute()

type Group = 'pages' | 'actions' | 'stations'
interface Entry {
  id: string
  group: Group
  label: string
  /** a word of the label that is in another language than the page, such as a language's own name */
  labelLang?: string
  purpose: string
  icon: string
  tile?: string
  /** where the entry stands now: the page being read, the appearance and the language in use */
  current?: boolean
  run: () => unknown
}

const query = ref('')
const active = ref(0)
const input = useTemplateRef<HTMLInputElement>('input')
const listId = useId()
const statusId = useId()

/** Letters without their accents and case, so that "munchen" finds "München" and "MUENCHEN" alike */
function fold(text: string) {
  return text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
}
function matches(entry: Entry, words: string[]) {
  const haystack = fold(`${entry.label} ${entry.purpose}`)
  return words.every(word => haystack.includes(word))
}

function go(path: string) {
  open.value = false
  return navigateTo(path)
}

// the pages, each with a line on what it is for (the line search engines are given, where there is one)
const pages = computed<Entry[]>(() => [
  { path: '/', label: t('nav.home'), purpose: t('home.tagline'), icon: 'i-lucide-home' },
  { path: '/meteogram', label: t('nav.meteogram'), purpose: t('seo.pages.meteogram'), icon: 'i-lucide-sun', tile: 'bg-tile-sun' },
  { path: '/stripes', label: t('nav.stripes'), purpose: t('seo.pages.stripes'), icon: 'i-lucide-bar-chart-3', tile: 'bg-tile-heat' },
  { path: '/explorer', label: t('nav.explorer'), purpose: t('seo.pages.explorer'), icon: 'i-lucide-globe', tile: 'bg-tile-rain' },
  { path: '/history', label: t('nav.history'), purpose: t('seo.pages.history'), icon: 'i-lucide-clock', tile: 'bg-tile-wind' },
  { path: '/api', label: t('nav.api'), purpose: t('seo.pages.api'), icon: 'i-lucide-code' },
  { path: '/providers', label: t('nav.providers'), purpose: t('seo.pages.providers'), icon: 'i-lucide-building-2' },
  { path: '/glossary', label: t('nav.glossary'), purpose: t('seo.pages.glossary'), icon: 'i-lucide-book-open' },
  { path: '/settings', label: t('settings.title'), purpose: t('settings.subtitle'), icon: 'i-lucide-settings-2' },
  { path: '/about', label: t('about.title'), purpose: t('seo.pages.about'), icon: 'i-lucide-info' },
  { path: '/support', label: t('nav.support'), purpose: t('seo.pages.support'), icon: 'i-lucide-heart' },
  { path: '/impressum', label: t('footer.legal'), purpose: t('search.purposeImpressum'), icon: 'i-lucide-scale' },
  { path: '/datenschutz', label: t('footer.privacy'), purpose: t('search.purposePrivacy'), icon: 'i-lucide-shield' },
].map(page => ({
  id: `page:${page.path}`,
  group: 'pages' as const,
  label: page.label,
  purpose: page.purpose,
  icon: page.icon,
  tile: page.tile,
  current: page.path === '/' ? route.path === '/' : route.path.startsWith(page.path),
  run: () => go(page.path),
})))

// what the settings menu does, one step away: the appearance and the language
const actions = computed<Entry[]>(() => [
  ...([
    ['light', t('settings.themeLight'), 'i-lucide-sun'],
    ['dark', t('settings.themeDark'), 'i-lucide-moon'],
    ['system', t('settings.themeSystem'), 'i-lucide-monitor'],
  ] as const).map(([mode, name, icon]) => ({
    id: `theme:${mode}`,
    group: 'actions' as const,
    label: `${t('settings.theme')}: ${name}`,
    purpose: colorMode.preference === mode ? t('search.inUse') : '',
    icon,
    current: colorMode.preference === mode,
    run: () => {
      colorMode.preference = mode
      open.value = false
    },
  })),
  ...LANGUAGES.map(language => ({
    id: `language:${language.value}`,
    group: 'actions' as const,
    label: language.name,
    labelLang: language.value === 'de-hh' ? 'nds' : language.value,
    purpose: locale.value === language.value ? `${t('settings.language')} · ${t('search.inUse')}` : t('settings.language'),
    icon: 'i-lucide-languages',
    current: locale.value === language.value,
    run: async () => {
      open.value = false
      await setLocale(language.value as typeof locale.value)
    },
  })),
])

// The stations of the forecast (DWD MOSMIX), the list the forecast's own picker reads: asked for once, the first time
// a query is long enough to name one, and kept for the visit
const stations = ref<Station[] | null>(null)
const stationsPending = ref(false)
const stationsFailed = ref(false)
async function loadStations() {
  if (stations.value || stationsPending.value)
    return
  stationsPending.value = true
  stationsFailed.value = false
  try {
    const answer = await $fetch<{ stations: Station[] }>('/api/stations', {
      query: { provider: 'dwd', network: 'mosmix', parameters: 'hourly/large', all: 'true' },
      ...RETRY_TRANSIENT,
    })
    stations.value = answer.stations ?? []
  }
  catch {
    stationsFailed.value = true
  }
  finally {
    stationsPending.value = false
  }
}

const words = computed(() => fold(query.value.trim()).split(/\s+/).filter(Boolean))
const wantsStations = computed(() => query.value.trim().length >= 2)
watch(wantsStations, (wanted) => {
  if (wanted)
    void loadStations()
})

const STATION_LIMIT = 8
const stationEntries = computed<Entry[]>(() => {
  if (!wantsStations.value || !stations.value)
    return []
  const found = stations.value
    .map(station => ({ station, name: fold(`${station.name} ${station.station_id}`) }))
    .filter(({ name }) => words.value.every(word => name.includes(word)))
    // a name that starts with what was typed first
    .sort((a, b) => Number(b.name.startsWith(words.value[0]!)) - Number(a.name.startsWith(words.value[0]!)))
    .slice(0, STATION_LIMIT)
  return found.map(({ station }) => ({
    id: `station:${station.station_id}`,
    group: 'stations' as const,
    label: station.name ?? station.station_id,
    purpose: [t('search.stationPurpose', { id: station.station_id }), station.region].filter(Boolean).join(' · '),
    icon: 'i-lucide-map-pin',
    tile: 'bg-tile-sun',
    run: () => go(`/meteogram?station=${station.station_id}`),
  }))
})

const groups = computed(() => {
  const all: { key: Group, label: string, entries: Entry[] }[] = [
    { key: 'pages', label: t('search.groupPages'), entries: pages.value.filter(entry => matches(entry, words.value)) },
    { key: 'actions', label: t('search.groupActions'), entries: actions.value.filter(entry => matches(entry, words.value)) },
    { key: 'stations', label: t('search.groupStations'), entries: stationEntries.value },
  ]
  return all.filter(group => group.entries.length)
})
const flat = computed(() => groups.value.flatMap(group => group.entries))
const activeEntry = computed(() => flat.value[active.value])
const optionId = (entry: Entry) => `${listId}-${entry.id.replace(/[^\w-]/g, '_')}`

watch(query, () => {
  active.value = 0
})
watch(flat, (entries) => {
  if (active.value >= entries.length)
    active.value = Math.max(0, entries.length - 1)
})
watch(open, (isOpen) => {
  if (isOpen) {
    query.value = ''
    active.value = 0
  }
})

function move(by: number) {
  const count = flat.value.length
  if (!count)
    return
  active.value = (active.value + by + count) % count
  void nextTick(() => {
    if (activeEntry.value)
      document.getElementById(optionId(activeEntry.value))?.scrollIntoView({ block: 'nearest' })
  })
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
  else if (event.key === 'Enter' && activeEntry.value) {
    event.preventDefault()
    void activeEntry.value.run()
  }
}

// what a screen reader is told as the list changes: how many there are, and that stations are being looked up
const status = computed(() => {
  if (wantsStations.value && stationsPending.value)
    return t('search.stationsLoading')
  if (!flat.value.length)
    return t('search.empty', { query: query.value.trim() })
  return t('search.results', { n: flat.value.length })
})

// the field takes the focus when the dialog opens, rather than the dialog's first button
function focusField(event: Event) {
  event.preventDefault()
  input.value?.focus()
}

// Ctrl+K, and ⌘K on a Mac, from anywhere in the app: a key combination with a modifier, so no single key is taken
// from a reader who types (WCAG 2.1.4)
useEventListener(globalThis.window, 'keydown', (event: KeyboardEvent) => {
  if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    open.value = !open.value
  }
})
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('search.title')"
    :description="t('search.hint')"
    :content="{ onOpenAutoFocus: focusField }"
    :ui="{
      content: 'sm:max-w-2xl rounded-sm',
      header: 'border-b-2 border-(--app-rule-strong) pb-3',
      title: 'font-serif text-2xl font-semibold',
      description: 'text-sm text-muted',
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
      <!-- the field stays at the top of what scrolls, so the list scrolls under it and the scroll area holds the focus -->
      <div class="sticky top-0 z-10 bg-default px-4 sm:px-6 pt-4 pb-3">
        <div class="flex items-center gap-3 border-b-2 border-(--app-rule) focus-within:border-(--app-rule-strong)">
          <UIcon name="i-lucide-search" class="size-5 text-muted shrink-0" />
          <input
            ref="input"
            v-model="query"
            type="text"
            role="combobox"
            autocomplete="off"
            spellcheck="false"
            class="w-full min-w-0 bg-transparent py-2 font-serif text-xl text-highlighted placeholder:text-dimmed"
            :placeholder="t('search.placeholder')"
            :aria-label="t('search.label')"
            aria-autocomplete="list"
            :aria-expanded="flat.length > 0"
            :aria-controls="flat.length ? listId : undefined"
            :aria-activedescendant="activeEntry ? optionId(activeEntry) : undefined"
            :aria-describedby="statusId"
            @keydown="onKeydown"
          >
        </div>
      </div>

      <div class="px-4 sm:px-6 pb-4">
        <div v-if="flat.length" :id="listId" role="listbox" :aria-label="t('search.label')" class="space-y-4">
          <ul v-for="group in groups" :key="group.key" role="group" :aria-labelledby="`${listId}-${group.key}`" class="space-y-0.5">
            <li :id="`${listId}-${group.key}`" role="presentation" class="app-kicker pt-1 pb-1.5">
              {{ group.label }}
            </li>
            <li
              v-for="entry in group.entries"
              :id="optionId(entry)"
              :key="entry.id"
              role="option"
              :aria-selected="activeEntry?.id === entry.id"
              class="flex items-start gap-3 rounded-sm border-l-[3px] px-3 py-2 cursor-pointer"
              :class="activeEntry?.id === entry.id ? 'border-(--app-rule-strong) bg-elevated' : 'border-transparent'"
              @mousemove="active = flat.indexOf(entry)"
              @click="entry.run()"
            >
              <span class="relative mt-1 shrink-0" aria-hidden="true">
                <UIcon :name="entry.icon" class="size-4 text-toned" />
                <span v-if="entry.tile" class="app-tile absolute -right-1 -bottom-1 size-2" :class="entry.tile" />
              </span>
              <span class="min-w-0 flex-1">
                <span class="flex items-baseline gap-2">
                  <span class="font-serif text-lg leading-snug text-highlighted" :lang="entry.labelLang">{{ entry.label }}</span>
                  <UIcon v-if="entry.current" name="i-lucide-check" class="size-4 text-primary shrink-0 self-center" aria-hidden="true" />
                </span>
                <span v-if="entry.purpose" class="block text-sm text-muted">{{ entry.purpose }}</span>
              </span>
            </li>
          </ul>
        </div>
        <p :id="statusId" role="status" class="text-muted" :class="flat.length ? 'pt-3 text-xs' : 'py-6'">
          {{ status }}
        </p>
      </div>
    </template>
  </UModal>
</template>
