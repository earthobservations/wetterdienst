<script setup lang="ts">
import type { StormCellsStatus } from '~/composables/useStormCells'
import type { StormCell, StormScan } from '~/utils/storm-cells'
import { formatNumber } from '~/utils/format'
import { formatFrameTime } from '~/utils/radar'
import { cellView, compassPoint, hasMotion, LIST_LIMIT, listed, roundedPosition, SEVERITIES, styleOf } from '~/utils/storm-cells'
import { timestampDate } from '~/utils/timestamp'

// The thunderstorm cells of the Radar tool (GH-4208, GH-3788): a switch for drawing them on the map and, under it, the list of the
// cells of the latest scan with their place, their severity and their motion, which the map draws and cannot tell a keyboard or a
// screen reader. It is in the panel beside the map (under it on a phone), so a cell is reached without the map. A cell is told where
// it is, by its position rounded to two decimals (the Radar has no station or place picked to tell it from); and a press on it (Enter on
// a keyboard) centres the map on it, as a click on a group of stations does. With the switch off nothing is asked for. The cells are
// the latest scan's: on a frame that is not within 15 minutes of it, or is of the forecast, the map fades them out, and the card says so. It also says what the map cannot show of an empty scan: DWD writes
// a scan every 5 minutes and about 80 % of them hold no cell, so "no thunderstorm cells" is the usual answer and says which
// scan it is true of. A scan kept too long is told out of date, its cells no longer drawn. The direction of a cell's motion
// is calculated by the backend from its forecast track and is marked as calculated wherever it is told. The credit of the
// data (DWD, KONRAD3D, the licence) is under the list, from the answer's own `metadata` block.

const props = defineProps<{
  scan: StormScan | null
  status: StormCellsStatus
  /** A refresh failed while the scan in hand is shown */
  refreshFailed: boolean
  /** The scan in hand is more than 20 minutes old: its cells are not drawn on the map */
  outdated: boolean
  /** The frame on the map is not within 15 minutes of the scan, or is of the forecast: the cells are faded out of the map, and this says so */
  fadedOnFrame?: boolean
}>()

defineEmits<{ retry: [], centre: [cell: StormCell] }>()
/** Whether the cells are drawn on the map and asked for (every 5 minutes) */
const on = defineModel<boolean>('on', { default: true })

const { t } = useI18n()
const formatLanguage = useFormatLanguage()

/** Whether the list shows every cell: it shows the most severe ten until the reader asks for more */
const showAll = ref(false)
const shown = computed(() => listed(props.scan?.cells ?? [], showAll.value))
const hasMore = computed(() => (props.scan?.cells.length ?? 0) > LIST_LIMIT)

/**
 * The scan's time as the radar writes its frames' (`formatFrameTime`): the time of day in the reader's own zone with the zone's name
 * ("09:40 CET"), the weekday where it is not today. The radar's times and the cells' are then the same kind, which a reader compares
 * (GH-3788); the cells were UTC with the date.
 */
const time = computed(() => {
  const at = props.scan?.referenceTime ? timestampDate(props.scan.referenceTime) : null
  return at ? formatFrameTime(at.getTime(), formatLanguage.value, Date.now()) : ''
})
/** The same, for the notes about the scan (out of date, faded, a refresh that failed) */
const clock = time
const count = computed(() => formatNumber(props.scan?.cells.length ?? 0, formatLanguage.value, 0))

/**
 * The one live line, which is in the page from the start so that a change of its text is announced: loading, then the count
 * (or that there is none). It carries no time, so an unchanged scan is not announced again every 5 minutes.
 */
const summary = computed(() => {
  if (props.scan)
    return props.scan.cells.length ? t('radar.cellsCount', { shown: count.value }) : t('radar.cellsNone')
  return props.status === 'error' ? '' : t('radar.cellsLoading')
})

/** What the severity of a cell is called: its number and DWD's word for it, or that there is none */
function severityText(cell: StormCell): string {
  if (cell.severity === null)
    return t('radar.cellsSeverityUnknown')
  const word = (['weak', 'moderate', 'severe', 'extreme'] as const)[SEVERITIES.indexOf(cell.severity)]!
  return t('radar.cellsSeverity', { level: cell.severity, label: t(`radar.cellsSeverityLabel.${word}`) })
}

/** What the cell's motion is, in words, and that its direction is calculated */
function motionText(cell: StormCell): string {
  const speed = cell.speedKmh === null ? null : formatNumber(cell.speedKmh, formatLanguage.value, 0)
  if (cell.speedKmh !== null && cell.speedKmh < 1)
    return t('radar.cellsStationary')
  if (!hasMotion(cell) || cell.directionDegrees === null)
    return speed === null ? t('radar.cellsMotionNone') : t('radar.cellsMotionSpeed', { speed })
  const direction = t(`radar.cellsCompass.${compassPoint(cell.directionDegrees)}`)
  return speed === null
    ? t('radar.cellsMotionDirection', { direction })
    : t('radar.cellsMotion', { direction, speed })
}

/** Where the cell is, in words: its position rounded to two decimals; none for a cell that has no position */
function locationText(cell: StormCell): string | null {
  const at = cellView(cell)
  return at ? t('radar.cellsPosition', { position: roundedPosition(at) }) : null
}

const credit = computed(() => props.scan?.credit ?? null)
const CENTRE_HINT_ID = 'radar-cells-centre-hint'
</script>

<template>
  <section class="radar-card radar-cells" aria-labelledby="radar-cells-title" data-testid="radar-cells">
    <h2 id="radar-cells-title" class="radar-card-title">
      <UIcon name="i-ph-cloud-lightning" class="radar-card-icon" />
      {{ t('radar.layerCells') }}
    </h2>

    <USwitch
      v-model="on"
      :label="t('radar.cellsSwitch')"
      :ui="{ root: 'w-full min-h-[44px] flex-row-reverse items-center justify-between', wrapper: 'ms-0 flex-1', label: 'flex min-h-[44px] items-center text-sm font-semibold' }"
      data-testid="radar-cells-switch"
    />

    <!-- in the page from the start, also with the switch off, and only screen-reader-only while empty (a hidden one is not in the accessibility tree): a live region that is inserted with its text is not announced -->
    <p class="text-sm font-semibold text-highlighted empty:sr-only" role="status" data-testid="radar-cells-summary">
      {{ on ? summary : '' }}
    </p>

    <template v-if="on">
      <div v-if="status === 'error' && !scan" class="flex flex-col items-start gap-2">
        <p class="radar-card-note" role="alert" data-testid="radar-cells-failed">
          {{ t('radar.cellsFailed') }}
        </p>
        <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" data-testid="radar-cells-retry" @click="$emit('retry')" />
      </div>

      <template v-else-if="scan">
        <p v-if="time" class="radar-card-note" data-testid="radar-cells-scan">
          {{ t('radar.cellsScan', { time }) }}
        </p>
        <p class="radar-card-note" data-testid="radar-cells-loop-note">
          {{ t('radar.cellsLoopNote') }}
        </p>
        <p v-if="fadedOnFrame" class="radar-card-note radar-note-row radar-cells-warning" data-testid="radar-cells-faded">
          <UIcon name="i-ph-eye-slash" class="size-4 shrink-0" />
          {{ t('radar.cellsFaded', { time: clock }) }}
        </p>
        <p v-if="outdated" class="radar-card-note radar-note-row radar-cells-warning" data-testid="radar-cells-outdated">
          <UIcon name="i-ph-warning" class="size-4 shrink-0" />
          {{ t('radar.cellsOutdated', { time: clock }) }}
        </p>
        <p v-else-if="scan.stale" class="radar-card-note radar-note-row radar-cells-warning" data-testid="radar-cells-stale">
          <UIcon name="i-ph-warning" class="size-4 shrink-0" />
          {{ t('radar.cellsStale') }}
        </p>
        <div v-if="refreshFailed" class="flex flex-col items-start gap-2" data-testid="radar-cells-refresh-failed">
          <p class="radar-card-note radar-note-row radar-cells-warning" role="alert">
            <UIcon name="i-ph-warning" class="size-4 shrink-0" />
            {{ t('radar.cellsRefreshFailed', { time: clock }) }}
          </p>
          <UButton :label="t('common.retry')" icon="i-ph-arrow-clockwise" size="sm" color="neutral" variant="outline" @click="$emit('retry')" />
        </div>

        <ul v-if="scan.cells.length" id="radar-cells-list" class="radar-cells-list" :aria-label="t('radar.cellsListLabel')" data-testid="radar-cells-list">
          <li v-for="cell in shown" :key="cell.id" data-testid="radar-cells-item">
            <!-- a cell with a position is a button that centres the map on it; the badge is the mark on the map, and its number is in the words beside it, so it is no cue alone -->
            <component
              :is="cellView(cell) ? 'button' : 'div'"
              :type="cellView(cell) ? 'button' : undefined"
              :aria-describedby="cellView(cell) ? CENTRE_HINT_ID : undefined"
              class="radar-cells-item"
              :class="{ 'radar-cells-button': cellView(cell) }"
              data-testid="radar-cells-entry"
              @click="cellView(cell) && $emit('centre', cell)"
            >
              <span class="radar-cells-badge" :style="{ background: styleOf(cell.severity).color }" aria-hidden="true">{{ styleOf(cell.severity).text }}</span>
              <span class="min-w-0">
                <span class="block font-semibold text-highlighted break-words">{{ t('radar.cellsItem', { id: cell.id }) }}</span>
                <span v-if="locationText(cell)" class="block text-sm text-toned" data-testid="radar-cells-location">{{ locationText(cell) }}</span>
                <span class="block text-sm text-toned" data-testid="radar-cells-severity">{{ severityText(cell) }}</span>
                <span class="block text-sm text-muted" data-testid="radar-cells-motion">{{ motionText(cell) }}</span>
              </span>
            </component>
          </li>
        </ul>
        <p v-if="scan.cells.length" :id="CENTRE_HINT_ID" class="sr-only">
          {{ t('radar.cellsCentreHint') }}
        </p>
        <!-- a long list (a day of storms has some hundred cells) is cut to the most severe ten, and the rest is a press away -->
        <UButton
          v-if="hasMore"
          :label="showAll ? t('radar.cellsShowFewer') : t('radar.cellsShowAll', { shown: count })"
          :icon="showAll ? 'i-ph-caret-up' : 'i-ph-caret-down'"
          color="neutral"
          variant="ghost"
          size="sm"
          class="-ms-2"
          aria-controls="radar-cells-list"
          :aria-expanded="showAll"
          data-testid="radar-cells-more"
          @click="showAll = !showAll"
        />

        <p v-if="scan.cells.length" class="radar-card-note">
          {{ t('radar.cellsLegendMark') }}. {{ t('radar.cellsLegendArrow') }}.
        </p>

        <p class="radar-card-note" data-testid="radar-cells-credit">
          {{ t('radar.cellsCredit') }}
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
    </template>
  </section>
</template>

<style>
/* the card is in the panel beside the list of the stations, which has its own gaps */
.radar-cells {
  margin-bottom: 1rem;
}
.radar-cells-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  align-self: stretch;
}
.radar-cells-item {
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
  width: 100%;
  padding: 0.375rem 0.5rem;
  border-radius: calc(var(--ui-radius) * 2);
  text-align: start;
}
/* a cell that centres the map on a press: a row as high as a target, hovered like the stations' list */
.radar-cells-button {
  min-height: 2.75rem;
  cursor: pointer;
}
.radar-cells-button:hover {
  background: var(--ui-bg-elevated);
}
/* the mark of the cell as the map draws it: the number of its severity on its colour, white on 4.5:1 or more (StationMap.vue, utils/storm-cells.ts) */
.radar-cells-badge {
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
.radar-note-row radar-cells-warning {
  display: flex;
  align-items: flex-start;
  gap: 0.375rem;
  color: var(--ui-text-toned);
}
@media (forced-colors: active) {
  .radar-cells-badge {
    forced-color-adjust: none;
  }
}
</style>
