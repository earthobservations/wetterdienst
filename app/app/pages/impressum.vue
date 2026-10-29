<script setup lang="ts">
const { t } = useI18n()

// the title says which page this is: WCAG 2.4.2, and what a screen reader announces after a navigation
useHead({ title: () => t('impressum.title') })

// The operator is written once, in ~/utils/operator.ts: the privacy policy names the same person.
const operator = OPERATOR

// False once the placeholders of the operator have been replaced, which hides the
// operator reminder banner.
const hasPlaceholders = computed(() =>
  Object.values(operator).some(v => typeof v === 'string' && v.includes('«')),
)
</script>

<template>
  <AppPage :title="t('impressum.title')">
    <!-- Reminder shown until the legally required placeholders are filled in. -->
    <UAlert
      v-if="hasPlaceholders"
      class="mb-6"
      color="warning"
      variant="subtle"
      icon="i-lucide-triangle-alert"
      :title="t('impressum.operatorNote')"
    />

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-user" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('impressum.providerTitle') }}
          </h2>
        </div>
      </template>
      <div class="space-y-2">
        <p class="font-medium">
          {{ operator.name }}
        </p>
        <p class="text-gray-600 dark:text-gray-400">
          {{ t('impressum.addressLabel') }}:<br>
          {{ operator.street }}<br>
          {{ operator.city }}<br>
          {{ operator.country }}
        </p>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-mail" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('impressum.contactTitle') }}
          </h2>
        </div>
      </template>
      <div class="space-y-2">
        <p class="text-gray-600 dark:text-gray-400">
          {{ t('impressum.emailLabel') }}: <a :href="`mailto:${operator.email}`" class="text-primary-700 dark:text-primary-400 underline hover:no-underline">{{ operator.email }}</a>
        </p>
        <p class="text-gray-600 dark:text-gray-400">
          {{ t('impressum.githubLabel') }}: <a :href="`https://github.com/${operator.github}`" target="_blank" class="text-primary-700 dark:text-primary-400 underline hover:no-underline">@{{ operator.github }}</a>
        </p>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-scale" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('impressum.mstvTitle') }}
          </h2>
        </div>
      </template>
      <div class="space-y-1 text-gray-600 dark:text-gray-400">
        <p>{{ operator.name }}</p>
        <p>{{ operator.street }}</p>
        <p>{{ operator.city }}</p>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-file-text" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('impressum.disclaimerTitle') }}
          </h2>
        </div>
      </template>
      <div class="space-y-4">
        <div>
          <h3 class="font-bold mb-2">
            {{ t('impressum.contentTitle') }}
          </h3>
          <p class="text-gray-600 dark:text-gray-400">
            {{ t('impressum.contentText') }}
          </p>
        </div>
        <div>
          <h3 class="font-bold mb-2">
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
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-code-2" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('impressum.openSourceTitle') }}
          </h2>
        </div>
      </template>
      <i18n-t keypath="impressum.openSourceText" tag="p" class="text-gray-600 dark:text-gray-400" scope="global">
        <template #link>
          <a href="https://github.com/earthobservations/wetterdienst" target="_blank" class="text-primary-700 dark:text-primary-400 underline hover:no-underline">GitHub</a>
        </template>
      </i18n-t>
    </UCard>
  </AppPage>
</template>
