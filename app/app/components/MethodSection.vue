<script setup lang="ts">
import type { MeasurementTexts } from '../../i18n/measurement/types'
import type { ChipMethod } from '../../i18n/methods/types'
import type { Chip } from '~/utils/ask/chip'
import { citationText, fill, methodPath, ruleParams, workPath } from '~/utils/ask/method-text'
import { measurementPath, parameterPatterns } from '~/utils/measurement'

// One section of the page of the methods (GH-3764): the method of one chip of "Ask the weather", written from its definition
// (`ChipExplanation`, `utils/ask/chip.ts`) and its words (`i18n/methods/`), so that a chip that is in the registry is on the page
// with no edit of it. A heading with an anchor of its own (`#summer`), the question, the method step by step, the formula where there
// is one, every choice with the work it comes from or the mark that it is wetterdienst's own (and why), the data, the terms, the limits.
//
// The text is in the language of the page, or where there is none yet in English or German, with a note that says so; the elements that
// are the text's say their own language (WCAG 3.1.2), the labels around them the interface's.
const props = defineProps<{
  chip: Chip
  method: ChipMethod
  measurement: MeasurementTexts
  /** The language of the text, set only where it is not the interface's own */
  lang?: string
  /** The note that says the text is not in the reader's language yet */
  note?: string
  /** The language the text is in, for the numbers */
  textLanguage: string
}>()

const emit = defineEmits<{ anchor: [id: string] }>()
const { t } = useI18n()
const explanation = computed(() => props.chip.explanation)
const params = computed(() => ruleParams(explanation.value.rules, props.textLanguage))
const headingId = computed(() => `${props.chip.id}-title`)
const ownCount = computed(() => explanation.value.rules.filter(rule => rule.own).length)

const rules = computed(() => explanation.value.rules.map((rule) => {
  const words = props.method.rules[rule.id]
  return {
    ...rule,
    anchor: `${props.chip.id}-${rule.id}`,
    text: words ? fill(words.text, params.value) : '',
    says: words?.says ? fill(words.says, params.value) : '',
    reason: words?.reason ? fill(words.reason, params.value) : '',
    cites: rule.cites.map(citation => ({ key: `${citation.work}-${citation.at ?? ''}`, label: citationText(citation), to: workPath(citation.work) })),
  }
}))

const link = 'text-primary-700 dark:text-primary-500 underline hover:no-underline'
</script>

<template>
  <article :id="chip.id" :aria-labelledby="headingId" class="method-section rounded-xl bg-default p-5 ring ring-default sm:p-6" data-testid="method-section">
    <div class="flex items-start justify-between gap-3">
      <h3 :id="headingId" tabindex="-1" :lang="lang" class="text-xl font-bold text-highlighted focus-visible:outline-none">
        {{ method.title }}
      </h3>
      <NuxtLink
        :to="methodPath(chip.id)"
        class="mt-1 shrink-0 rounded-md p-1 text-muted hover:text-highlighted"
        :aria-label="t('measurement.linkTo', { title: method.title })"
        :title="t('measurement.linkTo', { title: method.title })"
        data-print="hide"
        @click="emit('anchor', chip.id)"
      >
        <UIcon name="i-ph-link" class="size-5" />
      </NuxtLink>
    </div>
    <p :lang="lang" class="mt-2 text-gray-600 dark:text-gray-400">
      {{ method.summary }}
    </p>
    <p v-if="note" class="mt-3 rounded-lg bg-elevated px-3 py-2 text-sm text-muted" data-testid="methods-note">
      {{ note }}
    </p>
    <p class="mt-3 text-sm">
      <NuxtLink :to="{ path: '/', query: { ask: chip.id } }" :class="link" data-testid="method-ask">
        {{ t('methods.ask') }}
      </NuxtLink>
      <span class="text-muted"> · {{ t('methods.ownCount', { own: ownCount, total: rules.length }) }}</span>
    </p>

    <div :lang="lang" class="mt-5 space-y-6">
      <section :aria-labelledby="`${chip.id}-steps`">
        <h4 :id="`${chip.id}-steps`" class="text-base font-semibold text-highlighted">
          {{ t('methods.stepsTitle') }}
        </h4>
        <ol class="mt-2 list-decimal space-y-2 ps-5 text-gray-600 dark:text-gray-400">
          <li v-for="step in explanation.steps" :key="step" :data-step="step">
            {{ fill(method.steps[step] ?? '', params) }}
          </li>
        </ol>
      </section>

      <section v-if="explanation.formulas.length" :aria-labelledby="`${chip.id}-formulas`">
        <h4 :id="`${chip.id}-formulas`" class="text-base font-semibold text-highlighted">
          {{ t('methods.formulaTitle') }}
        </h4>
        <ul class="mt-2 space-y-2">
          <li v-for="formula in explanation.formulas" :key="formula" class="overflow-x-auto rounded-lg bg-elevated px-3 py-2 font-mono text-sm text-toned" data-testid="method-formula">
            {{ fill(method.formulas[formula] ?? '', params) }}
          </li>
        </ul>
      </section>

      <section :aria-labelledby="`${chip.id}-rules`">
        <h4 :id="`${chip.id}-rules`" class="text-base font-semibold text-highlighted">
          {{ t('methods.rulesTitle') }}
        </h4>
        <ul class="mt-2 space-y-4">
          <li v-for="rule in rules" :id="rule.anchor" :key="rule.id" class="scroll-mt-20" :data-rule="rule.id" :data-own="rule.own ? '' : undefined">
            <p class="text-sm font-medium text-muted">
              {{ t(`methods.kind.${rule.kind}`) }}
            </p>
            <p class="mt-0.5 text-gray-700 dark:text-gray-300">
              {{ rule.text }}
            </p>
            <p v-if="rule.says" class="mt-1 text-gray-600 dark:text-gray-400">
              <span class="font-semibold">{{ t('methods.says') }}</span>{{ ' ' }}{{ rule.says }}
            </p>
            <p v-if="rule.own" class="mt-1 text-gray-600 dark:text-gray-400">
              <span class="own-mark" data-testid="own-mark">{{ t('ask.explain.own') }}</span>{{ ' ' }}{{ rule.reason }}
            </p>
            <div v-if="rule.cites.length" class="mt-1 flex flex-wrap gap-x-1.5 text-sm">
              <span class="text-muted">{{ t(rule.own ? 'ask.explain.compare' : 'ask.explain.source') }}</span>
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

      <section :aria-labelledby="`${chip.id}-data`">
        <h4 :id="`${chip.id}-data`" class="text-base font-semibold text-highlighted">
          {{ t('methods.dataTitle') }}
        </h4>
        <p class="mt-2 text-gray-600 dark:text-gray-400">
          {{ fill(method.data, params) }}
        </p>
        <ul v-if="explanation.data.dataset || explanation.data.parameters.length" class="mt-2 flex flex-wrap gap-2">
          <li v-if="explanation.data.dataset" class="max-w-full break-all rounded-md bg-elevated px-2 py-0.5 font-mono text-sm">
            {{ [explanation.data.provider, explanation.data.network, explanation.data.dataset].filter(Boolean).join('/') }}
          </li>
          <li v-for="parameter in explanation.data.parameters" :key="parameter" class="max-w-full break-all rounded-md bg-elevated px-2 py-0.5 font-mono text-sm">
            {{ parameter }}
          </li>
        </ul>
      </section>

      <section :aria-labelledby="`${chip.id}-terms`">
        <h4 :id="`${chip.id}-terms`" class="text-base font-semibold text-highlighted">
          {{ t('methods.termsTitle') }}
        </h4>
        <ul class="mt-2 space-y-2">
          <li v-for="topic in explanation.topics" :key="topic" class="text-gray-600 dark:text-gray-400">
            <NuxtLink :to="measurementPath(topic)" :class="link">
              {{ measurement[topic].title }}
            </NuxtLink>: {{ measurement[topic].summary }}
            <template v-if="parameterPatterns(topic).length">
              {{ ' ' }}<NuxtLink :to="{ path: '/glossary', query: { topic } }" :class="link">
                {{ t('measurement.fieldsLink') }}
              </NuxtLink>
            </template>
          </li>
        </ul>
      </section>

      <section :aria-labelledby="`${chip.id}-limits`">
        <h4 :id="`${chip.id}-limits`" class="text-base font-semibold text-highlighted">
          {{ t('methods.limitsTitle') }}
        </h4>
        <ul class="mt-2 list-disc space-y-2 ps-5 text-gray-600 dark:text-gray-400">
          <li v-for="limit in explanation.limits" :key="limit">
            {{ fill(method.limits[limit] ?? '', params) }}
          </li>
        </ul>
      </section>
    </div>
  </article>
</template>

<style scoped>
/* the sources of a rule side by side, a semicolon between them (decoration: the list is a list) */
.cite-list li:not(:last-child)::after {
  content: ';';
}
.own-mark {
  display: inline-block;
  border-radius: 0.375rem;
  border: 1px solid var(--ui-border-accented);
  padding: 0 0.375rem;
  font-weight: 600;
  color: var(--ui-text-highlighted);
}
</style>
