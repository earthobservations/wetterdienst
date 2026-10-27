<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

// The header of every page but the widget (GH-3518: moved out of app.vue, restyled; the links, their order and their
// names are those it had). On the width of the footer and of the wide pages, with the same gutters.
const { t } = useI18n()
const route = useRoute()

const mobileMenuOpen = ref(false)

watch(() => route.path, () => {
  mobileMenuOpen.value = false
})

// the menu is the narrow layout's: past the breakpoint the header shows the links itself, and a dialog
// that is hidden with CSS would still hold the focus
const wide = useMediaQuery('(min-width: 1024px)')
watch(wide, (isWide) => {
  if (isWide)
    mobileMenuOpen.value = false
})

const items = computed<NavigationMenuItem[]>(() =>
  [
    {
      label: t('nav.home'),
      icon: 'i-lucide-home',
      to: '/',
      active: route.path === '/',
    },
    {
      label: t('nav.meteogram'),
      icon: 'i-lucide-sun',
      to: '/meteogram',
      active: route.path.startsWith('/meteogram'),
    },
    {
      label: t('nav.stripes'),
      icon: 'i-lucide-bar-chart-3',
      to: '/stripes',
      active: route.path.startsWith('/stripes'),
    },
    {
      label: t('nav.explorer'),
      icon: 'i-lucide-globe',
      to: '/explorer',
      active: route.path.startsWith('/explorer'),
    },
    {
      label: t('nav.history'),
      icon: 'i-lucide-clock',
      to: '/history',
      active: route.path.startsWith('/history'),
    },
    {
      label: t('nav.api'),
      icon: 'i-lucide-code',
      to: '/api',
      active: route.path.startsWith('/api'),
    },
    {
      label: t('nav.providers'),
      icon: 'i-lucide-building-2',
      to: '/providers',
      active: route.path.startsWith('/providers'),
    },
    {
      label: t('nav.glossary'),
      icon: 'i-lucide-book-open',
      to: '/glossary',
      active: route.path.startsWith('/glossary'),
    },
  ],
)
</script>

<template>
  <UHeader :toggle="false">
    <template #left>
      <div class="flex items-center gap-2.5">
        <img src="/icon.svg" alt="" class="size-8 rounded-lg">
        <span class="text-lg font-bold tracking-tight text-highlighted">Wetterdienst</span>
      </div>
    </template>

    <!-- the icons need the room of a wide screen: from 1024 px the eight links and the actions fit without them -->
    <UNavigationMenu :items="items" :ui="{ linkLeadingIcon: 'hidden xl:inline-flex size-4' }" />

    <template #right>
      <!-- Desktop controls -->
      <div class="hidden lg:flex items-center gap-1">
        <UTooltip :text="t('common.documentation')">
          <UButton
            to="https://wetterdienst.readthedocs.io/"
            target="_blank"
            icon="i-lucide-book-open"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.documentation')"
          />
        </UTooltip>
        <UTooltip :text="t('header.github')">
          <UButton
            to="https://github.com/earthobservations/wetterdienst"
            target="_blank"
            icon="i-lucide-github"
            color="neutral"
            variant="ghost"
            :aria-label="t('header.github')"
          />
        </UTooltip>
        <UTooltip :text="t('header.pypi')">
          <UButton
            to="https://pypi.org/project/wetterdienst"
            target="_blank"
            icon="i-lucide-package"
            color="neutral"
            variant="ghost"
            :aria-label="t('header.pypi')"
          />
        </UTooltip>
        <!-- Support is about the project rather than the data, so it sits with the other
             project links rather than in the task nav -- but as an icon, not a footer line,
             because issues, pull requests and donations all start here. -->
        <UTooltip :text="t('nav.support')">
          <UButton
            to="/support"
            icon="i-lucide-heart"
            color="neutral"
            variant="ghost"
            :aria-label="t('nav.support')"
          />
        </UTooltip>
        <SettingsMenu />
      </div>
      <!-- Mobile hamburger -->
      <UButton
        class="lg:hidden"
        icon="i-lucide-menu"
        color="neutral"
        variant="ghost"
        :aria-label="t('header.menu')"
        aria-haspopup="dialog"
        :aria-expanded="mobileMenuOpen"
        @click="mobileMenuOpen = true"
      />
    </template>
  </UHeader>

  <!-- Full-screen mobile menu. A dialog, not a layer of markup: the focus stays in it, Escape closes
       it and the page behind is hidden from a screen reader while it is open (WCAG 2.1.2, 2.4.3, 4.1.2) -->
  <UModal
    v-model:open="mobileMenuOpen"
    fullscreen
    :title="t('header.menu')"
    close
    :ui="{ body: 'flex flex-col flex-1 p-0 sm:p-0' }"
  >
    <!-- the label in the language of the app, which Nuxt UI's own is only for the two it ships -->
    <template #close="{ ui }">
      <UButton
        icon="i-lucide-x"
        color="neutral"
        variant="ghost"
        :aria-label="t('common.close')"
        :class="ui.close()"
      />
    </template>
    <template #body>
      <!-- Nav items -->
      <nav :aria-label="t('header.menu')" class="flex-1 overflow-y-auto px-3 py-4 flex flex-col gap-1">
        <NuxtLink
          v-for="item in items"
          :key="item.to as string"
          :to="item.to as string"
          class="flex items-center gap-4 px-4 py-3.5 rounded-xl text-base font-medium transition-colors motion-reduce:transition-none"
          :class="item.active
            ? 'bg-primary/10 text-primary'
            : 'text-default hover:bg-elevated'"
          @click="mobileMenuOpen = false"
        >
          <UIcon :name="item.icon as string" class="w-5 h-5 shrink-0" />
          {{ item.label }}
        </NuxtLink>
      </nav>

      <!-- Bottom bar: external links + settings -->
      <div class="shrink-0 border-t border-default px-4 py-4 flex items-center justify-between">
        <div class="flex items-center gap-1">
          <UTooltip :text="t('common.documentation')">
            <UButton
              to="https://wetterdienst.readthedocs.io/"
              target="_blank"
              icon="i-lucide-book-open"
              color="neutral"
              variant="ghost"
              :aria-label="t('common.documentation')"
            />
          </UTooltip>
          <UTooltip :text="t('header.github')">
            <UButton
              to="https://github.com/earthobservations/wetterdienst"
              target="_blank"
              icon="i-lucide-github"
              color="neutral"
              variant="ghost"
              :aria-label="t('header.github')"
            />
          </UTooltip>
          <UTooltip :text="t('header.pypi')">
            <UButton
              to="https://pypi.org/project/wetterdienst"
              target="_blank"
              icon="i-lucide-package"
              color="neutral"
              variant="ghost"
              :aria-label="t('header.pypi')"
            />
          </UTooltip>
          <!-- matches the desktop header: Support left the nav list, so it has to be here or
               the hamburger menu loses it entirely -->
          <UTooltip :text="t('nav.support')">
            <UButton
              to="/support"
              icon="i-lucide-heart"
              color="neutral"
              variant="ghost"
              :aria-label="t('nav.support')"
              @click="mobileMenuOpen = false"
            />
          </UTooltip>
        </div>
        <UButton
          to="/settings"
          icon="i-lucide-settings-2"
          color="neutral"
          variant="ghost"
          :aria-label="t('common.settings')"
          @click="mobileMenuOpen = false"
        />
      </div>
    </template>
  </UModal>
</template>
