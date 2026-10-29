<script setup lang="ts">
// The head of every page (GH-3518): the section it belongs to, its title and a sentence that says what it is for,
// at the page's left edge, above a rule. One component, so that every page starts at the same height and distance.
export type PageTile = 'sun' | 'heat' | 'rain' | 'wind'

defineProps<{
  title: string
  lede?: string
  kicker?: string
  /** the logo's tile of the section, as its colour: the sun (forecast), heat (stripes), rain (explorer), wind (history) */
  tile?: PageTile
}>()

// written out, as Tailwind finds a class only where it is spelled whole
const TILE_CLASS: Record<PageTile, string> = { sun: 'bg-tile-sun', heat: 'bg-tile-heat', rain: 'bg-tile-rain', wind: 'bg-tile-wind' }
</script>

<template>
  <div class="pt-8 sm:pt-12 pb-6 sm:pb-8 mb-8 border-b border-(--app-rule)">
    <p v-if="kicker" class="app-kicker mb-3">
      <span v-if="tile" class="app-tile" :class="TILE_CLASS[tile]" aria-hidden="true" />
      {{ kicker }}
    </p>
    <h1 class="app-title">
      {{ title }}
    </h1>
    <p v-if="lede" class="app-lede app-measure mt-4">
      {{ lede }}
    </p>
    <slot />
  </div>
</template>
