<script setup lang="ts">
import type { Station } from '#shared/types/api'
import type { Place } from '~/composables/usePlace'
import type { PaletteGroup, PaletteItem } from '~/utils/palette'
import type { Tile } from '~/utils/sections'
import { PLACE_NETWORK, placeOf } from '~/composables/usePlace'
import { filterGroups } from '~/utils/palette'
import { EXTERNAL, HOME, LEGAL, PROJECT, REFERENCE, TOOLS } from '~/utils/sections'

// The command palette of the search (GH-3518), inside the dialog of AppSearch.vue. One field that goes to every page
// (each with the line that says what it is for), to a provider's page, to the forecast of a station found by its
// name, and that changes the theme or the language.
//
// The WAI-ARIA combobox pattern with a listbox popup: the field is the combobox and keeps the focus; the arrow keys
// move the active option (`aria-activedescendant`), Enter takes it, and a click takes the one under the pointer. The
// dialog around it holds the focus, closes on Escape and gives the focus back to what opened it. How many results
// there are is said in a polite live region. The list is the one scrolling box, and takes the focus by Tab too, so a
// keyboard can scroll it (WCAG 2.1.1); there its keys are the field's.
//
// The stations come from the backend (`GET /api/stations` with `name`, its best five matches), from three letters
// on and a moment after the last key; the rest is matched here (utils/palette.ts).
//
// In its place mode (`mode="place"`, the home page's "Ask the weather") it is the same field and list for one thing
// only: the place the questions are about. It lists DWD's measuring stations by name (from two letters on), a station
// that has stopped reporting long ago left out, and choosing one makes it the reader's place (composables/usePlace.ts).
const props = withDefaults(defineProps<{
  mode?: 'search' | 'place'
}>(), { mode: 'search' })
const emit = defineEmits<{ done: [], place: [place: Place] }>()

const { t, locale, setLocale } = useI18n()
const colorMode = useColorMode()
const { data: providerList } = useProviders()

const query = ref('')
const activeIndex = ref(0)
const listId = useId()

const placeMode = computed(() => props.mode === 'place')
const MIN_STATION_QUERY = computed(() => placeMode.value ? 2 : 3)
const { setPlace } = usePlace()
const stations = ref<Station[]>([])
const stationsPending = ref(false)
const stationsFailed = ref(false)
let stationTicket = 0
// a search typed just before the dialog closed asks for nothing once it is gone
let closed = false
onBeforeUnmount(() => {
  closed = true
})
watchDebounced(query, async (value) => {
  if (closed)
    return
  const text = value.trim()
  const ticket = ++stationTicket
  if (text.length < MIN_STATION_QUERY.value) {
    stations.value = []
    stationsPending.value = false
    // a failure was of the text before: the text now is a hint, announced as one
    stationsFailed.value = false
    return
  }
  stationsPending.value = true
  stationsFailed.value = false
  try {
    const answer = await $fetch<{ stations: Station[] }>('/api/stations', {
      query: placeMode.value
        ? { ...PLACE_NETWORK, name: text }
        : { provider: 'dwd', network: 'mosmix', parameters: 'hourly/large', name: text },
    })
    if (ticket === stationTicket) {
      // a station that stopped reporting years ago has no recent weather to ask about
      const recent = Date.now() - 2 * 365 * 86_400_000
      stations.value = placeMode.value
        ? (answer.stations ?? []).filter(station => !station.end_timestamp || Date.parse(station.end_timestamp) > recent).slice(0, 8)
        : (answer.stations ?? []).slice(0, 5)
    }
  }
  catch {
    // a station search that fails leaves the pages and actions to choose from
    if (ticket === stationTicket) {
      stations.value = []
      stationsFailed.value = true
    }
  }
  finally {
    if (ticket === stationTicket)
      stationsPending.value = false
  }
}, { debounce: 300 })

function page(section: { key: string, to: string, label: string, icon: string, description?: string, tile?: string }, external = false): PaletteItem {
  return {
    id: section.key,
    label: t(section.label),
    description: section.description ? t(section.description) : undefined,
    icon: section.icon,
    tile: section.tile,
    to: section.to,
    external,
  }
}

const THEMES = [
  { value: 'system', label: 'settings.themeSystem', icon: 'i-ph-monitor' },
  { value: 'light', label: 'settings.themeLight', icon: 'i-ph-sun' },
  { value: 'dark', label: 'settings.themeDark', icon: 'i-ph-moon' },
] as const

function choosePlace(place: Place) {
  setPlace(place)
  emit('place', place)
}

const groups = computed<PaletteGroup[]>(() => {
  const searching = query.value.trim().length > 0
  if (placeMode.value) {
    return [{
      id: 'places',
      label: t('ask.placesGroup'),
      items: stations.value
        .map(placeOf)
        .filter((place): place is Place => place !== null)
        .map(place => ({
          id: `place-${place.id}`,
          label: place.name,
          description: place.region ?? undefined,
          icon: 'i-ph-map-pin',
          run: () => choosePlace(place),
        })),
    }]
  }
  return [
    { id: 'tools', label: t('shell.tools'), items: TOOLS.map(section => page(section)) },
    {
      id: 'stations',
      label: t('shell.stations'),
      items: stations.value.map(station => ({
        id: `station-${station.station_id}`,
        label: station.name ?? station.station_id,
        description: t('shell.stationForecast', { id: station.station_id }),
        icon: 'i-ph-sun-fill',
        tile: 'sun',
        to: `/meteogram?station=${station.station_id}`,
      })),
    },
    { id: 'reference', label: t('shell.reference'), items: REFERENCE.map(section => page(section)) },
    {
      id: 'providers',
      label: t('nav.providers'),
      // by name, once something is typed: the 23 of them are a page of their own
      items: searching
        ? (providerList.value?.providers ?? []).map(provider => ({
            id: `provider-${provider.provider}`,
            label: provider.name_short,
            description: provider.name_english,
            keywords: `${provider.provider} ${provider.country ?? ''} ${provider.name_local ?? ''}`,
            icon: 'i-ph-buildings',
            to: `/providers/${provider.provider}`,
          }))
        : [],
    },
    {
      id: 'project',
      label: t('shell.project'),
      items: [HOME, ...PROJECT, ...LEGAL].map(section => page(section)).concat(EXTERNAL.map(link => page(link, true))),
    },
    {
      id: 'theme',
      label: t('settings.theme'),
      items: THEMES.map(theme => ({
        id: `theme-${theme.value}`,
        label: t(theme.label),
        keywords: t('settings.theme'),
        icon: theme.icon,
        current: colorMode.preference === theme.value,
        run: () => {
          colorMode.preference = theme.value
        },
      })),
    },
    {
      id: 'language',
      label: t('settings.language'),
      items: LANGUAGES.map(language => ({
        id: `language-${language.value}`,
        label: language.name,
        keywords: `${language.value} ${t('settings.language')}`,
        icon: 'i-ph-translate',
        current: locale.value === language.value,
        run: () => {
          void setLocale(language.value as typeof locale.value)
        },
      })),
    },
  ]
})

// the stations are the backend's matches already; everything else is matched here
const shown = computed(() => {
  // the places are the backend's matches, as they are
  if (placeMode.value)
    return groups.value.filter(group => group.items.length)
  const stationGroup = groups.value.find(group => group.id === 'stations')!
  const filtered = filterGroups(groups.value.filter(group => group.id !== 'stations'), query.value)
  if (stationGroup.items.length)
    filtered.splice(1, 0, stationGroup)
  return filtered
})
const flat = computed(() => shown.value.flatMap(group => group.items))
const optionId = (item: PaletteItem) => `${listId}-${item.id}`
const active = computed(() => flat.value[Math.min(activeIndex.value, flat.value.length - 1)])
const activeId = computed(() => active.value ? optionId(active.value) : undefined)

watch(query, () => {
  activeIndex.value = 0
})
watch(activeId, async (id) => {
  await nextTick()
  if (id)
    document.getElementById(id)?.scrollIntoView({ block: 'nearest' })
})

const status = computed(() => {
  if (stationsPending.value)
    return placeMode.value ? t('ask.placeSearching') : t('common.loading')
  if (placeMode.value) {
    if (stationsFailed.value)
      return t('ask.placeFailed')
    return query.value.trim().length < MIN_STATION_QUERY.value ? t('ask.placeHint') : t('shell.resultsCount', flat.value.length)
  }
  const count = t('shell.resultsCount', flat.value.length)
  const typed = query.value.trim().length
  return typed > 0 && typed < MIN_STATION_QUERY.value ? `${count}. ${t('shell.stationsHint')}` : count
})

const emptyText = computed(() => {
  if (!placeMode.value)
    return t('shell.searchEmpty')
  return query.value.trim().length < MIN_STATION_QUERY.value ? t('ask.placeHint') : stationsPending.value ? t('ask.placeSearching') : stationsFailed.value ? t('ask.placeFailed') : t('shell.searchEmpty')
})

function choose(item: PaletteItem | undefined) {
  if (!item)
    return
  emit('done')
  if (item.run)
    item.run()
  else if (item.external && item.to)
    window.open(item.to, '_blank', 'noopener')
  else if (item.to)
    void navigateTo(item.to)
}

function onKeydown(event: KeyboardEvent) {
  const count = flat.value.length
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    if (count)
      activeIndex.value = (activeIndex.value + (event.key === 'ArrowDown' ? 1 : -1) + count) % count
  }
  else if (event.key === 'PageDown' || event.key === 'PageUp') {
    event.preventDefault()
    if (count)
      activeIndex.value = Math.max(0, Math.min(count - 1, activeIndex.value + (event.key === 'PageDown' ? 5 : -5)))
  }
  else if (event.key === 'Enter' && !event.isComposing) {
    event.preventDefault()
    choose(active.value)
  }
}

// no focus of its own here: the dialog puts it on the field, its first stop, once it has noted what had it before,
// which is where it goes back to on Escape
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <div class="flex items-center gap-3 border-b border-default px-4 py-1">
      <UIcon name="i-ph-magnifying-glass" class="size-5 shrink-0 text-muted" />
      <input
        v-model="query"
        type="text"
        role="combobox"
        autocomplete="off"
        spellcheck="false"
        aria-autocomplete="list"
        :aria-label="placeMode ? t('ask.placeDialogTitle') : t('shell.search')"
        :aria-expanded="flat.length > 0"
        :aria-controls="flat.length ? listId : undefined"
        :aria-activedescendant="activeId"
        :placeholder="placeMode ? t('ask.placePlaceholder') : t('shell.searchPlaceholder')"
        class="palette-input -ms-2 h-12 min-w-0 flex-1 bg-transparent px-2 text-base text-highlighted placeholder:text-dimmed"
        @keydown="onKeydown"
      >
      <!-- the way out for a touch screen reader, which cannot reach the overlay a sighted reader taps -->
      <UButton
        icon="i-ph-x"
        color="neutral"
        variant="ghost"
        size="sm"
        :aria-label="t('common.close')"
        data-testid="palette-close"
        @click="emit('done')"
      />
    </div>

    <div
      v-if="flat.length"
      :id="listId"
      role="listbox"
      tabindex="0"
      :aria-label="t('shell.results')"
      :aria-activedescendant="activeId"
      class="min-h-0 flex-1 overflow-y-auto overscroll-contain p-2"
      @keydown="onKeydown"
    >
      <div v-for="group in shown" :key="group.id" role="group" :aria-labelledby="`${listId}-group-${group.id}`">
        <div :id="`${listId}-group-${group.id}`" role="presentation" class="px-3 pb-1 pt-3 text-xs font-bold uppercase tracking-wider text-muted">
          {{ group.label }}
        </div>
        <div
          v-for="item in group.items"
          :id="optionId(item)"
          :key="item.id"
          role="option"
          :aria-selected="item === active"
          class="palette-option"
          @pointermove="activeIndex = flat.indexOf(item)"
          @click="choose(item)"
        >
          <ToolTile v-if="item.tile" :tile="item.tile as Tile" :icon="item.icon ?? ''" size="2rem" />
          <span v-else class="grid size-8 shrink-0 place-items-center rounded-lg bg-elevated" aria-hidden="true">
            <UIcon :name="item.icon ?? 'i-ph-arrow-right'" class="size-[1.125rem] text-toned" />
          </span>
          <span class="min-w-0 flex-1">
            <span class="block truncate font-semibold text-highlighted">{{ item.label }}</span>
            <span v-if="item.description" class="block truncate text-sm text-muted">{{ item.description }}</span>
          </span>
          <UIcon v-if="item.current" name="i-ph-check-bold" class="size-4 shrink-0 text-primary" />
          <UIcon v-else-if="item.external" name="i-ph-arrow-up-right" class="size-4 shrink-0 text-muted" />
          <UIcon v-else name="i-ph-arrow-elbow-down-left" class="palette-enter size-4 shrink-0 text-muted" />
        </div>
      </div>
    </div>
    <p v-else class="flex-1 px-6 py-10 text-center text-muted">
      {{ emptyText }}
    </p>

    <div class="flex items-center justify-between gap-4 border-t border-default px-4 py-2.5 text-xs text-muted">
      <p role="status" aria-live="polite" class="min-w-0">
        {{ status }}
      </p>
      <p class="shrink-0 max-sm:hidden" aria-hidden="true">
        {{ t('shell.keysHint') }}
      </p>
    </div>
  </div>
</template>

<style>
/* the field keeps the app's focus ring, drawn inside it so that it lies on the dialog's own colour */
.palette-input:focus-visible {
  outline-offset: -2px;
  border-radius: calc(var(--ui-radius) * 2);
}
.palette-option {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: calc(var(--ui-radius) * 2.5);
  cursor: pointer;
}
.palette-option[aria-selected="true"] {
  background: var(--ui-bg-elevated);
  box-shadow: inset 3px 0 0 var(--ui-primary);
}
.palette-enter {
  visibility: hidden;
}
.palette-option[aria-selected="true"] .palette-enter {
  visibility: visible;
}
@media (forced-colors: active) {
  .palette-option[aria-selected="true"] {
    outline: 2px solid Highlight;
    outline-offset: -2px;
  }
}
</style>
