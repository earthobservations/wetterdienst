<script setup lang="ts">
import type { KostraQuantity, KostraTable } from '~/utils/kostra'
import { durationLabel, KOSTRA_DURATIONS, KOSTRA_RETURN_PERIODS, KOSTRA_UNITS, quantityOf } from '~/utils/kostra'

// The table of the Heavy-rainfall tool (GH-4500): the 22 durations of a rain down, the 9 return periods across, the depth in mm or the
// intensity in l/(s·ha) in each cell, and under it, small and muted, DWD's uncertainty for that cell in plus-minus percent (a second
// line reads better on a phone than a tooltip, which a finger has no hover for). It scrolls sideways in its own box where the window is
// narrower than its nine columns, the durations staying at the left edge, and never scrolls the page.
const props = defineProps<{
  table: KostraTable
  quantity: KostraQuantity
}>()

const { t } = useI18n()
const formatLanguage = useFormatLanguage()
const numbers = computed(() => new Intl.NumberFormat(formatLanguage.value, { minimumFractionDigits: 1, maximumFractionDigits: 1 }))
const whole = computed(() => new Intl.NumberFormat(formatLanguage.value, { maximumFractionDigits: 0 }))
const unit = computed(() => KOSTRA_UNITS[props.quantity])

const rows = computed(() => KOSTRA_DURATIONS.map((minutes, durationIndex) => ({
  minutes,
  label: durationLabel(minutes, t),
  cells: KOSTRA_RETURN_PERIODS.map((years, periodIndex) => {
    const entry = props.table.rows[durationIndex]?.[periodIndex] ?? null
    const value = quantityOf(entry, props.quantity)
    return {
      years,
      value: value === null ? null : numbers.value.format(value),
      uncertainty: entry?.uncertaintyPercent == null ? null : whole.value.format(entry.uncertaintyPercent),
    }
  }),
})))
</script>

<template>
  <!-- focusable, so that a keyboard can scroll it (the box holds a table wider than a phone) -->
  <div class="kostra-table-scroll" tabindex="0" role="region" :aria-label="t('kostra.tableLabel')" data-testid="kostra-table-scroll">
    <table class="kostra-table" data-testid="kostra-table">
      <caption class="sr-only">
        {{ t('kostra.tableCaption', { quantity: t(`kostra.quantity.${quantity}`), unit }) }}
      </caption>
      <thead>
        <tr>
          <th scope="col" class="kostra-corner">
            {{ t('kostra.duration.heading') }}
          </th>
          <th v-for="years in KOSTRA_RETURN_PERIODS" :key="years" scope="col" class="kostra-head" :data-years="years">
            <span class="sr-only">{{ t('kostra.returnPeriodYears', { count: years }) }}</span>
            <span aria-hidden="true">{{ years }}</span>
          </th>
        </tr>
        <tr class="kostra-subhead">
          <td class="kostra-corner-unit">
            {{ unit }}
          </td>
          <td :colspan="KOSTRA_RETURN_PERIODS.length" class="kostra-period-title">
            {{ t('kostra.returnPeriodHeading') }}
          </td>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.minutes" :data-minutes="row.minutes">
          <th scope="row" class="kostra-duration">
            {{ row.label }}
          </th>
          <td v-for="cell in row.cells" :key="cell.years" :data-years="cell.years">
            <template v-if="cell.value !== null">
              <span class="kostra-value">{{ cell.value }}</span>
              <span v-if="cell.uncertainty !== null" class="kostra-uncertainty">
                <span class="sr-only">{{ t('kostra.uncertaintyLabel') }}{{ ' ' }}</span>±{{ cell.uncertainty }} %
              </span>
            </template>
            <span v-else class="kostra-none">
              <span aria-hidden="true">–</span><span class="sr-only">{{ t('kostra.noValue') }}</span>
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style>
.kostra-table-scroll {
  max-width: 100%;
  overflow-x: auto;
  border: 1px solid var(--ui-border);
  border-radius: calc(var(--ui-radius) * 2);
  background: var(--ui-bg);
}
.kostra-table-scroll:focus-visible {
  outline: 2px solid var(--app-focus-ring, var(--ui-primary));
  outline-offset: 2px;
}
.kostra-table {
  width: 100%;
  min-width: 36rem;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 0.875rem;
  font-variant-numeric: tabular-nums;
}
.kostra-table th,
.kostra-table td {
  padding: 0.375rem 0.625rem;
  text-align: end;
  white-space: nowrap;
  border-bottom: 1px solid var(--ui-border);
}
.kostra-table thead th {
  background: var(--ui-bg-muted, var(--ui-bg));
  color: var(--ui-text-highlighted);
  font-weight: 700;
}
.kostra-table .kostra-corner,
.kostra-table .kostra-duration {
  position: sticky;
  inset-inline-start: 0;
  text-align: start;
  background: var(--ui-bg);
  border-inline-end: 1px solid var(--ui-border);
}
.kostra-table .kostra-corner {
  z-index: 3;
  background: var(--ui-bg-muted, var(--ui-bg));
}
.kostra-table .kostra-duration {
  z-index: 2;
  font-weight: 600;
  color: var(--ui-text-highlighted);
}
.kostra-table .kostra-subhead td {
  padding-block: 0.125rem;
  font-size: 0.75rem;
  color: var(--ui-text-muted);
  background: var(--ui-bg-muted, var(--ui-bg));
}
.kostra-table .kostra-corner-unit {
  position: sticky;
  inset-inline-start: 0;
  z-index: 2;
  text-align: start;
  border-inline-end: 1px solid var(--ui-border);
}
.kostra-table .kostra-period-title {
  text-align: end;
}
.kostra-table tbody tr:last-child th,
.kostra-table tbody tr:last-child td {
  border-bottom: 0;
}
.kostra-table tbody tr:hover td,
.kostra-table tbody tr:hover th {
  background: var(--ui-bg-elevated, var(--ui-bg-muted));
}
.kostra-value {
  display: block;
  color: var(--ui-text-highlighted);
  font-weight: 600;
}
.kostra-uncertainty {
  display: block;
  font-size: 0.6875rem;
  line-height: 1.1;
  color: var(--ui-text-muted);
}
.kostra-none {
  color: var(--ui-text-muted);
}
</style>
