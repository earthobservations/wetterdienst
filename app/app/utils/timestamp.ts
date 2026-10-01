// A timestamp's text, as the REST API and a query's timestamps and dates write it: a calendar date,
// its year of four digits or six signed; then, or not, a time of day after a 'T' or a space, to the
// minute, the second or a fraction of it; then, after a time, a 'Z' or an offset of hours, and of
// minutes and seconds or not, as DuckDB writes a TIMESTAMPTZ cast to text, `2020-01-01 00:00:00+00`,
// or one in a zone's local mean time, `1880-01-01 00:00:00+00:53:28`; its parts all after a colon,
// or none
const ISO_TIMESTAMP = /^(?<year>\d{4}|[+-]\d{6})-(?<month>\d{2})-(?<day>\d{2})(?:[T ](?<hour>\d{2}):(?<minute>\d{2})(?::(?<second>\d{2})(?:\.(?<fraction>\d+))?)?(?:Z|(?<sign>[+-])(?<offsetHour>\d{2})(?:(?<colon>:?)(?<offsetMinute>\d{2})(?:\k<colon>(?<offsetSecond>\d{2}))?)?)?)?$/

/**
 * The moment a timestamp's text names, read as UTC where it gives no offset, or null for text that
 * is no such timestamp or names a date or time that does not exist, as `2020-02-30` or `24:00`.
 *
 * Read here rather than by `new Date(text)`, which reads a time without an offset as the browser's
 * local time, while a date alone and the rows the app fetches are UTC; which reads a space before the
 * time, or an offset of hours alone, as each browser will; and which rolls a day past the month's
 * end over into the next month.
 */
export function timestampDate(text: string): Date | null {
  const parts = ISO_TIMESTAMP.exec(text)?.groups
  if (!parts)
    return null
  // a part as a number, 0 where it is not given
  const part = (name: string) => Number(parts[name] ?? 0)
  const [year, month, day, hour, minute, second] = [part('year'), part('month'), part('day'), part('hour'), part('minute'), part('second')]
  const [offsetHour, offsetMinute, offsetSecond] = [part('offsetHour'), part('offsetMinute'), part('offsetSecond')]
  if (hour > 23 || minute > 59 || second > 59 || offsetHour > 23 || offsetMinute > 59 || offsetSecond > 59)
    return null
  const date = new Date(0)
  date.setUTCFullYear(year, month - 1, day)
  // a month or day out of range rolls the date over, onto another day than the text names
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day)
    return null
  const offset = (parts.sign === '-' ? -1 : 1) * (offsetHour * 3600 + offsetMinute * 60 + offsetSecond)
  date.setUTCHours(hour, minute, second - offset, Number((parts.fraction ?? '').slice(0, 3).padEnd(3, '0')))
  return Number.isNaN(date.getTime()) ? null : date
}
