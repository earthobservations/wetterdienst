<script setup lang="ts">
import { inSection } from '~/utils/sections'

// The header of every page but the widget (GH-3518). In the frame of the pages, so the logo stands over the left
// edge of each page's title. From 64 rem (1024 px at the default text size, wider when the reader has set a larger
// one) it carries the five tools as tabs, in the order the reader chose (GH-3936, `useTabBar`, the same list as the
// tab bar's), and the reference as a disclosure; below that four of the tools, the first four of that order
// (GH-3846), are in the tab bar at the foot of the window (AppTabBar.vue), the others in its menu, and the header
// keeps the logo, the search and the settings. The start page's tiles, the footer and the palette keep the fixed
// order of `TOOLS`.
const { t } = useI18n()
const { headerTools } = useTabBar()
const route = useRoute()
// the search is labelled from 80 rem, where the header has room for the word; in rem, so that a reader who has set
// a larger text size gets the shorter header sooner, as Tailwind's `xl:` does
const wide = useMediaQuery('(min-width: 80rem)')
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

      <nav :aria-label="t('shell.mainNav')" class="hidden h-full items-center gap-1 lg:flex">
        <ul class="flex h-full items-center gap-1">
          <li v-for="tool in headerTools" :key="tool.key" class="h-full flex items-center">
            <NuxtLink
              :to="tool.to"
              class="nav-tab"
              :aria-current="inSection(tool, route.path) ? 'page' : undefined"
            >
              <ToolTile :tile="tool.tile" :icon="tool.icon" size="1.5rem" />
              <span class="nav-label" :data-text="t(tool.label)">{{ t(tool.label) }}</span>
            </NuxtLink>
          </li>
        </ul>
        <span class="mx-1 h-6 w-px bg-(--ui-border)" aria-hidden="true" />
        <ReferenceMenu />
      </nav>

      <!-- the two icon buttons of a phone are 44 px targets (AppSearch, SettingsMenu) -->
      <div class="ms-auto flex items-center gap-0.5 sm:gap-1.5">
        <AppSearch :labelled="wide" />
        <UTooltip :text="t('nav.support')">
          <UButton
            to="/support"
            icon="i-ph-heart"
            color="neutral"
            variant="ghost"
            class="max-xl:hidden"
            :aria-label="t('nav.support')"
          />
        </UTooltip>
        <SettingsMenu />
      </div>
    </div>
  </header>
</template>
