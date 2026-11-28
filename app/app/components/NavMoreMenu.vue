<script setup lang="ts">
import type { Section } from '~/utils/sections'
import { inSection } from '~/utils/sections'

// The tools of the wide header that do not fit in its row (GH-4500), at the end of the list of tabs: the header measures its tabs in the
// reader's language at the width it has (`AppHeader.vue`, `utils/header-fit.ts`) and the tools that do not fit, from the end, are here, each
// with its tile and the sentence that says what it is for, as the reference's panel has them. A disclosure of links, as the reference is
// (`useNavDisclosure`). The button is marked as the tab of a page is where the page is one of these tools, so that the reader sees which
// tool they are in when its tab is not in the row.
const props = defineProps<{
  /** The tools that are in the menu, in the order of the header */
  tools: readonly Section[]
}>()

const { t } = useI18n()
const route = useRoute()
const root = useTemplateRef<HTMLElement>('root')
const trigger = useTemplateRef<HTMLButtonElement>('trigger')
const { open, panelId, onFocusout } = useNavDisclosure(root, trigger)

const current = computed(() => props.tools.some(tool => inSection(tool, route.path)))
</script>

<template>
  <div ref="root" class="relative" data-testid="nav-more" @focusout="onFocusout">
    <button
      ref="trigger"
      type="button"
      class="nav-tab"
      :data-current="current || undefined"
      :aria-current="current ? 'true' : undefined"
      :aria-expanded="open"
      :aria-controls="open ? panelId : undefined"
      data-testid="nav-more-button"
      @click="open = !open"
    >
      <span class="nav-label" :data-text="t('shell.more')">{{ t('shell.more') }}</span>
      <UIcon name="i-ph-caret-down" class="size-4 shrink-0 transition-transform duration-200" :class="open ? 'rotate-180' : ''" />
    </button>
    <div
      v-if="open"
      :id="panelId"
      class="reference-panel nav-more-panel absolute end-0 top-full z-50 mt-2 w-[24rem] max-w-[calc(100vw-2rem)] rounded-xl bg-default p-2 ring ring-default shadow-xl"
      data-testid="nav-more-panel"
    >
      <ul class="flex flex-col gap-0.5">
        <li v-for="tool in tools" :key="tool.key" :data-tool="tool.key">
          <NuxtLink
            :to="tool.to"
            class="flex items-start gap-3 rounded-lg p-3 hover:bg-elevated aria-[current=page]:bg-elevated"
            :aria-current="inSection(tool, route.path) ? 'page' : undefined"
            @click="open = false"
          >
            <ToolTile :tile="tool.tile" :icon="tool.icon" size="2.25rem" />
            <span class="min-w-0">
              <span class="block font-semibold text-highlighted">{{ t(tool.label) }}</span>
              <span v-if="tool.description" class="block text-sm text-muted leading-snug">{{ t(tool.description) }}</span>
            </span>
          </NuxtLink>
        </li>
      </ul>
    </div>
  </div>
</template>

<style>
/* the panel is anchored to the button's end, so it opens from its top right corner (the reference's opens from the left) */
@media (prefers-reduced-motion: no-preference) {
  .reference-panel.nav-more-panel {
    transform-origin: top right;
  }
}
</style>
