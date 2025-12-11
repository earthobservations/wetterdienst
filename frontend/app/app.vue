<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const route = useRoute()

const items = computed<NavigationMenuItem[]>(() =>
    [
    {
      label: "Home",
      icon: "i-lucide-home",
      to: "/",
      active: route.path === "/"
    },
    {
      label: "Explorer",
      icon: "i-lucide-globe",
      to: "/explorer",
      active: route.path.startsWith("/explorer")
    },
    {
      label: "Stripes",
      icon: "i-lucide-bar-chart-3",
      to: "/stripes",
      active: route.path.startsWith("/stripes")
    },
    {
      label: "API",
      icon: "i-lucide-code",
      to: "/api",
      active: route.path.startsWith("/api")
    }
  ]
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
      <UNavigationMenu :items="items"/>
      <template #right>
        <ColorModeSelect />
      </template>
    </UHeader>
    <UMain>
      <NuxtPage />
    </UMain>
    <UFooter>
      <div class="w-full text-center">
        © {{ new Date().getFullYear() }} earthobservations
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
