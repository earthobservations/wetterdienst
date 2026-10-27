<script setup lang="ts">
// The one column every page stands in (GH-3518): the same gutters on all of them (UContainer: 1rem, 1.5rem from 640 px,
// 2rem from 1024 px), the same vertical padding and rhythm between its blocks, and two widths. The default is the
// width of text, cards and forms; `wide` is the width of the header and the footer, for the pages that hold a map, a
// chart or a table (explorer, stripes, meteogram, history). The widths are tokens (--app-width-default, --app-width-wide
// in main.css), and below the narrower one the two are the same.
withDefaults(defineProps<{ wide?: boolean }>(), { wide: false })
</script>

<template>
  <UContainer
    class="py-8 sm:py-10 lg:py-12 space-y-6"
    :class="wide ? 'max-w-(--app-width-wide)' : 'max-w-(--app-width-default)'"
    :data-width="wide ? 'wide' : 'default'"
  >
    <slot />
  </UContainer>
</template>
