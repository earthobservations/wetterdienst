<script setup lang="ts">
import type { MeasurementEntry } from '~~/i18n/measurement/types'
import type { TopicId } from '~/utils/measurement'
import { measurementPath, parameterPatterns } from '~/utils/measurement'

// One entry of the page "How weather is measured" (GH-3787): a heading with an anchor of its own, a sentence that says
// what it is about, its parts (how it is measured, how a reading becomes a value, what the number can and cannot tell,
// where providers differ), the glossary parameters it explains and the sources it rests on.
//
// The text is in the language of the page, or, where there is none yet, in English or German with a note that says
// so; the elements that are the text's say their own language (WCAG 3.1.2), the labels around them the interface's.
const props = defineProps<{
  topic: TopicId
  entry: MeasurementEntry
  /** The language of the text, set only where it is not the interface's own */
  lang?: string
  /** The note that says the text is not in the reader's language yet */
  note?: string
}>()

const emit = defineEmits<{ anchor: [topic: TopicId] }>()
const { t } = useI18n()
const patterns = computed(() => parameterPatterns(props.topic))
const headingId = computed(() => `${props.topic}-title`)
</script>

<template>
  <article :id="topic" :aria-labelledby="headingId" class="measurement-entry rounded-xl bg-default p-5 ring ring-default sm:p-6">
    <div class="flex items-start justify-between gap-3">
      <h3 :id="headingId" tabindex="-1" :lang="lang" class="text-xl font-bold text-highlighted focus-visible:outline-none">
        {{ entry.title }}
      </h3>
      <NuxtLink
        :to="measurementPath(topic)"
        class="mt-1 shrink-0 rounded-md p-1 text-muted hover:text-highlighted"
        :aria-label="t('measurement.linkTo', { title: entry.title })"
        :title="t('measurement.linkTo', { title: entry.title })"
        data-print="hide"
        @click="emit('anchor', topic)"
      >
        <UIcon name="i-ph-link" class="size-5" />
      </NuxtLink>
    </div>
    <p :lang="lang" class="mt-2 text-gray-600 dark:text-gray-400">
      {{ entry.summary }}
    </p>
    <p v-if="note" class="mt-3 rounded-lg bg-elevated px-3 py-2 text-sm text-muted" data-testid="measurement-note">
      {{ note }}
    </p>

    <div :lang="lang" class="mt-4 space-y-5">
      <section v-for="(part, index) in entry.parts" :key="`${index}-${part.title}`">
        <h4 class="text-base font-semibold text-highlighted">
          {{ part.title }}
        </h4>
        <p v-for="(paragraph, number) in part.paragraphs" :key="number" class="mt-2 text-gray-600 dark:text-gray-400">
          {{ paragraph }}
        </p>
      </section>
    </div>

    <section v-if="patterns.length" class="mt-5">
      <h4 class="text-base font-semibold text-highlighted">
        {{ t('measurement.fieldsTitle') }}
      </h4>
      <p class="mt-2 text-gray-600 dark:text-gray-400">
        {{ t('measurement.fieldsText') }}
      </p>
      <ul class="mt-2 flex flex-wrap gap-2">
        <li v-for="pattern in patterns" :key="pattern" class="rounded-md bg-elevated px-2 py-0.5 font-mono text-sm">
          {{ pattern }}
        </li>
      </ul>
      <p class="mt-2">
        <NuxtLink :to="{ path: '/glossary', query: { topic } }" class="text-primary-700 dark:text-primary-500 underline hover:no-underline">
          {{ t('measurement.fieldsLink') }}
        </NuxtLink>
      </p>
    </section>

    <section class="mt-5">
      <h4 class="text-base font-semibold text-highlighted">
        {{ t('measurement.sourcesTitle') }}
      </h4>
      <ul class="mt-2 space-y-3">
        <li v-for="(source, index) in entry.sources" :key="`${index}-${source.href}`" :lang="lang">
          <p class="text-gray-600 dark:text-gray-400">
            {{ source.plain }}
          </p>
          <p class="mt-1 text-sm">
            <a :href="source.href" target="_blank" rel="noopener noreferrer" class="text-primary-700 dark:text-primary-500 break-words underline hover:no-underline">{{ source.citation }}</a>
          </p>
        </li>
      </ul>
    </section>
  </article>
</template>
