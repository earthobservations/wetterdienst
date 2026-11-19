import { describe, expect, it } from 'vitest'
import { stripeYears } from '../../app/utils/stripes'
import { stripesCsv, stripesTableColumns, stripesTableYears } from '../../app/utils/stripes-table'

// The table of the stripes and the CSV it is saved as (GH-4233)

function t(key: string) {
  return {
    'stripes.table.year': 'Year',
    'stripes.table.value': 'Value',
    'stripes.table.anomaly': 'Anomaly',
    'stripes.table.class': 'Class',
  }[key] ?? key
}
const className = (stripeClass: string) => ({ veryLow: 'Much cooler', low: 'Cooler', middle: 'Middle', high: 'Warmer', veryHigh: 'Much warmer' }[stripeClass] ?? stripeClass)

// out of order, with a year that has no value among them
const YEARS = stripeYears([
  { timestamp: '2020-01-01T00:00:00+00:00', value: 10.456, anomaly: 0.9206, stripe_class: 12 },
  { timestamp: '2018-01-01T00:00:00+00:00', value: 8, anomaly: -1.001, stripe_class: 4 },
  { timestamp: '2019-01-01T00:00:00+00:00', value: null, anomaly: null, stripe_class: null },
  { timestamp: '2017-01-01T00:00:00+00:00', value: 9.2, anomaly: -0.0004, stripe_class: 8 },
])

describe('the columns of the table', () => {
  it('put the unit in the header of the two numbers', () => {
    expect(stripesTableColumns('°C', t)).toEqual(['Year', 'Value (°C)', 'Anomaly (°C)', 'Class'])
  })

  it('leave it out where the answer names none', () => {
    expect(stripesTableColumns('', t)).toEqual(['Year', 'Value', 'Anomaly', 'Class'])
  })
})

describe('the years of the table', () => {
  it('are in the order of the calendar, whatever order the answer came in', () => {
    expect(stripesTableYears(YEARS).map(year => year.year)).toEqual([2017, 2018, 2020])
  })

  it('leave the years they are given as they are', () => {
    const before = YEARS.map(year => year.year)
    stripesTableYears(YEARS)
    expect(YEARS.map(year => year.year)).toEqual(before)
  })
})

describe('the CSV', () => {
  const columns = stripesTableColumns('°C', t)

  it('has the comments first, each after a #, then the header and a row for each year, in order', () => {
    const csv = stripesCsv(columns, YEARS, className, ['Climate stripes for Berlin', 'Colours: relative to 1971–2000', 'Source: DWD', 'Licence: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)'])
    expect(csv).toBe(`\uFEFF${[
      '# Climate stripes for Berlin',
      '# Colours: relative to 1971–2000',
      '# Source: DWD',
      '# Licence: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)',
      'Year,Value (°C),Anomaly (°C),Class',
      '2017,9.20,0.00,Middle',
      '2018,8.00,-1.00,Cooler',
      '2020,10.46,0.92,Warmer',
      '',
    ].join('\n')}`)
  })

  it('starts with a UTF-8 byte order mark, which Excel needs to read °C, – and the names of the classes (Kühler) as UTF-8', () => {
    const csv = stripesCsv(columns, YEARS, stripeClass => stripeClass === 'low' ? 'Kühler' : className(stripeClass), ['Quelle: Deutscher Wetterdienst'])
    expect(csv.charCodeAt(0)).toBe(0xFEFF)
    // once, and in front of the first comment
    expect(csv.indexOf('\uFEFF', 1)).toBe(-1)
    expect(csv.slice(1).startsWith('# Quelle')).toBe(true)
    // encoded, the three bytes of the mark come first, and the rest is UTF-8
    const bytes = new TextEncoder().encode(csv)
    expect(Array.from(bytes.slice(0, 3))).toEqual([0xEF, 0xBB, 0xBF])
    expect(new TextDecoder('utf-8', { ignoreBOM: true }).decode(bytes)).toBe(csv)
    expect(bytes.length).toBeGreaterThan(csv.length)
  })

  it('has the mark before the header where there are no comments', () => {
    expect(stripesCsv(columns, YEARS, className, []).startsWith('\uFEFFYear,Value (°C),Anomaly (°C),Class\n')).toBe(true)
  })

  it('writes the numbers plain, whatever the language: a point, two decimals, no plus, and no minus for a zero', () => {
    const rows = stripesCsv(columns, YEARS, className, []).trimEnd().split('\n').slice(1)
    expect(rows.every(row => /^\d{4},\d+\.\d{2},-?\d+\.\d{2},/.test(row))).toBe(true)
    expect(rows[0]).toBe('2017,9.20,0.00,Middle')
  })

  it('writes the class in the words the table has, and quotes what has a comma in it', () => {
    const csv = stripesCsv(columns, YEARS, stripeClass => stripeClass === 'middle' ? 'Mid, ish' : className(stripeClass), [])
    expect(csv).toContain('2017,9.20,0.00,"Mid, ish"')
  })

  it('keeps each comment to one line, and drops an empty one (a licence the answer does not have)', () => {
    const csv = stripesCsv(columns, YEARS, className, ['Two\nlines  of text', '', '   ']).replace(/^\uFEFF/, '')
    expect(csv.split('\n').filter(line => line.startsWith('#'))).toEqual(['# Two lines of text'])
  })

  it('is empty where there are no years', () => {
    expect(stripesCsv(columns, [], className, ['A comment'])).toBe('')
  })
})
