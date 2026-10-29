<script setup lang="ts">
import type { PageKey } from '~/composables/useTimeAxis'
import { AXIS_STOPS, NOW_AT, pageOfPath, zoneOfPage } from '~/composables/useTimeAxis'

// The one page layout of the app (GH-3518): one container with the same gutters on every page, a reading width
// for text and a `wide` one for the pages of maps and charts, and one page header that says where on the axis of
// time the page sits: its zone, the stretch of time it covers in words, and a small drawing of that stretch on the
// whole axis (for the eye: the words say it all).
const props = withDefaults(defineProps<{
  title?: string
  subtitle?: string
  wide?: boolean
  /** The page on the axis; by default the one of the route */
  page?: PageKey
}>(), { title: undefined, subtitle: undefined, wide: false, page: undefined })

const { t, locale } = useI18n()
const route = useRoute()
const { span } = useTimeAxis()

const key = computed(() => props.page ?? pageOfPath(route.path))
const zone = computed(() => zoneOfPage(key.value) ?? 'reference')
const stop = computed(() => AXIS_STOPS.find(item => item.key === key.value))
const where = computed(() => key.value ? span(key.value) : t('axis.spanReference'))
const zoneLabel = computed(() => t(`axis.${zone.value}`))
</script>

<template>
  <UContainer class="app-page space-y-6" :class="wide ? 'app-page--wide' : 'app-page--narrow'">
    <header v-if="title" class="page-head" :class="`page-head--${zone}`">
      <!-- in the language of the interface, where the page is in another (the privacy policy, WCAG 3.1.2) -->
      <p class="page-head__where" data-testid="page-axis-position" :lang="locale">
        <span class="page-head__zone">
          <span class="page-head__dot" aria-hidden="true" />
          {{ zoneLabel }}
        </span>
        <span class="page-head__span">{{ where }}</span>
      </p>
      <h1 class="page-head__title">
        {{ title }}
      </h1>
      <p v-if="subtitle" class="page-head__subtitle">
        {{ subtitle }}
      </p>
      <!-- the stretch of time on the whole axis: the past to the left of the present, the forecast to its right -->
      <div v-if="stop" class="page-head__axis" aria-hidden="true">
        <span class="page-head__axis-then" :style="{ width: `${NOW_AT}%` }" />
        <span class="page-head__axis-next" :style="{ left: `${NOW_AT}%`, width: `${100 - NOW_AT}%` }" />
        <span
          v-if="stop.to > stop.from"
          class="page-head__axis-span"
          :style="{ left: `${stop.from}%`, width: `${stop.to - stop.from}%` }"
        />
        <span class="page-head__axis-now" :style="{ left: `${NOW_AT}%` }" />
      </div>
    </header>
    <slot />
  </UContainer>
</template>
