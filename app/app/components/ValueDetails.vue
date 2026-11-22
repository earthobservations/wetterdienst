<script setup lang="ts">
// The Explorer's value details (GH-4296): count, min, max, mean and sum of the values shown, one row for each station of
// each parameter, and under them, where exactly two stations were asked for, the difference (the second less the first,
// in the parameter's unit, and for a sum also as a share of the first's). A point's rows (interpolation, summary) are one
// series and have no station column.
//
// Table of one box that scrolls and takes the focus (a scrolling area no key reaches fails 2.1.1), with a caption, column
// headers with `scope`, the parameter as the header of its group of rows (`scope="rowgroup"`, which its rows span) and the
// station as the header of its row. A missing value and a sum that means nothing are each a dash with its own words for a
// screen reader, and the sign of a difference is written out, so that no colour carries it.
import type { ValueDetails } from '~/utils/value-details'
import { formatNumber, formatSigned, formatSignedPercent } from '~/utils/format'

const props = defineProps<{
  details: ValueDetails
}>()

const { t, locale } = useI18n()
const { parameterLabel, datasetLabel } = useParameterLabel()

/** A station as it is named: its name and its id, which tells two stations of one name apart */
function stationLabel(station: { id: string, name: string | null }): string {
  if (!station.id)
    return '—'
  return station.name && station.name !== station.id ? `${station.name} (${station.id})` : station.id
}

/** Whether a station has a name besides its id, which the table then writes under it */
const named = (station: { id: string, name: string | null }) => Boolean(station.name) && station.name !== station.id
const stationName = (station: { id: string, name: string | null }) => named(station) ? station.name! : stationLabel(station)

const showUnit = computed(() => props.details.groups.some(group => group.unit))
// the order the stations are listed in matters for exactly two, the difference being the second less the first
const ordered = computed(() => props.details.split && props.details.stations.length === 2)
const someWithoutSum = computed(() => props.details.groups.some(group => !group.sums))

const number = (value: number) => formatNumber(value, locale.value, 2)
const signed = (value: number) => formatSigned(value, locale.value, 2)
const share = (value: number) => formatSignedPercent(value, locale.value, 1)

/** The rows a parameter's header cells span: each station's and the difference's */
const spanOf = (group: ValueDetails['groups'][number]) => group.rows.length + (group.difference ? 1 : 0)
</script>

<template>
  <div class="space-y-3" data-testid="value-details">
    <p v-if="ordered" class="text-sm text-gray-600 dark:text-gray-400" data-testid="value-details-order">
      {{ t('valueDetails.order', { first: stationLabel(details.stations[0]!), second: stationLabel(details.stations[1]!) }) }}
    </p>
    <div
      role="region" tabindex="0" :aria-label="t('explorer.valuesDetails')"
      class="values-table bleed-in relative overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700"
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
            <td v-if="index === 0" :rowspan="spanOf(group)" class="hidden px-2 py-1 align-top sm:table-cell">
              {{ datasetLabel(group.dataset) }}
            </td>
            <th v-if="index === 0" :scope="details.split ? 'rowgroup' : 'row'" :rowspan="spanOf(group)" class="px-2 py-1 text-left align-top font-medium">
              {{ parameterLabel(group.parameter) }}
              <!-- on a phone the dataset is no column of its own, which the numbers need the room of: it is named under the parameter -->
              <span class="block text-xs font-normal text-gray-600 sm:hidden dark:text-gray-400">{{ datasetLabel(group.dataset) }}</span>
            </th>
            <td v-if="index === 0 && showUnit" :rowspan="spanOf(group)" class="px-2 py-1 align-top whitespace-nowrap">
              {{ group.unit ?? '' }}
            </td>
            <th v-if="details.split" scope="row" class="px-2 py-1 text-left font-normal" data-testid="value-details-station">
              <span class="whitespace-nowrap"><span v-if="ordered" class="mr-1 inline-block min-w-4 tabular-nums text-gray-600 dark:text-gray-400">{{ index + 1 }}.</span>{{ stationName(row.station) }}</span>
              <span v-if="named(row.station)" class="block text-xs text-gray-600 dark:text-gray-400" :class="ordered ? 'pl-5' : ''">{{ row.station.id }}</span>
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
                <span aria-hidden="true">&mdash;</span><span class="sr-only">{{ group.sums ? t('valueDetails.noValue') : t('valueDetails.noSum') }}</span>
              </template>
            </td>
          </tr>
          <tr
            v-if="group.difference"
            class="border-t border-dashed border-gray-300 bg-gray-50 font-medium dark:border-gray-600 dark:bg-gray-800/60"
            data-testid="value-details-difference"
          >
            <th scope="row" class="px-2 py-1 text-left font-semibold">
              {{ t('valueDetails.difference') }}
            </th>
            <td class="px-2 py-1" />
            <td class="px-2 py-1 text-right tabular-nums">
              <template v-if="group.difference.min !== null">
                {{ signed(group.difference.min) }}
              </template>
              <template v-else>
                <span aria-hidden="true">&mdash;</span><span class="sr-only">{{ t('valueDetails.noValue') }}</span>
              </template>
            </td>
            <td class="px-2 py-1 text-right tabular-nums">
              <template v-if="group.difference.max !== null">
                {{ signed(group.difference.max) }}
              </template>
              <template v-else>
                <span aria-hidden="true">&mdash;</span><span class="sr-only">{{ t('valueDetails.noValue') }}</span>
              </template>
            </td>
            <td class="px-2 py-1 text-right tabular-nums">
              <template v-if="group.difference.mean !== null">
                {{ signed(group.difference.mean) }}
              </template>
              <template v-else>
                <span aria-hidden="true">&mdash;</span><span class="sr-only">{{ t('valueDetails.noValue') }}</span>
              </template>
            </td>
            <td class="px-2 py-1 text-right tabular-nums" data-testid="value-details-sum">
              <template v-if="group.difference.sum !== null">
                {{ signed(group.difference.sum) }}
                <span v-if="group.difference.sumShare !== null" class="block text-xs font-normal text-gray-600 dark:text-gray-400" data-testid="value-details-share">
                  ({{ share(group.difference.sumShare) }})
                </span>
              </template>
              <template v-else>
                <span aria-hidden="true">&mdash;</span><span class="sr-only">{{ group.sums ? t('valueDetails.noValue') : t('valueDetails.noSum') }}</span>
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
