<script setup lang="ts">
import type { Ref } from 'vue'
import type { Provider, Station, ValuesResponse } from '#shared/types/api'
import type { ChipApi, ChipContext, Choices, SelectChoice } from '~/utils/ask/chip'
import type { ChipId } from '~/utils/ask/registry'
import { DateTime } from 'luxon'
import { townTooFar } from '~/composables/usePlace'
import { describeFetchError } from '~/utils/api-error'
import { acceptsChoice } from '~/utils/ask/chip'
import { chipOf } from '~/utils/ask/registry'
import { formatDistance } from '~/utils/map-tool'
import { PLACE_REACH_KM } from '~/utils/place-stations'
import { TOOLS } from '~/utils/sections'
import { requestUnitTargets } from '~/utils/unit-targets'
import { unitsOfAnswer } from '~/utils/units'
import { parseWarnings, WARNINGS_TIMEOUT_MS } from '~/utils/warnings'

// The answer to one of the home page's questions (GH-3518), worked out from what the backend answers, with the chart that
// backs it and the way into the tool that holds the data, filled in. Nothing is said that the data does not say:
// where it has no answer (a forecast that does not reach tomorrow, a station with too few summers), the panel says so.
//
// The panel holds no code of any one question (GH-3764): what a question fetches, how it answers and how it says so is its
// definition (utils/ask/chip.ts), and this reads that. It fetches, keeps the newest answer, and writes what the definition
// hands back.
const props = defineProps<{
  question: ChipId
  /** The values of the question's choices, as the link has them (`day` for the day question) */
  choices: Choices
  /** Only the choices the link names: where it names none, the data gives the default (the season completed most recently that has enough of it) */
  explicit?: Choices
}>()
const emit = defineEmits<{ 'update:choice': [param: string, value: string], 'effective': [choices: Choices] }>()

const { t, locale } = useI18n()
const { place } = usePlace()
const formatLanguage = useFormatLanguage()
const { env, questionText } = useQuestions()
const { data: providerList } = useProviders()
const nuxtApp = useNuxtApp()

const chip = computed(() => chipOf(props.question)!)

type Status = 'loading' | 'ready' | 'empty' | 'error' | 'far'
/** Where the requests are: under way, answered, or failed; `far`: none were made, since the station nearest to the town is too far to be its (GH-3791) */
const phase = ref<'loading' | 'loaded' | 'error' | 'far'>('loading')

/**
 * The station a question reads (`readsStation`) for a town (GH-3791): which it is and how far from the town, said under the answer. Where it is farther than
 * `PLACE_REACH_KM` nothing is asked and the panel says so, names the nearest and gives no answer: a distant station is never stretched into the answer for a place.
 */
const town = computed(() => chip.value.readsStation ? place.value.town?.station ?? null : null)
const townFar = computed(() => !!town.value && townTooFar(place.value))
const townDistance = computed(() => town.value ? formatDistance(town.value.distanceKm, locale.value) : '')
const townStation = computed(() => town.value ? `${town.value.name} (${town.value.id})` : '')
const farText = computed(() => town.value ? t('ask.far', { place: place.value.name, reach: PLACE_REACH_KM, station: townStation.value, distance: townDistance.value }) : '')
const failure = ref('')
/** What the definition's requests brought back; null while they are under way */
/** and the chip it was fetched for: a question switched meanwhile must not have the new chip read the old one's data */
const fetched = shallowRef<{ loaded: unknown, chip: string } | null>(null)
/** What was fetched for the chip that is open now, or null */
const fetchedHere = computed(() => fetched.value && fetched.value.chip === chip.value.id ? fetched.value : null)

/**
 * The answer, worked out from what was fetched and the choices as they are now: a choice the requests do not read (the season, the normal)
 * changes the answer here and asks for nothing. Null where the data holds none.
 */
const answered = computed<{ result: unknown } | { error: string } | null>(() => {
  if (!fetchedHere.value)
    return null
  try {
    return { result: chip.value.answer(fetchedHere.value.loaded, context()) }
  }
  catch (error) {
    return { error: describeFetchError(error) }
  }
})
const status = computed<Status>(() => {
  if (phase.value !== 'loaded')
    return phase.value
  // data of another question, for the moment before the new one is asked: nothing is said of it
  if (!fetchedHere.value)
    return 'loading'
  return !answered.value || 'error' in answered.value ? 'error' : answered.value.result ? 'ready' : 'empty'
})
const failureText = computed(() => failure.value || (answered.value && 'error' in answered.value ? answered.value.error : ''))
// a Retry that works takes its notice, and the focus in it, away: the focus goes on to the question's heading
const failureNotice = useTemplateRef<HTMLElement>('failureNotice')
const heading = useTemplateRef<HTMLElement>('heading')
useFocusAfterRetry(() => status.value === 'error', failureNotice, heading)

/** What the definition's requests brought back, and the answer it made of that (null where the data holds none) */
const outcome = computed<{ loaded: unknown, result: unknown } | null>(() =>
  fetchedHere.value && answered.value && 'result' in answered.value ? { loaded: fetchedHere.value.loaded, result: answered.value.result } : null)

// ------------------------------------------------------------------------------------------- the choices as they are

/**
 * The choices once the data is there: what the link names, but a name the data cannot answer (a season or a normal the station has too
 * few seasons of) and a default that depends on the data are the definition's to settle; its note says why, and why an option is greyed out
 */
const resolved = computed(() => {
  const found = chip.value.resolveChoices
  return found && fetchedHere.value ? found(fetchedHere.value.loaded, props.choices, props.explicit ?? {}, env) : { choices: props.choices, note: '' }
})
const effective = computed(() => resolved.value.choices)
// the line under the choices: a polite status, so that a screen reader says it when it comes or changes
const choiceNote = computed(() => resolved.value.note)
watch(effective, choices => emit('effective', choices), { immediate: true })

// The units the app settings choose (GH-3980), read at each request: the question's own quantity (rain, millimetres; the
// summer, degrees; the wind, a speed) and whether the values are converted at all. The answer says which unit each
// parameter is in (`with_metadata`), and the sentences, the chart and its table are written in that; what the verdicts
// compare with is judged in canonical units (utils/answers.ts), so a verdict is the same in every unit.
const { settings } = useSettings()
/** The unit of the question's quantity the settings choose, and whether they convert: what a change of refetches the answer for */
const unitsAsked = computed(() => {
  const quantities = [chip.value.quantity ?? []].flat()
  if (!quantities.length)
    return ''
  // where nothing is converted the unit chosen changes nothing of the answer
  const targets = requestUnitTargets(settings.value.units)
  return JSON.stringify(settings.value.convertUnits ? [true, ...quantities.map(quantity => targets[quantity])] : [false])
})

// The requests a definition makes, with the app's settings and error handling
const api: ChipApi = {
  async values(query) {
    const response = await $fetch<ValuesResponse>('/api/values', {
      query: { shape: 'long', humanize: 'true', convert_units: String(settings.value.convertUnits), with_metadata: 'true', ...query },
      ...API_FETCH,
    })
    return { readings: response.values ?? [], units: unitsOfAnswer(response) }
  },
  async stations(query) {
    return (await $fetch<{ stations: Station[] }>('/api/stations', { query, ...API_FETCH })).stations ?? []
  },
  async providers() {
    return providerList.value?.providers ?? (await $fetch<{ providers: Provider[] }>('/api/providers', API_FETCH)).providers
  },
  coverage: query => $fetch('/api/coverage', { query, ...API_FETCH }),
  // DWD's warnings: the whole snapshot of the community product, which the answer reads the place's warnings from (GH-4295)
  async alerts(product) {
    return parseWarnings(await $fetch('/api/alerts', { query: { granularity: 'community', language: product }, timeout: WARNINGS_TIMEOUT_MS, ...API_FETCH }))
  },
  // what is kept for the visit (the promise is kept, as the server settings' is): a state of the page under the chip's own key
  kept<T>(key: string, load: () => Promise<T>): Promise<T> {
    const kept = nuxtApp.runWithContext(() => useState<Promise<unknown> | undefined>(key, () => undefined)) as Ref<Promise<unknown> | undefined>
    kept.value ??= load().catch((error) => {
      // a failed lookup is asked again by the next question, Retry included
      kept.value = undefined
      throw error
    })
    return kept.value as Promise<T>
  },
}

function context(): ChipContext {
  return {
    place: place.value,
    choices: effective.value,
    now: () => DateTime.now(),
    formatLanguage: formatLanguage.value,
    locale: locale.value,
    unitTarget: quantity => requestUnitTargets(settings.value.units)[quantity]!,
  }
}

// the last request wins: a question or place changed while one was under way discards its answer
let asked = 0

async function ask() {
  const turn = ++asked
  failure.value = ''
  fetched.value = null
  if (townFar.value) {
    phase.value = 'far'
    return
  }
  phase.value = 'loading'
  try {
    // the chip asked, held across the await: a question changed meanwhile must not read this one's data
    const asking = chip.value
    const loaded = await asking.load(context(), api)
    // only the newest request's data is kept: an older one that returns after it must not replace it (GH-3980)
    if (turn !== asked)
      return
    fetched.value = { loaded, chip: asking.id }
    phase.value = 'loaded'
  }
  catch (error) {
    if (turn !== asked)
      return
    failure.value = describeFetchError(error)
    phase.value = 'error'
  }
}

/** The choices the requests read, as one text: the whole of them, or the ones the definition says its `load` reads (the others change the answer, not the request) */
const requested = computed(() => {
  const names = chip.value.loadedBy
  return JSON.stringify(names ? names.map(name => props.choices[name]) : props.choices)
})

// the question, the place, its choices that the requests read (the day question's day), or the unit the settings choose for the question: a change
// of any of them asks again, and one under way is followed by the new one, whose answer is the only one shown
watch(() => [props.question, place.value.id, townFar.value, requested.value, unitsAsked.value], ask, { immediate: true })
onBeforeUnmount(() => {
  // an answer that comes after the panel is gone says nothing
  asked++
})

// ------------------------------------------------------------------------------------------------- what is said

/** How the answer is written: the definition's words for it, where there is an answer */
const view = computed(() => outcome.value?.result ? chip.value.present(outcome.value.result, outcome.value.loaded, env, effective.value) : null)
const verdict = computed(() => view.value?.verdict ?? '')
const emptyText = computed(() => chip.value.empty(outcome.value?.loaded ?? null, env, effective.value))

// What the polite status says: the verdict, or why there is none. A choice that changes the answer but not its words (a season whose verdict
// is the same sentence) is still announced: the same words are cleared and then set again, which a screen reader reads as a change.
const statusText = computed(() => status.value === 'ready' ? verdict.value : status.value === 'empty' ? emptyText.value : status.value === 'far' ? farText.value : '')
const announced = ref('')
let announceTimer: ReturnType<typeof setTimeout> | undefined
watch([statusText, () => JSON.stringify(effective.value)], () => {
  clearTimeout(announceTimer)
  const next = statusText.value
  if (next && next === announced.value) {
    announced.value = ''
    announceTimer = setTimeout(() => {
      announced.value = next
    }, 100)
  }
  else {
    announced.value = next
  }
}, { immediate: true })
onBeforeUnmount(() => clearTimeout(announceTimer))

// ------------------------------------------------------------------------------------- the tools, filled in

const actions = computed(() => chip.value.actions(env, effective.value, outcome.value?.loaded ?? null))
/** A link into a tool carries the tool's tile; a reference page (`api`) has none */
const toolOf = (action: { tool?: string }) => TOOLS.find(tool => tool.key === action.tool)

// ------------------------------------------------------------------------------------------- the choices

const now = () => DateTime.now()
function onChoice(param: string, value: unknown) {
  const choice = chip.value.choices?.find(each => each.param === param)
  if (choice && acceptsChoice(choice, value, now()))
    emit('update:choice', param, String(value))
}
/** The options of a choice of a few values, from what was fetched (null before it came): a disabled one says why in its text */
const optionsOf = (choice: SelectChoice) => choice.options(env, fetchedHere.value?.loaded ?? null, effective.value)
/** A choice made in a select: the value of the option, which the choice accepts (or the control keeps its own) */
const onSelect = (param: string, event: Event) => onChoice(param, (event.target as HTMLSelectElement).value)
</script>

<template>
  <section class="answer" aria-labelledby="answer-heading" data-testid="answer">
    <header>
      <p class="text-sm font-medium text-muted">
        {{ t(chip.from) }}
      </p>
      <h3 id="answer-heading" ref="heading" tabindex="-1" class="mt-0.5 break-words outline-none text-xl font-bold leading-snug text-highlighted sm:text-2xl">
        {{ questionText(chip, effective) }}
      </h3>
    </header>

    <!-- what the reader chooses about the question: real controls with their labels, beside the question's button and not in it -->
    <div v-if="chip.choices?.length" class="mt-4 flex flex-wrap gap-x-5 gap-y-3" data-testid="answer-choices">
      <div v-for="choice in chip.choices" :key="choice.param" class="flex min-w-0 max-w-full flex-wrap items-center gap-2">
        <label :for="choice.inputId" class="text-sm font-medium">{{ t(choice.label) }}</label>
        <UInput v-if="choice.kind === 'date'" :id="choice.inputId" type="date" :model-value="effective[choice.param]" :max="choice.latest(now())" class="w-44" @update:model-value="onChoice(choice.param, $event)" />
        <!-- a native select: a disabled option says why in its own text, and it reads and works the same on every screen reader and touch screen -->
        <select
          v-else
          :id="choice.inputId"
          class="answer-select"
          :value="effective[choice.param]"
          :data-testid="`choice-${choice.param}`"
          @change="onSelect(choice.param, $event)"
        >
          <option v-for="option in optionsOf(choice)" :key="option.value" :value="option.value" :disabled="option.disabled || undefined">
            {{ option.label }}
          </option>
        </select>
      </div>
    </div>
    <!-- why an option is greyed out, and why a choice named is not the one shown: a polite status, in the page always so that its change is announced -->
    <p v-if="chip.resolveChoices" class="text-sm text-muted" :class="choiceNote ? 'mt-3' : ''" role="status" data-testid="choice-note">
      {{ choiceNote }}
    </p>

    <!-- what a screen reader is told when the answer has come: the verdict, not the whole panel -->
    <p class="sr-only" role="status" data-testid="answer-status">
      {{ announced }}
    </p>

    <div class="mt-5">
      <div v-if="status === 'loading'" role="status" class="space-y-3">
        <p class="flex items-center gap-2 text-muted">
          <UIcon name="i-ph-circle-notch" class="size-5 animate-spin text-primary" />
          {{ t('ask.working') }}
        </p>
        <div class="h-8 w-2/3 animate-pulse rounded-md bg-elevated" aria-hidden="true" />
        <div class="h-36 animate-pulse rounded-md bg-elevated" aria-hidden="true" />
      </div>

      <div v-else-if="status === 'error'" ref="failureNotice">
        <UAlert
          color="error"
          variant="subtle"
          icon="i-ph-warning-circle"
          :title="t('ask.failed')"
          :description="failureText"
          :actions="[{ label: t('common.retry'), onClick: () => ask() }]"
        />
      </div>

      <!-- a town with no station near it (GH-3791): said plainly, the nearest named, and no answer made of a station that is another place's -->
      <p v-else-if="status === 'far'" class="flex items-start gap-2 text-toned" data-testid="answer-far">
        <UIcon name="i-ph-map-pin" class="mt-0.5 size-5 shrink-0 text-muted" aria-hidden="true" />
        {{ farText }}
      </p>

      <p v-else-if="status === 'empty'" class="flex items-start gap-2 text-toned">
        <UIcon name="i-ph-question" class="mt-0.5 size-5 shrink-0 text-muted" />
        {{ emptyText }}
      </p>

      <div v-else class="space-y-5">
        <div>
          <p class="font-extrabold text-highlighted" :class="chip.verdictStyle === 'sentence' ? 'text-xl sm:text-2xl' : 'text-2xl sm:text-3xl'" data-testid="answer-verdict">
            {{ verdict }}
          </p>
          <p v-for="line in view?.details" :key="line" class="mt-1.5 text-toned">
            {{ line }}
          </p>
        </div>

        <AnswerBars
          v-if="view?.chart"
          :bars="view.chart.bars"
          :caption="view.chart.caption"
          :unit="view.chart.unit"
          :diverging="view.chart.diverging"
          :every="view.chart.every"
          :emphasis="view.chart.emphasis"
          :row-label="view.chart.rowLabel"
        />

        <ul v-if="view?.list" class="grid gap-2 sm:grid-cols-2" :data-testid="view.list.testId">
          <li v-for="item in view.list.items" :key="item.key">
            <NuxtLink :to="item.to" class="answer-source">
              <span class="text-xl leading-none" aria-hidden="true">{{ item.mark }}</span>
              <span class="min-w-0 flex-1">
                <span class="block font-semibold text-highlighted">{{ item.title }}</span>
                <span class="block break-words text-xs text-muted">{{ item.detail }}<template v-if="item.place"> · <span class="font-medium text-toned">{{ item.place }}</span></template></span>
              </span>
              <UIcon name="i-ph-arrow-right" class="size-4 shrink-0 text-muted" />
            </NuxtLink>
          </li>
        </ul>

        <!-- what the provider wrote, quoted as it wrote it, apart from the answer's own sentences (a warning of DWD, GH-4295): the text is the provider's, in its language -->
        <ul v-if="view?.quotes?.length" class="answer-quotes" :aria-label="t('ask.quotesLabel')" data-testid="answer-quotes">
          <li v-for="quote in view.quotes" :key="quote.key" class="answer-quote" data-testid="answer-quote">
            <h4 class="font-semibold text-highlighted">
              {{ quote.heading }}
            </h4>
            <p v-for="fact in quote.facts" :key="fact" class="text-sm text-toned">
              {{ fact }}
            </p>
            <div v-if="quote.paragraphs.length" class="answer-quote-text" :lang="quote.lang">
              <p v-for="paragraph in quote.paragraphs" :key="paragraph">
                {{ paragraph }}
              </p>
            </div>
            <p v-if="quote.note" class="text-sm text-muted" data-testid="answer-quote-note">
              {{ quote.note }}
            </p>
          </li>
        </ul>

        <p v-if="view?.note" class="text-sm text-muted">
          {{ view.note }}
        </p>
        <!-- for a town: the station the answer is read at, and how far it is (GH-3791) -->
        <p v-if="town" class="text-sm text-muted" data-testid="answer-station">
          {{ t('ask.stationUsed', { station: townStation, place: place.name, distance: townDistance }) }}
        </p>
        <!-- the credit, and under it what wetterdienst did to the data (GH-3799): the values of these answers are the provider's own values -->
        <ProviderCredit v-if="chip.credit" :provider="chip.credit.provider" :fallback="chip.credit.fallback" />
        <!-- how the answer was worked out and what it rests on (GH-3764): the definition's explanation, for any chip -->
        <AnswerExplanation v-if="outcome" :key="chip.id" :chip="chip" :loaded="outcome.loaded" :result="outcome.result" :choices="effective" />
      </div>
    </div>

    <!-- into the tool that holds the data, with the tool's tile: the colour says which tool it is -->
    <ul v-if="actions.length && status !== 'loading' && status !== 'far'" class="mt-6 flex flex-wrap gap-2" :aria-label="t('ask.leadsTo')" data-testid="answer-actions">
      <li v-for="action in actions" :key="action.key">
        <NuxtLink :to="action.to" class="answer-action">
          <ToolTile v-if="toolOf(action)" :tile="toolOf(action)!.tile" :icon="toolOf(action)!.icon" size="1.75rem" />
          <UIcon v-else name="i-ph-code" class="size-5 shrink-0 text-toned" />
          <span>{{ action.label }}</span>
          <UIcon name="i-ph-arrow-right" class="size-4 shrink-0" />
        </NuxtLink>
      </li>
    </ul>
  </section>
</template>

<style scoped>
/* a select of the question's choices: the edge of a control (3:1), a touch target of 44 px, never wider than the panel */
.answer-select {
  min-height: 2.75rem;
  max-width: 100%;
  padding: 0.375rem 0.75rem;
  border-radius: 0.5rem;
  border: 1px solid var(--ui-border-accented);
  background: var(--ui-bg);
  color: var(--ui-text-highlighted);
  font-size: 0.875rem;
  cursor: pointer;
}
.answer-select:hover {
  border-color: var(--ui-primary);
}
.answer-action {
  display: inline-flex;
  min-height: 2.75rem;
  align-items: center;
  gap: 0.625rem;
  padding: 0.375rem 0.875rem 0.375rem 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--ui-border-accented);
  background: var(--ui-bg);
  font-weight: 600;
  color: var(--ui-text-highlighted);
  transition: border-color 150ms, background-color 150ms;
}
.answer-action:hover {
  border-color: var(--ui-primary);
  background: var(--ui-bg-elevated);
}
.answer-source {
  display: flex;
  min-height: 2.75rem;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 0.75rem;
  border: 1px solid var(--ui-border);
  transition: border-color 150ms, background-color 150ms;
}
.answer-quotes {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.answer-quote {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  padding: 0.75rem 0.875rem;
  border: 1px solid var(--ui-border);
  border-radius: 0.75rem;
}
/* DWD's own words: set off by a rule at the edge, line breaks kept (its instructions are lists) */
.answer-quote-text {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding-inline-start: 0.75rem;
  border-inline-start: 3px solid var(--ui-border-accented);
  white-space: pre-line;
  overflow-wrap: anywhere;
  color: var(--ui-text-toned);
}
.answer-source:hover {
  border-color: var(--ui-border-accented);
  background: var(--ui-bg-elevated);
}
</style>
