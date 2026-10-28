<script setup lang="ts">
// "App 0.39.0 · Backend 0.178.0": small, muted and monospaced, under the settings of the navigation (and inside their
// popover where the navigation is a rail of icons).
const { text } = useAppVersions()
</script>

<template>
  <p class="font-mono text-[0.6875rem] leading-4 text-muted" data-testid="app-versions">
    {{ text }}
  </p>
</template>
