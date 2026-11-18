<script setup lang="ts">
import { sectionOf } from '~/utils/sections'

// The head of a page (GH-3518): the page's place in the app (its tile or icon, and its group), its title, one
// sentence that says what it is for, and room for an action. Left-aligned at the frame's edge on every page, so
// that the titles of all pages stand on one line under the logo.
//
// A tool explains itself in a panel that the "About" button opens under the header (`about` slot), so the tool
// starts with the tool and the explanation is one click away. On a phone (GH-4227) the button is a small ⓘ beside the
// title, which gives the room of a row to the tool; it opens the same text, and Escape closes it and gives the focus back
// to the ⓘ. Wider than the tab bar's breakpoint the button is the labelled one in the row of actions, as it was.
const props = defineProps<{
  title: string
  lede?: string
  /** The page's section, when its path is not enough to tell it (a provider's own page is in Providers) */
  section?: string
  /** The label of the button that opens the `about` slot */
  aboutLabel?: string
  /** On a phone only the title and the ⓘ are shown (the map's page, whose room is the map's): the eyebrow and the lede are for a screen reader alone (GH-4227) */
  compact?: boolean
}>()

const slots = defineSlots<{
  about?: () => unknown
  actions?: () => unknown
  eyebrow?: () => unknown
  /** In place of the tile: what stands for the page (a provider's flag) */
  leading?: () => unknown
  /** A line under the lede: facts of the page (a provider's country and id) */
  meta?: () => unknown
}>()
const { t } = useI18n()
const route = useRoute()
const section = computed(() => sectionOf(props.section ?? route.path))
const groupLabel = computed(() => section.value ? t(`shell.${section.value.group}`) : '')

const showAbout = ref(false)
const aboutId = useId()

// the ⓘ of the narrow layout, and the way back from the panel it opened
const phone = usePhone()
const hasAbout = computed(() => Boolean(slots.about && props.aboutLabel))
const headerEl = ref<HTMLElement | null>(null)
const infoButton = ref<{ $el: HTMLElement } | null>(null)
/** Closes the panel; the focus goes back to the ⓘ where it was in the panel (which is gone with it) or nowhere */
function closeAbout() {
  const hadFocusInside = (() => {
    const active = document.activeElement
    return !active || active === document.body || Boolean(headerEl.value?.contains(active))
  })()
  showAbout.value = false
  if (hadFocusInside)
    void nextTick(() => infoButton.value?.$el?.focus())
}
if (import.meta.client) {
  useEventListener(document, 'keydown', (event: KeyboardEvent) => {
    if (event.key === 'Escape' && phone.value && showAbout.value && !event.defaultPrevented) {
      // the key is answered: a full screen that is under it (the map's) is left by the next one, not by this
      event.preventDefault()
      closeAbout()
    }
  })
}
</script>

<template>
  <header ref="headerEl" class="page-header" :data-group="section?.group" :data-compact="compact && phone ? '' : undefined">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between sm:gap-8">
      <div class="flex min-w-0 items-start gap-4">
        <slot name="leading">
          <!-- a tool by its tile, the reference by its icon on the navy of the logo; the project's pages by name -->
          <ToolTile
            v-if="section?.tile || section?.group === 'reference'"
            :tile="section?.tile ?? 'navy'"
            :icon="section?.icon ?? ''"
            size="3rem"
            class="mt-1 max-sm:hidden"
          />
        </slot>
        <div class="min-w-0">
          <p v-if="slots.eyebrow || groupLabel" class="page-eyebrow" :class="compact && phone ? 'sr-only' : undefined">
            <slot name="eyebrow">
              {{ groupLabel }}
            </slot>
          </p>
          <!-- the ⓘ stands beside the title, in the row of its first line (GH-4227) -->
          <div v-if="phone && hasAbout" class="page-title-row">
            <h1 class="page-title">
              {{ title }}
            </h1>
            <UButton
              ref="infoButton"
              icon="i-ph-info"
              color="neutral"
              variant="ghost"
              class="page-info"
              :aria-label="aboutLabel"
              :title="aboutLabel"
              :aria-expanded="showAbout"
              :aria-controls="aboutId"
              :data-open="showAbout || undefined"
              data-print="hide"
              data-testid="page-info"
              @click="showAbout ? closeAbout() : (showAbout = true)"
            />
          </div>
          <h1 v-else class="page-title">
            {{ title }}
          </h1>
          <p v-if="lede" class="page-lede" :class="compact && phone ? 'sr-only' : undefined">
            {{ lede }}
          </p>
          <p v-if="slots.meta" class="mt-2 text-sm text-muted">
            <slot name="meta" />
          </p>
        </div>
      </div>
      <div v-if="slots.actions || (hasAbout && !phone)" class="flex min-w-0 max-w-full flex-wrap items-center gap-2 sm:shrink-0" data-print="hide">
        <slot name="actions" />
        <UButton
          v-if="hasAbout && !phone"
          :label="aboutLabel"
          icon="i-ph-info"
          color="neutral"
          variant="outline"
          :trailing-icon="showAbout ? 'i-ph-caret-up' : 'i-ph-caret-down'"
          :aria-expanded="showAbout"
          :aria-controls="showAbout ? aboutId : undefined"
          :ui="{ base: 'max-w-full whitespace-normal text-left', label: 'whitespace-normal' }"
          @click="showAbout = !showAbout"
        />
      </div>
    </div>
    <!-- on a phone the panel is always there, hidden, so that what the ⓘ controls exists; the other button names it while it is open -->
    <div v-if="slots.about && (phone ? hasAbout : showAbout)" v-show="phone ? showAbout : true" :id="aboutId" class="page-about">
      <slot name="about" />
    </div>
  </header>
</template>
