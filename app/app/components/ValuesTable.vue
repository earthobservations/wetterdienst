<script setup lang="ts">
// The values a chart draws, as a table (WCAG 1.1.1, 1.3.1): a caption, column headers with `scope`, and the first
// cell of a row as its header (the year, the time). It sits in a box that scrolls, in both directions, and takes
// the focus, so that the keys scroll it (a scrolling area no key reaches fails 2.1.1).
//
// `full` is the table as a view of its own, not a text alternative folded away below a chart: it is tall (a
// forecast of ten days has hundreds of rows) and keeps its header and its first column in view while it
// scrolls, so that a value is always read against its time and its parameter.
defineProps<{
  /** The table's name: the chart's own */
  caption: string
  /** The column headers, the row header's first */
  columns: string[]
  /** The cells of each row, already written as a reader reads them */
  rows: string[][]
  /** What a reader needs to read the table, such as what a class is */
  note?: string
  /** The table as a view of its own: tall, with the first column fixed beside the scrolling ones */
  full?: boolean
}>()
</script>

<template>
  <p v-if="note" class="mt-3 text-sm text-gray-600 dark:text-gray-400">
    {{ note }}
  </p>
  <div
    role="region" tabindex="0" :aria-label="caption"
    class="overflow-auto rounded-lg border border-gray-200 dark:border-gray-700"
    :class="full ? 'max-h-[70vh] min-h-48' : 'mt-3 max-h-96'"
  >
    <table class="w-full text-sm" :class="full ? 'border-separate border-spacing-0' : 'border-collapse'">
      <caption class="sr-only">
        {{ caption }}
      </caption>
      <thead>
        <tr>
          <th
            v-for="(column, columnIndex) in columns" :key="column" scope="col"
            class="sticky top-0 bg-gray-100 px-3 py-1.5 text-left font-semibold text-gray-900 dark:bg-gray-800 dark:text-gray-100"
            :class="full && columnIndex === 0 ? 'left-0 z-20 border-b border-gray-200 dark:border-gray-700' : full ? 'z-10 border-b border-gray-200 dark:border-gray-700' : ''"
          >
            {{ column }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in rows" :key="index" :class="full ? '' : 'border-t border-gray-200 dark:border-gray-700'">
          <template v-for="(cell, cellIndex) in row" :key="cellIndex">
            <th
              v-if="cellIndex === 0" scope="row"
              class="px-3 py-1 text-left font-medium"
              :class="full
                ? 'sticky left-0 z-10 border-b border-gray-200 bg-white sm:whitespace-nowrap dark:border-gray-700 dark:bg-gray-900'
                : 'whitespace-nowrap'"
            >
              {{ cell }}
            </th>
            <td v-else class="whitespace-nowrap px-3 py-1" :class="full ? 'border-b border-gray-200 dark:border-gray-700' : ''">
              {{ cell }}
            </td>
          </template>
        </tr>
      </tbody>
    </table>
  </div>
</template>
