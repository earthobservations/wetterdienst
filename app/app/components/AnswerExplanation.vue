<script setup lang="ts">
import type { MeasurementTexts } from '../../i18n/measurement/types'
import type { MethodTexts } from '../../i18n/methods/types'
import type { Chip, Choices } from '~/utils/ask/chip'
import { citationText, fill, loadMeasurementTexts, loadMethodTexts, methodPath, numberLineText, ruleParams, textLanguageOf, workPath } from '~/utils/ask/method-text'
import { measurementPath, parameterPatterns } from '~/utils/measurement'
import { safeHref, termsOfProvider } from '~/utils/provider-credit'

// "How was this worked out?" under an answer of Ask the weather (GH-3764, step 1b): a button that opens a region, as a
// real `<button aria-expanded>` that controls it, not a hover. It says, for the chip the answer is of: the numbers of this
// answer (the station and its distance, the period and how many years or days, the thresholds), the rules each with its source
// or the mark that it is wetterdienst's own, the data (provider, dataset, licence, a link that opens the same data in the Explorer),
// the terms with links to "How weather is measured", and the limits. The full method and the works are on the page of the
// methods (`pages/methods.vue`), which this links to. The chip's definition holds the structure (`ChipExplanation`), the
// words are in `i18n/methods/`; nothing here is about one chip.
//
// The words are long texts in German and English, as on the page "How weather is measured": a reader of another
// language sees English (German for Low German and Luxembourgish) with the same note, and the text says so with `lang`. They are
// loaded when the disclosure is first opened, so the home page does not carry them until then.
const props = defineProps<{
  chip: Chip
  /** What the answer was worked out from */
  loaded: unknown
  result: unknown
  choices: Choices
}>()

const { t, locale } = useI18n()
const { env } = useQuestions()
const { data: providerList } = useProviders()

const open = ref(false)
const buttonId = useId()
const regionId = useId()

const own = computed(() => locale.value === 'de' || locale.value === 'en')
const textLanguage = computed(() => textLanguageOf(locale.value))
const lang = computed(() => own.value ? undefined : textLanguage.value)
const note = computed(() => own.value ? undefined : t(textLanguage.value === 'de' ? 'measurement.untranslatedDe' : 'measurement.untranslatedEn'))

const texts = shallowRef<{ language: string, method: MethodTexts, measurement: MeasurementTexts } | null>(null)
const failed = ref(false)
// the texts of the language, once it is first opened and again if the language is changed while it is open
watchEffect(async () => {
  if (!open.value)
    return
  const language = textLanguage.value
  if (texts.value?.language === language)
    return
  try {
    const [method, measurement] = await Promise.all([loadMethodTexts(language), loadMeasurementTexts(language)])
    if (language === textLanguage.value)
      texts.value = { language, method, measurement }
    failed.value = false
  }
  catch {
    failed.value = true
  }
})

const explanation = computed(() => props.chip.explanation)
const method = computed(() => texts.value?.method.chips[props.chip.id])
/** The values of the rules, written in the language of the text: the numbers that its steps, rules and limits say */
const params = computed(() => ruleParams(explanation.value.rules, textLanguage.value))

const numbers = computed(() => explanation.value.numbers(props.result, props.loaded, env, props.choices).map(line => ({ id: line.id, text: numberLineText(texts.value!.method, props.chip, line) })))

const rules = computed(() => explanation.value.rules.map((rule) => {
  const words = method.value?.rules[rule.id]
  return {
    ...rule,
    text: words ? fill(words.text, params.value) : '',
    reason: words?.reason ? fill(words.reason, params.value) : '',
    cites: rule.cites.map(citation => ({ key: `${citation.work}-${citation.at ?? ''}`, label: citationText(citation), to: workPath(citation.work) })),
  }
}))

const provider = computed(() => providerList.value?.providers.find(each => each.provider === explanation.value.data.provider))
const terms = computed(() => termsOfProvider(providerList.value?.providers, explanation.value.data.provider))
const licence = computed(() => terms.value?.license ? { name: terms.value.license.name, href: safeHref(terms.value.license.url) } : null)
const explorer = computed(() => explanation.value.data.open(env, props.choices, props.loaded))

const topics = computed(() => explanation.value.topics.map(topic => ({
  topic,
  title: texts.value!.measurement[topic].title,
  summary: texts.value!.measurement[topic].summary,
  glossary: parameterPatterns(topic).length > 0,
})))

const link = 'text-primary-700 dark:text-primary-500 underline hover:no-underline'
</script>

<template>
  <div class="explanation" data-testid="explanation">
    <h4 class="m-0 text-base font-normal">
      <button
        :id="buttonId"
        type="button"
        class="explanation-button"
        :aria-expanded="open"
        :aria-controls="regionId"
        data-testid="explanation-button"
        @click="open = !open"
      >
        <UIcon name="i-ph-caret-right" class="size-4 shrink-0 transition-transform duration-200" :class="open ? 'rotate-90' : ''" aria-hidden="true" />
        <span>{{ t('ask.explain.button') }}</span>
      </button>
    </h4>

    <div :id="regionId" role="region" :aria-labelledby="buttonId" :hidden="!open" data-testid="explanation-region" class="mt-3 space-y-5 text-sm">
      <template v-if="open">
        <p v-if="failed" class="text-error">
          {{ t('ask.explain.failed') }}
        </p>
        <p v-else-if="!texts || !method" role="status" class="text-muted">
          {{ t('common.loading') }}
        </p>
        <template v-else>
          <p v-if="note" class="rounded-lg bg-elevated px-3 py-2 text-muted" data-testid="explanation-note">
            {{ note }}
          </p>

          <section aria-labelledby="explain-numbers">
            <h5 id="explain-numbers" class="font-semibold text-highlighted">
              {{ t('ask.explain.numbers') }}
            </h5>
            <ul class="mt-1.5 list-disc space-y-1 ps-5 text-toned" data-testid="explanation-numbers">
              <li v-for="line in numbers" :key="line.id" :lang="lang">
                {{ line.text }}
              </li>
            </ul>
          </section>

          <section aria-labelledby="explain-rules">
            <h5 id="explain-rules" class="font-semibold text-highlighted">
              {{ t('ask.explain.rules') }}
            </h5>
            <ul class="mt-1.5 space-y-3" data-testid="explanation-rules">
              <li v-for="rule in rules" :key="rule.id" :data-rule="rule.id" :data-own="rule.own ? '' : undefined">
                <p :lang="lang" class="text-toned">
                  {{ rule.text }}
                </p>
                <p v-if="rule.own" class="mt-0.5 text-muted">
                  <span class="own-mark" data-testid="own-mark">{{ t('ask.explain.own') }}</span>
                  {{ ' ' }}<span :lang="lang">{{ rule.reason }}</span>
                </p>
                <div v-if="rule.cites.length" class="mt-0.5 flex flex-wrap gap-x-1.5 text-muted">
                  <span>{{ t(rule.own ? 'ask.explain.compare' : 'ask.explain.source') }}</span>
                  <ul class="cite-list flex flex-wrap gap-x-1.5">
                    <li v-for="cite in rule.cites" :key="cite.key">
                      <NuxtLink :to="cite.to" :class="link">
                        {{ cite.label }}
                      </NuxtLink>
                    </li>
                  </ul>
                </div>
              </li>
            </ul>
          </section>

          <section aria-labelledby="explain-data">
            <h5 id="explain-data" class="font-semibold text-highlighted">
              {{ t('ask.explain.data') }}
            </h5>
            <p :lang="lang" class="mt-1.5 text-toned">
              {{ fill(method.data, params) }}
            </p>
            <dl class="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-muted">
              <template v-if="explanation.data.provider">
                <dt>{{ t('ask.explain.provider') }}</dt>
                <dd>
                  {{ provider?.name_english || provider?.name_short || explanation.data.provider }}<template v-if="explanation.data.network">
                    · {{ explanation.data.network }}
                  </template>
                </dd>
              </template>
              <template v-if="explanation.data.dataset">
                <dt>{{ t('ask.explain.dataset') }}</dt>
                <dd class="break-words font-mono">
                  {{ explanation.data.dataset }}
                </dd>
              </template>
              <template v-if="explanation.data.parameters.length">
                <dt>{{ t('ask.explain.parameters') }}</dt>
                <dd class="break-words font-mono">
                  {{ explanation.data.parameters.join(', ') }}
                </dd>
              </template>
              <template v-if="licence">
                <dt>{{ t('ask.explain.licence') }}</dt>
                <dd>
                  <a v-if="licence.href" :href="licence.href" target="_blank" rel="noopener" :class="link">{{ licence.name }}</a>
                  <template v-else>
                    {{ licence.name }}
                  </template>
                </dd>
              </template>
            </dl>
            <p v-if="explorer" class="mt-2">
              <NuxtLink :to="explorer" :class="link" data-testid="explanation-explorer">
                {{ t('ask.explain.open') }}
              </NuxtLink>
            </p>
          </section>

          <section aria-labelledby="explain-terms">
            <h5 id="explain-terms" class="font-semibold text-highlighted">
              {{ t('ask.explain.terms') }}
            </h5>
            <ul class="mt-1.5 space-y-2" data-testid="explanation-terms">
              <li v-for="term in topics" :key="term.topic">
                <NuxtLink :to="measurementPath(term.topic)" :lang="lang" :class="link">
                  {{ term.title }}
                </NuxtLink>
                <span class="text-muted">: <span :lang="lang">{{ term.summary }}</span></span>
                <template v-if="term.glossary">
                  {{ ' ' }}<NuxtLink :to="{ path: '/glossary', query: { topic: term.topic } }" :class="link">
                    {{ t('measurement.fieldsLink') }}
                  </NuxtLink>
                </template>
              </li>
            </ul>
          </section>

          <section aria-labelledby="explain-limits">
            <h5 id="explain-limits" class="font-semibold text-highlighted">
              {{ t('ask.explain.limits') }}
            </h5>
            <ul class="mt-1.5 list-disc space-y-1 ps-5 text-toned" data-testid="explanation-limits">
              <li v-for="id in explanation.limits" :key="id" :lang="lang">
                {{ fill(method.limits[id] ?? '', params) }}
              </li>
            </ul>
          </section>

          <p>
            <NuxtLink :to="methodPath(chip.id)" :class="link" class="font-semibold" data-testid="explanation-full">
              {{ t('ask.explain.full') }}
            </NuxtLink>
          </p>
        </template>
      </template>
    </div>
  </div>
</template>

<style scoped>
.explanation-button {
  display: inline-flex;
  min-height: 2.75rem;
  align-items: center;
  gap: 0.5rem;
  border-radius: 0.5rem;
  padding: 0.25rem 0.5rem 0.25rem 0.25rem;
  font-weight: 600;
  color: var(--ui-text-toned);
  transition: color 150ms;
}
.explanation-button:hover {
  color: var(--ui-text-highlighted);
}
/* the sources of a rule side by side, a semicolon between them (decoration: the list is a list) */
.cite-list li:not(:last-child)::after {
  content: ';';
}
/* the mark that a choice is wetterdienst's own: a word, not only a colour */
.own-mark {
  display: inline-block;
  border-radius: 0.375rem;
  border: 1px solid var(--ui-border-accented);
  padding: 0 0.375rem;
  font-weight: 600;
  color: var(--ui-text-highlighted);
}
</style>
