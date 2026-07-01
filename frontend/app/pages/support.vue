<script setup lang="ts">
const { t } = useI18n()
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6 space-y-6">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold mb-4">
        {{ t('support.title') }}
      </h1>
    </div>

    <UCard>
      <template #header>
        <h2 class="text-lg font-bold">
          {{ t('support.reportTitle') }}
        </h2>
      </template>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('support.reportText') }}
      </p>
      <div class="mt-3">
        <UButton size="sm" variant="ghost" color="primary" to="https://github.com/earthobservations/wetterdienst/issues" target="_blank">
          {{ t('support.reportButton') }}
        </UButton>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <h2 class="text-lg font-bold">
          {{ t('support.contributeTitle') }}
        </h2>
      </template>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('support.contributeText') }}
      </p>
      <div class="mt-3">
        <UButton size="sm" variant="ghost" color="primary" to="https://github.com/earthobservations/wetterdienst/pulls" target="_blank">
          {{ t('support.contributeButton') }}
        </UButton>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <h2 class="text-lg font-bold">
          {{ t('support.discussionsTitle') }}
        </h2>
      </template>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('support.discussionsText') }}
      </p>
      <div class="mt-3">
        <UButton size="sm" variant="ghost" color="primary" to="https://github.com/earthobservations/wetterdienst/discussions" target="_blank">
          {{ t('support.discussionsButton') }}
        </UButton>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <h2 class="text-lg font-bold">
          {{ t('support.donateTitle') }}
        </h2>
      </template>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('support.donateText') }}
      </p>
      <div class="mt-3">
        <ul class="space-y-2 text-gray-700 dark:text-gray-300">
          <li class="flex items-center gap-2">
            <UIcon name="i-simple-icons-github" class="size-4" /><a href="https://github.com/sponsors/gutzbenj" target="_blank" class="text-primary-500 hover:underline">gutzbenj</a>
          </li>
          <li class="flex items-center gap-2">
            <UIcon name="i-simple-icons-paypal" class="size-4" /><a href="https://paypal.me/BenjaminGutzmann" target="_blank" class="text-primary-500 hover:underline">paypal.me/BenjaminGutzmann</a>
          </li>
        </ul>
      </div>
    </UCard>
  </UContainer>
</template>
