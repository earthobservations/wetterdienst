<script setup lang="ts">
import type { Station } from '#shared/types/api'
import type { PlaceMatch } from '#shared/utils/places'
import type { PlaceInLink } from '~/utils/place-link'
import { DateTime } from 'luxon'
import UseMyLocation from '~/components/UseMyLocation.vue'
import { PLACE_NETWORK, placeOf, townPlace } from '~/composables/usePlace'
import { queryOfChoice, queryOfPress, queryWith, readChoices, readExplicit } from '~/utils/ask/chip'
import { chipIdOf, chipOf, CHIPS } from '~/utils/ask/registry'
import { distanceKm, formatDistance } from '~/utils/map-tool'
import { PLACE_QUERY_KEYS, placeOfQuery, queryOfPlace } from '~/utils/place-link'

// Ask the weather (GH-3518): the questions people bring to a weather service, as suggestions on the home page, each
// answered here from live data (components/AnswerPanel.vue) and leading into the tool that holds that data, filled in.
// All about one place, a DWD station, which the reader can change (the place button opens a search of stations).
// Each question is one definition (utils/ask/chip.ts, the registry in utils/ask/registry.ts): nothing here is about one
// of them.
//
// The suggestions are buttons that are pressed or not (`aria-pressed`): one is open at a time, pressing it again
// closes it. The open one is in the link (`?ask=season`, with a question's choices, `&season=winter&ref=1961-1990` for the season question, `&measure=sun&day=2025-12-26` for the day
// question, and `&place=02564` for a station the reader chose or `&lat=47.7610&lon=11.5596&placeName=Bad Tölz&placeRegion=Bayern, Germany` for a town found by its name), so that an answer can be shared; a link without one
// opens none, and nothing is fetched until a question is asked. The focus stays on the button; the answer is announced
// by its live region.
const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { place, setPlace } = usePlace()
const { questionText } = useQuestions()

const question = computed(() => chipIdOf(route.query.ask))
/** The values of every question's choices, as the link has them: a question's own where the link names none, or none that is one */
const choices = computed(() => {
  const now = DateTime.now()
  return Object.fromEntries(CHIPS.map(chip => [chip.id, readChoices(chip, route.query, now)]))
})

function toggle(id: string) {
  void router.replace({ query: queryOfPress(route.query, CHIPS, id, question.value) }).catch(() => {})
}

/** Only what the link names of the open question's choices: the data gives the rest (the season completed most recently that has enough of it) */
const explicit = computed(() => {
  const open = chipOf(question.value)
  return open ? readExplicit(open, route.query, DateTime.now()) : {}
})
/** The open question's choices as the panel settled them once its data came, for the button to say what the heading says */
const settled = ref<Record<string, string> | null>(null)
watch(question, () => {
  settled.value = null
})
function setChoice(param: string, value: string) {
  if (question.value)
    void router.replace({ query: queryOfChoice(route.query, question.value, param, value, explicit.value) }).catch(() => {})
}

/** The link's query with `changes` put over it; a value of null leaves its key out */
const queryWithChanges = (changes: Record<string, string | null>) => queryWith(route.query, changes)

// a question just opened is brought into view: on a phone its answer lies below the suggestions
const answer = ref<HTMLElement | null>(null)
watch(question, async (id) => {
  if (!id)
    return
  await nextTick()
  answer.value?.scrollIntoView({ block: 'nearest', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
})

// A link that names a place (`?place=02564`) asks about that station: it is looked up once, by its id, and kept as the
// reader's place
const placeFailed = ref(false)
watch(() => route.query.place, async (id) => {
  if (typeof id !== 'string' || !/^\w+$/.test(id) || id === place.value.id)
    return
  placeFailed.value = false
  try {
    const response = await $fetch<{ stations: Station[] }>('/api/stations', { query: { ...PLACE_NETWORK, stations: id }, ...API_FETCH })
    const found = response.stations?.[0] ? placeOf(response.stations[0]) : null
    if (found)
      setPlace(found)
    else
      placeFailed.value = true
  }
  catch {
    placeFailed.value = true
  }
}, { immediate: true })

/** The keys of the link that name a town, taken out where the place is a station or the reader's position */
const NO_TOWN = { lat: null, lon: null, placeName: null, placeRegion: null }

// A link that names a town (`?lat=&lon=&placeName=`, GH-3791) asks about it without asking the search of places again: the station nearest to it is looked up once
// (the stations request, ranked by the town's position) and the town is kept as the reader's place, with that station: the answers name it and how far it is.
const townProblem = ref(false)
/** The town that could not be given a station: said by name, so that the answer of the place before is not taken for its */
const townProblemName = ref('')
/** How many of the stations nearest to a town are asked for, to find the nearest one that still reports: twenty reach past a cluster of closed ones, and a town whose twenty nearest are all closed has none */
const TOWN_CANDIDATES = 20
/** The town of the link is being looked up: no question is asked about the place before it, which is not the town's */
const townPending = ref(false)
async function resolveTown(town: PlaceInLink): Promise<boolean> {
  const response = await $fetch<{ stations: Station[] }>('/api/stations', {
    // the nearest stations, the nearest first: the nearest one may have stopped reporting, and the town's station is the nearest that still does
    query: { ...PLACE_NETWORK, latitude: town.latitude, longitude: town.longitude, rank: TOWN_CANDIDATES },
    ...API_FETCH,
  })
  const found = townPlace(town, response.stations ?? [])
  if (!found)
    return false
  setPlace(found)
  return true
}
watch(() => [route.query.lat, route.query.lon, route.query.placeName, route.query.placeRegion].join('\n'), async () => {
  const named = placeOfQuery(route.query)
  if (!named)
    return
  const current = place.value
  // the town that is the place already is not looked up again
  if (current.town && current.name === named.name && Math.abs(current.latitude - named.latitude) < 0.00006 && Math.abs(current.longitude - named.longitude) < 0.00006)
    return
  townProblem.value = false
  townProblemName.value = named.name
  townPending.value = true
  try {
    townProblem.value = !(await resolveTown(named))
  }
  catch {
    townProblem.value = true
  }
  finally {
    townPending.value = false
  }
}, { immediate: true })

// "Here" (GH-3651): the reader's own position, given by "Use my location" and rounded to about 1 km, takes the DWD station
// nearest to it (the stations request, ranked by the position) as the place, for this visit only unless the reader ticked
// "remember". The address then names no other place; the position itself is in no address.
const { remember, position, checking, checkOnLoad } = useMyLocation()
// the stored position's station is this page's place as it loads: the permission is looked at before it is asked about
checkOnLoad()
// "Remember" is ticked after the press (GH-4011), when the place the position made is already in hand, for this visit:
// it is kept in the browser with the position, as it would have been had the box been ticked before
watch(remember, (on) => {
  if (on && place.value.fromPosition)
    setPlace(place.value)
})
const locating = ref(false)
const locatedText = ref('')
const locateProblem = ref('')
let locateRequest = 0
// "Forget my position" (GH-4014) takes back what the position made of the place (`useMyLocation`), and a lookup of the
// nearest station still on its way is dropped with it: its late answer would put the place back for the visit and the
// status would read as if the position were current. Synchronous, so that no answer lands between the forget and this.
watch(position, (now) => {
  if (now)
    return
  locateRequest++
  locating.value = false
  locatedText.value = ''
  locateProblem.value = ''
}, { flush: 'sync' })
async function onPosition(point: { latitude: number, longitude: number }) {
  const mine = ++locateRequest
  locating.value = true
  locatedText.value = ''
  locateProblem.value = ''
  try {
    const response = await $fetch<{ stations: Station[] }>('/api/stations', {
      query: { ...PLACE_NETWORK, latitude: point.latitude, longitude: point.longitude, rank: 1 },
      ...API_FETCH,
    })
    if (mine !== locateRequest)
      return
    const found = response.stations?.[0] ? placeOf(response.stations[0]) : null
    if (!found) {
      locateProblem.value = t('location.noneNear')
      return
    }
    setPlace({ ...found, fromPosition: true }, remember.value)
    placeFailed.value = false
    townProblem.value = false
    locatedText.value = t('location.here', { name: found.name, distance: formatDistance(distanceKm(point, found), locale.value) })
    if (route.query.place || PLACE_QUERY_KEYS.some(key => route.query[key]))
      void router.replace({ query: queryWithChanges({ place: null, ...NO_TOWN }) }).catch(() => {})
  }
  catch {
    if (mine === locateRequest)
      locateProblem.value = t('location.lookupFailed')
  }
  finally {
    if (mine === locateRequest)
      locating.value = false
  }
}

// the place dialog: the search of stations (AppCommandPalette in its place mode). A place chosen is in the link too.
const placeOpen = ref(false)
// the page behind the open place dialog is held on iOS, and a finger in it moves nothing behind it (GH-3761)
const placeHold = useModalDialogHold(placeOpen)
const placeButton = ref<HTMLButtonElement | null>(null)
function onPlace(chosen: { id: string }) {
  placeOpen.value = false
  placeFailed.value = false
  townProblem.value = false
  void router.replace({ query: queryWithChanges({ place: chosen.id, ...NO_TOWN }) }).catch(() => {})
}

/** A town found by its name (OpenStreetMap's search, GH-3791) is chosen: it becomes the place of the questions, with the station nearest to it, and is in the link */
async function onTown(match: PlaceMatch) {
  placeOpen.value = false
  placeFailed.value = false
  townProblem.value = false
  const town: PlaceInLink = { name: match.name, region: match.region, latitude: Number(match.latitude.toFixed(4)), longitude: Number(match.longitude.toFixed(4)) }
  townProblemName.value = town.name
  try {
    townProblem.value = !(await resolveTown(town))
  }
  catch {
    townProblem.value = true
  }
  if (!townProblem.value)
    void router.replace({ query: queryWithChanges({ place: null, ...queryOfPlace(town) }) }).catch(() => {})
}
</script>

<template>
  <section class="ask" aria-labelledby="ask-title" data-testid="ask">
    <div class="ask-head">
      <h2 id="ask-title" class="home-heading">
        {{ t('ask.title') }}
      </h2>
      <p class="text-muted">
        {{ t('ask.lead') }}
      </p>
    </div>

    <div class="mt-5 flex flex-wrap items-center gap-x-3 gap-y-2">
      <span class="text-sm font-medium text-muted">{{ t('ask.placeLabel') }}</span>
      <button
        ref="placeButton"
        type="button"
        class="ask-place"
        aria-haspopup="dialog"
        data-testid="place-button"
        @click="placeOpen = true"
      >
        <UIcon name="i-ph-map-pin" class="size-4 shrink-0" aria-hidden="true" />
        <span class="truncate">{{ place.name }}</span>
        <span class="sr-only">– {{ t('ask.placeChange') }}</span>
        <UIcon name="i-ph-caret-down" class="size-4 shrink-0 text-muted" aria-hidden="true" />
      </button>
      <span v-if="place.town && place.region" class="text-sm text-muted" data-testid="place-region">{{ place.region }}</span>
      <span v-if="placeFailed" class="text-sm text-error" role="status">{{ t('ask.placeNotFound') }}</span>
      <span v-if="townProblem" class="text-sm text-error" role="status" data-testid="town-problem">{{ t('ask.townNoStation', { place: townProblemName }) }}</span>
    </div>

    <UseMyLocation class="mt-3" :resolving="locating" :status="locatedText" :problem="locateProblem" @position="onPosition" />

    <ul class="mt-4 flex flex-wrap gap-2" :aria-label="t('ask.questionsLabel')" data-testid="questions">
      <li v-for="entry in CHIPS" :key="entry.id" class="max-w-full">
        <button
          type="button"
          class="ask-chip"
          :aria-pressed="entry.id === question"
          :data-testid="`question-${entry.id}`"
          @click="toggle(entry.id)"
        >
          <UIcon :name="entry.icon" class="size-5 shrink-0" aria-hidden="true" />
          <span class="min-w-0 text-start">{{ questionText(entry, entry.id === question && settled ? settled : choices[entry.id]!) }}</span>
        </button>
      </li>
    </ul>

    <div ref="answer" class="ask-answer">
      <!-- while the stored position is checked against the browser's permission (GH-4014), nothing is asked about the station it made -->
      <!-- a town that could not be given a station is no reason to answer for the place before: nothing is said of it until the reader picks -->
      <AnswerPanel v-if="question && !checking && !townPending && !townProblem" :question="question" :choices="choices[question]!" :explicit="explicit" @update:choice="setChoice" @effective="settled = $event" />
      <p v-else-if="!question" class="ask-idle" data-testid="ask-idle">
        <UIcon name="i-ph-cursor-click" class="size-5 shrink-0" aria-hidden="true" />
        {{ t('ask.idle') }}
      </p>
    </div>

    <!-- the search of places, in the same dialog as the header's search -->
    <UModal
      v-model:open="placeOpen"
      :title="t('ask.placeDialogTitle')"
      :description="t('ask.placeHint')"
      :close="false"
      :ui="{ content: 'app-vv-dialog sm:max-w-2xl sm:top-[12vh] sm:translate-y-0 max-h-[min(36rem,calc(100dvh-2rem))] sm:max-h-[min(36rem,calc(100dvh-16vh))]', header: 'sr-only', body: 'p-0 sm:p-0 flex flex-col min-h-0' }"
      @after:leave="placeHold.afterLeave"
    >
      <template #body>
        <AppCommandPalette mode="place" @place="onPlace" @town="onTown" @done="placeOpen = false" />
      </template>
    </UModal>
  </section>
</template>

<style>
.ask-head {
  max-width: 54rem;
}
/* the place: a field-like button, the edge of a control (3:1) */
.ask-place {
  display: inline-flex;
  min-height: 2.75rem;
  max-width: 100%;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.875rem;
  border-radius: 999px;
  border: 1px solid var(--ui-border-accented);
  background: var(--ui-bg);
  font-weight: 700;
  color: var(--ui-text-highlighted);
  transition: border-color 150ms;
}
.ask-place:hover {
  border-color: var(--ui-primary);
}
/* a suggestion: a pill with the question in it; pressed, it is the colour of action */
.ask-chip {
  display: inline-flex;
  min-height: 2.75rem;
  max-width: 100%;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 1.375rem;
  border: 1px solid var(--ui-border-accented);
  background: var(--ui-bg);
  font-weight: 600;
  line-height: 1.3;
  color: var(--ui-text-toned);
  transition: border-color 150ms, background-color 150ms, color 150ms;
}
.ask-chip:hover {
  border-color: var(--ui-primary);
  color: var(--ui-text-highlighted);
}
.ask-chip[aria-pressed="true"] {
  border-color: var(--ui-primary);
  background: var(--ui-primary);
  color: var(--ui-text-inverted);
}
.ask-chip[aria-pressed="true"]:hover {
  color: var(--ui-text-inverted);
}
@media (forced-colors: active) {
  .ask-chip[aria-pressed="true"] {
    border-color: Highlight;
    background: Highlight;
    color: HighlightText;
    forced-color-adjust: none;
  }
}
.ask-answer {
  margin-top: 1.25rem;
}
.ask-answer > .answer {
  padding: 1.25rem;
  border-radius: 1.25rem;
  border: 1px solid var(--ui-border);
  background: var(--ui-bg);
  box-shadow: 0 1px 2px rgb(11 26 51 / 0.04), 0 8px 24px -16px rgb(11 26 51 / 0.2);
}
@media (min-width: 40rem) {
  .ask-answer > .answer {
    padding: 1.75rem;
  }
}
.dark .ask-answer > .answer {
  box-shadow: none;
}
.ask-idle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--ui-text-muted);
}
</style>
