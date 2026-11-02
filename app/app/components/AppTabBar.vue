<script setup lang="ts">
import { EXTERNAL, inSection, PROJECT, REFERENCE, TOOLS } from '~/utils/sections'

// The navigation of the narrow layout (GH-3518): the four tools as tabs at the foot of the window, where a thumb
// reaches them, and a fifth that opens the rest (the home page, the reference, the project, the settings) in a
// sheet. The sheet is a dialog: the focus stays in it, Escape closes it and gives the focus back to its tab, and the
// page behind it is hidden from a screen reader while it is open (WCAG 2.1.2, 2.4.3, 4.1.2).
//
// In a window too low for two bars and a page between them (a phone on its side, 400 % zoom) the bar stops being
// fixed and stands under the header (main.css, `.app-tabbar`), so it never covers what it would scroll over.
const { t } = useI18n()
const route = useRoute()
const open = ref(false)

watch(() => route.path, () => {
  open.value = false
})
// the sheet belongs to the narrow layout: past the breakpoint the header shows the tools itself, and a dialog that
// is hidden with CSS would still hold the focus
const wide = useMediaQuery('(min-width: 64rem)')
watch(wide, (isWide) => {
  if (isWide)
    open.value = false
})

const isCurrent = (to: string) => to === '/' ? route.path === '/' : inSection({ to }, route.path)
</script>

<template>
  <nav :aria-label="t('shell.mainNav')" class="app-tabbar lg:hidden" data-print="hide">
    <ul class="grid h-full grid-cols-5">
      <li v-for="tool in TOOLS" :key="tool.key">
        <NuxtLink :to="tool.to" class="tabbar-item" :aria-current="isCurrent(tool.to) ? 'page' : undefined">
          <ToolTile :tile="tool.tile" :icon="tool.icon" size="1.625rem" />
          <span class="tabbar-label">{{ t(tool.label) }}</span>
        </NuxtLink>
      </li>
      <li>
        <!-- by its label, which is also what the button says: Label in Name (2.5.3) and the e2e suite's handle -->
        <button
          type="button"
          class="tabbar-item"
          :aria-label="t('header.menu')"
          aria-haspopup="dialog"
          :aria-expanded="open"
          @click="open = true"
        >
          <span class="tile tile-navy" style="--tile-size: 1.625rem" aria-hidden="true"><UIcon name="i-ph-dots-three-outline-fill" /></span>
          <span class="tabbar-label" aria-hidden="true">{{ t('header.menu') }}</span>
        </button>
      </li>
    </ul>
  </nav>

  <UModal
    v-model:open="open"
    :title="t('header.menu')"
    :ui="{
      content: 'menu-sheet max-w-none sm:max-w-lg w-full sm:w-[calc(100vw-2rem)] top-auto bottom-0 sm:bottom-auto sm:top-1/2 left-0 sm:left-1/2 translate-x-0 sm:-translate-x-1/2 translate-y-0 sm:-translate-y-1/2 rounded-b-none sm:rounded-b-2xl max-h-[min(88dvh,44rem)]',
      body: 'p-0 sm:p-0 overflow-y-auto',
    }"
  >
    <!-- the label in the language of the app, which Nuxt UI's own is only for the two it ships -->
    <template #close="{ ui }">
      <UButton
        icon="i-ph-x"
        color="neutral"
        variant="ghost"
        :aria-label="t('common.close')"
        :class="ui.close()"
      />
    </template>
    <template #body>
      <nav :aria-label="t('header.menu')" class="px-3 py-3 space-y-4" data-print="no-urls">
        <section>
          <h2 class="px-3 pb-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
            {{ t('shell.tools') }}
          </h2>
          <ul class="grid grid-cols-1 gap-0.5">
            <li>
              <NuxtLink to="/" class="sheet-link" :aria-current="isCurrent('/') ? 'page' : undefined" @click="open = false">
                <span class="tile tile-navy" style="--tile-size: 2rem" aria-hidden="true"><UIcon name="i-ph-house-fill" /></span>
                {{ t('nav.home') }}
              </NuxtLink>
            </li>
            <li v-for="tool in TOOLS" :key="tool.key">
              <NuxtLink :to="tool.to" class="sheet-link" :aria-current="isCurrent(tool.to) ? 'page' : undefined" @click="open = false">
                <ToolTile :tile="tool.tile" :icon="tool.icon" size="2rem" />
                {{ t(tool.label) }}
              </NuxtLink>
            </li>
          </ul>
        </section>
        <section>
          <h2 class="px-3 pb-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
            {{ t('shell.reference') }}
          </h2>
          <ul class="grid grid-cols-1 gap-0.5">
            <li v-for="section in REFERENCE" :key="section.key">
              <NuxtLink :to="section.to" class="sheet-link" :aria-current="isCurrent(section.to) ? 'page' : undefined" @click="open = false">
                <UIcon :name="section.icon" class="size-5 shrink-0 text-muted" />
                {{ t(section.label) }}
              </NuxtLink>
            </li>
          </ul>
        </section>
        <section>
          <h2 class="px-3 pb-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
            {{ t('shell.project') }}
          </h2>
          <ul class="grid grid-cols-1 gap-0.5">
            <li v-for="section in PROJECT" :key="section.key">
              <NuxtLink :to="section.to" class="sheet-link" :aria-current="isCurrent(section.to) ? 'page' : undefined" @click="open = false">
                <UIcon :name="section.icon" class="size-5 shrink-0 text-muted" />
                {{ t(section.label) }}
              </NuxtLink>
            </li>
            <li v-for="link in EXTERNAL" :key="link.key">
              <a :href="link.to" target="_blank" class="sheet-link">
                <UIcon :name="link.icon" class="size-5 shrink-0 text-muted" />
                {{ t(link.label) }}
                <UIcon name="i-ph-arrow-up-right" class="ms-auto size-4 shrink-0 text-muted" />
              </a>
            </li>
          </ul>
        </section>
      </nav>
    </template>
  </UModal>
</template>
