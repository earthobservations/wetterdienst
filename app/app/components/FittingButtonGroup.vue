<script setup lang="ts">
// A joined row of buttons that stands on its own, one above the other, where its box is too narrow for the row (a
// phone's 320 px, or a card in a column: the width of the window does not tell, the width of the box does). The row
// is measured as it comes, side by side, and its width remembered while it is stacked, so that it goes back to a row
// once there is room for it. Nothing is cut short (GH-3985).
const box = useTemplateRef<HTMLElement>('box')
const group = useTemplateRef<{ $el: HTMLElement }>('group')
const { width: boxWidth } = useElementSize(box)
const { locale } = useI18n()

/** The width of the buttons side by side; 0 until measured */
const natural = ref(0)
const stacked = computed(() => boxWidth.value > 0 && natural.value > boxWidth.value + 1)

function measure() {
  const element = group.value?.$el
  // only a row can be measured: stacked, the group is as wide as its widest button
  if (element && !stacked.value)
    natural.value = element.scrollWidth
}

onMounted(measure)
useResizeObserver(() => group.value?.$el, measure)
// the names are other texts in another language, and then the row is measured again
watch(locale, async () => {
  natural.value = 0
  await nextTick()
  measure()
})
</script>

<template>
  <div ref="box">
    <UFieldGroup ref="group" :orientation="stacked ? 'vertical' : 'horizontal'">
      <slot />
    </UFieldGroup>
  </div>
</template>
