<script setup lang="ts">
// A button of a chart's toolbar (earlier, later, zoom in and out, reset) that is off where there is nothing left for it to do: the whole
// chart is shown, so there is nothing to reset; the window is at its edge, so there is nowhere to move to.
//
// It is `aria-disabled`, not `disabled`: a button that turns `disabled` while it has the focus drops the focus to the page (Space on Reset,
// Enter on Zoom in at its limit), and a keyboard user starts again from the top (WCAG 2.4.3). So it stays a button in the tab order,
// says it is unavailable (`aria-disabled`, 4.1.2), looks as Nuxt UI's disabled button looks (its `aria-disabled:` variants, the same classes
// as `disabled:`, with the focus ring on top) and does nothing when pressed, by a click, Enter or Space.
const props = defineProps<{
  /** Off: there is nothing for the button to do now */
  unavailable?: boolean
}>()

const emit = defineEmits<{
  click: []
}>()

function press() {
  if (!props.unavailable)
    emit('click')
}
</script>

<template>
  <UButton
    size="sm"
    variant="outline"
    color="neutral"
    class="shrink-0"
    :aria-disabled="props.unavailable ? 'true' : undefined"
    @click="press"
  />
</template>
