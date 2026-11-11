<script setup lang="ts">
import { TOOLS } from '~/utils/sections'

// Where a tool's result will be, until there is one (GH-3850): the dashed frame, the tool's own tile and one sentence,
// the same in every tool, so the column of the result is no empty hole and is not drawn four ways. The tile is the
// tool's, read from `utils/sections.ts` as the header reads it; the sentence is `toolPlaceholder.<key>`, which says how
// to begin and names no direction, since the form is above the frame on a phone and beside it on a wide screen. A new
// tool is a line of `TOOLS`, a sentence in every locale, and `<ToolPlaceholder tool="its key" />`.
const props = defineProps<{
  /** The key of the tool in `TOOLS` (`forecast`, `explorer`, `stripes`, `history`, `map`) */
  tool: string
}>()

const { t } = useI18n()
const section = computed(() => {
  const found = TOOLS.find(tool => tool.key === props.tool)
  if (!found)
    throw new Error(`ToolPlaceholder: "${props.tool}" is no tool of utils/sections.ts`)
  return found
})
</script>

<template>
  <div
    class="rounded-xl border-2 border-dashed border-default p-12 text-center text-muted"
    data-testid="tool-placeholder"
    :data-tool="section.key"
  >
    <ToolTile :tile="section.tile" :icon="section.icon" size="2.5rem" class="mx-auto mb-3" />
    <p class="text-sm">
      {{ t(`toolPlaceholder.${section.key}`) }}
    </p>
  </div>
</template>
