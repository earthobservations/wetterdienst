<script setup lang="ts">
// The Explorer's value details (GH-4296): count, min, max, mean and sum of the values shown, one row for each station of
// each parameter. A point's rows (interpolation, summary) are one series and have no station column.
//
// Table in one box that scrolls and takes the focus (a scrolling area no key reaches fails 2.1.1), with a caption, column
// headers with `scope`, the parameter as the header of its group of rows (`scope="rowgroup"`, which its rows span) and the
// station as the header of its row. A missing value and a sum that means nothing are each a dash with its own words for a
// screen reader. The box has no name of its own: the table's caption is its name, and a second one would be read twice.
import type { ValueDetails } from '~/utils/value-details'
import { formatNumber } from '~/utils/format'

const props = defineProps<{
  details: ValueDetails
}>()

const { t, locale } = useI18n()
const { parameterLabel, datasetLabel } = useParameterLabel()

/** Whether a station has a name besides its id, which the table then writes under it */
const named = (station: { id: string, name: string | null }) => Boolean(station.name) && station.name !== station.id
/** A station as the table names it: its name, else its id, and a dash for the values that are no station's */
const stationName = (station: { id: string, name: string | null }) => named(station) ? station.name! : (station.id || '—')

const showUnit = computed(() => props.details.groups.some(group => group.unit))
const someWithoutSum = computed(() => props.details.groups.some(group => !group.sums))

const number = (value: number) => formatNumber(value, locale.value, 2)

type Group = ValueDetails['groups'][number]
/** The words a dash in a sum cell has for a screen reader: why there is no sum, or that the station has no value */
const noSumWords = (group: Group) => group.overlap ? t('valueDetails.noSumOverlap') : group.sums ? t('valueDetails.noValue') : t('valueDetails.noSum')
</script>

<template>
  <div class="space-y-3" data-testid="value-details">
    <div
      tabindex="0"
      class="values-table bleed-in relative overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700"
      data-testid="value-details-scroll"
    >
      <table class="w-full text-sm border-collapse">
        <caption class="sr-only">
          {{ t('explorer.valuesDetails') }}
        </caption>
        <thead>
          <tr class="bg-gray-100 text-left dark:bg-gray-800">
            <th scope="col" class="hidden px-2 py-1.5 font-semibold sm:table-cell">
              {{ t('dataViewer.statDataset') }}
            </th>
            <th scope="col" class="px-2 py-1.5 font-semibold">
              {{ t('dataViewer.statParameter') }}
            </th>
            <th v-if="showUnit" scope="col" class="px-2 py-1.5 font-semibold">
              {{ t('valueDetails.unit') }}
            </th>
            <th v-if="details.split" scope="col" class="px-2 py-1.5 font-semibold">
              {{ t('valueDetails.station') }}
            </th>
            <th scope="col" class="px-2 py-1.5 text-right font-semibold">
              {{ t('dataViewer.statCount') }}
            </th>
            <th scope="col" class="px-2 py-1.5 text-right font-semibold">
              {{ t('dataViewer.statMin') }}
            </th>
            <th scope="col" class="px-2 py-1.5 text-right font-semibold">
              {{ t('dataViewer.statMax') }}
            </th>
            <th scope="col" class="px-2 py-1.5 text-right font-semibold">
              {{ t('dataViewer.statMean') }}
            </th>
            <th scope="col" class="px-2 py-1.5 text-right font-semibold">
              {{ t('dataViewer.statSum') }}
            </th>
          </tr>
        </thead>
        <tbody
          v-for="group in details.groups" :key="`${group.dataset}/${group.parameter}`"
          class="border-t border-gray-200 dark:border-gray-700" data-testid="value-details-group"
        >
          <tr v-for="(row, index) in group.rows" :key="row.station.id" data-testid="value-details-row">
            <td v-if="index === 0" :rowspan="group.rows.length" class="hidden px-2 py-1 align-top sm:table-cell">
              {{ datasetLabel(group.dataset) }}
            </td>
            <th v-if="index === 0" :scope="details.split ? 'rowgroup' : 'row'" :rowspan="group.rows.length" class="px-2 py-1 text-left align-top font-medium">
              {{ parameterLabel(group.parameter) }}
              <!-- on a phone the dataset is no column of its own, which the numbers need the room of: it is named under the parameter -->
              <span class="block text-xs font-normal text-gray-600 sm:hidden dark:text-gray-400">{{ datasetLabel(group.dataset) }}</span>
            </th>
            <td v-if="index === 0 && showUnit" :rowspan="group.rows.length" class="px-2 py-1 align-top whitespace-nowrap">
              {{ group.unit ?? '' }}
            </td>
            <th v-if="details.split" scope="row" class="px-2 py-1 text-left font-normal" data-testid="value-details-station">
              <span class="whitespace-nowrap">{{ stationName(row.station) }}</span>
              <template v-if="named(row.station)">
                <!-- the id is a line of its own for the eye; the comma keeps the name and the id apart for a screen reader -->
                <span class="sr-only">, </span>
                <span class="block text-xs text-gray-600 dark:text-gray-400">{{ row.station.id }}</span>
              </template>
            </th>
            <td class="px-2 py-1 text-right tabular-nums">
              {{ row.count }}
            </td>
            <td class="px-2 py-1 text-right tabular-nums">
              <template v-if="row.min !== null">
                {{ number(row.min) }}
              </template>
              <template v-else>
                <span aria-hidden="true">&mdash;</span><span class="sr-only">{{ t('valueDetails.noValue') }}</span>
              </template>
            </td>
            <td class="px-2 py-1 text-right tabular-nums">
              <template v-if="row.max !== null">
                {{ number(row.max) }}
              </template>
              <template v-else>
                <span aria-hidden="true">&mdash;</span><span class="sr-only">{{ t('valueDetails.noValue') }}</span>
              </template>
            </td>
            <td class="px-2 py-1 text-right tabular-nums">
              <template v-if="row.mean !== null">
                {{ number(row.mean) }}
              </template>
              <template v-else>
                <span aria-hidden="true">&mdash;</span><span class="sr-only">{{ t('valueDetails.noValue') }}</span>
              </template>
            </td>
            <td class="px-2 py-1 text-right tabular-nums" data-testid="value-details-sum">
              <template v-if="row.sum !== null">
                {{ number(row.sum) }}
              </template>
              <template v-else>
                <span aria-hidden="true">&mdash;</span><span class="sr-only">{{ noSumWords(group) }}</span>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="someWithoutSum" class="text-xs text-gray-600 dark:text-gray-400" data-testid="value-details-sum-note">
      {{ t('valueDetails.sumNote') }}
    </p>
  </div>
</template>
