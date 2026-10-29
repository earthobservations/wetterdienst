<script setup lang="ts">
import type { AxisKey } from '~/composables/useTimeAxis'
import { AXIS_STOPS, PAGE_LABEL_KEYS } from '~/composables/useTimeAxis'

// The navigation of the app, drawn as the axis of time its pages lie on (GH-3518): oldest on the left, the present,
// then the forecast. Each stop is a link with the stretch of time it covers; the one of the page that is open is
// `aria-current` and drawn solid on the track. The zone words above (then, now, next) are drawn for the eye; a
// screen reader hears the zone in each link's own text.
const { t } = useI18n()
const { current, span } = useTimeAxis()

const stops = computed(() => AXIS_STOPS.map(stop => ({
  ...stop,
  label: t(PAGE_LABEL_KEYS[stop.key]),
  span: span(stop.key),
  zoneLabel: t(`axis.${stop.zone}`),
  active: current.value === stop.key,
})))

// the active stop is scrolled into the rail's view where the rail is narrower than its stops (a phone)
const list = ref<HTMLElement | null>(null)
function reveal(key: AxisKey | null) {
  if (!key || !list.value)
    return
  const item = list.value.querySelector<HTMLElement>(`[data-stop="${key}"]`)
  const box = list.value.parentElement
  if (!item || !box || box.scrollWidth <= box.clientWidth)
    return
  box.scrollLeft = Math.max(0, item.offsetLeft - (box.clientWidth - item.offsetWidth) / 2)
}
onMounted(() => reveal(current.value as AxisKey | null))
watch(current, key => nextTick(() => reveal(key as AxisKey | null)))
</script>

<template>
  <nav :aria-label="t('axis.label')" class="time-rail" data-testid="time-rail">
    <div class="app-container">
      <div class="time-rail__scroll">
        <!-- the zones over the axis, for the eye: each link says its own zone to a screen reader -->
        <div class="time-rail__zones" aria-hidden="true">
          <span class="time-rail__zone time-rail__zone--then">
            <UIcon name="i-lucide-arrow-left" class="size-3" />{{ t('axis.then') }}
          </span>
          <span class="time-rail__zone time-rail__zone--now">{{ t('axis.now') }}</span>
          <span class="time-rail__zone time-rail__zone--next">
            {{ t('axis.next') }}<UIcon name="i-lucide-arrow-right" class="size-3" />
          </span>
        </div>
        <ol ref="list" class="time-rail__stops">
          <li
            v-for="stop in stops"
            :key="stop.key"
            :data-stop="stop.key"
            class="time-rail__stop"
            :class="[`time-rail__stop--${stop.zone}`, { 'is-active': stop.active }]"
          >
            <NuxtLink
              :to="stop.path"
              class="time-rail__link"
              :aria-current="stop.active ? 'page' : undefined"
            >
              <UIcon :name="stop.icon" class="time-rail__icon" />
              <span class="time-rail__text">
                <span class="time-rail__label">{{ stop.label }}</span>
                <span class="time-rail__span"><span class="sr-only">{{ stop.zoneLabel }}: </span>{{ stop.span }}</span>
              </span>
            </NuxtLink>
            <span class="time-rail__track" aria-hidden="true" />
          </li>
        </ol>
      </div>
    </div>
  </nav>
</template>
