<script setup lang="ts">
const { t } = useI18n()

// Operator / provider details required by § 5 DDG (formerly § 5 TMG) and the
// person responsible for editorial content per § 18 (2) MStV.
//
// IMPORTANT — fill these in before going live. The «…» tokens are placeholders;
// a German Impressum legally requires a full name, a postal address that can
// receive mail (no P.O. box), and a way to contact you quickly (e.g. email).
// Name and email are pre-filled from the project authors; the postal address
// and phone must be supplied by the operator.
const operator = {
  name: 'Benjamin Gutzmann',
  street: '«Straße und Hausnummer»',
  city: '«PLZ und Ort»',
  country: '«Land»',
  email: 'benjamin@eobs.org',
  phone: '«Telefon (optional)»',
  github: 'gutzbenj',
}

// Flip to false once the placeholders above have been replaced, to hide the
// operator reminder banner.
const hasPlaceholders = computed(() =>
  Object.values(operator).some(v => typeof v === 'string' && v.includes('«')),
)
</script>

<template>
  <UContainer class="max-w-3xl mx-auto py-8 px-4">
    <h1 class="text-3xl font-bold mb-8">
      {{ t('impressum.title') }}
    </h1>

    <!-- Reminder shown until the legally required placeholders are filled in. -->
    <UAlert
      v-if="hasPlaceholders"
      class="mb-6"
      color="warning"
      variant="subtle"
      icon="i-lucide-triangle-alert"
      :title="t('impressum.operatorNote')"
    />

    <UCard class="mb-4">
      <template #header>
        <h2 class="text-lg font-semibold">
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

    <UCard class="mb-4">
      <template #header>
        <h2 class="text-lg font-semibold">
          {{ t('impressum.contactTitle') }}
        </h2>
      </template>
      <div class="space-y-2">
        <p class="text-gray-600 dark:text-gray-400">
          {{ t('impressum.emailLabel') }}: <a :href="`mailto:${operator.email}`" class="text-primary-500 hover:underline">{{ operator.email }}</a>
        </p>
        <p class="text-gray-600 dark:text-gray-400">
          {{ t('impressum.phoneLabel') }}: {{ operator.phone }}
        </p>
        <p class="text-gray-600 dark:text-gray-400">
          {{ t('impressum.githubLabel') }}: <a :href="`https://github.com/${operator.github}`" target="_blank" class="text-primary-500 hover:underline">@{{ operator.github }}</a>
        </p>
      </div>
    </UCard>

    <UCard class="mb-4">
      <template #header>
        <h2 class="text-lg font-semibold">
          {{ t('impressum.mstvTitle') }}
        </h2>
      </template>
      <div class="space-y-1 text-gray-600 dark:text-gray-400">
        <p>{{ operator.name }}</p>
        <p>{{ operator.street }}</p>
        <p>{{ operator.city }}</p>
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
          <h3 class="font-medium mb-2">
            {{ t('impressum.contentTitle') }}
          </h3>
          <p class="text-gray-600 dark:text-gray-400">
            {{ t('impressum.contentText') }}
          </p>
        </div>
        <div>
          <h3 class="font-medium mb-2">
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
