<script setup lang="ts">
// The country of a provider, as the two capital letters of its code in the monospaced face; a provider of no one country
// (NOAA's worldwide GHCN, EUMETNET: the backend gives `null`) gets a globe, and anything else that is no code gets nothing,
// so a card never shows stray letters. Text and an icon, not a flag: a flag is an emoji that some systems draw as letters
// and others not at all.
const props = defineProps<{ country: string | null }>()

const code = computed(() => props.country !== null && /^[A-Z]{2}$/.test(props.country) ? props.country : null)
</script>

<template>
  <span v-if="props.country === null || code" class="inline-flex min-w-5 items-center justify-center font-mono text-xs text-muted" aria-hidden="true">
    <template v-if="code">{{ code }}</template>
    <UIcon v-else name="i-ph-globe-hemisphere-west" class="size-4" />
  </span>
</template>
