<script setup lang="ts">
const { t } = useI18n()

// the title says which page this is: WCAG 2.4.2, and what a screen reader announces after a navigation
useHead({ title: () => t('support.title') })
</script>

<template>
  <PageShell :title="t('support.title')" width="prose">
    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-bug" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('support.reportTitle') }}
          </h2>
        </div>
      </template>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('support.reportText') }}
      </p>
      <div class="mt-3">
        <UButton size="sm" variant="ghost" color="primary" icon="i-simple-icons-github" to="https://github.com/earthobservations/wetterdienst/issues" target="_blank">
          {{ t('support.reportButton') }}
        </UButton>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-git-pull-request" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('support.contributeTitle') }}
          </h2>
        </div>
      </template>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('support.contributeText') }}
      </p>
      <div class="mt-3">
        <UButton size="sm" variant="ghost" color="primary" icon="i-simple-icons-github" to="https://github.com/earthobservations/wetterdienst/pulls" target="_blank">
          {{ t('support.contributeButton') }}
        </UButton>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-message-circle" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('support.discussionsTitle') }}
          </h2>
        </div>
      </template>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('support.discussionsText') }}
      </p>
      <div class="mt-3">
        <UButton size="sm" variant="ghost" color="primary" icon="i-simple-icons-github" to="https://github.com/earthobservations/wetterdienst/discussions" target="_blank">
          {{ t('support.discussionsButton') }}
        </UButton>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-heart" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('support.donateTitle') }}
          </h2>
        </div>
      </template>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('support.donateText') }}
      </p>
      <div class="mt-3">
        <ul class="space-y-2 text-gray-700 dark:text-gray-300">
          <li class="flex items-center gap-2">
            <UIcon name="i-simple-icons-github" class="size-4" /><a href="https://github.com/sponsors/gutzbenj" target="_blank" class="text-primary-700 dark:text-primary-500 hover:underline">gutzbenj</a>
          </li>
          <li class="flex items-center gap-2">
            <UIcon name="i-simple-icons-paypal" class="size-4" /><a href="https://paypal.me/BenjaminGutzmann" target="_blank" class="text-primary-700 dark:text-primary-500 hover:underline">paypal.me/BenjaminGutzmann</a>
          </li>
        </ul>
      </div>
    </UCard>
  </PageShell>
</template>
