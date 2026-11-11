<script setup lang="ts">
import type { Point } from '~/utils/map-tool'

// "Use my location" (GH-3651): the button that asks for the reader's position, the box that keeps it in this browser,
// and what is told of it. The browser is asked on the press and nowhere else (`useMyLocation`), the position is
// rounded to about 1 km before it is handed over, and a refusal or a failure is announced (an alert), what was done
// with the position politely (a status, in the page from the start). The place search stays beside it, whatever
// the answer.
//
// What the position is used for is the page's: it takes `position` and finds the station. What it has to say about
// it, the nearest station and how far, goes in `status`, and a failure of its own in `problem`.
defineProps<{
  /** The position is being turned into a station: the button says so */
  resolving?: boolean
  /** What was done with the position, announced politely */
  status?: string
  /** A failure of what was done with it, announced at once */
  problem?: string
}>()

const emit = defineEmits<{
  /** The position, rounded, after a press of the button */
  position: [point: Point]
}>()

const { t } = useI18n()
const { position, failure, busy, remember, remembered, locate, setRemember, forget } = useMyLocation()

// a refusal of an earlier visit to another tool is not this one's to tell until the button is pressed here
onMounted(() => {
  failure.value = null
})

const working = computed(() => busy.value)
const failureText = computed(() => failure.value ? t(`location.${failure.value}`) : '')

async function press() {
  const point = await locate()
  if (point)
    emit('position', point)
}

const noteId = useId()
</script>

<template>
  <div class="flex flex-col gap-1.5" data-testid="use-my-location" data-print="hide">
    <div class="flex flex-wrap items-center gap-x-4 gap-y-1">
      <UButton
        type="button"
        color="neutral"
        variant="outline"
        size="sm"
        :icon="working || resolving ? 'i-ph-circle-notch' : 'i-ph-crosshair'"
        :label="working || resolving ? t('location.locating') : t('location.button')"
        :aria-busy="working || resolving"
        :aria-describedby="noteId"
        data-testid="use-my-location-button"
        @click="press"
      />
      <UCheckbox
        :model-value="remember"
        :label="t('location.remember')"
        size="sm"
        data-testid="use-my-location-remember"
        @update:model-value="setRemember($event === true)"
      />
    </div>
    <p :id="noteId" class="text-xs text-gray-600 dark:text-gray-400">
      {{ t('location.note') }}
    </p>
    <p v-if="remembered && position" class="flex flex-wrap items-center gap-x-2 text-xs text-gray-600 dark:text-gray-400" data-testid="use-my-location-remembered">
      <span>{{ t('location.remembered', { position: `${position.latitude.toFixed(2)}, ${position.longitude.toFixed(2)}` }) }}</span>
      <UButton type="button" color="neutral" variant="link" size="xs" :label="t('location.forget')" data-testid="use-my-location-forget" @click="forget" />
    </p>
    <!-- the status is in the page from the start, so that the text that fills it is announced; an alert is announced
         as it is put in, which is when there is something to say -->
    <p class="text-sm text-gray-700 dark:text-gray-300 empty:hidden" role="status" aria-live="polite" data-testid="use-my-location-status">
      {{ status }}
    </p>
    <p v-if="failureText || problem" class="text-sm text-error" role="alert" data-testid="use-my-location-problem">
      {{ failureText || problem }}
    </p>
  </div>
</template>
