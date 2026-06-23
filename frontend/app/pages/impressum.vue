<script setup lang="ts">
const { t } = useI18n()
</script>

<template>
  <UContainer class="max-w-3xl mx-auto py-8 px-4">
    <h1 class="text-3xl font-bold mb-8">
      {{ t('impressum.title') }}
    </h1>

    <UCard class="mb-4">
      <template #header>
        <h2 class="text-lg font-semibold text-white">
          {{ t('impressum.responsibleTitle') }}
        </h2>
      </template>
      <div class="space-y-2">
        <p class="font-medium text-white dark:text-white">
          Benjamin Gutzmann
        </p>
        <p class="text-gray-600 dark:text-gray-400">
          {{ t('impressum.emailLabel') }}: <a href="mailto:benjamin@eobs.org" class="text-primary-500 hover:underline">benjamin@eobs.org</a>
        </p>
        <p class="text-gray-600 dark:text-gray-400">
          {{ t('impressum.githubLabel') }}: <a href="https://github.com/gutzbenj" target="_blank" class="text-primary-500 hover:underline">@gutzbenj</a>
        </p>
      </div>
    </UCard>

    <UCard class="mb-4">
      <template #header>
        <h2 class="text-lg font-semibold">
          {{ t('impressum.disclaimerTitle') }}
        </h2>
      </template>
      <div class="space-y-4">
        <div>
          <h3 class="font-medium text-white dark:text-white mb-2">
            {{ t('impressum.contentTitle') }}
          </h3>
          <p class="text-gray-600 dark:text-gray-400">
            {{ t('impressum.contentText') }}
          </p>
        </div>
        <div>
          <h3 class="font-medium text-white dark:text-white mb-2">
            {{ t('impressum.linksTitle') }}
          </h3>
          <p class="text-gray-600 dark:text-gray-400">
            {{ t('impressum.linksText') }}
          </p>
        </div>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <h2 class="text-lg font-semibold">
          {{ t('impressum.openSourceTitle') }}
        </h2>
      </template>
      <i18n-t keypath="impressum.openSourceText" tag="p" class="text-gray-600 dark:text-gray-400" scope="global">
        <template #link>
          <a href="https://github.com/earthobservations/wetterdienst" target="_blank" class="text-primary-500 hover:underline">GitHub</a>
        </template>
      </i18n-t>
    </UCard>
  </UContainer>
</template>
