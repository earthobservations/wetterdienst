<script setup lang="ts">
const appConfig = useAppConfig()

const colors = [
  { name: 'green', hex: '#22c55e' },
  { name: 'blue', hex: '#3b82f6' },
  { name: 'purple', hex: '#a855f7' },
  { name: 'pink', hex: '#ec4899' },
  { name: 'orange', hex: '#f97316' },
  { name: 'red', hex: '#ef4444' },
] as const

const currentColor = computed(() => appConfig.ui.colors.primary)

function setColor(color: string) {
  appConfig.ui.colors.primary = color
}
</script>

<template>
  <UPopover>
    <UButton
      icon="i-lucide-palette"
      color="neutral"
      variant="ghost"
      aria-label="Change primary color"
    />
    <template #content>
      <div class="p-2 flex gap-2">
        <UTooltip
          v-for="color in colors"
          :key="color.name"
          :text="color.name"
        >
          <button
            class="w-8 h-8 rounded-full transition-transform hover:scale-110" :class="[
              currentColor === color.name && 'ring-2 ring-offset-2 ring-gray-400 dark:ring-gray-600',
            ]"
            :style="{ backgroundColor: color.hex }"
            @click="setColor(color.name)"
          />
        </UTooltip>
      </div>
    </template>
  </UPopover>
</template>
