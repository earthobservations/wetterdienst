<script setup lang="ts">
// The search of the header (GH-3518), on every page: one field that goes to any page, to a provider's page, to the
// forecast of a station, or changes the theme or the language (AppCommandPalette.vue). Opened by its button, and by
// Ctrl+K (⌘K on a Mac), a shortcut with a modifier, so that it cannot be set off by typing (WCAG 2.1.4). A dialog:
// it holds the focus, Escape closes it, and the focus goes back to what had it before. Everything in it is also
// reachable without it: it is a shortcut, not a place. On a phone (below 40 rem) the dialog is a bar at the top of the window,
// the field where the top bar is, so that the search opens over the bar it was tapped in (GH-4226); wider it is in the middle.
const props = defineProps<{
  /** Show the word beside the magnifying glass (the wide header), or the glass alone */
  labelled?: boolean
}>()

const { t } = useI18n()
const open = ref(false)
// the page behind the open dialog is held on iOS, and a finger in it moves nothing behind it (GH-3761)
const hold = useModalDialogHold(open)
// a step of the history (the back swipe) or a link takes the reader to another page: the dialog is closed with it, as the
// menu sheet is (AppTabBar.vue), and does not stay over the page that is arrived at
const route = useRoute()
watch(() => route.path, () => {
  open.value = false
})

// Ctrl+K and ⌘K on every system (Nuxt UI's `meta_k` is ⌘K alone on a Mac, where a reader may well use Ctrl), and
// from a field as well: the search is where one goes from anywhere
useEventListener(window, 'keydown', (event: KeyboardEvent) => {
  if (typeof event.key !== 'string' || event.key.toLowerCase() !== 'k' || !(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey || event.repeat)
    return
  event.preventDefault()
  open.value = !open.value
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
    class="rounded-full max-sm:size-11 max-sm:justify-center max-sm:bg-transparent max-sm:ring-0"
    :class="props.labelled ? 'ps-3 pe-2 min-w-32 justify-start text-muted' : ''"
    @click="open = true"
  >
    <template v-if="props.labelled">
      <span class="flex-1 text-start">{{ t('shell.search') }}</span>
      <span class="hidden min-[90rem]:inline-flex items-center gap-0.5" aria-hidden="true">
        <UKbd v-for="key in shortcut" :key="key" :value="key" size="sm" />
      </span>
    </template>
  </UButton>

  <UModal
    v-model:open="open"
    :title="t('shell.search')"
    :description="t('shell.searchPlaceholder')"
    :close="false"
    :ui="{ content: 'app-vv-dialog app-search-dialog sm:max-w-2xl sm:top-[12vh] sm:translate-y-0 max-h-[min(36rem,calc(100dvh-2rem))] sm:max-h-[min(36rem,calc(100dvh-16vh))] max-sm:top-0 max-sm:left-0 max-sm:w-full max-sm:max-w-none max-sm:translate-x-0 max-sm:translate-y-0 max-sm:rounded-t-none max-sm:pt-(--safe-top) max-sm:max-h-[min(36rem,100dvh)]', header: 'sr-only', body: 'p-0 sm:p-0 flex flex-col min-h-0' }"
    @after:leave="hold.afterLeave"
  >
    <template #body>
      <AppCommandPalette @done="open = false" />
    </template>
  </UModal>
</template>
