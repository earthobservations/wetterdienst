<script setup lang="ts">
import { inSection, REFERENCE } from '~/utils/sections'

// The reference of the wide header (GH-3518): the providers, the glossary and the API, each with the sentence that
// says what it is for. A disclosure of links, not an ARIA menu: Tab walks into it, the links are links, and
// Escape, a click elsewhere or the focus leaving it close it (WAI-ARIA APG, "disclosure navigation").
const { t } = useI18n()
const route = useRoute()
const open = ref(false)
const root = useTemplateRef<HTMLElement>('root')
const trigger = useTemplateRef<HTMLButtonElement>('trigger')
const panelId = useId()

const current = computed(() => REFERENCE.some(section => inSection(section, route.path)))

watch(() => route.path, () => {
  open.value = false
})
onClickOutside(root, () => {
  open.value = false
})

// Escape is heard on the whole document while the panel is open: a click on its padding leaves the focus on the
// body, where a listener of the panel itself would not hear it
useEventListener(document, 'keydown', (event: KeyboardEvent) => {
  if (event.key === 'Escape' && open.value) {
    open.value = false
    trigger.value?.focus()
  }
})
function onFocusout(event: FocusEvent) {
  // a focus that goes nowhere (`relatedTarget` null: a click on the panel's padding, a link a browser does not
  // focus on mousedown, the window losing focus) leaves it open: a click elsewhere is `onClickOutside`'s
  const next = event.relatedTarget as Node | null
  if (next && !root.value?.contains(next))
    open.value = false
}
</script>

<template>
  <div ref="root" class="relative" @focusout="onFocusout">
    <button
      ref="trigger"
      type="button"
      class="nav-tab"
      :data-current="current || undefined"
      :aria-expanded="open"
      :aria-controls="open ? panelId : undefined"
      @click="open = !open"
    >
      <span class="nav-label" :data-text="t('shell.reference')">{{ t('shell.reference') }}</span>
      <UIcon name="i-ph-caret-down" class="size-4 shrink-0 transition-transform duration-200" :class="open ? 'rotate-180' : ''" />
    </button>
    <div
      v-if="open"
      :id="panelId"
      class="reference-panel absolute start-0 top-full z-50 mt-2 w-[24rem] max-w-[calc(100vw-2rem)] rounded-xl bg-default p-2 ring ring-default shadow-xl"
    >
      <ul class="flex flex-col gap-0.5">
        <li v-for="section in REFERENCE" :key="section.key">
          <NuxtLink
            :to="section.to"
            class="flex items-start gap-3 rounded-lg p-3 hover:bg-elevated aria-[current=page]:bg-elevated"
            :aria-current="inSection(section, route.path) ? 'page' : undefined"
            @click="open = false"
          >
            <ToolTile tile="navy" :icon="section.icon" size="2.25rem" />
            <span class="min-w-0">
              <span class="block font-semibold text-highlighted">{{ t(section.label) }}</span>
              <span class="block text-sm text-muted leading-snug">{{ t(section.description!) }}</span>
            </span>
          </NuxtLink>
        </li>
      </ul>
    </div>
  </div>
</template>

<style>
@media (prefers-reduced-motion: no-preference) {
  .reference-panel {
    animation: reference-in 160ms var(--ease-out-soft);
    transform-origin: top left;
  }
}
@keyframes reference-in {
  from {
    opacity: 0;
    transform: translateY(-4px) scale(0.98);
  }
}
</style>
