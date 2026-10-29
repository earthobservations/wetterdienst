<script setup lang="ts">
// A band of vertical stripes in the manner of the climate stripes, in the colours of the tokens of main.css (the logo's navy,
// blue, sun and coral, and the tints between): decoration only (the
// real stripes are the page of that name). The values are a fixed rising line with a fixed, seeded wobble, so the band
// is the same on every load and in every test; nothing here is data.
const props = withDefaults(defineProps<{ count?: number }>(), { count: 64 })

// cold to warm: the logo's navy and blue, a pale blue, the cream between, then its sun and coral, and a deeper red
const SCALE = [
  'var(--color-ink-800)',
  'var(--color-brand-600)',
  'var(--color-brand-400)',
  'var(--color-brand-200)',
  'var(--color-sand)',
  'var(--color-sun)',
  'var(--color-coral)',
  'var(--color-ember)',
]

const bars = computed(() => {
  let seed = 7
  const next = () => {
    seed = (seed * 16807) % 2147483647
    return seed / 2147483647
  }
  return Array.from({ length: props.count }, (_, index) => {
    const trend = index / (props.count - 1)
    const value = Math.min(1, Math.max(0, 0.08 + trend * 0.82 + (next() - 0.5) * 0.36))
    return SCALE[Math.min(SCALE.length - 1, Math.floor(value * SCALE.length))]!
  })
})
</script>

<template>
  <svg
    class="block w-full h-full [forced-color-adjust:none]"
    :viewBox="`0 0 ${count} 1`"
    preserveAspectRatio="none"
    aria-hidden="true"
    focusable="false"
  >
    <rect v-for="(color, index) in bars" :key="index" :x="index" y="0" width="1.02" height="1" :style="{ fill: color }" />
  </svg>
</template>
