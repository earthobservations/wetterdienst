<script setup lang="ts">
import type { RadarFrame } from '~/utils/radar'
import { describeFrame } from '~/utils/radar'

// The player of the Radar tool (GH-3788): play and pause, a step back and a step on, and a slider over the frames of the loop, with the
// time of the frame in the reader's own zone and whether it is observed or forecast, in words and by an icon, never by colour alone
// (WCAG 1.4.1). Everything a pointer does a keyboard does: the buttons are 44 px, the slider is the browser's own range input (the
// arrow keys step, Home and End jump to the ends, Page Up and Page Down jump further) and a step back and a step on are the way for a
// pointer that cannot drag (WCAG 2.5.7). The slider's track is solid for the observed frames and hatched for the forecast, so
// that the line between them is seen where the loop is long. Any of these controls pauses the loop; a step, which is no slider, says the
// frame it is at in a polite status where the loop is not playing (the slider says its own value). A step that cannot go on (the first
// or the last frame) is `aria-disabled` and does nothing, not `disabled`: a native disabled button drops the focus the reader has on it,
// and the keys would then have nowhere to go (GH-3788).
const props = defineProps<{
  /** The frames of the loop in time order, those that could be loaded */
  frames: readonly RadarFrame[]
  index: number
  playing: boolean
  /** The moment the day of a frame is told against: a frame of another day has its weekday */
  now: number
  /** The system asks for less motion: the loop did not start by itself, and says so */
  reducedMotion: boolean
  /** The frame the player stands at is not on the map yet: its image is still on its way, and the map shows the one before */
  loading?: boolean
}>()

const emit = defineEmits<{ toggle: [], seek: [index: number], step: [by: number] }>()

const { t } = useI18n()
const formatLanguage = useFormatLanguage()
const sliderId = useId()
const hintId = useId()

const frame = computed(() => props.frames[props.index] ?? null)
const words = computed(() => frame.value ? describeFrame(t, frame.value, formatLanguage.value, props.now) : null)
const last = computed(() => Math.max(props.frames.length - 1, 0))
/** Where the forecast begins on the track, as a share of it: the first frame that is a forecast */
const split = computed(() => {
  const first = props.frames.findIndex(entry => entry.kind === 'forecast')
  return first === -1 || last.value === 0 ? 100 : Math.round((first - 0.5) / last.value * 1000) / 10
})
const disabled = computed(() => props.frames.length < 2)
const atStart = computed(() => props.index <= 0)
const atEnd = computed(() => props.index >= last.value)

/** What the polite status says: the frame the reader stepped to, where the loop is not playing (a slider is read out by itself, so a move of it says nothing here) */
const stepped = ref(false)
const announcement = computed(() => stepped.value && !props.playing && words.value ? words.value.value : '')
function onSeek(event: Event) {
  // a move of the slider is read out by the slider: a step announced before it must not be said again for this frame
  stepped.value = false
  emit('seek', Number((event.target as HTMLInputElement).value))
}
function onStep(by: number) {
  if ((by < 0 && atStart.value) || (by > 0 && atEnd.value))
    return
  stepped.value = true
  emit('step', by)
}
</script>

<template>
  <section class="radar-player" role="group" :aria-label="t('radar.playerLabel')" :aria-busy="loading ? 'true' : undefined" data-testid="radar-player">
    <div class="radar-player-row">
      <UButton
        :icon="playing ? 'i-ph-pause-fill' : 'i-ph-play-fill'"
        :aria-label="playing ? t('radar.pause') : t('radar.play')"
        :title="playing ? t('radar.pause') : t('radar.play')"
        :disabled="disabled"
        color="primary"
        variant="solid"
        size="xl"
        square
        class="radar-player-button"
        data-testid="radar-play"
        @click="emit('toggle')"
      />
      <UButton
        icon="i-ph-skip-back-fill"
        :aria-label="t('radar.stepBack')"
        :title="t('radar.stepBack')"
        :disabled="disabled"
        :aria-disabled="atStart ? 'true' : undefined"
        :class="{ 'radar-step-off': atStart }"
        color="neutral"
        variant="outline"
        size="xl"
        square
        class="radar-player-button"
        data-testid="radar-step-back"
        @click="onStep(-1)"
      />
      <UButton
        icon="i-ph-skip-forward-fill"
        :aria-label="t('radar.stepForward')"
        :title="t('radar.stepForward')"
        :disabled="disabled"
        :aria-disabled="atEnd ? 'true' : undefined"
        :class="{ 'radar-step-off': atEnd }"
        color="neutral"
        variant="outline"
        size="xl"
        square
        class="radar-player-button"
        data-testid="radar-step-forward"
        @click="onStep(1)"
      />
      <div v-if="words && frame" class="radar-player-now" data-testid="radar-now">
        <time class="radar-player-time" :datetime="frame.time" data-testid="radar-time">{{ words.time }}</time>
        <span class="radar-kind" :data-kind="frame.kind" data-testid="radar-kind">
          <UIcon :name="frame.kind === 'forecast' ? 'i-ph-fast-forward-fill' : 'i-ph-eye-fill'" class="size-4 shrink-0" aria-hidden="true" />
          {{ words.ahead ?? words.kind }}
        </span>
        <span v-if="loading" class="radar-player-loading" data-testid="radar-frame-loading">
          <UIcon name="i-ph-circle-notch" class="size-4 shrink-0 motion-safe:animate-spin" aria-hidden="true" />
          {{ t('radar.frameLoading') }}
        </span>
      </div>
    </div>

    <div class="radar-slider-box">
      <label :for="sliderId" class="sr-only">{{ t('radar.timeLabel') }}</label>
      <input
        :id="sliderId"
        type="range"
        class="radar-slider"
        min="0"
        :max="last"
        step="1"
        :value="index"
        :disabled="disabled"
        :style="{ '--radar-split': `${split}%` }"
        :aria-valuetext="words?.value"
        :aria-describedby="hintId"
        data-testid="radar-slider"
        @input="onSeek"
      >
    </div>
    <p :id="hintId" class="sr-only">
      {{ t('radar.timeHint') }}
    </p>
    <p class="radar-player-key" data-testid="radar-track-key">
      {{ t('radar.trackKey') }}
    </p>
    <p v-if="reducedMotion && !playing" class="radar-player-key" data-testid="radar-reduced-motion">
      {{ t('radar.reducedMotion') }}
    </p>
    <p class="sr-only" role="status" data-testid="radar-announcement">
      {{ announcement }}
    </p>
  </section>
</template>

<style>
.radar-player {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.radar-player-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}
/* the buttons are as high as a target (WCAG 2.5.8): 44 px */
.radar-player-button.radar-player-button {
  width: 2.75rem;
  height: 2.75rem;
  justify-content: center;
}
.radar-player-now {
  display: flex;
  flex: 1 1 10rem;
  flex-wrap: wrap;
  align-items: baseline;
  column-gap: 0.75rem;
  row-gap: 0.125rem;
  min-width: 0;
  margin-inline-start: 0.25rem;
}
.radar-player-time {
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.2;
  color: var(--ui-text-highlighted);
  font-variant-numeric: tabular-nums;
}
/* observed or forecast: a word and an icon, and the forecast also an outline of its own (a dashed edge), so that the colour is no cue alone */
.radar-kind {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.125rem 0.5rem;
  border: 1px solid var(--ui-border-accented);
  border-radius: 999px;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--ui-text-toned);
}
.radar-kind[data-kind="forecast"] {
  border-style: dashed;
  border-width: 2px;
}
/* a step that cannot go on: dimmed, still a stop of the keyboard and still named */
.radar-player-button.radar-step-off {
  opacity: 0.45;
  cursor: default;
}
.radar-player-loading {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.8125rem;
  color: var(--ui-text-muted);
}
.radar-slider-box {
  padding-inline: 0.25rem;
}

/* The slider: the range input with its own look, its track solid up to the forecast and hatched from there (--radar-split) */
.radar-slider {
  --radar-track: var(--ui-text-toned);
  --radar-thumb: 1.75rem;
  display: block;
  width: 100%;
  height: var(--radar-thumb);
  margin: 0;
  background: transparent;
  appearance: none;
  cursor: pointer;
}
.radar-slider:disabled {
  cursor: default;
  opacity: 0.5;
}
.radar-slider::-webkit-slider-runnable-track {
  height: 0.625rem;
  border-radius: 999px;
  border: 1px solid var(--radar-track);
  background-image:
    repeating-linear-gradient(135deg, var(--radar-track) 0 3px, transparent 3px 6px),
    linear-gradient(var(--radar-track), var(--radar-track));
  background-size: 100% 100%, var(--radar-split) 100%;
  background-repeat: no-repeat;
}
.radar-slider::-moz-range-track {
  height: 0.625rem;
  border-radius: 999px;
  border: 1px solid var(--radar-track);
  background-image:
    repeating-linear-gradient(135deg, var(--radar-track) 0 3px, transparent 3px 6px),
    linear-gradient(var(--radar-track), var(--radar-track));
  background-size: 100% 100%, var(--radar-split) 100%;
  background-repeat: no-repeat;
}
.radar-slider::-webkit-slider-thumb {
  width: var(--radar-thumb);
  height: var(--radar-thumb);
  margin-top: calc((0.625rem - var(--radar-thumb)) / 2 - 1px);
  border-radius: 50%;
  border: 3px solid var(--ui-bg);
  background: var(--ui-primary);
  box-shadow: 0 0 0 1px var(--radar-track);
  appearance: none;
}
.radar-slider::-moz-range-thumb {
  box-sizing: border-box;
  width: var(--radar-thumb);
  height: var(--radar-thumb);
  border-radius: 50%;
  border: 3px solid var(--ui-bg);
  background: var(--ui-primary);
  box-shadow: 0 0 0 1px var(--radar-track);
}
.radar-slider:focus-visible {
  outline: 2px solid var(--app-focus-ring);
  outline-offset: 2px;
  border-radius: 999px;
}
.radar-player-key {
  font-size: 0.75rem;
  color: var(--ui-text-muted);
}
/* separate rules: a selector list with a pseudo-element the browser does not know is dropped whole */
@media (forced-colors: active) {
  .radar-slider::-webkit-slider-runnable-track {
    forced-color-adjust: none;
  }
}
@media (forced-colors: active) {
  .radar-slider::-moz-range-track {
    forced-color-adjust: none;
  }
}
</style>
