import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { timestampDate } from '../../app/utils/timestamp'

describe('timestampDate', () => {
  // a browser an hour east of UTC, where `new Date(text)` reads a time without an offset an hour early
  let zone: string | undefined
  beforeAll(() => {
    zone = process.env.TZ
    process.env.TZ = 'Europe/Berlin'
    // the zone taken up, else the tests pass in UTC against `new Date(text)` as well
    expect(new Date(2020, 0, 1).getTimezoneOffset()).toBe(-60)
  })
  afterAll(() => {
    if (zone === undefined)
      delete process.env.TZ
    else
      process.env.TZ = zone
  })

  it.each([
    // `strftime(timestamp::TIMESTAMP, '%Y-%m-%d %H:%M')`
    ['2020-01-01 00:00', '2020-01-01T00:00:00.000Z'],
    ['2020-01-01T00:00', '2020-01-01T00:00:00.000Z'],
    ['2020-01-01 00:00:00', '2020-01-01T00:00:00.000Z'],
    ['2020-01-01', '2020-01-01T00:00:00.000Z'],
    // the REST API's, and a query's TIMESTAMP as plainRows writes it, to the microsecond
    ['2020-01-01T00:00:00.123456+00:00', '2020-01-01T00:00:00.123Z'],
    ['2020-01-01 00:00:00.5', '2020-01-01T00:00:00.500Z'],
    ['2020-01-01T00:00:00Z', '2020-01-01T00:00:00.000Z'],
    // `CAST(timestamp::TIMESTAMPTZ AS VARCHAR)`: an offset of hours alone, or with seconds
    ['2020-01-01 00:00:00+00', '2020-01-01T00:00:00.000Z'],
    ['2020-01-01 01:00:00+01', '2020-01-01T00:00:00.000Z'],
    ['2019-12-31T18:30:00-05:30', '2020-01-01T00:00:00.000Z'],
    ['2019-12-31T18:30:00-0530', '2020-01-01T00:00:00.000Z'],
    ['1880-01-01 00:53:28+00:53:28', '1880-01-01T00:00:00.000Z'],
    // a year of six digits, as toISOString writes one past 9999 or before 0, and one before 100
    ['+010000-01-01T00:00:00.000Z', '+010000-01-01T00:00:00.000Z'],
    ['-000001-01-01', '-000001-01-01T00:00:00.000Z'],
    ['0050-01-01', '0050-01-01T00:00:00.000Z'],
    ['2020-02-29', '2020-02-29T00:00:00.000Z'],
  ])('reads %s as %s', (text, iso) => {
    expect(timestampDate(text)?.toISOString()).toBe(iso)
  })

  it.each([
    // read by a Date as 2020-03-01, a day past the month's end rolled over
    '2020-02-30',
    '2019-02-29',
    '2020-13-01',
    '2020-00-01',
    '2020-01-00',
    '2020-01-01 24:00',
    '2020-01-01 00:60',
    '2020-01-01 00:00:60',
    '2020-01-01T00:00:00+24:00',
    '2020-01-01T00:00:00+00:60',
    // text before or after the timestamp, an offset without a time, and no timestamp at all
    '2020-01-01 00:00:00 UTC',
    ' 2020-01-01',
    '2020-01-01Z',
    '2020-01-01T',
    '01:00:00.000000',
    '1',
    'n/a',
    '',
    // past the years a Date holds
    '+999999-01-01',
  ])('reads %j as no timestamp', (text) => {
    expect(timestampDate(text)).toBeNull()
  })
})
