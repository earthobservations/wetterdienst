<script setup lang="ts">
import type { Value } from '#shared/types/api'
import type { PanelId } from '~/composables/useMeteogramView'
import type { SeriesLabel } from '~/utils/chart-theme'
import type { MeteogramView } from '~/utils/meteogram'
import { DateTime, Info } from 'luxon'
import tzLookup from 'tz-lookup'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import MeteogramChart from '~/components/MeteogramChart.vue'
import { panelToggleStyle, seriesLabelColor } from '~/utils/chart-theme'
import { meteogramDays } from '~/utils/meteogram-days'
import { buildSeries, seriesSpan } from '~/utils/meteogram-series'
import { meteogramSummary, meteogramTable } from '~/utils/meteogram-summary'
import { meteogramUnits } from '~/utils/meteogram-units'
import { WEATHER_ICONS } from '~/utils/weather-kind'

const props = defineProps<{
  values: Value[]
  stationName?: string | null
  stationCoords?: { latitude: number | null, longitude: number | null } | null
  widget?: boolean
  /**
   * The day rows alone, with no chart and no controls: the forecast in the map's panel (GH-3650). The view is not
   * the reader's to choose and nothing is remembered or written to the address.
   */
  daysOnly?: boolean
  /**
   * The unit each parameter's values are in, by the parameter's canonical name, as the answer says (`metadata.parameters`
   * of an answer `with_metadata`, `unitsOfAnswer`). The labels of the charts, the table and the day rows are written
   * from it, and the verdicts (rain or snow, the weather of a day, the wind barbs) are judged in canonical units
   * whatever it is (GH-3980). A parameter the answer gives no unit for is read as the canonical unit of its quantity.
   */
  units?: Record<string, string>
}>()

const { t, locale } = useI18n()

// The language's own tag (`en-GB`, `de-DE`) where `locale` is the app's code (`en`), with the stand-in for a language
// the browser has no data for (`lb-LU` is written as `de-LU`): what the date formats, `Intl` and luxon are handed
const formatLanguage = useFormatLanguage()

// The chart's colours are read from the app's CSS tokens for the colour scheme in force (utils/chart-theme.ts)
const { isDark } = useChartTheme()

// What the reader chose: the view (remembered, and in the address), the panels, the horizon
const { view, compact, visiblePanels, horizonHours, chooseView } = useMeteogramView(props)
const viewOptions = computed<{ value: MeteogramView, label: string, icon: string }[]>(() => [
  { value: 'chart', label: t('meteogram.chart.viewChart'), icon: 'i-ph-chart-line' },
  { value: 'compact', label: t('meteogram.chart.viewCompact'), icon: 'i-ph-squares-four' },
  { value: 'table', label: t('meteogram.chart.viewTable'), icon: 'i-ph-table' },
])

// The panel toggles, in the order of the panels: the colour of each is that of its series' labels
// `icon` is the outline, `iconOn` the filled variant of the same icon: a toggle that is on draws the filled one, so that on
// and off differ by shape and not by colour alone (WCAG 1.4.1, GH-3951)
const panelToggles: { panel: PanelId, icon: string, iconOn: string, title: string, series: SeriesLabel }[] = [
  { panel: 'temp', icon: 'i-ph-thermometer', iconOn: 'i-ph-thermometer-fill', title: 'meteogram.chart.panelTemperature', series: 'red' },
  { panel: 'wind', icon: 'i-ph-wind', iconOn: 'i-ph-wind-fill', title: 'meteogram.chart.panelWind', series: 'cyan' },
  { panel: 'precip', icon: 'i-ph-cloud-rain', iconOn: 'i-ph-cloud-rain-fill', title: 'meteogram.chart.panelPrecipitation', series: 'blue' },
  { panel: 'cloud', icon: 'i-ph-cloud', iconOn: 'i-ph-cloud-fill', title: 'meteogram.chart.panelCloud', series: 'slate' },
  { panel: 'pressure', icon: 'i-ph-gauge', iconOn: 'i-ph-gauge-fill', title: 'meteogram.chart.panelPressure', series: 'lime' },
]
// a toggle that is on: the icon in the label colour, on a wash and in an edge of it
const activeToggleStyle = (series: SeriesLabel) => panelToggleStyle(seriesLabelColor(series, isDark.value))

const horizonOptions = computed(() => [
  { label: '24h', value: 24 },
  { label: '3d', value: 72 },
  { label: '7d', value: 168 },
  { label: t('meteogram.chart.horizonAll'), value: null },
])

const seriesCache = computed(() => buildSeries(props.values ?? []))
const units = computed(() => meteogramUnits(props.units, t))

// The chart: its zoom, which the toolbar's buttons and the reset move
const chart = useTemplateRef<InstanceType<typeof MeteogramChart>>('chart')
function resetChart() {
  horizonHours.value = null
  chart.value?.resetZoom()
}

// The station's time zone, which the times of the table are written in, as the chart's axis is
const stationTimeZone = computed(() => {
  const { latitude, longitude } = props.stationCoords ?? {}
  if (latitude == null || longitude == null)
    return 'UTC'
  try {
    const zone = tzLookup(latitude, longitude)
    // a zone the browser does not know would make every date of the chart invalid
    return Info.isValidIANAZone(zone) ? zone : 'UTC'
  }
  catch {
    return 'UTC'
  }
})

// The zone as the summary row names it: `Europe/Berlin (UTC+02:00)`, at the run's first moment
const toolbarTzLabel = computed(() => {
  const span = seriesSpan(seriesCache.value)
  if (!span)
    return stationTimeZone.value
  const offsetMin = DateTime.fromMillis(span.min, { zone: stationTimeZone.value }).offset
  const sign = offsetMin >= 0 ? '+' : '-'
  const h = String(Math.floor(Math.abs(offsetMin) / 60)).padStart(2, '0')
  const m = String(Math.abs(offsetMin) % 60).padStart(2, '0')
  return `${stationTimeZone.value} (UTC${sign}${h}:${m})`
})

// The date it is today at the station: a computed of its own, so that what reads it runs again at the station's
// midnight and not with every tick of the clock below (GH-3840)
const now = ref(Date.now())
const localToday = computed(() => DateTime.fromMillis(now.value, { zone: stationTimeZone.value }).toISODate()!)
// a page that stays open past midnight moves its Today on
let clock: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  clock = setInterval(() => {
    now.value = Date.now()
  }, 60_000)
})
onBeforeUnmount(() => {
  clearInterval(clock)
})

const compactDays = computed(() => meteogramDays(seriesCache.value, {
  zone: stationTimeZone.value,
  today: localToday.value,
  units: units.value,
  locale: locale.value,
  language: formatLanguage.value,
}))

// What the chart draws, as a table and a sentence (WCAG 1.1.1, 1.3.1, and 1.4.13 for the values that appear
// on hover only)
const chartTable = computed(() => meteogramTable(seriesCache.value, {
  panels: visiblePanels.value,
  horizonHours: horizonHours.value,
  zone: stationTimeZone.value,
  formatLanguage: formatLanguage.value,
  locale: locale.value,
  units: units.value,
  t,
  widget: !!props.widget,
}))
const summaryId = useId()
const chartLabel = computed(() => props.stationName ? t('meteogram.chart.label', { name: props.stationName }) : t('meteogram.chart.labelNoStation'))

// Calculate summary statistics for the loaded forecast period
const summaryStats = computed(() => meteogramSummary(seriesCache.value, units.value, locale.value))
</script>

<template>
  <div>
    <UEmpty
      v-if="!values || values.length === 0"
      icon="i-ph-cloud-slash"
      :title="t('meteogram.chart.noData')"
    />

    <div v-if="values && values.length > 0" class="space-y-5">
      <!-- Premium Overhauled Filter / Controls Toolbar -->
      <div v-if="!widget" class="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-gray-50/70 dark:bg-gray-800/40 p-3.5 rounded-xl border border-gray-100 dark:border-gray-800 shadow-sm">
        <!-- Left group: panel toggles + horizon selector (wraps as a unit on narrow viewports) -->
        <div v-if="!compact" class="flex flex-wrap items-center gap-2 min-w-0">
          <!-- Interactive Panel Selectors -->
          <div class="flex items-center gap-1">
            <span class="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-widest mr-1 select-none">{{ t('meteogram.chart.panels') }}</span>

            <!-- the colours are those of the series' labels (SERIES_LABEL, WCAG 1.4.11 and 1.4.3: tests/unit/button-contrast.test.ts), not the series' own -->
            <button
              v-for="toggle in panelToggles"
              :key="toggle.panel"
              type="button"
              :title="t(toggle.title)"
              :aria-label="t(toggle.title)"
              :data-panel="toggle.panel"
              :aria-pressed="visiblePanels[toggle.panel]"
              class="inline-flex items-center p-1.5 rounded-full border transition-all duration-200 cursor-pointer select-none active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none"
              :class="visiblePanels[toggle.panel]
                ? ''
                : 'bg-white/40 dark:bg-gray-900/40 border-gray-200/80 dark:border-gray-800/80 text-gray-500 dark:text-gray-400 hover:bg-white dark:hover:bg-gray-900 hover:text-gray-700 dark:hover:text-gray-200 hover:border-gray-300 dark:hover:border-gray-700'"
              :style="visiblePanels[toggle.panel] ? activeToggleStyle(toggle.series) : undefined"
              :disabled="toggle.panel === 'cloud' && compact"
              @click="visiblePanels[toggle.panel] = !visiblePanels[toggle.panel]"
            >
              <UIcon :name="visiblePanels[toggle.panel] ? toggle.iconOn : toggle.icon" class="w-3.5 h-3.5" />
            </button>
          </div>

          <!-- Forecast Horizon Selector -->
          <div class="flex items-center bg-gray-100 dark:bg-gray-800/70 rounded-lg p-0.5 gap-0.5">
            <button
              v-for="opt in horizonOptions"
              :key="String(opt.value)"
              type="button"
              class="text-xs px-2.5 py-1 rounded-md transition-all duration-150 select-none cursor-pointer"
              :class="horizonHours === opt.value
                ? 'bg-white dark:bg-gray-700 shadow-sm text-gray-900 dark:text-white font-semibold'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-300'"
              @click="horizonHours = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <!-- View Controls & Zoom Reset: the view first on a narrow screen, where the toolbar stacks -->
        <div class="flex flex-wrap items-center gap-2 md:ml-auto min-w-0 max-w-full order-first md:order-last">
          <!-- the single-pointer ways to what a drag, a pinch and the scroll bar do (WCAG 2.5.7), named by what they do -->
          <div v-if="view === 'chart'" class="flex items-center gap-1" role="group" :aria-label="t('meteogram.chart.zoomGroup')">
            <UButton
              icon="i-ph-caret-left"
              size="sm"
              variant="outline"
              color="neutral"
              :title="t('meteogram.chart.earlier')"
              :aria-label="t('meteogram.chart.earlier')"
              :disabled="chart?.atStart"
              class="shrink-0"
              @click="chart?.shift(-0.5)"
            />
            <UButton
              icon="i-ph-caret-right"
              size="sm"
              variant="outline"
              color="neutral"
              :title="t('meteogram.chart.later')"
              :aria-label="t('meteogram.chart.later')"
              :disabled="chart?.atEnd"
              class="shrink-0"
              @click="chart?.shift(0.5)"
            />
            <UButton
              icon="i-ph-magnifying-glass-minus"
              size="sm"
              variant="outline"
              color="neutral"
              :title="t('meteogram.chart.zoomOut')"
              :aria-label="t('meteogram.chart.zoomOut')"
              :disabled="chart?.atMinZoom"
              class="shrink-0"
              @click="chart?.zoomOut()"
            />
            <UButton
              icon="i-ph-magnifying-glass-plus"
              size="sm"
              variant="outline"
              color="neutral"
              :title="t('meteogram.chart.zoomIn')"
              :aria-label="t('meteogram.chart.zoomIn')"
              :disabled="chart?.atMaxZoom"
              class="shrink-0"
              @click="chart?.zoomIn()"
            />
            <UButton
              icon="i-ph-arrow-counter-clockwise"
              size="sm"
              variant="outline"
              color="neutral"
              :title="t('meteogram.chart.resetZoom')"
              :aria-label="t('meteogram.chart.resetZoom')"
              class="shrink-0"
              @click="resetChart"
            />
          </div>
          <SegmentedControl
            :model-value="view"
            :options="viewOptions"
            :label="t('meteogram.chart.viewLabel')"
            @update:model-value="chooseView"
          />
        </div>
      </div>

      <!-- Summary stats: same order as the panel toggles (temp/wind/precip/cloud/pressure) -->
      <div v-if="summaryStats && !widget" class="flex flex-wrap gap-x-5 gap-y-2 px-1 text-sm">
        <div v-if="summaryStats.temp" class="flex items-center gap-1.5">
          <UIcon name="i-ph-thermometer" class="w-4 h-4 shrink-0" data-summary-icon="temp" :style="{ color: seriesLabelColor('red', isDark) }" />
          <span class="text-blue-600 dark:text-blue-400 font-semibold">{{ summaryStats.temp.min }}</span>
          <span class="text-gray-500 dark:text-gray-400">/</span>
          <span class="text-red-600 dark:text-red-400 font-semibold">{{ summaryStats.temp.max }}</span>
        </div>
        <div class="flex items-center gap-1.5">
          <UIcon name="i-ph-wind" class="w-4 h-4 shrink-0" data-summary-icon="wind" :style="{ color: seriesLabelColor('cyan', isDark) }" />
          <span class="font-semibold text-gray-800 dark:text-gray-100">{{ summaryStats.gust.value }}</span>
          <span class="text-gray-500 dark:text-gray-400 text-xs">{{ summaryStats.gust.unit }}</span>
        </div>
        <div class="flex items-center gap-1.5">
          <UIcon name="i-ph-cloud-rain" class="w-4 h-4 shrink-0" data-summary-icon="precip" :style="{ color: seriesLabelColor('blue', isDark) }" />
          <span class="font-semibold text-gray-800 dark:text-gray-100">{{ summaryStats.precip.value }}</span>
          <span class="text-gray-500 dark:text-gray-400 text-xs">{{ summaryStats.precip.unit }}</span>
        </div>
        <div class="flex items-center gap-1.5">
          <UIcon name="i-ph-cloud" class="w-4 h-4 shrink-0" data-summary-icon="cloud" :style="{ color: seriesLabelColor('slate', isDark) }" />
          <span class="font-semibold text-gray-800 dark:text-gray-100">{{ summaryStats.cloud.value }}</span>
          <span class="text-gray-500 dark:text-gray-400 text-xs">{{ summaryStats.cloud.unit }}</span>
        </div>
        <div v-if="summaryStats.pressure" class="flex items-center gap-1.5">
          <UIcon name="i-ph-gauge" class="w-4 h-4 shrink-0" data-summary-icon="pressure" :style="{ color: seriesLabelColor('lime', isDark) }" />
          <span class="font-semibold text-gray-800 dark:text-gray-100">{{ summaryStats.pressure.range }}</span>
          <span class="text-gray-500 dark:text-gray-400 text-xs">{{ summaryStats.pressure.unit }}</span>
        </div>
        <!-- the time zone of the chart's axis: the table names its own in its header -->
        <div v-if="view === 'chart'" class="hidden sm:block ml-auto self-center text-xs text-gray-500 dark:text-gray-400 select-none">
          {{ toolbarTzLabel }}
        </div>
      </div>

      <!-- Main Interactive Chart Container -->
      <div v-if="view === 'chart'">
        <div class="rounded-xl border border-gray-200 dark:border-gray-800 bg-default shadow-sm overflow-hidden">
          <!-- a figure, as the app's other charts, and no landmark. Described by what it shows; the table has the values -->
          <MeteogramChart
            ref="chart"
            :series="seriesCache"
            :panels="visiblePanels"
            :horizon-hours="horizonHours"
            :zone="stationTimeZone"
            :station-coords="stationCoords"
            :units="units"
            :label="chartLabel"
            :described-by="chartTable ? summaryId : undefined"
            :widget="widget"
          />
        </div>
        <template v-if="chartTable">
          <p :id="summaryId" class="sr-only">
            {{ chartTable.summary }}
          </p>
          <!-- the widget has no control to choose the table with: its text alternative stays below the chart -->
          <ChartTable v-if="widget" :caption="chartLabel" :columns="chartTable.columns" :rows="chartTable.rows" />
        </template>
      </div>

      <!-- The values the chart draws, as a table of their own at the width of the page -->
      <div v-else-if="view === 'table'">
        <ValuesTable v-if="chartTable" full :caption="chartLabel" :columns="chartTable.columns" :rows="chartTable.rows" />
        <UEmpty v-else icon="i-ph-table" :title="t('meteogram.chart.noData')" />
      </div>

      <!-- in the map's panel, one row a day: the day, its weather, its rain and its temperatures -->
      <!-- every day of the run is before today at the station: no row to show -->
      <p v-else-if="daysOnly && !compactDays.length" class="text-sm text-muted" data-testid="day-rows-empty">
        {{ t('widget.noData') }}
      </p>
      <ul v-else-if="daysOnly" class="divide-y divide-default" data-testid="day-rows">
        <li v-for="(d, idx) in compactDays" :key="idx" class="grid grid-cols-[minmax(4.5rem,auto)_2rem_1fr_auto] items-center gap-x-3 py-2">
          <span class="text-sm" :class="d.isToday ? 'font-bold text-highlighted' : 'text-toned'">
            {{ d.isToday ? t('meteogram.chart.today') : d.weekday }}
            <span class="block text-xs font-normal text-muted tabular-nums">{{ d.dayMonth }}</span>
            <span v-if="d.partialHours" class="block text-xs font-normal text-muted" data-testid="partial-day">{{ t('meteogram.chart.partialDay', { hours: d.partialHours }) }}</span>
          </span>
          <!-- the icon is a decoration; the words are what a screen reader reads (WCAG 1.1.1). text-toned: 3:1 and more on the row, by day and at night -->
          <UIcon :name="WEATHER_ICONS[d.kind]" class="size-6 text-toned" aria-hidden="true" :data-weather="d.kind" />
          <span class="text-sm text-toned">
            <span class="sr-only">{{ t(`meteogram.chart.weather.${d.kind}`) }}</span>
            <span v-if="d.precipLabel" class="text-blue-700 dark:text-blue-300 tabular-nums">
              <span class="sr-only">{{ ', ' }}{{ t('meteogram.chart.panelPrecipitation') }}{{ t('common.colon') }}{{ ' ' }}</span>{{ d.precipLabel }}
            </span>
          </span>
          <span v-if="d.tempLabel" class="text-sm font-bold text-highlighted tabular-nums text-end">{{ d.tempLabel }}</span>
        </li>
      </ul>

      <UEmpty v-else-if="!compactDays.length" icon="i-ph-cloud-slash" :title="t('meteogram.chart.noData')" />

      <!-- Premium Compact Overview Grid -->
      <div v-else class="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-950 shadow-md p-4">
        <!-- relative: the cards' visually hidden texts are positioned, and would otherwise lie outside the box that scrolls and make the page scroll sideways (WCAG 1.4.10) -->
        <div class="relative flex items-center justify-start gap-4 overflow-x-auto whitespace-nowrap py-1 px-1">
          <template v-for="(d, idx) in compactDays" :key="idx">
            <div
              class="inline-flex flex-col items-center justify-center text-center p-4 rounded-2xl border transition-all duration-300 min-w-[105px] flex-shrink-0" :class="[
                d.isToday
                  ? 'bg-blue-500/5 dark:bg-blue-500/10 border-blue-600 dark:border-blue-400 ring-1 ring-blue-400/20 shadow-md shadow-blue-500/5'
                  : 'bg-gray-50/50 dark:bg-gray-900/30 border-gray-100 dark:border-gray-800 hover:bg-gray-100 dark:hover:bg-gray-900/70 hover:border-gray-200 dark:hover:border-gray-700',
              ]"
            >
              <div class="text-xs font-bold text-gray-600 dark:text-gray-400 uppercase tracking-widest mb-1">
                {{ d.isToday ? t('meteogram.chart.today') : d.weekday }}
              </div>
              <!-- the icon is a decoration; the words are what a screen reader reads (WCAG 1.1.1) -->
              <div class="my-3 animate-bounce-slow">
                <UIcon :name="WEATHER_ICONS[d.kind]" class="size-8 text-toned" aria-hidden="true" :data-weather="d.kind" />
              </div>
              <div class="sr-only">
                {{ t(`meteogram.chart.weather.${d.kind}`) }}
              </div>
              <div class="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">
                {{ d.dayMonth }}
              </div>
              <div v-if="d.partialHours" class="text-xs text-gray-600 dark:text-gray-400 mb-2" data-testid="partial-day">
                {{ t('meteogram.chart.partialDay', { hours: d.partialHours }) }}
              </div>
              <div v-if="d.tempLabel" class="text-xs font-extrabold text-gray-700 dark:text-gray-200 mt-1 bg-white dark:bg-gray-800/80 px-2 py-0.5 rounded-lg border border-gray-100 dark:border-gray-700 shadow-xs">
                {{ d.tempLabel }}
              </div>
              <div v-if="d.precipLabel" class="text-xs font-semibold text-blue-600 dark:text-blue-400 mt-1 select-none">
                <UIcon name="i-ph-drop" class="size-3.5 align-text-bottom" aria-hidden="true" />
                <span class="sr-only">{{ t('meteogram.chart.panelPrecipitation') }}{{ t('common.colon') }}{{ ' ' }}</span>{{ d.precipLabel }}
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Smooth custom bounce animation for the weather icons. Once, and not at all for a visitor who asked
   for less motion: movement that starts by itself and goes on for more than five seconds needs a way
   to be stopped (WCAG 2.2.2), and a decoration is not worth one. */
@keyframes bounce-slow {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}
@media (prefers-reduced-motion: no-preference) {
  .animate-bounce-slow {
    animation: bounce-slow 4s ease-in-out 1;
  }
}
</style>
