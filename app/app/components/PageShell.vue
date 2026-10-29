<script setup lang="ts">
/**
 * The one page container (GH-3518): the same gutters at every width (`--wd-gutter`, main.css), and one of
 * three widths, centred: `prose` for text, `default` for forms and lists, `wide` for the map and chart pages.
 * The header and the footer are `wide`, so a wide page lines up with them at both edges.
 */
withDefaults(defineProps<{
  width?: 'prose' | 'default' | 'wide'
  as?: string
}>(), { width: 'default', as: 'div' })
</script>

<template>
  <component
    :is="as"
    class="mx-auto w-full px-(--wd-gutter) pb-16"
    :class="{
      'max-w-[calc(48rem+2*var(--wd-gutter))]': width === 'prose',
      'max-w-[calc(64rem+2*var(--wd-gutter))]': width === 'default',
      'max-w-[calc(90rem+2*var(--wd-gutter))]': width === 'wide',
    }"
  >
    <slot />
  </component>
</template>
