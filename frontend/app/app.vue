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
  ],
)
</script>

<template>
  <UApp>
    <UHeader>
      <template #left>
        <NuxtLink to="/">
          wetterdienst by earthobservations
        </NuxtLink>
      </template>
      <UNavigationMenu :items="items" />
      <template #right>
        <div class="flex items-center gap-1">
          <UButton
            to="https://wetterdienst.readthedocs.io/"
            target="_blank"
            icon="i-lucide-book-open"
            color="neutral"
            variant="ghost"
            aria-label="Documentation"
          />
          <UButton
            to="https://github.com/earthobservations/wetterdienst"
            target="_blank"
            icon="i-lucide-github"
            color="neutral"
            variant="ghost"
            aria-label="GitHub"
          />
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
