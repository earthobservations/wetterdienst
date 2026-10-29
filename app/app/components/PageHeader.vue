<script setup lang="ts">
/**
 * The head of a page (GH-3518): what part of the app it is in, its title (the page's one `h1`) and a
 * sentence of what it is for, laid over the sky (SkyBackdrop.vue), so its text is of the strong colours
 * that keep 4.5:1 on every colour of the sky (main.css). An `actions` slot takes the page's own buttons.
 */
defineProps<{
  title: string
  lead?: string
  /** The part of the app, above the title: `Weather`, `Climate`, `Data`, `Project` */
  eyebrow?: string
  icon?: string
}>()
</script>

<template>
  <div class="pt-6 pb-8 sm:pt-10 sm:pb-10">
    <p v-if="eyebrow" class="mb-3 inline-flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-brand-700 dark:text-brand-300">
      <UIcon v-if="icon" :name="icon" class="size-4 shrink-0" />
      {{ eyebrow }}
    </p>
    <div class="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div class="min-w-0 max-w-2xl">
        <h1 class="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-highlighted break-words text-balance">
          {{ title }}
        </h1>
        <p v-if="lead" class="mt-3 text-base sm:text-lg text-toned text-pretty">
          {{ lead }}
        </p>
        <slot name="lead" />
      </div>
      <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>
