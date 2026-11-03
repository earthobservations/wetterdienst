<script setup lang="ts">
import { sectionOf } from '~/utils/sections'

// The head of a page (GH-3518): the page's place in the app (its tile or icon, and its group), its title, one
// sentence that says what it is for, and room for an action. Left-aligned at the frame's edge on every page, so
// that the titles of all pages stand on one line under the logo.
//
// A tool explains itself in a panel that the "About" button opens under the header (`about` slot), so the tool
// starts with the tool and the explanation is one click away.
const props = defineProps<{
  title: string
  lede?: string
  /** The page's section, when its path is not enough to tell it (a provider's own page is in Providers) */
  section?: string
  /** The label of the button that opens the `about` slot */
  aboutLabel?: string
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
</script>

<template>
  <header class="page-header" :data-group="section?.group">
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
          <p v-if="slots.eyebrow || groupLabel" class="page-eyebrow">
            <slot name="eyebrow">
              {{ groupLabel }}
            </slot>
          </p>
          <h1 class="page-title">
            {{ title }}
          </h1>
          <p v-if="lede" class="page-lede">
            {{ lede }}
          </p>
          <p v-if="slots.meta" class="mt-2 text-sm text-muted">
            <slot name="meta" />
          </p>
        </div>
      </div>
      <div v-if="slots.actions || (slots.about && aboutLabel)" class="flex shrink-0 flex-wrap items-center gap-2" data-print="hide">
        <slot name="actions" />
        <UButton
          v-if="slots.about && aboutLabel"
          :label="aboutLabel"
          icon="i-ph-info"
          color="neutral"
          variant="outline"
          :trailing-icon="showAbout ? 'i-ph-caret-up' : 'i-ph-caret-down'"
          :aria-expanded="showAbout"
          :aria-controls="showAbout ? aboutId : undefined"
          @click="showAbout = !showAbout"
        />
      </div>
    </div>
    <div v-if="slots.about && showAbout" :id="aboutId" class="page-about">
      <slot name="about" />
    </div>
  </header>
</template>
