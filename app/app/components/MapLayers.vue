<script setup lang="ts">
import type { PopoverProps } from '@nuxt/ui'
import type { MapLayer } from '~/utils/map-tool'

// The one control the map tool lays over the map (GH-4209): a round button with a layers icon in the map's top right
// corner, which opens a small panel with the choice of the layer (a radio group), what the layer is read at (the
// resolution and dataset of the measurements, the page's own selects in the slot) and, under it, the switch that
// groups the stations (GH-4079). It replaces the two rows of chips the map carried, which took a quarter of a phone's map.
//
// The panel is a Nuxt UI popover (Reka UI's non-modal one): the button names it and says whether it is open
// (`aria-expanded`, `aria-controls`), Escape and a press outside close it, and the focus goes back to the button after
// Escape. The page tells the map that the panel is open, so that the press on the map that closes it picks nothing (StationMap.vue). A layer chosen leaves it open, so that the grouping can be set after it.

defineProps<{
  layerItems: { value: MapLayer, label: string, icon: string }[]
  /** Whether the switch is shown: where the layer's stations are in, and not while they load or have failed */
  showGrouping: boolean
  /** Whether the stations of the layer cannot be left ungrouped (more than `GROUPING_COMPULSORY_ABOVE`): the switch is on and disabled, and the note says why */
  compulsory: boolean
  note: string
}>()

const layer = defineModel<MapLayer>('layer', { required: true })
const grouped = defineModel<boolean>('grouped', { required: true })
/** Whether the panel is open, which the map is told (a press on the map that closes the panel is that and nothing else) */
const open = defineModel<boolean>('open', { default: false })

const { t } = useI18n()
/** The panel's own element is the dialog the button opens: it needs a name, and a hook for the tests, which the popover passes on to it although its type does not list them */
const content = computed(() => ({ 'side': 'bottom', 'align': 'end', 'sideOffset': 8, 'aria-label': t('mapTool.layersButton'), 'data-testid': 'map-layers-panel' }) as NonNullable<PopoverProps['content']>)
const GROUPING_NOTE_ID = 'map-grouping-note'
const GROUPING_SWITCH_ID = 'map-grouping-switch'
</script>

<template>
  <UPopover
    v-model:open="open"
    :portal="false"
    :content="content"
    :ui="{ content: 'map-layers-panel w-72 max-w-[calc(100vw-1.5rem)] p-3 space-y-3' }"
  >
    <UButton
      icon="i-ph-stack"
      color="neutral"
      variant="outline"
      size="xl"
      class="map-layers-button"
      :aria-label="t('mapTool.layersButton')"
      :title="t('mapTool.layersButton')"
      data-testid="map-layers-button"
    />

    <template #content>
      <URadioGroup
        v-model="layer"
        :items="layerItems"
        :legend="t('mapTool.layers')"
        variant="card"
        data-testid="map-layers"
      >
        <template #label="{ item }">
          <span class="inline-flex items-center gap-2">
            <UIcon :name="(item as { icon: string }).icon" class="size-4 shrink-0" />
            {{ item.label }}
          </span>
        </template>
      </URadioGroup>

      <slot />

      <template v-if="showGrouping">
        <USeparator />
        <div class="map-layers-grouping">
          <USwitch
            :id="GROUPING_SWITCH_ID"
            v-model="grouped"
            :disabled="compulsory"
            :label="t('mapTool.groupStations')"
            :aria-describedby="compulsory ? GROUPING_NOTE_ID : undefined"
            :ui="{ root: 'w-full min-h-[44px] flex-row-reverse items-center justify-between', wrapper: 'ms-0 flex-1', label: 'flex min-h-[44px] items-center text-sm font-semibold' }"
            data-testid="map-grouping"
          />
          <p v-if="compulsory" :id="GROUPING_NOTE_ID" class="text-sm text-muted" data-testid="map-grouping-note">
            {{ note }}
          </p>
        </div>
      </template>
    </template>
  </UPopover>
</template>

<style>
/* a round button, 44 px (the app's own measure of a target), over the map, in the page's own background (white by day, the card's navy at night) */
.map-layers-button.map-layers-button {
  width: 2.75rem;
  height: 2.75rem;
  justify-content: center;
  border-radius: 999px;
  background: var(--ui-bg);
  box-shadow: 0 1px 3px rgb(15 23 42 / 0.15);
  pointer-events: auto;
}
.map-layers-grouping {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
/* the row of the switch is 44 px high, and its label, which is the larger part of the target, is the whole of the row's height */
.map-layers-grouping [data-slot="root"] {
  min-height: 44px;
  align-items: center;
}
.map-layers-grouping [data-slot="wrapper"],
.map-layers-grouping [data-slot="label"] {
  display: flex;
  align-items: center;
  min-height: 44px;
}
</style>
