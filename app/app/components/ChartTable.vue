<script setup lang="ts">
// The text alternative of a chart that carries its data in colour and shape (WCAG 1.1.1, 1.3.1): what the
// chart draws, as a table behind a "Show as table" disclosure, as the explorer offers its values. The
// first cell of a row is its header (the year, the time). The forecast's table is a view of its own
// (`ValuesTable`, `full`) and this disclosure is its text alternative in the widget only.
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
      <ValuesTable :caption="caption" :columns="columns" :rows="rows" :note="note" />
    </template>
  </UCollapsible>
</template>
