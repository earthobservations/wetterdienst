<script setup lang="ts">
// The frame of every page (GH-3518): one width and one gutter (`.app-frame` in main.css), so the title of each page
// starts where the one before it did, and one header: the page's tile when it is one of the four tasks, its title,
// and a sentence that says what it is for. A page of text keeps its lines to a reading measure; a `wide` page (a map,
// a chart) takes the frame's width.
const props = defineProps<{
  title?: string
  lede?: string
  /** a page of maps or charts: the content takes the full width of the frame */
  wide?: boolean
  /** the tile of the logo the page is (app.vue): its colour and its icon beside the title */
  tile?: 'sun' | 'rain' | 'wind' | 'heat'
  icon?: string
}>()

const measure = computed(() => props.wide ? '' : 'max-w-3xl')
</script>

<template>
  <div class="app-frame pt-8 pb-4 sm:pt-12">
    <div v-if="title || $slots.header" class="mb-8 sm:mb-10" :class="measure">
      <slot name="header">
        <div class="flex items-start gap-4">
          <span v-if="tile && icon" class="app-tile size-12! mt-0.5 max-sm:hidden!" :data-tile="tile" aria-hidden="true">
            <UIcon :name="icon" class="size-6" />
          </span>
          <div class="min-w-0">
            <h1 class="text-3xl sm:text-4xl font-bold tracking-tight text-highlighted text-balance break-words hyphens-auto">
              {{ title }}
            </h1>
            <p v-if="lede" class="mt-2 text-base sm:text-lg text-muted text-pretty break-words hyphens-auto">
              {{ lede }}
            </p>
          </div>
        </div>
      </slot>
      <slot name="meta" />
    </div>
    <div class="space-y-6" :class="measure">
      <slot />
    </div>
  </div>
</template>
