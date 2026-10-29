<script setup lang="ts">
// The small drawings of the home page's three ways in (GH-3518): schematic, drawn here, a few hundred bytes each,
// and decoration only (the words beside them say what each way in is). Not data: the forecast's curve and the
// stripes' run from cool to warm are shapes, not readings.
defineProps<{ kind: 'forecast' | 'stripes' | 'explorer' }>()

// the stripes' palette (stripes.vue), from the coolest to the warmest class, as a schematic run
const STRIPES = ['#053061', '#2166ac', '#4393c3', '#92c5de', '#d1e5f0', '#f7f7f7', '#fddbc7', '#f4a582', '#ef8a62', '#d6604d', '#b2182b', '#67001f']
// station dots of the explorer's map
const DOTS: Array<[number, number]> = [[18, 14], [42, 22], [64, 10], [90, 18], [118, 12], [140, 24], [26, 38], [52, 46], [78, 34], [104, 42], [132, 50], [14, 56], [60, 60], [96, 58], [148, 40], [36, 26], [120, 30]]
</script>

<template>
  <svg
    viewBox="0 0 160 64"
    class="w-full h-auto block"
    aria-hidden="true"
    focusable="false"
    preserveAspectRatio="xMidYMid meet"
  >
    <template v-if="kind === 'forecast'">
      <!-- nights as bands, the temperature as a curve, the rain as bars -->
      <rect x="30" y="0" width="22" height="64" class="fill-(--ui-bg-elevated)" />
      <rect x="84" y="0" width="22" height="64" class="fill-(--ui-bg-elevated)" />
      <rect x="138" y="0" width="22" height="64" class="fill-(--ui-bg-elevated)" />
      <g class="fill-tile-rain" opacity="0.75">
        <rect x="58" y="52" width="4" height="12" />
        <rect x="64" y="46" width="4" height="18" />
        <rect x="70" y="55" width="4" height="9" />
        <rect x="112" y="58" width="4" height="6" />
      </g>
      <path d="M0 40 C 14 22, 24 18, 36 30 S 56 46, 70 30 S 92 14, 100 26 S 124 44, 140 28 S 154 20, 160 24" fill="none" class="stroke-tile-heat" stroke-width="2.5" stroke-linecap="round" />
    </template>
    <template v-else-if="kind === 'stripes'">
      <rect
        v-for="(colour, index) in STRIPES" :key="colour"
        :x="index * (160 / STRIPES.length)" y="0" :width="160 / STRIPES.length + 0.5" height="64" :fill="colour"
      />
    </template>
    <template v-else>
      <!-- stations on a map, one of them chosen -->
      <path d="M0 50 C 30 44, 50 58, 80 50 S 130 40, 160 46" fill="none" class="stroke-(--app-rule)" stroke-width="1.5" />
      <path d="M0 20 C 40 30, 70 8, 110 18 S 150 28, 160 22" fill="none" class="stroke-(--app-rule)" stroke-width="1.5" />
      <circle v-for="([x, y], index) in DOTS" :key="index" :cx="x" :cy="y" r="2.5" class="fill-(--ui-text-muted)" />
      <circle cx="78" cy="34" r="8" fill="none" class="stroke-tile-rain" stroke-width="2.5" />
      <circle cx="78" cy="34" r="3" class="fill-tile-rain" />
    </template>
  </svg>
</template>
