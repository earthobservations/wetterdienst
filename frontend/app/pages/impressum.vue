<template>
  <UContainer class="max-w-3xl mx-auto py-8 px-4">
    <h1 class="text-3xl font-bold mb-8">
      Legal Notice
    </h1>

    <UCard class="mb-4">
      <template #header>
        <h2 class="text-lg font-semibold text-white">
          Responsible Person
        </h2>
      </template>
      <div class="space-y-2">
        <p class="font-medium text-white dark:text-white">
          Benjamin Gutzmann
        </p>
        <p class="text-gray-600 dark:text-gray-400">
          Email: <a href="mailto:benjamin@eobs.org" class="text-primary-500 hover:underline">benjamin@eobs.org</a>
        </p>
        <p class="text-gray-600 dark:text-gray-400">
          GitHub: <a href="https://github.com/gutzbenj" target="_blank" class="text-primary-500 hover:underline">@gutzbenj</a>
        </p>
      </div>
    </UCard>

    <UCard class="mb-4">
      <template #header>
        <h2 class="text-lg font-semibold">
          Disclaimer
        </h2>
      </template>
      <div class="space-y-4">
        <div>
          <h3 class="font-medium text-white dark:text-white mb-2">
            Content
          </h3>
          <p class="text-gray-600 dark:text-gray-400">
            The content of this website has been created with the greatest possible care. However, we cannot guarantee the accuracy, completeness, or timeliness of the content. The weather data provided is sourced from various meteorological services and is provided "as is" without warranty.
          </p>
        </div>
        <div>
          <h3 class="font-medium text-white dark:text-white mb-2">
            External Links
          </h3>
          <p class="text-gray-600 dark:text-gray-400">
            This website contains links to external third-party websites over whose content we have no control. Therefore, we cannot accept any liability for this external content. The respective provider or operator of the linked pages is always responsible for their content.
          </p>
        </div>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <h2 class="text-lg font-semibold">
          Open Source
        </h2>
      </template>
      <p class="text-gray-600 dark:text-gray-400">
        Wetterdienst is an open-source project licensed under the MIT License. The source code is available on <a href="https://github.com/earthobservations/wetterdienst" target="_blank" class="text-primary-500 hover:underline"> GitHub </a>.
      </p>
    </UCard>
  </UContainer>
</template>
