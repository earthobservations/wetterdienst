<script setup lang="ts">
// Opens the command palette (AppSearch): a field-like button with the shortcut beside it, or an icon where there is no
// room for the words.
// `shortcut` is whether to show the keys that open it, which a phone has none of.
const props = withDefaults(defineProps<{ collapsed?: boolean, shortcut?: boolean }>(), { collapsed: false, shortcut: true })

const { t } = useI18n()
const open = useState('app-search-open', () => false)
</script>

<template>
  <UButton
    icon="i-ph-magnifying-glass"
    color="neutral"
    :variant="props.collapsed ? 'ghost' : 'outline'"
    :label="props.collapsed ? undefined : t('nav.search')"
    :square="props.collapsed"
    :block="!props.collapsed"
    :aria-label="t('nav.search')"
    :class="props.collapsed ? '' : 'justify-start font-normal text-muted'"
    @click="open = true"
  >
    <template v-if="!props.collapsed && props.shortcut" #trailing>
      <span class="ms-auto flex items-center gap-0.5" aria-hidden="true">
        <UKbd value="meta" />
        <UKbd value="K" />
      </span>
    </template>
  </UButton>
</template>
