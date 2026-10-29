<script setup lang="ts">
import { privacy as privacyDe } from '~~/i18n/privacy/de'
import { privacy as privacyEn } from '~~/i18n/privacy/en'

const { locale } = useI18n()

// `/datenschutz` and `/privacy` are the same page. The text is a legal one, written once in German (the
// binding version) and once in English by the operator (`i18n/privacy/`), not in the eleven catalogs of
// the interface: German for the German locales, English for every other language.
definePageMeta({ alias: ['/privacy'] })

const policy = computed(() => (locale.value === 'de' || locale.value === 'de-hh' ? privacyDe : privacyEn))

// the title says which page this is: WCAG 2.4.2, and what a screen reader announces after a navigation
useHead({ title: () => policy.value.title })

// The controller is the operator of the Impressum, whose details are written once (~/utils/operator.ts)
const operator = OPERATOR
</script>

<template>
  <!-- the text is in a language of its own, which the interface may not be in (WCAG 3.1.2) -->
  <PageShell width="prose" :lang="policy === privacyDe ? 'de' : 'en'">
    <template #header>
      <h1 class="page-shell-title">
        {{ policy.title }}
      </h1>
      <p class="text-sm text-muted">
        {{ policy.updated }}
      </p>
      <p v-if="policy.binding" class="text-sm text-toned">
        {{ policy.binding }}
      </p>
    </template>

    <p class="text-gray-600 dark:text-gray-400">
      {{ policy.intro }}
    </p>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-user" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ policy.controller.title }}
          </h2>
        </div>
      </template>
      <div class="space-y-2">
        <p class="text-gray-600 dark:text-gray-400">
          {{ policy.controller.text }}
        </p>
        <p class="font-medium">
          {{ operator.name }}
        </p>
        <p class="text-gray-600 dark:text-gray-400">
          {{ policy.controller.addressLabel }}:<br>
          {{ operator.street }}<br>
          {{ operator.city }}<br>
          {{ operator.country }}
        </p>
        <p class="text-gray-600 dark:text-gray-400">
          {{ policy.controller.emailLabel }}: <a :href="`mailto:${operator.email}`" class="text-primary-700 dark:text-primary-500 underline hover:no-underline">{{ operator.email }}</a>
        </p>
      </div>
    </UCard>

    <UCard v-for="section in policy.sections" :id="section.id" :key="section.id">
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon :name="section.icon" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ section.title }}
          </h2>
        </div>
      </template>
      <div class="space-y-3 text-gray-600 dark:text-gray-400">
        <p v-for="paragraph in section.paragraphs" :key="paragraph">
          {{ paragraph }}
        </p>
        <ul v-if="section.items" class="list-disc space-y-1 pl-5">
          <li v-for="item in section.items" :key="item">
            {{ item }}
          </li>
        </ul>
        <p v-if="section.link">
          <a :href="section.link.href" target="_blank" rel="noopener noreferrer" class="text-primary-700 dark:text-primary-500 underline hover:no-underline">{{ section.link.label }}</a>
        </p>
      </div>
    </UCard>
  </PageShell>
</template>
