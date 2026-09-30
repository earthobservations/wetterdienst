/** A column of a query result, as the Arrow schema DuckDB answers with describes it. */
export interface ArrowField {
  name: string
  type: { toString: () => string, scale?: number }
}

type Convert = (value: unknown) => unknown

// JSON has no way to write a BigInt: a safe one as its number, a larger one as its digits
function bigintValue(value: bigint): number | string {
  const number = Number(value)
  return Number.isSafeInteger(number) ? number : value.toString()
}

function jsonText(value: unknown): string {
  return JSON.stringify(value, (_key, inner) => typeof inner === 'bigint' ? bigintValue(inner) : inner)
}

/**
 * Turn a value no column type asked for anything special into a plain one: a BigInt as a number, or
 * its digits past where a number is exact; bytes (a BLOB, an interval) as the list of them; a
 * struct, list or map as its JSON text, as a CSV cell holds text.
 */
function plainOther(value: unknown): unknown {
  if (value === null || value === undefined)
    return null
  if (typeof value === 'bigint')
    return bigintValue(value)
  if (ArrayBuffer.isView(value))
    return jsonText(Array.from(value as unknown as ArrayLike<unknown>))
  if (typeof value === 'object')
    return jsonText(value)
  return value
}

// Milliseconds since the epoch, as Arrow gives a timestamp or a date, written as the REST API writes
// a timestamp: `2020-01-01T00:00:00.000000+00:00`. A value past what a Date holds (DuckDB's
// `infinity`) is left the number it came as, rather than failing the whole query.
function timestampValue(value: unknown): unknown {
  if (typeof value !== 'number')
    return plainOther(value)
  const date = new Date(value)
  if (!Number.isFinite(date.getTime()))
    return value
  return date.toISOString().replace(/Z$/, '000+00:00')
}

// A DECIMAL's unscaled integer as text, the point put where the scale says
function decimalText(unscaled: string, scale: number): string {
  const negative = unscaled.startsWith('-')
  const digits = (negative ? unscaled.slice(1) : unscaled).padStart(scale + 1, '0')
  const text = scale > 0 ? `${digits.slice(0, -scale)}.${digits.slice(-scale)}` : digits
  return negative ? `-${text}` : text
}

// Arrow gives a DECIMAL as an object holding its unscaled integer (12.34 at scale 2 as 1234), whose
// `valueOf(scale)` gives the number it stands for; past where a number is exact it throws, and the
// decimal is written as its digits instead
function decimalValue(value: unknown, scale: number): unknown {
  if (value === null || value === undefined)
    return null
  try {
    const number = (value as { valueOf: (scale: number) => unknown }).valueOf(scale)
    if (typeof number === 'number' && Number.isFinite(number))
      return number
  }
  catch {}
  return decimalText(String(value), scale)
}

function converterFor(field: ArrowField): Convert {
  const type = field.type.toString()
  if (type.startsWith('Timestamp') || type.startsWith('Date'))
    return timestampValue
  if (type.startsWith('Decimal')) {
    const scale = field.type.scale ?? 0
    return value => decimalValue(value, scale)
  }
  return plainOther
}

/**
 * Turn one value Arrow's `toJSON()` gave into the plain value the table, the chart and anything else
 * that takes the query panel's rows read, by the type of its column (GH-2068).
 */
export function plainValue(value: unknown, field: ArrowField): unknown {
  return converterFor(field)(value)
}

/**
 * Turn the rows of a query result into plain values, as `plainValue` does, reading each column's
 * type once rather than once a cell; the rows, fresh from Arrow's `toJSON()`, are changed in place.
 *
 * @param rows - The rows, as Arrow's `toJSON()` gives them
 * @param fields - The result's columns, from its schema
 * @returns The same rows, with plain values
 */
export function plainRows(rows: Record<string, unknown>[], fields: ArrowField[]): Record<string, unknown>[] {
  const converters = fields.map(field => [field.name, converterFor(field)] as const)
  for (const row of rows) {
    for (const [name, convert] of converters)
      row[name] = convert(row[name])
  }
  return rows
}
