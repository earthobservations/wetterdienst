import type { CompareRow, CompareSummary } from './compare-model'
import { valuesToCsv } from './values-export'

// The files of a comparison (GH-4296): both sides and the difference, in one table, with what the sides are and the credit of the data
// (GH-4255). The columns are the table's own, in the unit of the values (the unit is in the description, not repeated on every row).

/** What the sides are, as a file says it */
export interface CompareDescription {
  by: 'stations' | 'periods'
  parameter: string
  resolution: string
  unit: string
  aggregation: string | null
  sides: { a: { name: string, period: string }, b: { name: string, period: string } }
  /** How the steps of the sides are matched: by calendar date, or by position in the period */
  alignment: 'calendar' | 'position-in-period'
  /** What the difference is: `B - A` */
  difference: 'B - A'
}

/** The columns of a file, in order: the step, the date of each side, the value of each, and B minus A */
export const COMPARE_COLUMNS = ['step', 'date_a', 'date_b', 'value_a', 'value_b', 'difference'] as const

/** A row as a file holds it: a missing date or value is null */
export function fileRow(row: CompareRow): Record<(typeof COMPARE_COLUMNS)[number], string | number | null> {
  return { step: row.step, date_a: row.dateA, date_b: row.dateB, value_a: row.a, value_b: row.b, difference: row.difference }
}

/**
 * The CSV: the credit and the notes as `#` comment lines before the header (as the other files of the app have them), then one row for each
 * step. A comment that is empty is left out.
 */
export function compareToCsv(rows: readonly CompareRow[], description: CompareDescription, comments: readonly string[]): string {
  const header = [
    `${description.parameter} (${description.unit}), ${description.resolution}, difference = ${description.difference}`,
    ...comments,
  ]
  return valuesToCsv(rows.map(fileRow), [...COMPARE_COLUMNS], header)
}

/** What the JSON's `metadata` holds besides the description: the credit and the note of the data */
export interface CompareFileMetadata {
  provider?: { attribution: string | null, license: { name: string, url: string } | null }
  processing_note: string
}

/**
 * The JSON: `{ metadata: { ...credit, compare: <description and the numbers under the table> }, values: [...] }`, the same shape the REST
 * API answers with, so that a reader that takes `values` finds the rows, here the two sides and the difference of each step.
 */
export function compareToJson(rows: readonly CompareRow[], description: CompareDescription, summary: CompareSummary, metadata: CompareFileMetadata): string {
  return JSON.stringify({ metadata: { ...metadata, compare: { ...description, summary } }, values: rows.map(fileRow) })
}
