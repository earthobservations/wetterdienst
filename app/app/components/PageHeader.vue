<script setup lang="ts">
// The head of a page (GH-3518): the one h1, an optional lead, an optional tile with the page's icon in one of the
// colours of the logo's tiles, and, in the `actions` slot, what the page offers beside its title. The same on every
// page, so that titles start at the same place and are the same size.
withDefaults(defineProps<{
  title: string
  lead?: string
  icon?: string
  tone?: 'blue' | 'sun' | 'teal' | 'coral'
}>(), { tone: 'blue' })

const TONES = {
  blue: 'bg-brand-600 text-white',
  sun: 'bg-sun text-ink-950',
  teal: 'bg-teal text-ink-950',
  coral: 'bg-coral text-ink-950',
} as const
</script>

<template>
  <div class="app-rise pb-2">
    <div class="flex flex-wrap items-center justify-between gap-x-6 gap-y-4">
      <div class="flex min-w-0 items-center gap-4">
        <span
          v-if="icon"
          class="grid size-11 shrink-0 place-items-center rounded-2xl shadow-(--app-shadow-sm) sm:size-12"
          :class="TONES[tone]"
          aria-hidden="true"
        >
          <UIcon :name="icon" class="size-6" />
        </span>
        <h1 class="min-w-0 text-3xl font-bold leading-tight text-highlighted break-words text-balance sm:text-4xl">
          {{ title }}
        </h1>
      </div>
      <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
    <p v-if="lead" class="mt-4 max-w-2xl text-base text-muted text-pretty sm:text-lg">
      {{ lead }}
    </p>
  </div>
</template>
