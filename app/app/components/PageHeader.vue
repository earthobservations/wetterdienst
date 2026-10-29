<script setup lang="ts">
import type { TileTone } from './AskTile.vue'

// The head of every page: its title, the sentence that says what it is for, and the tile of the kind of weather it
// is about. Left-aligned on the page's own edge, which is the edge of the logo in the header above it.
defineProps<{
  title: string
  subtitle?: string
  icon?: string
  tone?: TileTone
}>()
</script>

<template>
  <div class="page-header flex items-start gap-4">
    <AskTile v-if="icon" :icon="icon" :tone="tone" size="lg" class="hidden sm:inline-flex mt-1" />
    <div class="min-w-0 flex-1">
      <h1 class="text-3xl sm:text-4xl font-bold leading-tight break-words">
        {{ title }}
      </h1>
      <p v-if="subtitle" class="mt-2 text-lg text-muted max-w-prose">
        {{ subtitle }}
      </p>
      <slot />
    </div>
  </div>
</template>
