<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const route = useRoute()

const items = computed<NavigationMenuItem[]>(() =>
    [
    {
      label: "Home",
      icon: "i-heroicons-home",
      to: "/",
      active: route.path === "/"
    },
    {
      label: "Explorer",
      icon: "i-heroicons-magnifying-glass",
      to: "/explorer",
      active: route.path.startsWith("/explorer")
    },
    {
      label: "Stripes",
      icon: "i-heroicons-chart-bar",
      to: "/stripes",
      active: route.path.startsWith("/stripes")
    },
    {
      label: "API",
      icon: "i-heroicons-code-bracket",
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
        <UColorModeButton />
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
</style>
