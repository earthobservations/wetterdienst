<script setup lang="ts">
// The country of a provider, as the two letters of its code in the monospaced face; a provider of no one country (NOAA's
// worldwide GHCN, EUMETNET) gets a globe. Text and an icon, not a flag: a flag is an emoji that some systems draw as letters
// and others not at all.
defineProps<{ country: string | null }>()
</script>

<template>
  <span class="inline-flex min-w-5 items-center justify-center font-mono text-xs text-muted" aria-hidden="true">
    <template v-if="country">{{ country.toUpperCase() }}</template>
    <UIcon v-else name="i-ph-globe-hemisphere-west" class="size-4" />
  </span>
</template>
