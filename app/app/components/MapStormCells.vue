<script setup lang="ts">
import type { StormCellsStatus } from '~/composables/useStormCells'
import type { StormCell, StormScan } from '~/utils/storm-cells'
import { formatNumber, formatRunTime } from '~/utils/format'
import { compassPoint, hasMotion, LIST_LIMIT, listed, SEVERITIES, styleOf } from '~/utils/storm-cells'

// The text of the map's thunderstorm cells (GH-4208): the list of the cells of the latest scan with their severity and
// their motion, which the map draws and cannot tell a keyboard or a screen reader. It is in the panel beside the map
// (under it on a phone), where the stations are, so a cell is reached without the map. It also says what the map cannot
// show of an empty scan: DWD writes a scan every 5 minutes and about 80 % of them hold no cell, so "no thunderstorm
// cells" is the usual answer and says which scan it is true of. The direction of a cell's motion is calculated by the
// backend from its forecast track and is marked as calculated wherever it is told. The credit of the data (DWD, KONRAD3D,
// the licence) is under the list, from the answer's own `metadata` block.

const props = defineProps<{
  scan: StormScan | null
  status: StormCellsStatus
  /** A refresh failed while the scan in hand is shown */
  refreshFailed: boolean
}>()

defineEmits<{ retry: [] }>()

const { t } = useI18n()
const formatLanguage = useFormatLanguage()

/** Whether the list shows every cell: it shows the most severe ten until the reader asks for more */
const showAll = ref(false)
const shown = computed(() => listed(props.scan?.cells ?? [], showAll.value))
const hasMore = computed(() => (props.scan?.cells.length ?? 0) > LIST_LIMIT)

const time = computed(() => props.scan?.referenceTime ? formatRunTime(props.scan.referenceTime, formatLanguage.value) : '')
const count = computed(() => formatNumber(props.scan?.cells.length ?? 0, formatLanguage.value, 0))

/** What the severity of a cell is called: its number and DWD's word for it, or that there is none */
function severityText(cell: StormCell): string {
  if (cell.severity === null)
    return t('mapTool.cellsSeverityUnknown')
  const word = (['weak', 'moderate', 'severe', 'extreme'] as const)[SEVERITIES.indexOf(cell.severity)]!
  return t('mapTool.cellsSeverity', { level: cell.severity, label: t(`mapTool.cellsSeverityLabel.${word}`) })
}

/** What the cell's motion is, in words, and that its direction is calculated */
function motionText(cell: StormCell): string {
  const speed = cell.speedKmh === null ? null : formatNumber(cell.speedKmh, formatLanguage.value, 0)
  if (cell.speedKmh !== null && cell.speedKmh < 1)
    return t('mapTool.cellsStationary')
  if (!hasMotion(cell) || cell.directionDegrees === null)
    return speed === null ? t('mapTool.cellsMotionNone') : t('mapTool.cellsMotionSpeed', { speed })
  const direction = t(`mapTool.cellsCompass.${compassPoint(cell.directionDegrees)}`)
  return speed === null
    ? t('mapTool.cellsMotionDirection', { direction })
    : t('mapTool.cellsMotion', { direction, speed })
}

const credit = computed(() => props.scan?.credit ?? null)
</script>

<template>
  <section class="map-card map-cells" aria-labelledby="map-cells-title" data-testid="map-cells">
    <h2 id="map-cells-title" class="map-card-title">
      <UIcon name="i-ph-cloud-lightning" class="map-card-icon" />
      {{ t('mapTool.layerCells') }}
    </h2>

    <p v-if="status === 'pending' || status === 'idle'" class="map-card-note" role="status" data-testid="map-cells-loading">
      {{ t('mapTool.cellsLoading') }}
    </p>

    <div v-else-if="status === 'error'" class="flex flex-col items-start gap-2">
      <p class="map-card-note" role="alert" data-testid="map-cells-failed">
        {{ t('mapTool.cellsFailed') }}
      </p>
      <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" data-testid="map-cells-retry" @click="$emit('retry')" />
    </div>

    <template v-else-if="scan">
      <!-- the one live line: the count, which changes when the cells do and not each time the scan does -->
      <p class="text-sm font-semibold text-highlighted" role="status" data-testid="map-cells-summary">
        {{ scan.cells.length ? t('mapTool.cellsCount', { shown: count }) : t('mapTool.cellsNone') }}
      </p>
      <p v-if="time" class="map-card-note" data-testid="map-cells-scan">
        {{ t('mapTool.cellsScan', { time }) }}
      </p>
      <p v-if="scan.stale" class="map-card-note map-cells-warning" data-testid="map-cells-stale">
        <UIcon name="i-ph-warning" class="size-4 shrink-0" />
        {{ t('mapTool.cellsStale') }}
      </p>
      <div v-if="refreshFailed" class="flex flex-col items-start gap-2" data-testid="map-cells-refresh-failed">
        <p class="map-card-note map-cells-warning" role="alert">
          <UIcon name="i-ph-warning" class="size-4 shrink-0" />
          {{ t('mapTool.cellsRefreshFailed', { time }) }}
        </p>
        <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" @click="$emit('retry')" />
      </div>

      <ul v-if="scan.cells.length" id="map-cells-list" class="map-cells-list" :aria-label="t('mapTool.cellsListLabel')" data-testid="map-cells-list">
        <li v-for="cell in shown" :key="cell.id" class="map-cells-item" data-testid="map-cells-item">
          <!-- the badge is the mark on the map: the number is repeated in the words beside it, so it is no cue alone -->
          <span class="map-cells-badge" :style="{ background: styleOf(cell.severity).color }" aria-hidden="true">{{ styleOf(cell.severity).text }}</span>
          <span class="min-w-0">
            <span class="block font-semibold text-highlighted break-words">{{ t('mapTool.cellsItem', { id: cell.id }) }}</span>
            <span class="block text-sm text-toned" data-testid="map-cells-severity">{{ severityText(cell) }}</span>
            <span class="block text-sm text-muted" data-testid="map-cells-motion">{{ motionText(cell) }}</span>
          </span>
        </li>
      </ul>
      <!-- a long list (a day of storms has some hundred cells) is cut to the most severe ten, and the rest is a press away -->
      <UButton
        v-if="hasMore"
        :label="showAll ? t('mapTool.cellsShowFewer') : t('mapTool.cellsShowAll', { shown: count })"
        :icon="showAll ? 'i-ph-caret-up' : 'i-ph-caret-down'"
        color="neutral"
        variant="ghost"
        size="sm"
        class="-ms-2"
        aria-controls="map-cells-list"
        :aria-expanded="showAll"
        data-testid="map-cells-more"
        @click="showAll = !showAll"
      />

      <p v-if="scan.cells.length" class="map-card-note">
        {{ t('mapTool.cellsLegendMark') }}. {{ t('mapTool.cellsLegendArrow') }}.
      </p>

      <p class="map-card-note" data-testid="map-cells-credit">
        {{ t('mapTool.cellsCredit') }}
        <template v-if="credit?.attribution">
          {{ credit.attribution }}.
        </template>
        <template v-if="credit?.license">
          {{ t('providers.licence') }}{{ t('common.colon') }}
          <NuxtLink
            :to="credit.license.url"
            external
            target="_blank"
            rel="noopener"
            class="text-primary-700 dark:text-primary-500 underline hover:no-underline"
          >
            {{ credit.license.name }}
          </NuxtLink>.
        </template>
      </p>
    </template>
  </section>
</template>

<style>
/* the card is in the panel beside the list of the stations, which has its own gaps */
.map-cells {
  margin-bottom: 1rem;
}
.map-cells-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  align-self: stretch;
}
.map-cells-item {
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
}
/* the mark of the cell as the map draws it: the number of its severity on its colour, white on 4.5:1 or more (StationMap.vue, utils/storm-cells.ts) */
.map-cells-badge {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  margin-top: 0.125rem;
  border-radius: 50%;
  color: #ffffff;
  font-size: 0.8125rem;
  font-weight: 700;
  line-height: 1;
}
.map-cells-warning {
  display: flex;
  align-items: flex-start;
  gap: 0.375rem;
  color: var(--ui-text-toned);
}
@media (forced-colors: active) {
  .map-cells-badge {
    forced-color-adjust: none;
  }
}
</style>
