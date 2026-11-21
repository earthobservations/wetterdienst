<script setup lang="ts">
import { measurement as measurementDe } from '~~/i18n/measurement/de'
import { measurement as measurementEn } from '~~/i18n/measurement/en'
import { methods as textsDe } from '~~/i18n/methods/de'
import { methods as textsEn } from '~~/i18n/methods/en'
import { methodPath, textLanguageOf, workPath, worksOf } from '~/utils/ask/method-text'
import { CHIPS } from '~/utils/ask/registry'
import { WORK_IDS, workAnchor, WORKS } from '~/utils/ask/works'

// "How the answers are worked out" (GH-3764, steps 1b and 1c): the reference page of the methods of Ask the weather, in the
// Reference group beside the Glossary and "How weather is measured". One section for each chip of the registry, written from its
// definition (`ChipExplanation`) so that a new chip is on the page with no edit of it, each with an anchor (`/methods#summer`), and at
// the end the list of the works cited, each with an anchor (`/methods#work-wmo-1203`). The disclosure under each answer links here.
//
// The texts are long and are written in German and English (`i18n/methods/`), as the entries of "How weather is measured" are: a reader of
// another language sees the text in English, with a note, and a reader of Low German or Luxembourgish in German.
const { t, locale } = useI18n()
const route = useRoute()

// the title says which page this is: WCAG 2.4.2, and what a screen reader announces after a navigation
useHead({ title: () => t('methods.title') })

const own = computed(() => locale.value === 'de' || locale.value === 'en')
const textLanguage = computed(() => textLanguageOf(locale.value))
const texts = computed(() => textLanguage.value === 'de' ? textsDe : textsEn)
const measurement = computed(() => textLanguage.value === 'de' ? measurementDe : measurementEn)
// the elements of the text say their language where it is not the interface's (WCAG 3.1.2)
const lang = computed(() => own.value ? undefined : textLanguage.value)
const note = computed(() => own.value ? undefined : t(textLanguage.value === 'de' ? 'measurement.untranslatedDe' : 'measurement.untranslatedEn'))

const chips = CHIPS.map(chip => ({ chip, id: chip.id }))
const works = WORK_IDS.map(id => ({
  id,
  work: WORKS[id],
  anchor: workAnchor(id),
  usedBy: CHIPS.filter(chip => worksOf(chip).includes(id)).map(chip => chip.id),
}))

// A link to a section (`#summer`) or a work (`#work-wmo-1203`) takes the reader to its heading and puts the focus there, so that a keyboard
// and a screen reader continue at the section and not at the link that was used; the router scrolls (and respects reduced motion). The
// anchor of anything that is not a section or a work (a rule) is left to the browser.
const anchors = new Set<string>([...CHIPS.map(chip => chip.id), ...WORK_IDS.map(workAnchor)])
function reveal(hash: string) {
  let id = hash.slice(1)
  try {
    id = decodeURIComponent(id)
  }
  catch {
    return
  }
  if (!anchors.has(id))
    return
  document.getElementById(`${id}-title`)?.focus({ preventScroll: true })
}
// Following the link of the section that the address already names changes no hash, so nothing above runs: scroll and focus here, as a
// first visit would
function onAnchor(id: string) {
  if (route.hash === `#${id}`) {
    document.getElementById(id)?.scrollIntoView({ block: 'start' })
    reveal(`#${id}`)
  }
}
onMounted(() => {
  if (route.hash)
    void nextTick(() => reveal(route.hash))
})
watch(() => route.hash, (hash) => {
  if (hash)
    void nextTick(() => reveal(hash))
})

const link = 'text-primary-700 dark:text-primary-500 underline hover:no-underline'
</script>

<template>
  <div class="frame">
    <PageHeader :title="t('methods.title')" :lede="t('methods.subtitle')" />
    <div class="page-body" data-width="read">
      <nav aria-labelledby="methods-toc" class="rounded-xl bg-default p-5 ring ring-default sm:p-6">
        <h2 id="methods-toc" class="text-lg font-bold">
          {{ t('methods.tocTitle') }}
        </h2>
        <ol class="mt-3 space-y-1">
          <li v-for="entry in chips" :key="entry.id">
            <NuxtLink :to="methodPath(entry.id)" :lang="lang" :class="link" @click="onAnchor(entry.id)">
              {{ texts.chips[entry.id]?.title }}
            </NuxtLink>
          </li>
          <li>
            <NuxtLink to="/methods#works" :class="link">
              {{ t('methods.worksTitle') }}
            </NuxtLink>
          </li>
        </ol>
      </nav>

      <section aria-labelledby="methods-intro" class="rounded-xl bg-default p-5 ring ring-default sm:p-6">
        <h2 id="methods-intro" class="text-lg font-bold">
          {{ t('methods.introTitle') }}
        </h2>
        <p class="mt-2 text-gray-600 dark:text-gray-400">
          {{ t('methods.introText') }}
        </p>
        <p class="mt-2 text-gray-600 dark:text-gray-400">
          {{ t('methods.ownText') }}
        </p>
        <p class="mt-2 text-gray-600 dark:text-gray-400">
          <i18n-t keypath="methods.measurementText" tag="span">
            <template #page>
              <NuxtLink to="/measurement" :class="link">
                {{ t('measurement.title') }}
              </NuxtLink>
            </template>
            <template #glossary>
              <NuxtLink to="/glossary" :class="link">
                {{ t('glossary.title') }}
              </NuxtLink>
            </template>
          </i18n-t>
        </p>
      </section>

      <section aria-labelledby="methods-chips" class="space-y-6">
        <h2 id="methods-chips" class="text-lg font-bold">
          {{ t('methods.chipsTitle') }}
        </h2>
        <MethodSection
          v-for="entry in chips"
          :key="entry.id"
          :chip="entry.chip"
          :method="texts.chips[entry.id]!"
          :measurement="measurement"
          :lang="lang"
          :note="note"
          :text-language="textLanguage"
          @anchor="onAnchor"
        />
      </section>

      <section id="works" aria-labelledby="methods-works" class="space-y-6">
        <div>
          <h2 id="methods-works" class="text-lg font-bold">
            {{ t('methods.worksTitle') }}
          </h2>
          <p class="mt-2 text-gray-600 dark:text-gray-400">
            {{ t('methods.worksIntro') }}
          </p>
        </div>
        <article
          v-for="entry in works"
          :id="entry.anchor"
          :key="entry.id"
          :aria-labelledby="`${entry.anchor}-title`"
          class="rounded-xl bg-default p-5 ring ring-default sm:p-6"
          data-testid="work"
        >
          <div class="flex items-start justify-between gap-3">
            <h3 :id="`${entry.anchor}-title`" tabindex="-1" class="text-xl font-bold text-highlighted focus-visible:outline-none">
              {{ entry.work.short }}
            </h3>
            <NuxtLink
              :to="workPath(entry.id)"
              class="mt-1 shrink-0 rounded-md p-1 text-muted hover:text-highlighted"
              :aria-label="t('measurement.linkTo', { title: entry.work.short })"
              :title="t('measurement.linkTo', { title: entry.work.short })"
              data-print="hide"
              @click="onAnchor(entry.anchor)"
            >
              <UIcon name="i-ph-link" class="size-5" />
            </NuxtLink>
          </div>
          <p :lang="lang" class="mt-2 text-gray-600 dark:text-gray-400">
            {{ texts.works[entry.id].plain }}
          </p>
          <p class="mt-2 text-sm">
            <a :href="entry.work.href" target="_blank" rel="noopener noreferrer" :class="link" class="break-words">{{ entry.work.citation }}</a>
          </p>
          <p v-if="entry.usedBy.length" class="mt-2 text-sm text-muted">
            {{ t('methods.usedBy') }}
            <template v-for="(id, index) in entry.usedBy" :key="id">
              <template v-if="index > 0">
                {{ ', ' }}
              </template>
              <NuxtLink :to="methodPath(id)" :lang="lang" :class="link" @click="onAnchor(id)">
                {{ texts.chips[id]?.title }}
              </NuxtLink>
            </template>
          </p>
        </article>
      </section>
    </div>
  </div>
</template>
