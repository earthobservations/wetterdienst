<script setup lang="ts">
import type { NuxtError } from '#app'
// Nuxt's own error page, which is what the app showed before this file existed (and what a project without an
// `error.vue` gets); it is not a registered component, so it is imported
import NuxtErrorPage from '#app/components/nuxt-error-page.vue'

// Drawn unless the page is framed by another origin outside the widget: then there is nothing to show, least of
// all a 404 that prints the path it was asked for (`app/utils/frame-guard.ts`).
defineProps<{ error: NuxtError }>()

const blank = useFrameBlank()
</script>

<template>
  <div v-if="blank" />
  <NuxtErrorPage v-else :error="error" />
</template>
