<script setup lang="ts">
// The credit Yr's symbols ask for (CC BY 4.0) where they are shown: under the chart, and under the day cards and rows where there is no chart
// (the compact view, the map's panel, the widget's narrow frame; GH-4193). A class and a `data-testid` given to it are those of the paragraph.
</script>

<template>
  <i18n-t keypath="meteogram.chart.symbolsCredit" tag="p" scope="global">
    <template #yr>
      <a href="https://github.com/nrkno/yr-weather-symbols" target="_blank" rel="noopener" class="underline underline-offset-2">Yr</a>
    </template>
    <template #licence>
      <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener" class="underline underline-offset-2">CC BY 4.0</a>
    </template>
  </i18n-t>
</template>
