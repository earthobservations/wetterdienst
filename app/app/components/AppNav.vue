<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

// The navigation of the app (GH-3518): the brand, the search, the places in three groups, and the settings. It is
// the sidebar's content from 1024 px (icons only until 1280 px), and the drawer's below. The same list serves the
// command palette (`useAppNav`).
const props = withDefaults(defineProps<{ collapsed?: boolean }>(), { collapsed: false })
const emit = defineEmits<{ navigate: [] }>()

const { t } = useI18n()
const { groups } = useAppNav()

// one list per group, a label ahead of the items of a group that has one (hidden in the rail, where the groups are
// told apart by their spacing)
const items = computed<NavigationMenuItem[][]>(() => groups.value.map(group => [
  ...(group.label ? [{ label: group.label, type: 'label' as const }] : []),
  ...group.items.map(item => ({ ...item, onSelect: () => emit('navigate') })),
]))
</script>

<template>
  <div class="flex h-full min-h-0 flex-col gap-4 py-4" :class="props.collapsed ? 'items-center px-2' : 'px-3'">
    <NuxtLink
      to="/"
      class="flex items-center gap-2.5 rounded-md px-2 py-1 text-highlighted"
      :class="props.collapsed ? 'justify-center px-0' : ''"
      aria-label="Wetterdienst"
      @click="emit('navigate')"
    >
      <img src="/icon.svg" alt="" class="size-7 shrink-0 rounded-md">
      <span v-if="!props.collapsed" class="text-base font-semibold tracking-tight">Wetterdienst</span>
    </NuxtLink>

    <AppSearchButton :collapsed="props.collapsed" />

    <UNavigationMenu
      orientation="vertical"
      :items="items"
      :collapsed="props.collapsed"
      :tooltip="props.collapsed"
      :aria-label="t('header.menu')"
      :ui="{ linkLabel: props.collapsed ? 'sr-only' : 'truncate' }"
      class="min-h-0 flex-1 overflow-y-auto"
    />

    <SettingsMenu :collapsed="props.collapsed" @navigate="emit('navigate')" />
  </div>
</template>
