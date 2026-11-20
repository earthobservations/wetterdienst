<script setup lang="ts">
import { measurement as textsDe } from '~~/i18n/measurement/de'
import { measurement as textsEn } from '~~/i18n/measurement/en'
import { isTopic, measurementPath, TOPIC_GROUPS } from '~/utils/measurement'

// "How weather is measured" (GH-3787): one entry for each quantity, with an anchor, in the reference group beside the
// glossary, which links to it (`/glossary`: "How is this measured?"). The texts are long and are written in German and
// English (`i18n/measurement/`), not in the eleven catalogs of the interface; a reader of another language sees the
// entry in English, with a note, and a reader of Low German or Luxembourgish in German (as the privacy policy is shown).
const { t, locale } = useI18n()
const route = useRoute()

// the title says which page this is: WCAG 2.4.2, and what a screen reader announces after a navigation
useHead({ title: () => t('measurement.title') })

const own = computed(() => locale.value === 'de' || locale.value === 'en')
const textLanguage = computed<'de' | 'en'>(() => ['de', 'de-hh', 'lb'].includes(locale.value) ? 'de' : 'en')
const texts = computed(() => textLanguage.value === 'de' ? textsDe : textsEn)
// the elements of the text say their language where it is not the interface's (WCAG 3.1.2)
const lang = computed(() => own.value ? undefined : textLanguage.value)
const note = computed(() => own.value ? undefined : t(textLanguage.value === 'de' ? 'measurement.untranslatedDe' : 'measurement.untranslatedEn'))

const groups = computed(() => TOPIC_GROUPS.map(group => ({
  ...group,
  label: t(group.id === 'measured' ? 'measurement.groupMeasured' : 'measurement.groupReading'),
})))

// A link to an entry (`#wind`) takes the reader to its heading and puts the focus there, so that a keyboard and a
// screen reader continue at the entry and not at the link that was used; the router scrolls (and respects reduced
// motion). The anchor of an entry that is not one is left to the browser.
function reveal(hash: string) {
  let id = hash.slice(1)
  try {
    id = decodeURIComponent(id)
  }
  catch {
    return
  }
  if (!isTopic(id))
    return
  document.getElementById(`${id}-title`)?.focus({ preventScroll: true })
}
// Following the link of the entry that the address already names changes no hash, so nothing above runs: scroll
// and focus here, as a first visit would
function onAnchor(topic: string) {
  if (route.hash === `#${topic}`) {
    document.getElementById(topic)?.scrollIntoView({ block: 'start' })
    reveal(`#${topic}`)
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
</script>

<template>
  <div class="frame">
    <PageHeader :title="t('measurement.title')" :lede="t('measurement.subtitle')" />
    <div class="page-body" data-width="read">
      <nav aria-labelledby="measurement-toc" class="rounded-xl bg-default p-5 ring ring-default sm:p-6">
        <h2 id="measurement-toc" class="text-lg font-bold">
          {{ t('measurement.tocTitle') }}
        </h2>
        <div class="mt-3 space-y-4">
          <div v-for="group in groups" :key="group.id">
            <p class="text-sm font-medium text-muted">
              {{ group.label }}
            </p>
            <ol class="mt-1 space-y-1">
              <li v-for="topic in group.topics" :key="topic">
                <NuxtLink
                  :to="measurementPath(topic)"
                  :lang="lang"
                  class="text-primary-700 dark:text-primary-500 underline hover:no-underline"
                  @click="onAnchor(topic)"
                >
                  {{ texts[topic].title }}
                </NuxtLink>
              </li>
            </ol>
          </div>
        </div>
      </nav>

      <section aria-labelledby="measurement-edition" class="rounded-xl bg-default p-5 ring ring-default sm:p-6">
        <h2 id="measurement-edition" class="text-lg font-bold">
          {{ t('measurement.editionTitle') }}
        </h2>
        <p class="mt-2 text-gray-600 dark:text-gray-400">
          {{ t('measurement.editionText') }}
        </p>
        <p class="mt-2">
          <a
            href="https://community.wmo.int/node/37733"
            target="_blank"
            rel="noopener noreferrer"
            class="text-primary-700 dark:text-primary-500 underline hover:no-underline"
          >{{ t('measurement.editionLink') }}</a>
        </p>
      </section>

      <section v-for="group in groups" :key="group.id" :aria-labelledby="`measurement-group-${group.id}`" class="space-y-6">
        <h2 :id="`measurement-group-${group.id}`" class="text-lg font-bold">
          {{ group.label }}
        </h2>
        <MeasurementEntry
          v-for="topic in group.topics"
          :key="topic"
          :topic="topic"
          :entry="texts[topic]"
          :lang="lang"
          :note="note"
          @anchor="onAnchor"
        />
      </section>
    </div>
  </div>
</template>
