<script setup lang="ts">
// The frame of every page but the widget (GH-3518). Navigation is a sidebar, not a bar across the top: it holds the
// places in three groups and the settings, takes no height from the page, and shows where you are. From 1280 px it is
// a column with labels, from 1024 px a rail of icons, below that a bar with a menu button that opens the same
// navigation as a drawer. The search (Ctrl or Cmd + K) is the quickest way anywhere, on every width. A page sets its
// own width with `PageContainer`, so that the gutters are the same everywhere.
const { t } = useI18n()
const route = useRoute()

const drawerOpen = ref(false)
watch(() => route.path, () => {
  drawerOpen.value = false
})

// What is printed is the page: the skip link, the sidebar or rail, the top bar and the footer are `print:hidden` (a print is
// not always made from a page whose scripts ran again, and the frame is laid out by the flag below, so the markup says it
// itself), and `plugins/print-light.client.ts` prints a dark page in the light colours.
// the sidebar is the large layout's: a drawer that is hidden with CSS would still hold the focus. The row layout is driven by
// this flag too, not by a Tailwind breakpoint: Tailwind's are in rem, which a browser set to a larger default font size
// makes wider than these pixels, and the rail and the page would stack
const large = useMediaQuery('(min-width: 1024px)')
const wide = useMediaQuery('(min-width: 1280px)')

// Where the focus is, taken before a change of layout draws the navigation anew (these watchers run before the page is
// updated): in the navigation (the sidebar, the top bar, a drawer or a popover over the page), or nowhere in particular.
function focusInNavigation(): Element | null {
  const active = document.activeElement
  return active && active !== document.body && active.closest('[data-app-nav], [role="dialog"]') ? active : null
}

watch(large, async (isLarge) => {
  const had = focusInNavigation()
  if (isLarge)
    drawerOpen.value = false
  // what had the focus (the menu button, an open drawer or popover) is gone with the layout: the page takes it, not the
  // body. A closing drawer or popover is given the time of its own exit first. A page that had no focus keeps none.
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 400))
  if (had && (!document.activeElement || document.activeElement === document.body))
    document.getElementById('main')?.focus({ preventScroll: true })
})

// From 1280 px the rail has labels: its links are drawn anew, and one that had the focus is given it again
watch(wide, async () => {
  const link = document.activeElement?.closest('aside nav a[href]')
  const href = link?.getAttribute('href')
  await nextTick()
  if (href && (!document.activeElement || document.activeElement === document.body))
    document.querySelector<HTMLElement>(`aside nav a[href="${CSS.escape(href)}"]`)?.focus({ preventScroll: true })
})

function skipToContent(event: Event) {
  event.preventDefault()
  document.getElementById('main')?.focus()
}
</script>

<template>
  <div class="min-h-screen print:block" :class="large ? 'flex' : ''">
    <a
      href="#main"
      class="fixed left-3 top-3 z-50 -translate-y-24 rounded-md print:hidden bg-default px-4 py-2 text-sm font-medium text-highlighted ring ring-default focus:translate-y-0"
      @click="skipToContent"
    >
      {{ t('nav.skip') }}
    </a>

    <div v-if="large" data-app-nav class="shrink-0 border-e border-default print:hidden" :class="wide ? 'w-(--app-sidebar-width)' : 'w-(--app-rail-width)'">
      <aside class="sticky top-0 h-screen">
        <AppNav :collapsed="!wide" />
      </aside>
    </div>

    <div class="flex min-w-0 flex-1 flex-col">
      <header v-if="!large" data-app-nav class="print:hidden sticky top-0 z-30 flex h-(--ui-header-height) items-center gap-2 border-b border-default bg-default/90 px-4 backdrop-blur sm:px-6">
        <NuxtLink to="/" class="flex items-center gap-2.5 rounded-md py-1 text-highlighted" aria-label="Wetterdienst">
          <img src="/icon.svg" alt="" class="size-7 rounded-md">
          <span class="text-base font-semibold tracking-tight">Wetterdienst</span>
        </NuxtLink>
        <div class="ms-auto flex items-center gap-1">
          <AppSearchButton collapsed />
          <UButton
            icon="i-ph-list"
            color="neutral"
            variant="ghost"
            :aria-label="t('header.menu')"
            aria-haspopup="dialog"
            :aria-expanded="drawerOpen"
            @click="drawerOpen = true"
          />
        </div>
      </header>

      <UMain id="main" tabindex="-1" class="flex-1">
        <slot />
      </UMain>
      <AppFooter />
    </div>
  </div>

  <!-- the navigation of the narrow layout. A dialog, not a layer of markup: the focus stays in it, Escape closes it and
       the page behind is hidden from a screen reader while it is open (WCAG 2.1.2, 2.4.3, 4.1.2) -->
  <USlideover
    v-model:open="drawerOpen"
    side="left"
    :title="t('header.menu')"
    :description="t('nav.drawerDescription')"
    :ui="{ content: 'max-w-xs', body: 'p-0 sm:p-0', header: 'absolute end-2 top-3 z-10 min-h-0 border-0 p-0', title: 'sr-only', description: 'sr-only' }"
  >
    <!-- the label in the language of the app, which Nuxt UI's own is only for the two it ships -->
    <template #close="{ ui }">
      <UButton icon="i-ph-x" color="neutral" variant="ghost" :aria-label="t('common.close')" :class="ui.close()" />
    </template>
    <template #body>
      <AppNav drawer @navigate="drawerOpen = false" />
    </template>
  </USlideover>

  <AppSearch />
</template>
