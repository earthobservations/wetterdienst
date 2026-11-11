<script setup lang="ts">
import type { Point } from '~/utils/map-tool'

// "Use my location" (GH-3651, GH-4011): the button that asks for the reader's position, the choice to keep it in this
// browser, and what is told of it. The browser is asked on the press and nowhere else (`useMyLocation`), the position is
// rounded to about 1 km before it is handed over, and a refusal or a failure is announced (an alert), what was done
// with the position politely (a status, in the page from the start). The place search stays beside it, whatever
// the answer.
//
// What it shows follows what is in hand and what is stored, and needs no storage of its own:
// - at first only the button;
// - after a press, with a position in hand and nothing stored: the box "Remember my position in this browser" and the
//   note (what is kept, the link to the privacy policy) under the button, so that the note is read before the box is
//   ticked. The box is there only while a position is in hand, so that ticking it always stores that position;
// - once a position is stored (ticked, or restored from an earlier visit): a compact "Stored" control beside the
//   button, which opens the position and "Forget" and replaces the box and the note. "Forget" takes the position
//   back to nothing, and the next press starts again.
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

/** The box and its note: a position is in hand and nothing is stored */
const offerToKeep = computed(() => position.value !== null && !remembered.value)
const positionText = computed(() => position.value ? `${position.value.latitude.toFixed(2)}, ${position.value.longitude.toFixed(2)}` : '')
const open = ref(false)
const button = useTemplateRef<{ $el: HTMLElement }>('button')
const stored = useTemplateRef<{ $el: HTMLElement }>('stored')

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

/** The box is ticked: the position is stored, the box and its note give way to the control, and the focus goes with them */
async function keep(on: boolean) {
  setRemember(on)
  if (!on)
    return
  await nextTick()
  stored.value?.$el.focus()
}

/** "Forget": the control goes with the position, and the focus goes back to the button, which starts again */
async function forgetPosition() {
  open.value = false
  forget()
  await nextTick()
  // the popover gives its focus back as it closes, to a control that is gone: the button takes it after that
  setTimeout(() => button.value?.$el.focus(), 0)
}

const noteId = useId()
</script>

<template>
  <div class="flex flex-col gap-1.5" data-testid="use-my-location" data-print="hide">
    <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
      <UButton
        ref="button"
        type="button"
        color="neutral"
        variant="outline"
        size="sm"
        :icon="working || resolving ? 'i-ph-circle-notch' : 'i-ph-crosshair'"
        :label="working || resolving ? t('location.locating') : t('location.button')"
        :aria-busy="working || resolving"
        :aria-describedby="offerToKeep ? noteId : undefined"
        data-testid="use-my-location-button"
        @click="press"
      />
      <UPopover v-if="remembered && position" v-model:open="open">
        <UButton
          ref="stored"
          type="button"
          color="neutral"
          variant="subtle"
          size="sm"
          class="max-w-full"
          icon="i-ph-map-pin"
          trailing-icon="i-ph-caret-down"
          :label="t('location.stored')"
          :aria-label="t('location.storedLabel')"
          data-testid="use-my-location-stored"
        />
        <template #content>
          <div class="flex max-w-[min(20rem,calc(100vw-2rem))] flex-col items-start gap-2 p-3 text-sm" data-testid="use-my-location-remembered">
            <p class="text-gray-700 dark:text-gray-300">
              {{ t('location.remembered', { position: positionText }) }}
            </p>
            <UButton type="button" color="neutral" variant="outline" size="xs" icon="i-ph-trash" :label="t('location.forget')" data-testid="use-my-location-forget" @click="forgetPosition" />
          </div>
        </template>
      </UPopover>
    </div>
    <template v-if="offerToKeep">
      <UCheckbox
        :model-value="remember"
        :label="t('location.remember')"
        size="sm"
        data-testid="use-my-location-remember"
        @update:model-value="keep($event === true)"
      />
      <p :id="noteId" class="text-xs text-gray-600 dark:text-gray-400" data-testid="use-my-location-note">
        {{ t('location.note') }}
        <NuxtLink to="/datenschutz#location" target="_blank" class="text-primary-700 dark:text-primary-500 underline hover:no-underline" data-testid="use-my-location-privacy">
          {{ t('location.privacyLink') }}
        </NuxtLink>
      </p>
    </template>
    <!-- the status is in the page and in the tree from the start (`empty:sr-only`, never `hidden`), so that the text that
         fills it is announced; an alert is announced as it is put in, which is when there is something to say -->
    <p class="text-sm text-gray-700 empty:sr-only dark:text-gray-300" role="status" aria-live="polite" data-testid="use-my-location-status">
      {{ status }}
    </p>
    <p v-if="failureText || problem" class="text-sm text-error" role="alert" data-testid="use-my-location-problem">
      {{ failureText || problem }}
    </p>
  </div>
</template>
