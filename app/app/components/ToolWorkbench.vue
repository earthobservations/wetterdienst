<script setup lang="ts">
// The layout of a tool (GH-3518): what to look at on the left, what comes of it on the right. From 72 rem (1152 px at
// the default text size) the two stand side by side, the result taking the width that a chart and a table want;
// below that, and on paper, they stack in the same order, so the order of reading and of the keyboard is the same at
// every width: first the choice, then its result.
defineSlots<{ setup: () => unknown, result: () => unknown }>()
</script>

<template>
  <div class="workbench" data-layout="workbench">
    <div class="workbench-setup">
      <slot name="setup" />
    </div>
    <div class="workbench-result">
      <slot name="result" />
    </div>
  </div>
</template>

<style>
.workbench {
  display: grid;
  /* one column no wider than the page: an implicit column would grow to the widest thing in it (the forecast's row
     of day cards, a table), and the page would scroll sideways */
  grid-template-columns: minmax(0, 1fr);
  gap: 1.5rem;
  align-items: start;
}
.workbench-setup,
.workbench-result {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  min-width: 0;
}
@media (min-width: 72rem) {
  .workbench {
    grid-template-columns: minmax(20rem, 26rem) minmax(0, 1fr);
    gap: 2rem;
  }
}
</style>
