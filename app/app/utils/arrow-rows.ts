/** A column of a query result, as the Arrow schema DuckDB answers with describes it. */
export interface ArrowField {
  name: string
  type: { toString: () => string }
}

type Convert = (value: unknown) => unknown

// JSON text of a nested value: a BigInt as a number, bytes as the list of them, at any depth
function jsonText(value: unknown): string {
  return JSON.stringify(value, (_key, inner) => {
    if (typeof inner === 'bigint')
      return Number(inner)
    if (ArrayBuffer.isView(inner))
      return Array.from(inner as unknown as ArrayLike<unknown>)
    return inner
  })
}

/**
 * A value of a column no type asked anything special of, made plain. DuckDB is opened to answer a
 * DECIMAL as a double (QueryPanel's `castDecimalToDouble`); a BIGINT comes as a BigInt and becomes a
 * number. Bytes (a BLOB) become the list of them, and a struct, list or map its JSON text, as a CSV
 * cell holds text. Intervals and TIME values are not turned into anything readable (GH-2071).
 */
function plainOther(value: unknown): unknown {
  if (value === null || value === undefined)
    return null
  if (typeof value === 'bigint')
    return Number(value)
  if (ArrayBuffer.isView(value))
    return jsonText(Array.from(value as unknown as ArrayLike<unknown>))
  if (typeof value === 'object')
    return jsonText(value)
  return value
}

/**
 * A timestamp or date, which Arrow gives as milliseconds since the epoch -- fractional for a
 * microsecond timestamp -- written as the REST API writes a timestamp, to the microsecond:
 * `2020-01-01T00:00:00.123456+00:00`. Floored, so a moment before 1970 is not rounded towards it. A
 * date past what a Date holds (DuckDB's `'infinity'::DATE`) is null, as there is no time to write.
 */
function timestampValue(value: unknown): unknown {
  if (typeof value !== 'number')
    return plainOther(value)
  // the fraction holds whole microseconds, which rounding recovers from the double
  const micros = Math.round(value * 1000)
  const millis = Math.floor(micros / 1000)
  const date = new Date(millis)
  if (!Number.isFinite(date.getTime()))
    return null
  const iso = date.toISOString()
  return `${iso.slice(0, 23)}${String(micros - millis * 1000).padStart(3, '0')}+00:00`
}

// types whose values Arrow's toJSON() gives as plain numbers, strings or booleans already: a column of
// one is left as it is. Int64 is not among them, as it comes as a BigInt.
const PLAIN_TYPES = /^(?:Float\d*|Int(?:8|16|32)|Uint(?:8|16|32)|Utf8|LargeUtf8|Bool)$/

function converterFor(field: ArrowField): Convert | undefined {
  const type = field.type.toString()
  if (type.startsWith('Timestamp') || type.startsWith('Date'))
    return timestampValue
  return PLAIN_TYPES.test(type) ? undefined : plainOther
}

/**
 * Turn the rows of a query result into the plain values the table, the chart and anything else that
 * takes the query panel's rows read, by the type of each column, read once (GH-2068). The rows,
 * fresh from Arrow's `toJSON()`, are changed in place.
 *
 * A name given to two columns holds the last one's value, as `toJSON()` keeps, so it takes the last
 * one's converter.
 *
 * @param rows - The rows, as Arrow's `toJSON()` gives them
 * @param fields - The result's columns, from its schema
 * @returns The same rows, with plain values
 */
export function plainRows(rows: Record<string, unknown>[], fields: ArrowField[]): Record<string, unknown>[] {
  const converters = new Map<string, Convert>()
  for (const field of fields) {
    const convert = converterFor(field)
    if (convert)
      converters.set(field.name, convert)
    else
      converters.delete(field.name)
  }
  for (const row of rows) {
    for (const [name, convert] of converters)
      row[name] = convert(row[name])
  }
  return rows
}
