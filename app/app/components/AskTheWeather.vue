<script setup lang="ts">
import type { Station } from '#shared/types/api'
import type { QuestionId } from '~/utils/questions'
import { DateTime } from 'luxon'
import { PLACE_NETWORK, placeOf } from '~/composables/usePlace'
import { lastBoxingDay } from '~/utils/answers'
import { isQuestion, QUESTIONS } from '~/utils/questions'

// Ask the weather (GH-3518): the questions people bring to a weather service, as suggestions on the home page, each
// answered here from live data (components/AnswerPanel.vue) and leading into the tool that holds that data, filled in.
// All about one place, a DWD station, which the reader can change (the place button opens a search of stations).
//
// The suggestions are buttons that are pressed or not (`aria-pressed`): one is open at a time, pressing it again
// closes it. The open one is in the link (`?ask=summer`, `&day=2025-12-26` for the wind question, `&place=02564` for
// a place the reader chose), so that an answer can be shared; a link without one opens none, and nothing is fetched
// until a question is asked. The focus stays on the button; the answer is announced by its live region.
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const { place, setPlace } = usePlace()
const { questionText } = useQuestions()

const question = computed<QuestionId | null>(() => isQuestion(route.query.ask) ? route.query.ask : null)
const day = computed(() => {
  const asked = route.query.day?.toString()
  return asked && /^\d{4}-\d{2}-\d{2}$/.test(asked) ? asked : lastBoxingDay(DateTime.now())
})

/** The link's query with `changes` put over it; a value of null leaves its key out */
function queryWith(changes: Record<string, string | null>) {
  const query: Record<string, string> = {}
  for (const [key, value] of Object.entries({ ...route.query, ...changes })) {
    if (typeof value === 'string')
      query[key] = value
  }
  return query
}

function toggle(id: QuestionId) {
  void router.replace({ query: queryWith({ ask: question.value === id ? null : id, day: id === 'wind' ? (route.query.day?.toString() ?? null) : null }) }).catch(() => {})
}

function setDay(next: string) {
  void router.replace({ query: queryWith({ ask: 'wind', day: next }) }).catch(() => {})
}

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
    const response = await $fetch<{ stations: Station[] }>('/api/stations', { query: { ...PLACE_NETWORK, stations: id }, ...RETRY_TRANSIENT })
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

// the place dialog: the search of stations (AppCommandPalette in its place mode). A place chosen is in the link too.
const placeOpen = ref(false)
const placeButton = ref<HTMLButtonElement | null>(null)
function onPlace(chosen: { id: string }) {
  placeOpen.value = false
  placeFailed.value = false
  void router.replace({ query: queryWith({ place: chosen.id }) }).catch(() => {})
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
      <span v-if="placeFailed" class="text-sm text-error" role="status">{{ t('ask.placeNotFound') }}</span>
    </div>

    <ul class="mt-4 flex flex-wrap gap-2" :aria-label="t('ask.questionsLabel')" data-testid="questions">
      <li v-for="entry in QUESTIONS" :key="entry.id" class="max-w-full">
        <button
          type="button"
          class="ask-chip"
          :aria-pressed="entry.id === question"
          :data-testid="`question-${entry.id}`"
          @click="toggle(entry.id)"
        >
          <UIcon :name="entry.icon" class="size-5 shrink-0" aria-hidden="true" />
          <span class="min-w-0 text-start">{{ questionText(entry.id, day) }}</span>
        </button>
      </li>
    </ul>

    <div ref="answer" class="ask-answer">
      <AnswerPanel v-if="question" :question="question" :day="day" @update:day="setDay" />
      <p v-else class="ask-idle" data-testid="ask-idle">
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
      :ui="{ content: 'sm:max-w-2xl sm:top-[12vh] sm:translate-y-0 max-h-[min(36rem,calc(100dvh-2rem))] sm:max-h-[min(36rem,calc(100dvh-16vh))]', header: 'sr-only', body: 'p-0 sm:p-0 flex flex-col min-h-0' }"
    >
      <template #body>
        <AppCommandPalette mode="place" @place="onPlace" @done="placeOpen = false" />
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
