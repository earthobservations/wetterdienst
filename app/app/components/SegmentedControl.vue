<script setup lang="ts" generic="T extends string">
// One choice out of a few ways to look at the same thing (the chart, the compact cards, the table), as a
// radio group: one stop in the tab order, which the arrow keys move along and select with (the pattern
// of the WAI-ARIA authoring practices for a radio group), Home and End to the ends. The selected option
// says so (`aria-checked`) and by its look, which is not colour alone: it is raised.
const props = defineProps<{
  modelValue: T
  options: { value: T, label: string, icon?: string }[]
  /** The group's name, which a screen reader announces with the option */
  label: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: T] }>()

const buttons: (HTMLButtonElement | null)[] = []

function choose(index: number) {
  emit('update:modelValue', props.options[index]!.value)
  void nextTick(() => buttons[index]?.focus())
}

function onKeydown(event: KeyboardEvent, index: number) {
  const last = props.options.length - 1
  const target: Record<string, number> = {
    ArrowRight: index === last ? 0 : index + 1,
    ArrowDown: index === last ? 0 : index + 1,
    ArrowLeft: index === 0 ? last : index - 1,
    ArrowUp: index === 0 ? last : index - 1,
    Home: 0,
    End: last,
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
      :tabindex="option.value === modelValue ? 0 : -1"
      class="inline-flex cursor-pointer select-none items-center gap-1.5 rounded-md px-3 py-1.5 text-xs transition-all duration-150"
      :class="option.value === modelValue
        ? 'bg-white font-semibold text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white'
        : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-300'"
      @click="choose(index)"
      @keydown="onKeydown($event, index)"
    >
      <UIcon v-if="option.icon" :name="option.icon" class="hidden h-3.5 w-3.5 shrink-0 sm:block" aria-hidden="true" />
      {{ option.label }}
    </button>
  </div>
</template>
