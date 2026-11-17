<script setup lang="ts" generic="T extends string">
// One choice out of a few ways to look at the same thing (the chart, the compact cards, the table), as a
// radio group: one stop in the tab order, which the arrow keys move along and select with (the pattern
// of the WAI-ARIA authoring practices for a radio group), Home and End to the ends. The selected option
// says so (`aria-checked`) and by its look, which is not colour alone: it is raised.
const props = defineProps<{
  modelValue: T
  /** An option that is `disabled` is shown and cannot be chosen (the arrow keys pass it); the group says why by its own `aria-describedby` */
  options: { value: T, label: string, icon?: string, disabled?: boolean }[]
  /** The group's name, which a screen reader announces with the option */
  label: string
  /** The id of what the group controls (`aria-controls` of each option): one element, which shows the chosen option */
  controls?: string
  /**
   * Whether the chosen option takes the focus after a click or Enter/Space (the default: Safari does not focus a
   * button on click). Off, the one that listens to `activate` moves the focus itself, as the picker of the stations
   * moves it into the search or the map. The arrow keys keep it on the group either way, to walk along it.
   */
  focusOnClick?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: T]
  /** An option chosen by a click or by Enter/Space on it (`event.detail` is 0 for a key), not by the arrow keys: after `update:modelValue` */
  'activate': [value: T, event: MouseEvent]
}>()

const buttons: (HTMLButtonElement | null)[] = []

/** The option that is the group's one stop of Tab: the chosen one, or, where that is a disabled one (a native `disabled` button takes no focus), the first that can be chosen */
const tabStop = computed(() => {
  const chosen = props.options.findIndex(option => option.value === props.modelValue && !option.disabled)
  return chosen !== -1 ? chosen : props.options.findIndex(option => !option.disabled)
})

function choose(index: number) {
  emit('update:modelValue', props.options[index]!.value)
  void nextTick(() => buttons[index]?.focus())
}

function activate(index: number, event: MouseEvent) {
  const value = props.options[index]!.value
  emit('update:modelValue', value)
  emit('activate', value, event)
  if (props.focusOnClick !== false)
    void nextTick(() => buttons[index]?.focus())
}

function onKeydown(event: KeyboardEvent, index: number) {
  const last = props.options.length - 1
  const enabled = (at: number) => !props.options[at]!.disabled
  /** The nearest option that can be chosen from `from` in a direction, round the ends; where there is none, the option itself */
  const step = (from: number, direction: 1 | -1) => {
    for (let count = 1; count <= last + 1; count++) {
      const at = (from + direction * count + last + 1) % (last + 1)
      if (enabled(at))
        return at
    }
    return from
  }
  const target: Record<string, number> = {
    ArrowRight: step(index, 1),
    ArrowDown: step(index, 1),
    ArrowLeft: step(index, -1),
    ArrowUp: step(index, -1),
    Home: enabled(0) ? 0 : step(0, 1),
    End: enabled(last) ? last : step(last, -1),
  }
  const next = target[event.key]
  if (next === undefined || event.altKey || event.ctrlKey || event.metaKey)
    return
  event.preventDefault()
  choose(next)
}
</script>

<template>
  <div
    role="radiogroup"
    :aria-label="label"
    class="inline-flex shrink-0 items-center gap-0.5 rounded-lg bg-gray-100 p-0.5 dark:bg-gray-800/70"
  >
    <button
      v-for="(option, index) in options"
      :key="option.value"
      :ref="(el) => { buttons[index] = el as HTMLButtonElement | null }"
      type="button"
      role="radio"
      :aria-checked="option.value === modelValue"
      :aria-controls="controls"
      :disabled="option.disabled || undefined"
      :tabindex="index === tabStop ? 0 : -1"
      class="inline-flex cursor-pointer select-none items-center gap-1.5 rounded-md px-3 py-1.5 text-xs transition-all duration-150"
      :class="option.value === modelValue
        ? 'bg-white font-semibold text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white'
        : `text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-300${
          option.disabled ? ' disabled:cursor-not-allowed disabled:opacity-60' : ''}`"
      @click="activate(index, $event)"
      @keydown="onKeydown($event, index)"
    >
      <UIcon v-if="option.icon" :name="option.icon" class="hidden h-3.5 w-3.5 shrink-0 sm:block" aria-hidden="true" />
      {{ option.label }}
    </button>
  </div>
</template>
