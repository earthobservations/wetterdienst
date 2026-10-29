<script setup lang="ts">
// The one container of every page but the map and the widget (GH-3518): the same gutters at every width,
// a title set at the left with its subtitle under it, and the content in one column. `width` is how wide
// that column may grow: `prose` for text to read, `default` for a tool, `wide` for a grid of cards or a table.

withDefaults(defineProps<{
  title?: string
  subtitle?: string
  width?: 'prose' | 'default' | 'wide'
}>(), { width: 'default' })
</script>

<template>
  <div class="page-shell" :class="`page-shell--${width}`">
    <header v-if="title || $slots.header" class="page-shell-header">
      <slot name="header">
        <h1 class="page-shell-title">
          {{ title }}
        </h1>
        <p v-if="subtitle" class="page-shell-subtitle">
          {{ subtitle }}
        </p>
      </slot>
    </header>
    <div class="page-shell-body">
      <slot />
    </div>
  </div>
</template>

<style>
.page-shell {
  --page-gutter: 1rem;
  width: 100%;
  margin-inline: auto;
  padding: 1.75rem var(--page-gutter) 3.5rem;
}
@media (min-width: 640px) {
  .page-shell {
    --page-gutter: 1.5rem;
    padding-top: 2.5rem;
  }
}
@media (min-width: 1024px) {
  .page-shell {
    --page-gutter: 2rem;
    padding-top: 3rem;
  }
}
.page-shell--prose {
  max-width: calc(46rem + 2 * var(--page-gutter));
}
.page-shell--default {
  max-width: calc(52rem + 2 * var(--page-gutter));
}
.page-shell--wide {
  max-width: calc(76rem + 2 * var(--page-gutter));
}
.page-shell-header {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--ui-border);
}
.page-shell-title {
  color: var(--ui-text-highlighted);
  font-size: clamp(1.75rem, 1.4rem + 1.4vw, 2.375rem);
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.015em;
  overflow-wrap: anywhere;
}
.page-shell-subtitle {
  max-width: 42rem;
  color: var(--ui-text-muted);
  font-size: 1.0625rem;
  line-height: 1.55;
}
/* block flow, as `space-y` lays it out: a flex column would stretch a button to the width of the page */
.page-shell-body > * + * {
  margin-top: 1.5rem;
}
</style>
