<script setup lang="ts">
import type { Ref } from 'vue'
import type { Provider, Station, ValuesResponse } from '#shared/types/api'
import type { ChipApi, ChipContext, Choices } from '~/utils/ask/chip'
import type { ChipId } from '~/utils/ask/registry'
import { DateTime } from 'luxon'
import { describeFetchError } from '~/utils/api-error'
import { acceptsChoice } from '~/utils/ask/chip'
import { chipOf } from '~/utils/ask/registry'
import { TOOLS } from '~/utils/sections'
import { requestUnitTargets } from '~/utils/unit-targets'
import { unitsOfAnswer } from '~/utils/units'

// The answer to one of the home page's questions (GH-3518), worked out from what the backend answers, with the chart that
// backs it and the way into the tool that holds the data, filled in. Nothing is said that the data does not say:
// where it has no answer (a forecast that does not reach tomorrow, a station with too few summers), the panel says so.
//
// The panel holds no code of any one question (GH-3764): what a question fetches, how it answers and how it says so is its
// definition (utils/ask/chip.ts), and this reads that. It fetches, keeps the newest answer, and writes what the definition
// hands back.
const props = defineProps<{
  question: ChipId
  /** The values of the question's choices, as the link has them (`day` for the wind question) */
  choices: Choices
}>()
const emit = defineEmits<{ 'update:choice': [param: string, value: string] }>()

const { t } = useI18n()
const { place } = usePlace()
const formatLanguage = useFormatLanguage()
const { env, questionText } = useQuestions()
const { data: providerList } = useProviders()
const nuxtApp = useNuxtApp()

const chip = computed(() => chipOf(props.question)!)

type Status = 'loading' | 'ready' | 'empty' | 'error'
const status = ref<Status>('loading')
const failure = ref('')
// a Retry that works takes its notice, and the focus in it, away: the focus goes on to the question's heading
const failureNotice = useTemplateRef<HTMLElement>('failureNotice')
const heading = useTemplateRef<HTMLElement>('heading')
useFocusAfterRetry(() => status.value === 'error', failureNotice, heading)

/** What the definition's requests brought back, and the answer it made of that (null where the data holds none) */
const outcome = shallowRef<{ loaded: unknown, result: unknown } | null>(null)

// The units the app settings choose (GH-3980), read at each request: the question's own quantity (rain, millimetres; the
// summer, degrees; the wind, a speed) and whether the values are converted at all. The answer says which unit each
// parameter is in (`with_metadata`), and the sentences, the chart and its table are written in that; what the verdicts
// compare with is judged in canonical units (utils/answers.ts), so a verdict is the same in every unit.
const { settings } = useSettings()
/** The unit of the question's quantity the settings choose, and whether they convert: what a change of refetches the answer for */
const unitsAsked = computed(() => {
  const quantity = chip.value.quantity
  if (!quantity)
    return ''
  // where nothing is converted the unit chosen changes nothing of the answer
  return JSON.stringify(settings.value.convertUnits ? [true, requestUnitTargets(settings.value.units)[quantity]] : [false])
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
    choices: props.choices,
    now: () => DateTime.now(),
    formatLanguage: formatLanguage.value,
    unitTarget: quantity => requestUnitTargets(settings.value.units)[quantity]!,
  }
}

// the last request wins: a question or place changed while one was under way discards its answer
let asked = 0

async function ask() {
  const turn = ++asked
  status.value = 'loading'
  failure.value = ''
  outcome.value = null
  try {
    const here = context()
    // the chip asked, held across the await: a question changed meanwhile must not read this one's data
    const asking = chip.value
    const loaded = await asking.load(here, api)
    const result = asking.answer(loaded, here)
    // only the newest request's data is kept: an older one that returns after it must not replace it (GH-3980)
    if (turn !== asked)
      return
    outcome.value = { loaded, result }
    status.value = result ? 'ready' : 'empty'
  }
  catch (error) {
    if (turn !== asked)
      return
    failure.value = describeFetchError(error)
    status.value = 'error'
  }
}

// the question, the place, its choices (the wind's day), or the unit the settings choose for the question: a change of any
// of them asks again, and one under way is followed by the new one, whose answer is the only one shown
watch(() => [props.question, place.value.id, JSON.stringify(props.choices), unitsAsked.value], ask, { immediate: true })
onBeforeUnmount(() => {
  // an answer that comes after the panel is gone says nothing
  asked++
})

// ------------------------------------------------------------------------------------------------- what is said

/** How the answer is written: the definition's words for it, where there is an answer */
const view = computed(() => outcome.value?.result ? chip.value.present(outcome.value.result, outcome.value.loaded, env, props.choices) : null)
const verdict = computed(() => view.value?.verdict ?? '')
const emptyText = computed(() => chip.value.empty(outcome.value?.loaded ?? null, env, props.choices))

/** Who the data is from, in the words its licence asks for */
const attribution = computed(() => {
  const credit = chip.value.credit
  return credit ? (providerList.value?.providers.find(provider => provider.provider === credit.provider)?.attribution ?? credit.fallback) : ''
})

// ------------------------------------------------------------------------------------- the tools, filled in

const actions = computed(() => chip.value.actions(env, props.choices, outcome.value?.loaded ?? null))
/** A link into a tool carries the tool's tile; a reference page (`api`) has none */
const toolOf = (action: { tool?: string }) => TOOLS.find(tool => tool.key === action.tool)

// ------------------------------------------------------------------------------------------- the choices

const now = () => DateTime.now()
function onChoice(param: string, value: unknown) {
  const choice = chip.value.choices?.find(each => each.param === param)
  if (choice && acceptsChoice(choice, value, now()))
    emit('update:choice', param, String(value))
}
</script>

<template>
  <section class="answer" aria-labelledby="answer-heading" data-testid="answer">
    <header>
      <p class="text-sm font-medium text-muted">
        {{ t(chip.from) }}
      </p>
      <h3 id="answer-heading" ref="heading" tabindex="-1" class="mt-0.5 break-words outline-none text-xl font-bold leading-snug text-highlighted sm:text-2xl">
        {{ questionText(chip, choices) }}
      </h3>
    </header>

    <div v-for="choice in chip.choices" :key="choice.param" class="mt-4 flex flex-wrap items-center gap-2">
      <label :for="choice.inputId" class="text-sm font-medium">{{ t(choice.label) }}</label>
      <UInput :id="choice.inputId" type="date" :model-value="choices[choice.param]" :max="choice.latest(now())" class="w-44" @update:model-value="onChoice(choice.param, $event)" />
    </div>

    <!-- what a screen reader is told when the answer has come: the verdict, not the whole panel -->
    <p class="sr-only" role="status" data-testid="answer-status">
      {{ status === 'ready' ? verdict : status === 'empty' ? emptyText : '' }}
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
          :description="failure"
          :actions="[{ label: t('common.retry'), onClick: () => ask() }]"
        />
      </div>

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

        <p v-if="view?.note" class="text-sm text-muted">
          {{ view.note }}
        </p>
        <!-- the credit, and under it what wetterdienst did to the data (GH-3799): the values of these answers are the provider's own values -->
        <div v-if="chip.credit">
          <p class="text-sm text-muted">
            {{ attribution }}
          </p>
          <ProcessingNote class="mt-1" />
        </div>
      </div>
    </div>

    <!-- into the tool that holds the data, with the tool's tile: the colour says which tool it is -->
    <ul v-if="actions.length && status !== 'loading'" class="mt-6 flex flex-wrap gap-2" :aria-label="t('ask.leadsTo')" data-testid="answer-actions">
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
.answer-source:hover {
  border-color: var(--ui-border-accented);
  background: var(--ui-bg-elevated);
}
</style>
