<script setup lang="ts">
// Shown in place of the station map where its lazily loaded code could not be loaded. The realistic
// cause is a redeploy replacing the map's hashed chunk under an open tab, which only reloading the
// page mends; a passing network failure is retried by closing and opening the map again.

// the loader's error, passed by defineAsyncComponent: declared so it is not set on the element
defineProps<{ error?: Error }>()

const { t } = useI18n()

function reloadPage() {
  // forced: the user's click, not a reload loop, which is what Nuxt's guard stops. Unforced, a
  // second click within ten seconds of a first that did not help would do nothing
  reloadNuxtApp({ force: true })
}
</script>

<template>
  <div class="flex flex-wrap items-center justify-center gap-3 p-4">
    <p role="alert" class="text-sm font-medium text-center text-red-600 dark:text-red-400">
      {{ t('map.markersNotShown') }}
    </p>
    <UButton :label="t('common.reloadPage')" icon="i-lucide-refresh-cw" size="sm" color="neutral" variant="outline" @click="reloadPage()" />
  </div>
</template>
