<script setup lang="ts">
import type { Station } from '#shared/types/api'
import type { Place } from '~/composables/usePlace'
import type { PaletteGroup, PaletteItem } from '~/utils/palette'
import type { Hit } from '~/utils/search-index'
import type { Tile } from '~/utils/sections'
import { DateTime } from 'luxon'
import { PLACE_NETWORK, placeOf } from '~/composables/usePlace'
import { readChoices } from '~/utils/ask/chip'
import { coordinatesText, hemispheresOf, mapAtPoint, parseCoordinates } from '~/utils/coordinates'
import { countsByGroup, filterGroups, GROUP_LIMITS, itemOfHit, limitItems, orderGroups } from '~/utils/palette'
import { EXTERNAL, HOME, LEGAL, MAP_TOOL, PROJECT, REFERENCE, TOOLS } from '~/utils/sections'

// The command palette of the search (GH-3518), inside the dialog of AppSearch.vue. One field that goes to every page
// (each with the line that says what it is for), to a provider's page, to the forecast of a station found by its
// name or to the map opened on it (GH-3650), and that changes the theme or the language.
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
// The words of the app (GH-3790) are matched here too, in the browser: a full-text index of the pages built with the app
// (`modules/search-index`), the glossary the backend gives, the questions of "Ask the weather" and a position typed in
// (`utils/coordinates.ts`). All of it is loaded when the search is opened, not before (`useSiteSearch`). Each kind is a
// group that shows a few results and, where its page has more, a last option that opens the page. The order of the groups
// is `GROUP_ORDER` of utils/palette.ts: a point, the stations, the rest.
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
const { questionText } = useQuestions()
// the words of the app are for the search; the place of the questions asks for stations only
const site = props.mode === 'place' ? null : useSiteSearch()

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
      ...API_ANSWER,
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

// ---- the groups ----------------------------------------------------------------------------------------------------

/** What is typed, for the words of the app */
const text = computed(() => query.value.trim())
/** A position typed in, with the letters this language writes the hemispheres with */
const point = computed(() => text.value ? parseCoordinates(text.value, hemispheresOf(locale.value)) : null)

const placeGroup = computed<PaletteGroup[]>(() => point.value
  ? [{
      id: 'place',
      label: t('shell.placeGroup'),
      items: [{
        id: 'place-point',
        label: coordinatesText(point.value),
        description: t('shell.placeOnMap'),
        icon: MAP_TOOL.icon,
        tile: MAP_TOOL.tile,
        to: mapAtPoint(point.value),
      }],
    }]
  : [])

/** The icon of each kind of result of the app's own words: the page's, as the reference and the project show it */
const HIT_ICONS: Record<string, string> = {
  measurement: 'i-ph-ruler',
  method: 'i-ph-seal-check',
  glossary: 'i-ph-book-open-text',
  settings: 'i-ph-gear-six',
  about: 'i-ph-info',
  support: 'i-ph-heart',
}

/** The last item of a group that shows a few of more: it opens the page that has them all */
function moreItem(id: string, page: string, to: string) {
  return (hidden: number): PaletteItem => ({ id: `more-${id}`, label: t('shell.moreIn', { count: hidden, page }), icon: 'i-ph-arrow-right', to, more: true })
}

/** The few results of a kind, from the entries of the pages (`useSiteSearch`) */
function wordGroup(id: string, label: string, hits: Hit[], more: (hidden: number) => PaletteItem): PaletteGroup {
  return { id, label, items: limitItems(hits.map(hit => itemOfHit(hit, HIT_ICONS[hit.kind] ?? 'i-ph-arrow-right')), GROUP_LIMITS[id] ?? 3, more) }
}

/** The words of the app that answer what is typed: the entries and methods, the glossary, the settings; none before a word is typed */
const wordGroups = computed<PaletteGroup[]>(() => {
  if (!site || !text.value)
    return []
  const pages = site.findPages(text.value)
  const of = (...kinds: string[]) => pages.filter(hit => kinds.includes(hit.kind))
  return [
    wordGroup('measurement', t('measurement.title'), of('measurement'), moreItem('measurement', t('measurement.title'), '/measurement')),
    wordGroup('method', t('methods.title'), of('method'), moreItem('method', t('methods.title'), '/methods')),
    wordGroup('glossary', t('glossary.title'), site.findGlossary(text.value), moreItem('glossary', t('glossary.title'), `/glossary?q=${encodeURIComponent(text.value)}`)),
    wordGroup('settings', t('common.settings'), of('settings'), moreItem('settings', t('common.settings'), '/settings')),
  ]
})

/** The questions of "Ask the weather", worded for the place the reader has chosen; each opens its question on the home page */
const questionItems = computed<PaletteItem[]>(() => {
  if (!site || !text.value)
    return []
  const now = DateTime.now()
  return site.chips.value.map(chip => ({
    id: `question-${chip.id}`,
    label: questionText(chip, readChoices(chip, {}, now)),
    description: t(chip.from),
    keywords: chip.id,
    icon: chip.icon,
    to: `/?ask=${chip.id}`,
  }))
})

/** What of the pages the search lists in a group of its own, matched here by `scoreOf` */
const pageGroups = computed<PaletteGroup[]>(() => {
  const searching = query.value.trim().length > 0
  return [
    { id: 'tools', label: t('shell.tools'), items: TOOLS.map(section => page(section)) },
    { id: 'questions', label: t('ask.title'), items: questionItems.value },
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

// the stations are the backend's matches already, as the places are; the pages and actions are matched here
const stationGroups = computed<PaletteGroup[]>(() => [
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
  // the same stations, opened on the map: the map takes a forecast station of its address (`?station=`)
  {
    id: 'stations-map',
    label: t('shell.stationsMap'),
    items: stations.value.map(station => ({
      id: `station-map-${station.station_id}`,
      label: station.name ?? station.station_id,
      description: t('shell.stationOnMap', { id: station.station_id }),
      icon: MAP_TOOL.icon,
      tile: MAP_TOOL.tile,
      to: `${MAP_TOOL.to}?station=${station.station_id}`,
    })),
  },
])

const placesGroup = computed<PaletteGroup>(() => ({
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
}))

const shown = computed<PaletteGroup[]>(() => {
  // the places are the backend's matches, as they are
  if (placeMode.value)
    return [placesGroup.value].filter(group => group.items.length)
  const matched = filterGroups(pageGroups.value, query.value)
  // the cards of About and Support, found by their words, are with the pages of the project
  const cards = site && text.value ? site.findPages(text.value).filter(hit => hit.kind === 'about' || hit.kind === 'support').map(hit => itemOfHit(hit, HIT_ICONS[hit.kind]!)) : []
  if (cards.length) {
    const project = matched.find(group => group.id === 'project')
    const items = limitItems(cards, GROUP_LIMITS.project!)
    if (project)
      project.items = [...project.items, ...items]
    else
      matched.push({ id: 'project', label: t('shell.project'), items })
  }
  return orderGroups([...placeGroup.value, ...stationGroups.value, ...matched, ...wordGroups.value])
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
  // what is typed is searched when the index of the pages is there (GH-3790)
  if (text.value && site?.loading.value && !flat.value.length)
    return t('common.loading')
  // the count of the results, not of the "more" options that lead on from a group, then how many each group has
  const count = t('shell.resultsCount', flat.value.filter(item => !item.more).length)
  const typed = text.value.length
  const groupsSaid = typed > 0 && flat.value.length ? `${count}. ${countsByGroup(shown.value, (group, number) => t('shell.resultsIn', { group, count: number }))}` : count
  return typed > 0 && typed < MIN_STATION_QUERY.value ? `${groupsSaid}. ${t('shell.stationsHint')}` : groupsSaid
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
