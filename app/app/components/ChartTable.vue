<script setup lang="ts">
// The text alternative of a chart that carries its data in colour and shape (WCAG 1.1.1, 1.3.1): what the
// chart draws, as a table behind a "Show as table" disclosure, as the explorer offers its values. The
// first cell of a row is its header (the year, the time).
defineProps<{
  /** The table's name: the chart's own */
  caption: string
  /** The column headers, the row header's first */
  columns: string[]
  /** The cells of each row, already written as a reader reads them */
  rows: string[][]
  /** What a reader needs to read the table, such as what a class is */
  note?: string
}>()

const { t } = useI18n()
</script>

<template>
  <UCollapsible class="mt-4">
    <UButton
      :label="t('dataViewer.viewTable')"
      icon="i-lucide-table"
      variant="subtle"
      color="neutral"
      trailing-icon="i-lucide-chevron-down"
      size="sm"
    />
    <template #content>
      <p v-if="note" class="mt-3 text-sm text-gray-600 dark:text-gray-400">
        {{ note }}
      </p>
      <!-- a box that scrolls takes the focus, so that the keys scroll it (a scrolling area no key reaches fails 2.1.1) -->
      <div
        role="region" tabindex="0" :aria-label="caption"
        class="mt-3 max-h-96 overflow-auto rounded-lg border border-gray-200 dark:border-gray-700"
      >
        <table class="w-full border-collapse text-sm">
          <caption class="sr-only">
            {{ caption }}
          </caption>
          <thead>
            <tr>
              <th
                v-for="column in columns" :key="column" scope="col"
                class="sticky top-0 bg-gray-100 px-3 py-1.5 text-left font-semibold text-gray-900 dark:bg-gray-800 dark:text-gray-100"
              >
                {{ column }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in rows" :key="index" class="border-t border-gray-200 dark:border-gray-700">
              <template v-for="(cell, cellIndex) in row" :key="cellIndex">
                <th v-if="cellIndex === 0" scope="row" class="px-3 py-1 text-left font-medium whitespace-nowrap">
                  {{ cell }}
                </th>
                <td v-else class="px-3 py-1 whitespace-nowrap">
                  {{ cell }}
                </td>
              </template>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </UCollapsible>
</template>
