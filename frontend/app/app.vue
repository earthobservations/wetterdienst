<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'
import pkg from '../package.json'

const route = useRoute()

const { data: versionData } = await useFetch<{ version: string }>('/api/version')

const version = computed(() => versionData.value?.version ?? 'unknown')
const frontendVersion = pkg.version || 'unknown'

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
    {
      label: 'History',
      icon: 'i-lucide-clock',
      to: '/history',
      active: route.path.startsWith('/history'),
    },
  ],
)
</script>

<template>
  <UApp>
    <UHeader>
      <template #left>
        <div class="flex items-center gap-3">
          <img src="/favicon.ico" alt="Wetterdienst" class="w-7 h-7">
          <div class="ml-2 inline-flex items-center gap-2">
            <span
              class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
            >
              FE {{ frontendVersion === 'unknown' ? frontendVersion : `v${frontendVersion}` }}
            </span>
            <span
              class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
            >
              BE {{ version === 'unknown' ? version : `v${version}` }}
            </span>
          </div>
        </div>
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
          <UTooltip text="Primary Color">
            <PrimaryColorSelect />
          </UTooltip>
          <UTooltip text="Color Mode">
            <ColorModeSelect />
          </UTooltip>
        </div>
      </template>
    </UHeader>
    <UMain>
      <NuxtPage />
    </UMain>
    <UFooter>
      <div class="w-full flex items-center gap-4">
        <span>© {{ new Date().getFullYear() }} earthobservations</span>
        <span class="text-gray-400">|</span>
        <NuxtLink to="/impressum" class="ml-auto text-gray-500 hover:text-primary-500 transition-colors">
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
