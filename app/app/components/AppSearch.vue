<script setup lang="ts">
// The search of the header (GH-3518): one field that goes to any page, to a provider's page, or changes the theme or
// the language. Opened by its button, and by Ctrl+K (⌘K on a Mac), a shortcut with a modifier, so that it cannot be
// set off by typing (WCAG 2.1.4). Everything in it is also reachable without it: it is a shortcut, not a place.
const props = defineProps<{
  /** Show the word beside the magnifying glass (the wide header), or the glass alone */
  labelled?: boolean
}>()

const { t } = useI18n()
const open = ref(false)

defineShortcuts({
  meta_k: () => {
    open.value = !open.value
  },
})

// a Mac names the key ⌘, everything else Ctrl; read once the page runs, as the server cannot know
const isMac = ref(false)
onMounted(() => {
  isMac.value = /Mac|iP(?:hone|ad|od)/.test(navigator.platform || navigator.userAgent)
})
const shortcut = computed(() => isMac.value ? ['meta', 'K'] : ['ctrl', 'K'])
</script>

<template>
  <UButton
    color="neutral"
    variant="outline"
    icon="i-ph-magnifying-glass"
    :aria-label="props.labelled ? undefined : t('shell.search')"
    aria-haspopup="dialog"
    :aria-expanded="open"
    aria-keyshortcuts="Control+K Meta+K"
    class="rounded-full"
    :class="props.labelled ? 'ps-3 pe-2 min-w-40 justify-start text-muted' : ''"
    @click="open = true"
  >
    <template v-if="props.labelled">
      <span class="flex-1 text-start">{{ t('shell.search') }}</span>
      <span class="hidden xl:inline-flex items-center gap-0.5" aria-hidden="true">
        <UKbd v-for="key in shortcut" :key="key" :value="key" size="sm" />
      </span>
    </template>
  </UButton>

  <UModal
    v-model:open="open"
    :title="t('shell.search')"
    :description="t('shell.searchPlaceholder')"
    :close="false"
    :ui="{ content: 'sm:max-w-2xl sm:top-[12vh] sm:translate-y-0 max-h-[min(36rem,calc(100dvh-2rem))]', header: 'sr-only', body: 'p-0 sm:p-0 flex flex-col min-h-0' }"
  >
    <template #body>
      <AppSearchPalette @done="open = false" />
    </template>
  </UModal>
</template>
