<script setup lang="ts">
// The one column every page stands in (GH-3518): the same gutters on all of them (UContainer: 1rem, 1.5rem from 640 px,
// 2rem from 1024 px), the same maximum width, the same vertical padding and the same rhythm between its blocks, so that
// the left and right distances do not change from page to page. The pages of text (about, API, glossary, settings, the
// legal pages) read in a narrower measure, kept on the left edge of the same column; the pages with a map, a chart or
// a table (`wide`: explorer, stripes, forecast, history, providers) use the whole of it.
// `section` is the home page's: more air between its blocks.
withDefaults(defineProps<{ wide?: boolean, section?: boolean }>(), { wide: false, section: false })
</script>

<template>
  <UContainer
    class="max-w-(--app-width) py-8 sm:py-10 lg:py-14"
    :data-width="wide ? 'wide' : 'default'"
  >
    <div :class="[section ? 'space-y-(--app-space-section)' : 'space-y-8', wide ? '' : 'max-w-(--app-measure)']">
      <slot />
    </div>
  </UContainer>
</template>
