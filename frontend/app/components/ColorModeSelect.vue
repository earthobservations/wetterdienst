<script setup lang="ts">
const colorMode = useColorMode()

const modes = [
  { value: 'system', icon: 'i-lucide-monitor' },
  { value: 'light', icon: 'i-lucide-sun' },
  { value: 'dark', icon: 'i-lucide-moon' },
  { value: 'sepia', icon: 'i-lucide-coffee' },
] as const

const currentIcon = computed(() => {
  const mode = modes.find(m => m.value === colorMode.preference)
  return mode?.icon ?? 'i-lucide-monitor'
})

function cycleMode() {
  const currentIndex = modes.findIndex(m => m.value === colorMode.preference)
  const nextIndex = (currentIndex + 1) % modes.length
  colorMode.preference = modes[nextIndex]?.value ?? modes[0].value
}
</script>

<template>
  <UButton
    :icon="currentIcon"
    color="neutral"
    variant="ghost"
    @click="cycleMode"
  />
</template>
