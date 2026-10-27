<template>
  <!-- The shell of every page but the widget (GH-3518): header, the page, footer. The page sets its own width with
       `PageContainer`, so that the gutters are the same everywhere. -->
  <div class="relative isolate flex min-h-screen flex-col">
    <!-- a wash of the logo's colours behind the head of each page; decoration, and the same in both modes -->
    <div class="app-backdrop pointer-events-none absolute inset-x-0 top-0 -z-10 h-[28rem]" aria-hidden="true" />
    <AppHeader />
    <UMain class="flex-1">
      <slot />
    </UMain>
    <AppFooter />
  </div>
</template>
