<script setup lang="ts">
import type { Warning } from '~/utils/warnings'

// A list of warnings, each a row that opens (WarningEntry.vue). One is open at a time, which is also the one the map draws stronger:
// opening a row tells the page (`focus`), closing it takes the emphasis off. A list that is refreshed keeps the row that is open while
// its warning is still in the snapshot.

const props = defineProps<{
  warnings: readonly Warning[]
  now: number
  /** The name of the list for assistive technology */
  label: string
  /** Makes the ids of the rows' details unique where there are two lists on a page */
  idPrefix: string
  /** The warning the map draws stronger, which is the one open; set by the page when the map is the one that picked it */
  focused?: string | null
  /** Whether opening a row is told to the page (the map's): the banner of the Forecast has no map to tell */
  announceFocus?: boolean
}>()

const emit = defineEmits<{ focus: [id: string | null] }>()

const open = ref<string | null>(props.focused ?? null)
watch(() => props.focused, (id) => {
  if (id !== undefined)
    open.value = id
})
// a warning that has left the snapshot closes its row
watch(() => props.warnings.map(warning => warning.id), (ids) => {
  if (open.value && !ids.includes(open.value))
    open.value = null
})

function toggle(id: string) {
  open.value = open.value === id ? null : id
  if (props.announceFocus)
    emit('focus', open.value)
}
</script>

<template>
  <ul class="warnings-list" :aria-label="label" data-testid="warnings-list">
    <li v-for="warning in warnings" :key="warning.id">
      <WarningEntry
        :warning="warning"
        :now="now"
        :open="open === warning.id"
        :focused="focused === warning.id"
        :details-id="`${idPrefix}-${warning.id.replace(/\W/g, '-')}`"
        @toggle="toggle(warning.id)"
      />
    </li>
  </ul>
</template>

<style>
.warnings-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  align-self: stretch;
}
</style>
