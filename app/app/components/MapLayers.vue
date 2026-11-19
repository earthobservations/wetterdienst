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
  /** Whether the legend of the dots and the groups (the `legend` slot) is shown (GH-4227): the map has no box of it any more */
  showLegend?: boolean
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
    :ui="{ content: 'map-layers-panel w-72 max-w-[calc(100vw-1.5rem)] p-3 space-y-3 overflow-y-auto overscroll-contain max-h-(--reka-popover-content-available-height)' }"
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

      <!-- what the dots and the discs on the map are, in this layer and at this zoom (GH-4227): it was a box on the map, over its foot -->
      <template v-if="showLegend">
        <USeparator />
        <section class="map-layers-legend" aria-labelledby="map-legend-title">
          <h3 id="map-legend-title" class="map-layers-legend-title">
            {{ t('mapTool.legend') }}
          </h3>
          <slot name="legend" />
        </section>
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
/* The legend of the dots, under the switch (GH-4227). The swatches are the map's own (StationMap.vue), which is a light surface in both colour schemes:
   the one that reports filled, the one that has stopped hollow, a difference of shape that is no colour alone (WCAG 1.4.1). Each has a halo of white
   (the map's), so it stands against the navy of the panel at night as against the white of the day (1.4.11). */
.map-layers-legend-title {
  margin-bottom: 0.375rem;
  font-size: 0.8125rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ui-text-muted);
}
.map-legend {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  font-size: 0.8125rem;
  line-height: 1.3;
  color: var(--ui-text-toned);
}
.map-legend li {
  display: flex;
  align-items: center;
  gap: 0.625rem;
}
.map-legend-dot {
  flex: none;
  box-sizing: border-box;
  width: 0.875rem;
  height: 0.875rem;
  border: 1.5px solid #ffffff;
  border-radius: 50%;
  background: #2358a8;
  box-shadow: 0 0 0 1px #2358a8;
}
.map-legend-group {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.25rem;
  height: 1.25rem;
  margin-inline: -0.1875rem;
  color: #ffffff;
  font-size: 0.6875rem;
  font-weight: 700;
  line-height: 1;
}
.map-legend-group-share {
  /* a group of stations that report and stations that have stopped: a ring filled for the share that reports, round a light middle */
  position: relative;
  border: 1.5px solid #2358a8;
  background: conic-gradient(#2358a8 0 62%, #ffffff 62% 100%);
  box-shadow: none;
  color: #2358a8;
  z-index: 0;
}
.map-legend-group-share::before {
  content: "";
  position: absolute;
  inset: 3px;
  z-index: -1;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 0 0 1px #2358a8;
}
.map-legend-dot-stopped {
  border: 2px solid #2358a8;
  background: #ffffff;
  box-shadow: none;
}
/* in forced colours the dots keep their own colours (the filled and the hollow one are told apart by them, which system
   colours would make alike), as the tiles and the tool marks do */
@media (forced-colors: active) {
  .map-legend,
  .map-legend-dot {
    forced-color-adjust: none;
  }
}
</style>
