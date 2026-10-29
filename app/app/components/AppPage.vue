<script setup lang="ts">
// The one page layout (GH-3518): the frame's width and gutters, which the header, the navigation and the footer
// share, so that every page starts at the same left edge; a page header of a title and a sentence that says what the
// page is for; and the page's content below it. A page of text and forms keeps to a reading width (`reading`); a page
// of maps, charts and tables takes the frame's full width (`wide`).
withDefaults(defineProps<{
  /** The page's name, its only `h1`; leave it out where the page writes its own heading (the `header` slot) */
  title?: string
  /** One or two sentences under the title: what the page is for */
  lead?: string
  width?: 'reading' | 'wide'
}>(), { width: 'reading' })
</script>

<template>
  <div class="app-frame py-8 sm:py-10">
    <div v-if="title || $slots.header" class="mb-8 app-measure">
      <slot name="header">
        <h1 class="text-3xl sm:text-4xl font-bold tracking-tight text-highlighted break-words">
          {{ title }}
        </h1>
        <p v-if="lead" class="mt-3 text-lg text-toned">
          {{ lead }}
        </p>
      </slot>
    </div>
    <div class="space-y-6" :class="width === 'reading' ? 'max-w-3xl' : ''">
      <slot />
    </div>
  </div>
</template>
