<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const route = useRoute()

const items = computed<NavigationMenuItem[]>(() =>
  [
    {
      label: 'Home',
      icon: 'i-lucide-home',
      to: '/',
      active: route.path === '/',
    },
    {
      label: 'Explorer',
      icon: 'i-lucide-globe',
      to: '/explorer',
      active: route.path.startsWith('/explorer'),
    },
    {
      label: 'Stripes',
      icon: 'i-lucide-bar-chart-3',
      to: '/stripes',
      active: route.path.startsWith('/stripes'),
    },
    {
      label: 'API',
      icon: 'i-lucide-code',
      to: '/api',
      active: route.path.startsWith('/api'),
    },
    {
      label: 'Support',
      icon: 'i-lucide-heart',
      to: '/support',
      active: route.path.startsWith('/support'),
    },
  ],
)
</script>

<template>
  <UApp>
    <UHeader>
      <template #left>
        <div />
      </template>
      <UNavigationMenu :items="items" />
      <template #body>
        <UNavigationMenu orientation="vertical" :items="items" />
      </template>
      <template #right>
        <div class="flex items-center gap-1">
          <UTooltip text="Documentation">
            <UButton
              to="https://wetterdienst.readthedocs.io/"
              target="_blank"
              icon="i-lucide-book-open"
              color="neutral"
              variant="ghost"
              aria-label="Documentation"
            />
          </UTooltip>
          <UTooltip text="GitHub">
            <UButton
              to="https://github.com/earthobservations/wetterdienst"
              target="_blank"
              icon="i-lucide-github"
              color="neutral"
              variant="ghost"
              aria-label="GitHub"
            />
          </UTooltip>
          <UTooltip text="PyPI">
            <UButton
              to="https://pypi.org/project/wetterdienst"
              target="_blank"
              icon="i-lucide-package"
              color="neutral"
              variant="ghost"
              aria-label="PyPI"
            />
          </UTooltip>
          <ColorModeSelect />
        </div>
      </template>
    </UHeader>
    <UMain>
      <NuxtPage />
    </UMain>
    <UFooter>
      <div class="w-full flex justify-center items-center gap-4">
        <span>© {{ new Date().getFullYear() }} earthobservations</span>
        <span class="text-gray-400">|</span>
        <NuxtLink to="/impressum" class="text-gray-500 hover:text-primary-500 transition-colors">
          Legal Notice
        </NuxtLink>
      </div>
    </UFooter>
  </UApp>
</template>

<style>
/* Make main container full width for better map display */
:deep(.u-main) {
  max-width: 100% !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
}
</style>
