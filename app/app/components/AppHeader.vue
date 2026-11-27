<script setup lang="ts">
import { visibleTabCount } from '~/utils/header-fit'
import { inSection } from '~/utils/sections'

// The header of every page but the widget (GH-3518). In the frame of the pages, so the logo stands over the left
// edge of each page's title. From 64 rem (1024 px at the default text size, wider when the reader has set a larger
// one) it carries the tools as tabs, in the order the reader chose (GH-3936, `useTabBar`, the same list as the
// tab bar's), and the reference as a disclosure. The tabs that do not fit in the row, in the reader's language at the
// width the window has, are measured and go from the end into a "More" menu (GH-4500); below that four of the tools, the first four of that order
// (GH-3846), are in the tab bar at the foot of the window (AppTabBar.vue), the others in its menu, and the header
// keeps the logo, the search and the settings. The start page's tiles, the footer and the palette keep the fixed
// order of `TOOLS`.
const { t } = useI18n()
const { headerTools } = useTabBar()
const route = useRoute()
// the search is labelled, and the support heart shown, from 90 rem, where the header has room for the word beside
// the six tools; in rem, so that a reader who has set a larger text size gets the shorter header sooner, as
// Tailwind's `xl:` does
const wide = useMediaQuery('(min-width: 90rem)')

// ---- the tabs that fit (GH-4500) --------------------------------------------------------------------------------------
// The row of the tabs is the room between the logo and the search (the nav fills it: `flex-1`, `min-w-0`). Every tab is measured in a copy of the
// row that is not seen (`.nav-measure`: the same classes, so the same widths in this language, with or without the tiles, at this text size), and
// `visibleTabCount` takes the tabs that fit, from the start; the others are in the "More" menu. Measured again whenever the room or a tab changes
// (a resize, the width of the search, the language, a font that has come, the reader's order). The tabs are not seen until the fonts they are set in
// have come (`document.fonts.ready`, at most `FONTS_WAIT_MS`: a face is a request of its own, and the tabs are as wide as its letters, in cs, pl and lb
// as the latin-ext subset's), so that the row is not shown with the width of a fallback face and then changes; the measurement itself is made in
// `onMounted`, before the first paint.
const FONTS_WAIT_MS = 1000
const nav = useTemplateRef<HTMLElement>('nav')
const measure = useTemplateRef<HTMLElement>('measure')
// the copy of the row the tabs are measured in is there only where the header shows the tabs (from 64 rem, `lg:`): below it there is nothing to
// measure, and an element with `inert` that is always in the page would be one a phone has no use for (the map's full screen counts the page's `inert`)
const tabsShown = useMediaQuery('(min-width: 64rem)')
const shown = ref(headerTools.value.length)
const ready = ref(false)
const visibleTools = computed(() => headerTools.value.slice(0, shown.value))
const moreTools = computed(() => headerTools.value.slice(shown.value))

function fit() {
  const layer = measure.value
  const room = nav.value
  if (!layer || !room)
    return
  const list = layer.querySelector<HTMLElement>('[data-measure="list"]')
  const row = layer.querySelector<HTMLElement>('[data-measure="row"]')
  const more = layer.querySelector<HTMLElement>('[data-measure="more"]')
  if (!list || !row || !more)
    return
  const widths = [...layer.querySelectorAll<HTMLElement>('[data-measure="tab"]')].map(tab => tab.getBoundingClientRect().width)
  const before = moreTools.value
  // where the focus is in the More menu, and the menu or its item is about to go (every tab fits now, or this one does), the focus goes to the tab that takes its place
  const active = document.activeElement
  const inMore = active instanceof HTMLElement && Boolean(room.querySelector('[data-testid="nav-more"]')?.contains(active))
  const focused = inMore ? active.closest('a')?.getAttribute('href') ?? null : null
  shown.value = visibleTabCount({
    widths,
    gap: Number.parseFloat(getComputedStyle(list).columnGap) || 0,
    fixed: row.getBoundingClientRect().width - list.getBoundingClientRect().width,
    more: more.getBoundingClientRect().width,
    available: room.getBoundingClientRect().width,
  })
  if (inMore && moreTools.value.length < before.length) {
    // the item the focus was on, or the first that left the menu where it was on the menu's button
    const target = before.find(tool => tool.to === focused && !moreTools.value.includes(tool)) ?? (focused === null ? before.find(tool => !moreTools.value.includes(tool)) : undefined)
    // the button stays while some tabs are in the menu: only an item or a button that is gone loses the focus
    if (target && (focused !== null || !moreTools.value.length))
      void nextTick(() => room.querySelector<HTMLElement>(`ul a[href="${target.to}"]`)?.focus())
  }
}
let revealCap: ReturnType<typeof setTimeout> | undefined
onBeforeUnmount(() => clearTimeout(revealCap))
onMounted(() => {
  fit()
  // the room changes with the window and with the search's word (90 rem); the tabs change with the media queries of the tiles (80 rem), the language and the fonts
  useResizeObserver([nav, measure], fit)
  const reveal = () => {
    ready.value = true
  }
  if (!document.fonts) {
    reveal()
    return
  }
  revealCap = setTimeout(reveal, FONTS_WAIT_MS)
  void document.fonts.ready.then(() => {
    fit()
    clearTimeout(revealCap)
    reveal()
  })
})
// the copy comes with the width and goes with it: measured when it has come
watch([headerTools, () => t('shell.more'), tabsShown], () => void nextTick(fit))
</script>

<template>
  <header class="app-header" data-print="hide">
    <div class="frame flex h-full items-center gap-2 lg:gap-4">
      <!-- on a phone the bar is 44 px (GH-4226): the link is as high as it, with a smaller logo and name -->
      <NuxtLink to="/" class="brand -ms-1.5 flex shrink-0 items-center gap-2.5 rounded-lg p-1.5 max-sm:min-h-11 max-sm:gap-2 max-sm:px-1.5 max-sm:py-1" :aria-current="route.path === '/' ? 'page' : undefined">
        <img src="/icon.svg" alt="" width="32" height="32" class="size-8 max-sm:size-7">
        <!-- the name is the link's name at every width; written out where there is room for it -->
        <span class="wordmark lg:max-xl:sr-only text-lg font-bold tracking-tight text-highlighted max-sm:text-base">Wetterdienst</span>
      </NuxtLink>

      <nav ref="nav" :aria-label="t('shell.mainNav')" class="app-nav hidden h-full items-center gap-1 lg:flex" :class="{ 'app-nav-pending': !ready }">
        <ul class="flex h-full items-center gap-1">
          <li v-for="tool in visibleTools" :key="tool.key" class="h-full flex items-center">
            <NuxtLink
              :to="tool.to"
              class="nav-tab"
              :aria-current="inSection(tool, route.path) ? 'page' : undefined"
            >
              <ToolTile :tile="tool.tile" :icon="tool.icon" size="1.5rem" />
              <span class="nav-label" :data-text="t(tool.label)">{{ t(tool.label) }}</span>
            </NuxtLink>
          </li>
          <li v-if="moreTools.length" class="h-full flex items-center">
            <NavMoreMenu :tools="moreTools" />
          </li>
        </ul>
        <span class="mx-1 h-6 w-px bg-(--ui-border)" aria-hidden="true" />
        <ReferenceMenu />
      </nav>

      <!-- the row as it would be with every tab and no "More" button, which is not seen and no part of the page: the widths the fitting is done from -->
      <div v-if="tabsShown" ref="measure" class="nav-measure" aria-hidden="true" inert>
        <div data-measure="row" class="flex items-center gap-1">
          <ul data-measure="list" class="flex items-center gap-1">
            <li v-for="tool in headerTools" :key="tool.key">
              <span class="nav-tab" data-measure="tab">
                <ToolTile :tile="tool.tile" :icon="tool.icon" size="1.5rem" />
                <span class="nav-label" :data-text="t(tool.label)">{{ t(tool.label) }}</span>
              </span>
            </li>
          </ul>
          <span class="mx-1 h-6 w-px" />
          <span class="nav-tab">
            <span class="nav-label" :data-text="t('shell.reference')">{{ t('shell.reference') }}</span>
            <UIcon name="i-ph-caret-down" class="size-4 shrink-0" />
          </span>
        </div>
        <span class="nav-tab" data-measure="more">
          <span class="nav-label" :data-text="t('shell.more')">{{ t('shell.more') }}</span>
          <UIcon name="i-ph-caret-down" class="size-4 shrink-0" />
        </span>
      </div>

      <!-- the two icon buttons of a phone are 44 px targets (AppSearch, SettingsMenu) -->
      <div class="ms-auto flex items-center gap-0.5 sm:gap-1.5">
        <AppSearch :labelled="wide" />
        <UTooltip :text="t('nav.support')">
          <UButton
            to="/support"
            icon="i-ph-heart"
            color="neutral"
            variant="ghost"
            class="max-[90rem]:hidden"
            :aria-label="t('nav.support')"
          />
        </UTooltip>
        <SettingsMenu />
      </div>
    </div>
  </header>
</template>
