<script setup lang="ts">
import type { NuxtError } from '#app'

// The error page is Nuxt's own, drawn unless the page is framed by another origin outside the widget: then there
// is nothing to show, least of all a 404 that prints the path it was asked for (`app/utils/frame-guard.ts`).
defineProps<{ error: NuxtError }>()

const blank = useFrameBlank()
</script>

<template>
  <div v-if="blank" />
  <NuxtError v-else :error="error" />
</template>
