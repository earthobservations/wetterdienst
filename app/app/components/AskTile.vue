<script setup lang="ts">
// A rounded square with an icon, as the four of the logo are drawn: sun, rain, wind and warmth. The colour says
// which kind of weather a question is about; the icon is decoration, the text beside it says it in words.
export type TileTone = 'sun' | 'rain' | 'wind' | 'warmth' | 'plain'

withDefaults(defineProps<{
  icon: string
  tone?: TileTone
  size?: 'sm' | 'md' | 'lg'
}>(), { tone: 'plain', size: 'md' })
</script>

<template>
  <span
    class="app-tile inline-flex shrink-0 items-center justify-center"
    :class="[`app-tile--${tone}`, `app-tile--${size}`]"
    aria-hidden="true"
  >
    <UIcon :name="icon" class="app-tile__icon" />
  </span>
</template>

<style scoped>
.app-tile {
  border-radius: 32%;
  color: var(--app-on-tile);
}
.app-tile--sm {
  width: 2rem;
  height: 2rem;
}
.app-tile--md {
  width: 2.75rem;
  height: 2.75rem;
}
.app-tile--lg {
  width: 3.5rem;
  height: 3.5rem;
}
.app-tile--sm .app-tile__icon {
  width: 1.125rem;
  height: 1.125rem;
}
.app-tile--md .app-tile__icon {
  width: 1.5rem;
  height: 1.5rem;
}
.app-tile--lg .app-tile__icon {
  width: 1.875rem;
  height: 1.875rem;
}
.app-tile--sun {
  background: var(--color-sun);
}
/* white on the logo's blue, as in the logo (4.9:1) */
.app-tile--rain {
  background: var(--color-rain);
  color: #fff;
}
.app-tile--wind {
  background: var(--color-wind);
}
.app-tile--warmth {
  background: var(--color-warmth);
}
.app-tile--plain {
  background: var(--ui-bg-elevated);
  color: var(--ui-text-highlighted);
}
</style>
