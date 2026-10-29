<script setup lang="ts">
import type { Station } from '#shared/types/api'
import { LANGUAGES } from '~/utils/languages'
import { findStations, matches } from '~/utils/palette'
import { FORECAST_STATIONS_QUERY, placeName, placeOfStation } from '~/utils/place'

/**
 * The command palette (GH-3518): one field that finds the pages (each with its line of what it is for), the
 * settings of appearance and language, and the forecast's stations, the places of the home page's search.
 * Opened by the search button of the header and by Ctrl+K / ⌘K on every page.
 *
 * The ARIA combobox pattern with a listbox popup (WAI-ARIA APG, "editable combobox with list autocomplete"):
 * the focus stays in the field, the arrow keys move the active option (`aria-activedescendant`, and
 * `aria-selected` on it), Enter takes it, Escape closes the dialog. The dialog keeps the focus and gives it back
 * to what had it before (Reka's focus scope). The listbox does not scroll by itself: the dialog's body, which
 * holds the field, does, so what scrolls has something that takes the focus (axe `scrollable-region-focusable`).
 */
const open = defineModel<boolean>('open', { required: true })

const { t, setLocale } = useI18n()
const colorMode = useColorMode()
const { groups } = useAppNav()
const { setPlace } = usePlace()
const reducedMotion = usePreferredReducedMotion()

const query = ref('')
const active = ref(0)
const ids = { input: useId(), listbox: useId(), hint: useId() }

// The stations are the forecast's list, asked for once, the first time a query could find one (two letters)
const stations = useState<Station[] | null>('palette-stations', () => null)
const stationsPending = ref(false)
async function loadStations() {
  if (stations.value || stationsPending.value)
    return
  stationsPending.value = true
  try {
    const answer = await $fetch<{ stations: Station[] }>('/api/stations', { query: FORECAST_STATIONS_QUERY, ...RETRY_TRANSIENT })
    stations.value = answer.stations ?? []
  }
  catch {
    // the pages and settings are found all the same; the places are missing until a later query asks again
  }
  finally {
    stationsPending.value = false
  }
}
watch(query, (value) => {
  active.value = 0
  if (value.trim().length >= 2)
    void loadStations()
})
watch(open, (isOpen) => {
  if (isOpen) {
    query.value = ''
    active.value = 0
  }
})

interface PaletteOption {
  id: string
  group: 'pages' | 'settings' | 'places'
  label: string
  description: string
  icon: string
  /** The language of the label, where it is not the page's: a language named in its own (WCAG 3.1.2) */
  lang?: string
  current?: boolean
  run: () => void
}

function go(to: string) {
  open.value = false
  void navigateTo(to)
}

const options = computed<PaletteOption[]>(() => {
  const q = query.value
  const pages: PaletteOption[] = groups.value.flatMap(group => group.items)
    .filter(item => matches(q, item.label, item.description))
    .map(item => ({ id: `page-${item.key}`, group: 'pages', label: item.label, description: item.description, icon: item.icon, run: () => go(item.to) }))

  const themes = [
    { value: 'light', label: t('settings.themeLight'), icon: 'i-lucide-sun' },
    { value: 'dark', label: t('settings.themeDark'), icon: 'i-lucide-moon' },
    { value: 'system', label: t('settings.themeSystem'), icon: 'i-lucide-monitor' },
  ]
  const settings: PaletteOption[] = themes
    .filter(theme => matches(q, theme.label, t('settings.theme')))
    .map(theme => ({
      id: `theme-${theme.value}`,
      group: 'settings',
      label: theme.label,
      description: t('settings.theme'),
      icon: theme.icon,
      current: colorMode.preference === theme.value,
      run: () => {
        colorMode.preference = theme.value
        open.value = false
      },
    }))
  // the languages once something is typed: eleven of them would fill the list before a word is
  if (q.trim()) {
    settings.push(...LANGUAGES
      .filter(language => matches(q, language.name, t('settings.language'), language.value))
      .map(language => ({
        id: `language-${language.value}`,
        group: 'settings' as const,
        label: language.name,
        lang: language.value === 'de-hh' ? 'nds' : language.value,
        description: t('settings.language'),
        icon: 'i-lucide-languages',
        run: () => {
          void setLocale(language.value as Parameters<typeof setLocale>[0])
          open.value = false
        },
      })))
  }

  const places: PaletteOption[] = findStations(stations.value ?? [], q).map(station => ({
    id: `place-${station.station_id}`,
    group: 'places',
    label: placeName(station.name ?? station.station_id),
    description: t('palette.stationDesc', { id: station.station_id }),
    icon: 'i-lucide-map-pin',
    run: () => {
      const place = placeOfStation(station)
      if (place)
        setPlace(place)
      go(`/meteogram?station=${encodeURIComponent(station.station_id)}`)
    },
  }))
  // the pages and settings first, which a word finds exactly, then the places, of which a word finds several
  return [...pages, ...settings, ...places]
})

const sections = computed(() => [
  { key: 'pages', title: t('palette.groupPages'), items: options.value.filter(option => option.group === 'pages') },
  { key: 'settings', title: t('palette.groupSettings'), items: options.value.filter(option => option.group === 'settings') },
  { key: 'places', title: t('palette.groupPlaces'), items: options.value.filter(option => option.group === 'places') },
].filter(section => section.items.length))

const activeOption = computed(() => options.value[active.value])
// a list that has become shorter (the places came, a language changed) keeps an option active
watch(() => options.value.length, (count) => {
  if (active.value >= count)
    active.value = 0
})
const optionId = (option: PaletteOption) => `${ids.listbox}-${option.id}`
const indexOf = (option: PaletteOption) => options.value.indexOf(option)

function move(step: number) {
  const count = options.value.length
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
    case 'Home':
      if (event.ctrlKey) {
        event.preventDefault()
        active.value = 0
      }
      break
    case 'End':
      if (event.ctrlKey) {
        event.preventDefault()
        active.value = Math.max(0, options.value.length - 1)
      }
      break
    case 'Enter':
      if (activeOption.value) {
        event.preventDefault()
        activeOption.value.run()
      }
      break
  }
}

// the active option is kept in view inside the dialog's body as the arrow keys move it
watch(active, async () => {
  await nextTick()
  const option = activeOption.value
  if (option)
    document.getElementById(optionId(option))?.scrollIntoView({ block: 'nearest' })
})

const empty = computed(() => query.value.trim() !== '' && !options.value.length && !stationsPending.value)

// the field takes the focus when the dialog opens, not the close button, which comes first in it
const input = ref<HTMLInputElement | null>(null)
const content = {
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
    :transition="reducedMotion !== 'reduce'"
    :content="content"
    :ui="{ content: 'sm:max-w-xl', header: 'min-h-14 py-3', body: 'p-0 sm:p-0 max-h-[min(70vh,36rem)] overflow-y-auto' }"
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
      <div class="sticky top-0 z-10 border-b border-default bg-default px-4 py-3">
        <label :for="ids.input" class="sr-only">{{ t('palette.inputLabel') }}</label>
        <!-- the field is the whole box, so that the focus ring of the app goes round it -->
        <div class="relative">
          <UIcon name="i-lucide-search" class="pointer-events-none absolute top-1/2 left-3 size-5 -translate-y-1/2 text-toned" />
          <input
            :id="ids.input"
            ref="input"
            v-model="query"
            type="text"
            role="combobox"
            autocomplete="off"
            spellcheck="false"
            aria-expanded="true"
            aria-autocomplete="list"
            :aria-controls="ids.listbox"
            :aria-activedescendant="activeOption ? optionId(activeOption) : undefined"
            :aria-describedby="ids.hint"
            :placeholder="t('palette.placeholder')"
            class="h-12 w-full min-w-0 rounded-xl bg-muted pr-10 pl-11 text-base text-highlighted ring ring-default placeholder:text-dimmed"
            @keydown="onKeydown"
          >
          <UIcon v-if="stationsPending" name="i-lucide-loader-circle" class="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 animate-spin text-toned motion-reduce:animate-none" />
        </div>
        <p :id="ids.hint" class="mt-2 text-xs text-toned">
          {{ t('palette.hint') }}
        </p>
      </div>

      <div :id="ids.listbox" role="listbox" :aria-label="t('palette.title')" class="px-2 py-2">
        <div v-for="section in sections" :key="section.key" role="group" :aria-labelledby="`${ids.listbox}-${section.key}`" class="mb-2 last:mb-0">
          <div :id="`${ids.listbox}-${section.key}`" role="presentation" class="px-3 pt-2 pb-1 text-xs font-bold uppercase tracking-wider text-toned">
            {{ section.title }}
          </div>
          <div
            v-for="option in section.items"
            :id="optionId(option)"
            :key="option.id"
            role="option"
            :aria-selected="activeOption === option"
            :aria-labelledby="`${optionId(option)}-label`"
            :aria-describedby="option.description ? `${optionId(option)}-desc` : undefined"
            class="flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2"
            :class="activeOption === option ? 'bg-brand-50 ring-1 ring-brand-600 dark:bg-brand-950 dark:ring-brand-400' : ''"
            @click="option.run()"
            @mousemove="active = indexOf(option)"
          >
            <span
              class="grid size-8 shrink-0 place-items-center rounded-lg"
              :class="activeOption === option ? 'bg-brand-600 text-white dark:bg-brand-400 dark:text-ink-900' : 'bg-ink-100 text-ink-700 dark:bg-ink-800 dark:text-ink-200'"
              aria-hidden="true"
            >
              <UIcon :name="option.icon" class="size-4" />
            </span>
            <span class="min-w-0 flex-1">
              <span :id="`${optionId(option)}-label`" class="block font-semibold text-highlighted" :lang="option.lang">{{ option.label }}</span>
              <span v-if="option.description" :id="`${optionId(option)}-desc`" class="block text-sm text-toned">{{ option.description }}</span>
            </span>
            <UIcon v-if="option.current" name="i-lucide-check" class="size-4 shrink-0 text-brand-700 dark:text-brand-300" />
          </div>
        </div>
      </div>
      <!-- always in the page, so that a screen reader hears it when it is filled -->
      <p role="status" class="px-5 text-sm text-toned" :class="empty ? 'pb-5' : 'sr-only'">
        {{ empty ? t('palette.empty') : '' }}
      </p>
    </template>
    <template #footer>
      <p class="hidden w-full text-xs text-toned sm:block">
        {{ t('palette.keysHint') }}
      </p>
    </template>
  </UModal>
</template>
