<script setup lang="ts">
import type { Tile } from '~/utils/sections'

// A tool's mark: one tile of the logo, in its colour, with the tool's glyph (main.css, `.tile`). A picture of a name
// that is always written beside it, so it is hidden from assistive technology.
const props = withDefaults(defineProps<{
  tile?: Tile
  icon: string
  /** The edge of the square, as a CSS length */
  size?: string
}>(), { tile: 'navy', size: '1.75rem' })

const style = computed(() => ({ '--tile-size': props.size }))
</script>

<template>
  <span class="tile" :class="`tile-${tile}`" :style="style" aria-hidden="true">
    <UIcon :name="icon" />
  </span>
</template>
