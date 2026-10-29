<script setup lang="ts">
import type { Station, StripesStation, StripesStationsResponse } from '#shared/types/api'
import type { PageKey, Zone } from '~/composables/useTimeAxis'
import { AXIS_STOPS, PAGE_LABEL_KEYS, REFERENCE_PAGES } from '~/composables/useTimeAxis'
import { LANGUAGES } from '~/utils/languages'
import { rankEntries, stepIndex } from '~/utils/palette'

// The command palette (GH-3518): one field that finds the pages, the places on the axis of time, the stations of
// the forecast and of the climate stripes, and the appearance and language of the app. Opened by the search button
// of the header and by Ctrl+K / Cmd+K.
//
// The ARIA combobox pattern with a list box (WAI-ARIA APG, "Combobox with listbox popup"): the focus stays in the
// field, the arrow keys move the active option (`aria-activedescendant`), Enter runs it. The dialog around it keeps
// the focus (Tab cannot leave it), Escape closes it, and the focus goes back to what had it before it opened.

interface Entry {
  id: string
  group: string
  label: string
  description?: string
  keywords?: string
  icon: string
  zone?: Zone
  /** The appearance or language in use, or the page that is open */
  current?: boolean
  run: () => unknown
}

interface Group {
  id: string
  label: string
  entries: Entry[]
}

const { t, locale, setLocale } = useI18n()
const colorMode = useColorMode()
const route = useRoute()
const { open, hide, takeOpener } = useCommandPalette()
const { current, span, lastYear } = useTimeAxis()

const query = ref('')
const activeIndex = ref(-1)
const input = ref<HTMLInputElement | null>(null)
const scroller = ref<HTMLElement | null>(null)
const uid = useId()
const listId = `${uid}-list`
const optionId = (entry: Entry) => `${uid}-${entry.id}`

/**
 * Where to go: another page of the app, or the page that is open with another station or stretch of time. The
 * pages read those from the address once, when they are opened, so the page is then loaded anew.
 */
async function go(target: string) {
  hide()
  const [path, search = ''] = target.split('?')
  if (path !== route.path)
    await navigateTo(target)
  else if (new URLSearchParams(search).toString() !== new URLSearchParams(route.fullPath.split('?')[1] ?? '').toString())
    window.location.assign(target)
}

// the station on screen, so that a jump along the axis keeps it: the forecast of this station for the next day,
// the stripes of this station for the last thirty years
const stationQuery = computed(() => {
  const station = route.query.station?.toString()
  return station || null
})

function withQuery(path: string, params: Record<string, string | null | undefined>) {
  const search = new URLSearchParams(Object.entries(params).filter((pair): pair is [string, string] => !!pair[1]))
  const text = search.toString()
  return text ? `${path}?${text}` : path
}

const pageEntries = computed<Entry[]>(() => {
  const axis = AXIS_STOPS.map(stop => ({ key: stop.key as PageKey, path: stop.path, icon: stop.icon, zone: stop.zone as Zone }))
  const reference = REFERENCE_PAGES.map(page => ({ key: page.key as PageKey, path: page.path, icon: page.icon, zone: 'reference' as Zone }))
  return [...axis, ...reference].map(page => ({
    id: `page-${page.key}`,
    group: 'pages',
    label: page.key === 'now' ? t('nav.home') : t(PAGE_LABEL_KEYS[page.key]),
    description: t(`palette.pages.${page.key}`),
    keywords: page.zone === 'reference' ? '' : `${t(`axis.${page.zone}`)} ${span(page.key)}`,
    icon: page.icon,
    zone: page.zone,
    current: current.value === page.key,
    // the page that is open stays as it is, with what it shows
    run: () => route.path === page.path ? hide() : go(page.path),
  }))
})

const timeEntries = computed<Entry[]>(() => {
  const forecastStation = route.path === '/meteogram' ? stationQuery.value : null
  const stripesStation = route.path === '/stripes' ? stationQuery.value : null
  const stripesKind = route.path === '/stripes' ? route.query.kind?.toString() : undefined
  const forecast = (key: string, horizon: string | null) => ({
    id: `time-${key}`,
    group: 'time',
    label: t(`palette.time.${key}`),
    description: t('nav.meteogram'),
    keywords: t('axis.next'),
    icon: 'i-lucide-arrow-right-to-line',
    zone: 'next' as Zone,
    run: () => go(withQuery('/meteogram', { station: forecastStation, horizon })),
  })
  return [
    forecast('next24h', '24'),
    forecast('next3d', '72'),
    forecast('next7d', '168'),
    forecast('next10d', null),
    {
      id: 'time-last30y',
      group: 'time',
      label: t('palette.time.last30y'),
      description: `${t('nav.stripes')} · ${lastYear.value - 29}–${lastYear.value}`,
      keywords: t('axis.then'),
      icon: 'i-lucide-arrow-left-to-line',
      zone: 'then',
      run: () => go(withQuery('/stripes', { kind: stripesKind, station: stripesStation, start_year: String(lastYear.value - 29) })),
    },
    {
      id: 'time-allYears',
      group: 'time',
      label: t('palette.time.allYears'),
      description: t('nav.stripes'),
      keywords: t('axis.then'),
      icon: 'i-lucide-arrow-left-to-line',
      zone: 'then',
      run: () => go(withQuery('/stripes', { kind: stripesKind, station: stripesStation })),
    },
  ]
})

const themeEntries = computed<Entry[]>(() => ([
  { value: 'light', label: t('settings.themeLight'), icon: 'i-lucide-sun' },
  { value: 'dark', label: t('settings.themeDark'), icon: 'i-lucide-moon' },
  { value: 'system', label: t('settings.themeSystem'), icon: 'i-lucide-monitor' },
] as const).map(mode => ({
  id: `theme-${mode.value}`,
  group: 'theme',
  label: t('palette.themeOption', { mode: mode.label }),
  keywords: `${t('settings.theme')} ${mode.value}`,
  icon: mode.icon,
  current: colorMode.preference === mode.value,
  run: () => {
    colorMode.preference = mode.value
    hide()
  },
})))

const languageEntries = computed<Entry[]>(() => LANGUAGES.map(language => ({
  id: `language-${language.value}`,
  group: 'language',
  label: t('palette.languageOption', { language: language.name }),
  keywords: `${t('settings.language')} ${language.value}`,
  icon: 'i-lucide-languages',
  current: locale.value === language.value,
  run: async () => {
    hide()
    await setLocale(language.value as typeof locale.value)
  },
})))

// The stations, asked for the first time two letters are typed: the forecast's (DWD MOSMIX, the list the forecast
// page searches) and the climate stripes' (the stations with a long record). The same requests the two pages make.
const STATION_LIMIT = 6
const forecastStations = useState<Station[] | null>('palette-forecast-stations', () => null)
const stripesStations = useState<StripesStation[] | null>('palette-stripes-stations', () => null)
const stationsLoading = ref(false)
const wantsStations = computed(() => query.value.trim().length >= 2)

async function loadStations() {
  if (stationsLoading.value || (forecastStations.value && stripesStations.value))
    return
  stationsLoading.value = true
  const [forecast, stripes] = await Promise.allSettled([
    forecastStations.value ?? $fetch<{ stations: Station[] }>('/api/stations', {
      query: { provider: 'dwd', network: 'mosmix', parameters: 'hourly/large', all: 'true' },
      ...RETRY_TRANSIENT,
    }).then(answer => answer.stations ?? []),
    stripesStations.value ?? $fetch<StripesStationsResponse>('/api/stripes/stations', {
      query: { kind: 'temperature' },
      ...RETRY_TRANSIENT,
    }).then(answer => answer.stations ?? []),
  ])
  // a list that could not be had is no list: the next query asks again
  if (forecast.status === 'fulfilled')
    forecastStations.value = forecast.value
  if (stripes.status === 'fulfilled')
    stripesStations.value = stripes.value
  stationsLoading.value = false
}

watch(wantsStations, (wants) => {
  if (wants)
    void loadStations()
})

const yearOf = (timestamp: string | null) => timestamp ? timestamp.slice(0, 4) : '…'

const stationGroups = computed<Group[]>(() => {
  if (!wantsStations.value)
    return []
  const forecast = rankEntries((forecastStations.value ?? []).map(station => ({
    id: `forecast-${station.station_id}`,
    group: 'forecastStations',
    label: station.name ?? station.station_id,
    description: station.region ? `${station.station_id} · ${station.region}` : station.station_id,
    keywords: station.station_id,
    icon: 'i-lucide-cloud-sun',
    zone: 'next' as Zone,
    run: () => go(`/meteogram?station=${encodeURIComponent(station.station_id)}`),
  })), query.value, STATION_LIMIT)
  const stripes = rankEntries((stripesStations.value ?? []).map(station => ({
    id: `stripes-${station.station_id}`,
    group: 'stripesStations',
    label: station.name,
    description: `${station.station_id} · ${station.region} · ${yearOf(station.start_timestamp)}–${yearOf(station.end_timestamp)}`,
    keywords: station.station_id,
    icon: 'i-lucide-bar-chart-3',
    zone: 'then' as Zone,
    run: () => go(`/stripes?kind=temperature&station=${encodeURIComponent(station.station_id)}`),
  })), query.value, STATION_LIMIT)
  return [
    { id: 'forecastStations', label: t('palette.groupForecastStations'), entries: forecast },
    { id: 'stripesStations', label: t('palette.groupStripesStations'), entries: stripes },
  ]
})

const groups = computed<Group[]>(() => {
  const fixed: Group[] = [
    { id: 'pages', label: t('palette.groupPages'), entries: pageEntries.value },
    { id: 'time', label: t('palette.groupTime'), entries: timeEntries.value },
    { id: 'theme', label: t('settings.theme'), entries: themeEntries.value },
    { id: 'language', label: t('settings.language'), entries: languageEntries.value },
  ]
  const searched = fixed.map(group => ({ ...group, entries: rankEntries(group.entries, query.value) }))
  // the stations after the pages and the time, before the settings: a name typed is most likely a place
  return [...searched.slice(0, 2), ...stationGroups.value, ...searched.slice(2)].filter(group => group.entries.length)
})

const flat = computed(() => groups.value.flatMap(group => group.entries))
const active = computed(() => flat.value[activeIndex.value] ?? null)
const expanded = computed(() => flat.value.length > 0)

// a new query starts at its best answer
watch(query, () => {
  activeIndex.value = flat.value.length ? 0 : -1
})
watch(flat, (entries) => {
  if (activeIndex.value >= entries.length)
    activeIndex.value = entries.length ? 0 : -1
})

function reveal() {
  nextTick(() => {
    if (!active.value || !scroller.value)
      return
    scroller.value.querySelector(`[id="${optionId(active.value)}"]`)?.scrollIntoView({ block: 'nearest' })
  })
}

function onKeydown(event: KeyboardEvent) {
  switch (event.key) {
    case 'ArrowDown':
    case 'ArrowUp':
      event.preventDefault()
      activeIndex.value = stepIndex(activeIndex.value, event.key === 'ArrowDown' ? 1 : -1, flat.value.length)
      reveal()
      break
    case 'PageDown':
    case 'PageUp':
      event.preventDefault()
      if (flat.value.length) {
        const step = event.key === 'PageDown' ? 5 : -5
        activeIndex.value = Math.min(flat.value.length - 1, Math.max(0, activeIndex.value + step))
        reveal()
      }
      break
    case 'Enter':
      if (active.value) {
        event.preventDefault()
        void active.value.run()
      }
      break
  }
}

// Reset on every opening: an empty field, the first entry active, the list at its top
watch(open, (isOpen) => {
  if (isOpen) {
    query.value = ''
    activeIndex.value = 0
    nextTick(() => scroller.value?.scrollTo({ top: 0 }))
  }
})

const statusText = computed(() => {
  if (wantsStations.value && stationsLoading.value)
    return t('palette.stationsLoading')
  return flat.value.length ? t('palette.results', { count: flat.value.length }) : t('palette.empty')
})
// told once the typing has settled, not at every key
const announced = refDebounced(statusText, 600)

function focusField(event: Event) {
  event.preventDefault()
  input.value?.focus()
}

// the focus back to whatever had it before the palette opened: the search button, or wherever Ctrl+K was pressed
function returnFocus(event: Event) {
  const opener = takeOpener()
  if (opener) {
    event.preventDefault()
    opener.focus()
  }
}

const zoneTag = (zone?: Zone) => zone && zone !== 'reference' ? t(`axis.${zone}`) : null
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('palette.title')"
    :description="t('palette.description')"
    :content="{ onOpenAutoFocus: focusField, onCloseAutoFocus: returnFocus }"
    :ui="{ content: 'palette-dialog max-w-xl top-[6dvh] sm:top-[10dvh] -translate-y-0 max-h-[calc(100dvh-8dvh)] sm:max-h-[min(40rem,calc(100dvh-14dvh))] divide-y-0' }"
  >
    <template #content>
      <!-- One box that scrolls, with the field in it: the list is no scrolling region of its own that a keyboard
           could not reach (axe: scrollable-region-focusable), and the field stays on top as it scrolls -->
      <div ref="scroller" class="palette" data-testid="command-palette">
        <div class="palette__field">
          <UIcon name="i-lucide-search" class="palette__field-icon" />
          <input
            ref="input"
            v-model="query"
            class="palette__input"
            type="text"
            role="combobox"
            aria-autocomplete="list"
            :aria-expanded="expanded"
            :aria-controls="listId"
            :aria-activedescendant="active ? optionId(active) : undefined"
            :aria-label="t('palette.title')"
            :placeholder="t('palette.placeholder')"
            autocomplete="off"
            autocapitalize="off"
            spellcheck="false"
            enterkeyhint="go"
            @keydown="onKeydown"
          >
          <UButton
            icon="i-lucide-x"
            color="neutral"
            variant="ghost"
            size="sm"
            :aria-label="t('common.close')"
            @click="hide()"
          />
        </div>

        <div
          v-show="expanded"
          :id="listId"
          role="listbox"
          :aria-label="t('palette.title')"
          class="palette__list"
        >
          <div
            v-for="group in groups"
            :key="group.id"
            role="group"
            :aria-labelledby="`${uid}-group-${group.id}`"
            class="palette__group"
          >
            <div :id="`${uid}-group-${group.id}`" role="presentation" class="palette__group-label">
              {{ group.label }}
            </div>
            <div
              v-for="entry in group.entries"
              :id="optionId(entry)"
              :key="entry.id"
              role="option"
              :aria-selected="active?.id === entry.id"
              :aria-current="entry.current && entry.group === 'pages' ? 'page' : undefined"
              class="palette__option"
              :class="[{ 'is-active': active?.id === entry.id }, entry.zone ? `palette__option--${entry.zone}` : '']"
              @pointermove="activeIndex = flat.indexOf(entry)"
              @click="entry.run()"
            >
              <UIcon :name="entry.icon" class="palette__option-icon" />
              <span class="palette__option-text">
                <span class="palette__option-label">{{ entry.label }}</span>
                <span v-if="entry.description" class="palette__option-description">{{ entry.description }}</span>
              </span>
              <span v-if="zoneTag(entry.zone)" class="palette__zone" :class="`palette__zone--${entry.zone}`">{{ zoneTag(entry.zone) }}</span>
              <UIcon v-if="entry.current && entry.group !== 'pages'" name="i-lucide-check" class="palette__check" />
              <span v-if="entry.current && entry.group !== 'pages'" class="sr-only">({{ t('palette.inUse') }})</span>
            </div>
          </div>
        </div>

        <p v-if="!expanded" class="palette__empty">
          {{ statusText }}
        </p>
        <p v-else-if="!wantsStations" class="palette__hint">
          {{ t('palette.stationsHint') }}
        </p>
        <p v-else-if="stationsLoading" class="palette__hint">
          {{ t('palette.stationsLoading') }}
        </p>

        <div class="palette__keys" aria-hidden="true">
          <span><kbd>↑</kbd><kbd>↓</kbd> {{ t('palette.keyMove') }}</span>
          <span><kbd>↵</kbd> {{ t('palette.keyOpen') }}</span>
          <span><kbd>Esc</kbd> {{ t('palette.keyClose') }}</span>
        </div>
        <span class="sr-only" role="status" aria-live="polite">{{ announced }}</span>
      </div>
    </template>
  </UModal>
</template>
