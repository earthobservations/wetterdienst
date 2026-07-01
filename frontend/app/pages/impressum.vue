<script setup lang="ts">
const { t } = useI18n()

// Operator / provider details required by § 5 DDG (formerly § 5 TMG) and the
// person responsible for editorial content per § 18 (2) MStV.
//
// A German Impressum legally requires a full name, a postal address that can
// receive mail (no P.O. box), and a way to contact you quickly. A phone number
// is optional — § 5 DDG only requires a means of "quick electronic contact",
// which the email below satisfies, so no phone is published here.
const operator = {
  name: 'Benjamin Gutzmann',
  street: 'Falkenbergsweg 26',
  city: '21149 Hamburg',
  country: 'Deutschland',
  email: 'benjamin@eobs.org',
  github: 'gutzbenj',
}

// Flip to false once the placeholders above have been replaced, to hide the
// operator reminder banner.
const hasPlaceholders = computed(() =>
  Object.values(operator).some(v => typeof v === 'string' && v.includes('«')),
)
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6 space-y-6">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold mb-4">
        {{ t('impressum.title') }}
      </h1>
    </div>

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
        <h2 class="text-lg font-bold">
          {{ t('impressum.providerTitle') }}
        </h2>
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
        <h2 class="text-lg font-bold">
          {{ t('impressum.contactTitle') }}
        </h2>
      </template>
      <div class="space-y-2">
        <p class="text-gray-600 dark:text-gray-400">
          {{ t('impressum.emailLabel') }}: <a :href="`mailto:${operator.email}`" class="text-primary-500 hover:underline">{{ operator.email }}</a>
        </p>
        <p class="text-gray-600 dark:text-gray-400">
          {{ t('impressum.githubLabel') }}: <a :href="`https://github.com/${operator.github}`" target="_blank" class="text-primary-500 hover:underline">@{{ operator.github }}</a>
        </p>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <h2 class="text-lg font-bold">
          {{ t('impressum.mstvTitle') }}
        </h2>
      </template>
      <div class="space-y-1 text-gray-600 dark:text-gray-400">
        <p>{{ operator.name }}</p>
        <p>{{ operator.street }}</p>
        <p>{{ operator.city }}</p>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <h2 class="text-lg font-bold">
          {{ t('impressum.disclaimerTitle') }}
        </h2>
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
        <h2 class="text-lg font-bold">
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
