<script setup lang="ts">
// The head of a page (GH-3518): the one h1, an optional lead, and, in the `actions` slot, what the page offers beside its
// title. The same on every page, so that titles start at the same place and are the same size.
defineProps<{
  title: string
  lead?: string
}>()
</script>

<template>
  <div>
    <div class="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <h1 class="min-w-0 text-3xl font-semibold leading-tight text-highlighted break-words text-balance sm:text-4xl">
        {{ title }}
      </h1>
      <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
    <p v-if="lead" class="mt-3 max-w-2xl text-base text-muted text-pretty sm:text-lg">
      {{ lead }}
    </p>
  </div>
</template>
