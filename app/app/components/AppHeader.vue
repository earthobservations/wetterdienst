<script setup lang="ts">
import { inSection, TOOLS } from '~/utils/sections'

// The header of every page but the widget (GH-3518). In the frame of the pages, so the logo stands over the left
// edge of each page's title. From 64 rem (1024 px at the default text size, wider when the reader has set a larger
// one) it carries the four tools as tabs and the reference as a disclosure; below that the tools are in the tab bar
// at the foot of the window (AppTabBar.vue) and the header keeps the logo, the search and the settings.
const { t } = useI18n()
const route = useRoute()
// the search is labelled from 80 rem, where the header has room for the word; in rem, so that a reader who has set
// a larger text size gets the shorter header sooner, as Tailwind's `xl:` does
const wide = useMediaQuery('(min-width: 80rem)')
</script>

<template>
  <header class="app-header" data-print="hide">
    <div class="frame flex h-full items-center gap-2 lg:gap-4">
      <NuxtLink to="/" class="brand -ms-1.5 flex shrink-0 items-center gap-2.5 rounded-lg p-1.5" :aria-current="route.path === '/' ? 'page' : undefined">
        <img src="/icon.svg" alt="" width="32" height="32" class="size-8">
        <!-- the name is the link's name at every width; written out where there is room for it -->
        <span class="wordmark lg:max-xl:sr-only text-lg font-bold tracking-tight text-highlighted">Wetterdienst</span>
      </NuxtLink>

      <nav :aria-label="t('shell.mainNav')" class="hidden h-full items-center gap-1 lg:flex">
        <ul class="flex h-full items-center gap-1">
          <li v-for="tool in TOOLS" :key="tool.key" class="h-full flex items-center">
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

      <div class="ms-auto flex items-center gap-1 sm:gap-1.5">
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
