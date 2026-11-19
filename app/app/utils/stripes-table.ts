import type { StripeClass, StripeYear } from './stripes'
import { valuesToCsv } from './values-export'

/**
 * The table of the stripes (GH-4233) and the CSV it is saved as: the years drawn, each with its value, its anomaly and its
 * class, as the backend calculated them against the station's whole record. Pure functions of the years, so that the file's
 * content is tested without a browser.
 */

type Translate = (key: string, params?: Record<string, unknown>) => string

const BYTE_ORDER_MARK = '\uFEFF'

/** The headers, the unit of the values in those of the two numbers: `Value (°C)` */
export function stripesTableColumns(unit: string, t: Translate): string[] {
  const withUnit = (label: string) => unit ? `${label} (${unit})` : label
  return [t('stripes.table.year'), withUnit(t('stripes.table.value')), withUnit(t('stripes.table.anomaly')), t('stripes.table.class')]
}

/** The years in the order of the calendar, whatever order the answer came in */
export function stripesTableYears(years: readonly StripeYear[]): StripeYear[] {
  return [...years].sort((a, b) => a.year - b.year)
}

/** A number as a file writes it: two decimals, a point, no sign for a zero that rounds to none (`-0.00`) */
function plain(value: number): string {
  return Number(value.toFixed(2)).toFixed(2)
}

/**
 * The CSV of the table: the lines of `comments` first, each after a `#` (what the colours are relative to, the credit and the
 * licence, so that the file carries them away from the page), then the header and a row for each year. The numbers are plain
 * (`.` for the decimal point, no sign for a positive one, no unit: it is in the header), whatever the page's language; the
 * class is written in the language of the page, as the table writes it. The text starts with a UTF-8 byte order mark: Excel
 * reads a file without one in the legacy code page, and `°C`, `–` and the names of the classes (`Kühler`) come out garbled.
 *
 * @param columns - The headers, as `stripesTableColumns` writes them
 * @param years - The years, as `stripeYears` lists them
 * @param className - Names a class in the language of the page
 * @param comments - The lines before the header, without their `#`
 * @returns The text of the file, after its byte order mark, ending in a line break; an empty string for no years
 */
export function stripesCsv(columns: string[], years: readonly StripeYear[], className: (stripeClass: StripeClass) => string, comments: readonly string[]): string {
  const rows = stripesTableYears(years).map(year => ({
    [columns[0]!]: year.year,
    [columns[1]!]: plain(year.value),
    [columns[2]!]: plain(year.anomaly),
    [columns[3]!]: className(year.class),
  }))
  const body = valuesToCsv(rows, columns)
  if (!body)
    return ''
  // a line break in a comment would end it: the comment is one line
  const header = comments.map(comment => comment.replace(/\s+/g, ' ').trim()).filter(Boolean).map(comment => `# ${comment}`)
  return `${BYTE_ORDER_MARK}${[...header, body].join('\n')}\n`
}
