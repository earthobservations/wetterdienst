import type { DataType, Decimal, Field, FixedSizeList, Struct, Table, Time, Timestamp, Union, Vector } from 'apache-arrow'
import { TimeUnit, Type } from 'apache-arrow/enum'

// A time's ticks in a second, by the unit of its type
const TICKS_PER_SECOND: Record<TimeUnit, bigint> = {
  [TimeUnit.SECOND]: 1n,
  [TimeUnit.MILLISECOND]: 1_000n,
  [TimeUnit.MICROSECOND]: 1_000_000n,
  [TimeUnit.NANOSECOND]: 1_000_000_000n,
}

// DuckDB's infinite timestamps, in any unit: the largest 64-bit integer and its negative
const INFINITE_TICKS = 2n ** 63n - 1n

// A division rounded down, so a moment before 1970 is floored to the microsecond rather than rounded
// towards 1970
function floorDiv(dividend: bigint, divisor: bigint): bigint {
  const quotient = dividend / divisor
  return dividend % divisor < 0n ? quotient - 1n : quotient
}

// An integer type's value (a BIGINT, a HUGEINT) or a decimal of no scale as a number where that is
// exact, its digits past 2^53
function integerValue(value: bigint): number | string {
  const number = Number(value)
  return Number.isSafeInteger(number) ? number : value.toString()
}

/**
 * Microseconds since the epoch written as the REST API writes a timestamp, to the microsecond:
 * `2020-01-01T00:00:00.123456+00:00`. A moment a Date cannot hold, as DuckDB's `'infinity'::DATE`
 * or `'infinity'::TIMESTAMP`, is null.
 */
function timestampValue(micros: bigint): string | null {
  const millis = floorDiv(micros, 1000n)
  const date = new Date(Number(millis))
  if (Number.isNaN(date.getTime()))
    return null
  return `${date.toISOString().slice(0, -1)}${String(micros - millis * 1000n).padStart(3, '0')}+00:00`
}

// A time of day, which Arrow gives as ticks of its unit since midnight, as `01:00:00.500000`: to the
// microsecond, as a timestamp is written
function timeValue(value: number | bigint, unit: TimeUnit): string {
  const ticks = BigInt(value)
  const perSecond = TICKS_PER_SECOND[unit]
  const seconds = ticks / perSecond
  const micros = (ticks % perSecond) * 1_000_000n / perSecond
  const pad = (part: bigint, width = 2) => part.toString().padStart(width, '0')
  return `${pad(seconds / 3600n)}:${pad(seconds / 60n % 60n)}:${pad(seconds % 60n)}.${pad(micros, 6)}`
}

/**
 * An interval as an ISO 8601 duration, `P1Y2M3DT4H5M6.5S`, each part carrying its own sign as DuckDB
 * keeps months, days and the time apart: `-INTERVAL '1 year 2 days'` is `P-1Y-2D`. Nanoseconds are
 * dropped, as a timestamp's are.
 */
function intervalValue(months: number, days: number, nanos: bigint): string {
  const micros = nanos / 1000n
  const sign = micros < 0n ? '-' : ''
  const magnitude = micros < 0n ? -micros : micros
  const seconds = magnitude / 1_000_000n
  const fraction = (magnitude % 1_000_000n).toString().padStart(6, '0').replace(/0+$/, '')
  const part = (amount: number, unit: string) => amount ? `${amount}${unit}` : ''
  const timePart = (amount: bigint, unit: string) => amount ? `${sign}${amount}${unit}` : ''
  const date = part(Math.trunc(months / 12), 'Y') + part(months % 12, 'M') + part(days, 'D')
  const time = timePart(seconds / 3600n, 'H') + timePart(seconds / 60n % 60n, 'M')
    + (fraction ? `${sign}${seconds % 60n}.${fraction}S` : timePart(seconds % 60n, 'S'))
  return date || time ? `P${date}${time && `T${time}`}` : 'PT0S'
}

// Whether a column holds DuckDB's BIGNUM (VARINT), which DuckDB hands over as its own bytes under
// Arrow's opaque extension type, named in the field's metadata
function isBignum(field: Field): boolean {
  if (field.metadata.get('ARROW:extension:name') !== 'arrow.opaque')
    return false
  try {
    const { type_name, vendor_name } = JSON.parse(field.metadata.get('ARROW:extension:metadata') ?? '')
    return type_name === 'bignum' && vendor_name === 'DuckDB'
  }
  catch {
    return false
  }
}

// A BIGNUM from DuckDB's bytes, as integerValue writes an integer: a three-byte header whose top bit
// is set for a number of no sign, then the magnitude's bytes, big-endian. A negative one has all its
// bytes inverted
function bignumValue(bytes: Uint8Array): number | string {
  const negative = (bytes[0]! & 0x80) === 0
  // read at once from its hex digits, where a shift a byte would copy the growing number each time
  const hex = Array.from(bytes.subarray(3), byte => (negative ? ~byte & 0xFF : byte).toString(16).padStart(2, '0'))
  const magnitude = BigInt(`0x${hex.join('')}`)
  return integerValue(negative ? -magnitude : magnitude)
}

// A decimal, which Arrow gives as its unscaled integer (a DecimalBigNum, whose text is that integer's
// digits): one of no scale as integerValue writes it, and one with a scale as the double nearest it,
// as the REST API's values are doubles
function decimalValue(value: object, scale: number): number | string {
  const unscaled = BigInt(String(value))
  if (scale === 0)
    return integerValue(unscaled)
  const sign = unscaled < 0n ? '-' : ''
  const digits = (unscaled < 0n ? -unscaled : unscaled).toString().padStart(scale + 1, '0')
  return Number(`${sign}${digits.slice(0, -scale)}.${digits.slice(-scale)}`)
}

// A value Arrow's getter gives exactly, made plain by its type. A BLOB's bytes become the list of them,
// and a NaN or an infinity null: the REST API answers none, JSON cannot write one, and a CSV download
// wrote it as text where the JSON download wrote null (GH-2111)
function leafValue(value: unknown, type: DataType): unknown {
  if (value === null || value === undefined || (typeof value === 'number' && !Number.isFinite(value)))
    return null
  switch (type.typeId) {
    case Type.Decimal:
      return decimalValue(value as object, (type as Decimal).scale)
    case Type.Date:
      // whole milliseconds since the epoch
      return timestampValue(BigInt(value as number) * 1000n)
    case Type.Time:
      return timeValue(value as number | bigint, (type as Time).unit)
  }
  // a 64-bit integer comes as a BigInt, which JSON cannot write
  if (typeof value === 'bigint')
    return integerValue(value)
  if (ArrayBuffer.isView(value))
    return Array.from(value as unknown as ArrayLike<unknown>)
  return value
}

// Where each row of a list, a fixed-size list or a map finds its values in its child's column, counted
// across all chunks, or null for a missing row
function childRanges(vector: Vector): ([number, number] | null)[] {
  const listSize = vector.type.typeId === Type.FixedSizeList ? (vector.type as FixedSizeList).listSize : 0
  const ranges: ([number, number] | null)[] = []
  let base = 0
  for (const data of vector.data) {
    const offsets = data.valueOffsets as Int32Array | undefined
    for (let index = 0; index < data.length; index++) {
      if (!data.getValid(index))
        ranges.push(null)
      else if (offsets)
        ranges.push([base + offsets[index]!, base + offsets[index + 1]!])
      else
        ranges.push([base + index * listSize, base + (index + 1) * listSize])
    }
    base += data.children[0]!.length
  }
  return ranges
}

/**
 * The plain values of a column, by its type. A nested column is made plain from its children's
 * columns, so a value inside a list, a struct or a map is made plain as it would be on its own. A
 * timestamp is read from its column's 64-bit integers: Arrow's getter gives it as a double of
 * milliseconds, which holds the microseconds only near 1970.
 */
function plainColumn(vector: Vector, field: Field): unknown[] {
  const type = vector.type
  if (type.typeId === Type.Binary && isBignum(field))
    return Array.from(vector, value => value === null ? null : bignumValue(value as Uint8Array))
  switch (type.typeId) {
    case Type.Timestamp: {
      const perSecond = TICKS_PER_SECOND[(type as Timestamp).unit]
      return vector.data.flatMap(data => Array.from({ length: data.length }, (_, index) => {
        const ticks = (data.values as BigInt64Array)[index]!
        // an infinite nanosecond timestamp falls within what a Date holds, so it is told by its ticks
        if (!data.getValid(index) || ticks === INFINITE_TICKS || ticks === -INFINITE_TICKS)
          return null
        return timestampValue(floorDiv(ticks * 1_000_000n, perSecond))
      }))
    }
    case Type.Struct: {
      // by position, as a field may be named anything, `toJSON` included
      const fields = (type as Struct).children
      const columns = fields.map((child, index) => plainColumn(vector.getChildAt(index)!, child))
      return Array.from({ length: vector.length }, (_, row) => vector.isValid(row)
        ? Object.fromEntries(fields.map((child, index) => [child.name, columns[index]![row]]))
        : null)
    }
    case Type.List:
    case Type.FixedSizeList: {
      const values = plainColumn(vector.getChildAt(0)!, type.children[0]!)
      return childRanges(vector).map(range => range && values.slice(...range))
    }
    case Type.Map: {
      // an object, the shape DuckDB's to_json gives a map, keyed by the plain key's text. A BIGNUM
      // that is the map's own key or value stays DuckDB's bytes: these two fields lose the extension
      // type it is told by, which a list, a struct or a union inside them keeps
      const entries = vector.getChildAt(0)!
      const [keyField, valueField] = entries.type.children as Field[]
      const keyVector = entries.getChildAt(0)!
      const keys = plainColumn(keyVector, keyField!)
      const values = plainColumn(entries.getChildAt(1)!, valueField!)
      // a float key of NaN or an infinity, which is made null as any value is, by its own name, so
      // that each stays apart (GH-2116); a key is never NULL. Other keys made null, as an infinite
      // date, still collide (GH-2148)
      const floatKeys = keyVector.type.typeId === Type.Float
      const keyText = (key: unknown, at: number) => key === null && floatKeys
        ? String(keyVector.get(at))
        : typeof key === 'string' ? key : JSON.stringify(key)
      return childRanges(vector).map(range => range && Object.fromEntries(keys.slice(...range).map((key, index) =>
        [keyText(key, range[0] + index), values[range[0] + index]])))
    }
    case Type.Interval: {
      // DuckDB's intervals are all MONTH_DAY_NANO, four 32-bit integers a row -- months, days and the
      // nanoseconds' low and high halves -- which Arrow 17's getter misreads as a year-month pair
      return vector.data.flatMap((data) => {
        const values = data.values as Int32Array
        return Array.from({ length: data.length }, (_, index) => {
          if (!data.getValid(index))
            return null
          const [months, days, low, high] = values.subarray(4 * index, 4 * index + 4)
          return intervalValue(months!, days!, BigInt(high!) << 32n | BigInt(low! >>> 0))
        })
      })
    }
    case Type.Union: {
      // DuckDB's unions are sparse: each member a column as long as the union, the row's type id naming
      // the one that holds its value
      const union = type as Union
      const members = union.children.map((member, index) => plainColumn(vector.getChildAt(index)!, member))
      return vector.data.flatMap(data => Array.from(data.typeIds as Int8Array))
        .map((typeId, row) => members[union.typeIdToChildIndex[typeId]!]![row])
    }
  }
  return Array.from(vector, value => leafValue(value, type))
}

/**
 * Turn a query result into the rows the table, the chart and the downloads read, each value made
 * plain by its column's type (GH-2068, GH-2071): a BIGINT, a BIGNUM or a decimal as a number (an
 * integer type or a decimal of no scale past 2^53 as its digits), a timestamp or a date as ISO text,
 * a time of day as its text, an interval as an ISO 8601 duration, a list as an array and a struct or
 * a map as an object, at any depth, and a NaN or an infinity as null (GH-2111). Arrow's own
 * `toJSON()` left BigInts, milliseconds since the epoch, unscaled decimals, DuckDB's bytes of a
 * BIGNUM (GH-2102) and its own rows and vectors.
 *
 * A name given to two columns holds the last one's value, as `toJSON()` keeps.
 *
 * @param table - The result, as DuckDB answers a query
 * @returns One object per row, keyed by column name
 */
export function plainRows(table: Table): Record<string, unknown>[] {
  // DuckDB answers a result of no rows with an empty batch whose nested columns have no children to read
  if (table.numRows === 0)
    return []
  const columns = table.schema.fields.map((field, index) => [field.name, plainColumn(table.getChildAt(index)!, field)] as const)
  return Array.from({ length: table.numRows }, (_, row) =>
    Object.fromEntries(columns.map(([name, values]) => [name, values[row]])))
}
