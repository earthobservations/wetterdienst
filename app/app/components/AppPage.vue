<script setup lang="ts">
// The container and the header of every page (GH-3518): one gutter, so that every page starts at the same distance
// from the rail and the window's edge, and three widths. `text` is a page that is read (48rem, a line of about 75
// characters), `default` one of panels and tables (80rem), `wide` a tool with a map or a chart, which takes the window.
// The styles are in main.css (`.app-page`).
withDefaults(defineProps<{
  title?: string
  subtitle?: string
  width?: 'text' | 'default' | 'wide'
}>(), {
  title: undefined,
  subtitle: undefined,
  width: 'default',
})
</script>

<template>
  <div class="app-page" :class="`app-page--${width}`">
    <div v-if="title || $slots.header" class="app-page-header">
      <div class="min-w-0">
        <slot name="header">
          <h1 class="app-page-title">
            {{ title }}
          </h1>
          <p v-if="subtitle" class="app-page-subtitle">
            {{ subtitle }}
          </p>
        </slot>
      </div>
      <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
    <div class="space-y-6">
      <slot />
    </div>
  </div>
</template>
