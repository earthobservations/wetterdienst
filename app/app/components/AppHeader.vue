<script setup lang="ts">
/**
 * The header (GH-3518): the logo, the three pages for a place, the place the visitor chose, the quick
 * settings and the menu, which has every page. It scrolls with the page rather than stay on top of it, so
 * that nothing covers what has the focus (WCAG 2.4.11), and at 400 % zoom the page keeps its height.
 */
const { t } = useI18n()
const { primary, isActive } = useAppNav()
const { place } = usePlace()

const menuOpen = ref(false)
const route = useRoute()
watch(() => route.fullPath, () => {
  menuOpen.value = false
})

// The command palette (AppPalette.vue): the search button, and Ctrl+K / ⌘K on every page, which browsers would
// otherwise take for their own search bar. The menu gives way to it.
const paletteOpen = ref(false)
const isMac = ref(false)
onMounted(() => {
  isMac.value = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)
})
useEventListener(window, 'keydown', (event: KeyboardEvent) => {
  if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    menuOpen.value = false
    paletteOpen.value = true
  }
})
</script>

<template>
  <header class="wd-noprint">
    <div class="mx-auto flex h-16 w-full max-w-[calc(90rem+2*var(--wd-gutter))] items-center gap-2 px-(--wd-gutter)">
      <NuxtLink
        to="/"
        class="-ml-1 flex shrink-0 items-center gap-2.5 rounded-lg p-1 text-lg font-extrabold tracking-tight text-highlighted"
      >
        <img src="/icon.svg" alt="" class="size-8" width="32" height="32">
        <span>Wetterdienst</span>
      </NuxtLink>

      <nav :aria-label="t('header.mainNav')" class="ml-4 hidden lg:block">
        <ul class="flex items-center gap-1">
          <li v-for="item in primary" :key="item.key">
            <NuxtLink
              :to="item.to"
              :aria-current="isActive(item.to) ? 'page' : undefined"
              class="flex items-center gap-2 rounded-full px-3.5 py-2 text-sm font-semibold transition-colors"
              :class="isActive(item.to)
                ? 'bg-ink-900 text-white dark:bg-white dark:text-ink-900'
                : 'text-ink-700 hover:bg-white hover:text-ink-900 dark:text-ink-200 dark:hover:bg-ink-800 dark:hover:text-white'"
            >
              <UIcon :name="item.icon" class="size-4 shrink-0" />
              {{ item.label }}
            </NuxtLink>
          </li>
        </ul>
      </nav>

      <div class="ml-auto flex min-w-0 items-center gap-1">
        <!-- the place the visitor chose, back to its forecast in one tap -->
        <NuxtLink
          v-if="place"
          :to="`/meteogram?station=${encodeURIComponent(place.id)}`"
          class="mr-1 hidden min-w-0 items-center gap-1.5 rounded-full bg-white/80 px-3 py-1.5 text-sm font-semibold text-ink-800 ring-1 ring-ink-200 transition-colors hover:bg-white sm:flex dark:bg-ink-900/70 dark:text-ink-100 dark:ring-ink-700 dark:hover:bg-ink-900"
        >
          <UIcon name="i-lucide-map-pin" class="size-4 shrink-0 text-ember" />
          <span class="sr-only">{{ t('header.yourPlace') }}:</span>
          <span class="truncate max-w-40">{{ placeName(place.name) }}</span>
        </NuxtLink>
        <button
          type="button"
          class="flex h-9 items-center gap-2 rounded-full bg-white/80 px-2.5 text-sm font-semibold text-ink-700 ring-1 ring-ink-200 transition-colors hover:bg-white hover:text-ink-900 md:pr-2 md:pl-3 dark:bg-ink-900/70 dark:text-ink-200 dark:ring-ink-700 dark:hover:bg-ink-900 dark:hover:text-white"
          :aria-label="t('palette.open')"
          aria-haspopup="dialog"
          :aria-expanded="paletteOpen"
          aria-keyshortcuts="Control+K Meta+K"
          @click="paletteOpen = true"
        >
          <UIcon name="i-lucide-search" class="size-4 shrink-0" />
          <span class="hidden md:inline">{{ t('palette.open') }}</span>
          <kbd class="hidden rounded-md bg-ink-100 px-1.5 py-0.5 font-sans text-xs text-ink-700 md:inline dark:bg-ink-800 dark:text-ink-200" aria-hidden="true">{{ isMac ? '⌘K' : 'Ctrl K' }}</kbd>
        </button>
        <SettingsMenu />
        <UButton
          icon="i-lucide-menu"
          color="neutral"
          variant="ghost"
          :aria-label="t('header.menu')"
          aria-haspopup="dialog"
          :aria-expanded="menuOpen"
          :ui="{ label: 'hidden sm:inline' }"
          :label="t('header.menu')"
          class="font-semibold"
          @click="menuOpen = true"
        />
      </div>
    </div>
    <AppMenu v-model:open="menuOpen" />
    <AppPalette v-model:open="paletteOpen" />
  </header>
</template>
