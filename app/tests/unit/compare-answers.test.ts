import { DateTime } from 'luxon'
import { describe, expect, it } from 'vitest'
import { monthRainWindow } from '../../app/utils/ask/chips/monthrain'
import {
  MONTH_MIN_DAYS,
  monthRain,
  monthRainVerdict,
  NEARBY_MIN_DAYS,
  NEARBY_WINDOW_DAYS,
  nearbyDaysWithBoth,
  nearbyVerdict,
  nearbyWarmer,
  nearbyWindow,
} from '../../app/utils/compare-answers'

// The two comparisons of "Ask the weather" (GH-4296), by hand: the readings are small and the answers are worked out here in the comment.

const rain = (date: string, value: number | null) => ({ parameter: 'precipitation_amount', timestamp: `${date}T00:00:00+00:00`, value })
const temperature = (station: string, date: string, value: number | null) => ({ station_id: station, parameter: 'temperature_air_mean_2m', timestamp: `${date}T00:00:00+00:00`, value })
const days = (year: number, month: number, count: number, value: number) => Array.from({ length: count }, (_, index) => rain(`${year}-${String(month).padStart(2, '0')}-${String(index + 1).padStart(2, '0')}`, value))

describe('was this month wetter than the same month last year', () => {
  // 22 November 2026: the running month has readings for 1 to 21 November
  const NOW = DateTime.fromISO('2026-11-22T10:00:00', { zone: 'Europe/Berlin' })

  it('adds up the same days of the month in both years, 21 days of 2 mm against 21 days of 1 mm', () => {
    const answer = monthRain([...days(2026, 11, 21, 2), ...days(2025, 11, 30, 1)], NOW)!
    // 21 paired days: 42 mm this year, 21 mm last year, 21 mm more
    expect(answer).toMatchObject({ month: '2026-11', lastMonth: '2025-11', days: 21, sum: 42, lastSum: 21, difference: 21, verdict: 'wetter', fallback: false, unit: 'mm' })
    expect(answer.bars).toEqual([
      { key: '2025-11', label: '2025-11', value: 21 },
      { key: '2026-11', label: '2026-11', value: 42, highlight: true },
    ])
  })

  it('is drier where the sum is less', () => {
    const answer = monthRain([...days(2026, 11, 21, 0.5), ...days(2025, 11, 30, 2)], NOW)!
    expect(answer).toMatchObject({ sum: 10.5, lastSum: 42, difference: -31.5, verdict: 'drier' })
  })

  it('leaves out a day that one year lacks, and a day with no reading is never a dry day', () => {
    const this_ = days(2026, 11, 21, 1).filter((_, index) => index !== 2 && index !== 5)
    const last = days(2025, 11, 30, 1).map((reading, index) => index === 9 ? rain(reading.timestamp.slice(0, 10), null) : reading)
    // 21 days, less the 3rd and 6th of this year and the 10th of last year
    expect(monthRain([...this_, ...last], NOW)).toMatchObject({ days: 18, sum: 18, lastSum: 18 })
  })

  it('takes the last complete month where the running one has fewer than a week of days', () => {
    const early = DateTime.fromISO('2026-11-05T10:00:00', { zone: 'Europe/Berlin' })
    // 4 days of November (the 1st to the 4th) and the whole of October, in both years
    const readings = [...days(2026, 11, 4, 3), ...days(2025, 11, 30, 3), ...days(2026, 10, 31, 2), ...days(2025, 10, 31, 1)]
    const answer = monthRain(readings, early)!
    expect(answer).toMatchObject({ month: '2026-10', lastMonth: '2025-10', days: 31, sum: 62, lastSum: 31, fallback: true, runningDays: 4 })
    expect(MONTH_MIN_DAYS).toBe(7)
  })

  it('has no answer where even that has too few days', () => {
    expect(monthRain([...days(2026, 11, 3, 1), ...days(2025, 11, 3, 1)], NOW)).toBeNull()
    expect(monthRain([], NOW)).toBeNull()
  })

  it('pairs only the days both Februaries have: the 29th has no partner', () => {
    const leap = DateTime.fromISO('2028-03-03T10:00:00', { zone: 'Europe/Berlin' })
    const answer = monthRain([...days(2028, 2, 29, 1), ...days(2027, 2, 28, 1)], leap)!
    expect(answer).toMatchObject({ month: '2028-02', days: 28, sum: 28, lastSum: 28, fallback: true })
  })

  it('judges "about as wet" within a millimetre or a tenth of the larger sum, in millimetres whatever the unit', () => {
    expect(monthRainVerdict(10, 9.5)).toBe('similar')
    expect(monthRainVerdict(10.9, 10)).toBe('similar')
    // 100 mm and 109 mm: within a tenth of the larger
    expect(monthRainVerdict(109, 100)).toBe('similar')
    expect(monthRainVerdict(111.5, 100)).toBe('wetter')
    expect(monthRainVerdict(80, 100)).toBe('drier')
    // a tenth of a millimetre: not a verdict, a trace
    expect(monthRainVerdict(0.4, 0)).toBe('similar')
    // the sums in litres per square metre are the same numbers in the answer's own unit
    expect(monthRain([...days(2026, 11, 21, 2), ...days(2025, 11, 30, 1)], NOW, 'l/m²')!.verdict).toBe('wetter')
  })

  it('asks for the two months it may be about, to yesterday', () => {
    expect(monthRainWindow(NOW)).toEqual({ from: '2025-10-01', to: '2026-11-21' })
    expect(monthRainWindow(DateTime.fromISO('2027-01-03T10:00:00', { zone: 'Europe/Berlin' }))).toEqual({ from: '2025-12-01', to: '2027-01-02' })
  })
})

describe('is it warmer here than at a station nearby', () => {
  const NOW = DateTime.fromISO('2026-11-22T10:00:00', { zone: 'Europe/Berlin' })
  const { from, to } = nearbyWindow(NOW)
  const allDays = Array.from({ length: NEARBY_WINDOW_DAYS }, (_, index) => DateTime.fromISO(from, { zone: 'utc' }).plus({ days: index }).toISODate()!)

  it('takes the thirty days up to yesterday', () => {
    expect([from, to]).toEqual(['2026-10-23', '2026-11-21'])
    expect(allDays).toHaveLength(30)
    expect(allDays.at(-1)).toBe(to)
  })

  it('is the mean over the days both have, here minus there: 2 °C against 1 °C is one degree warmer', () => {
    const readings = allDays.flatMap(date => [temperature('here', date, 2), temperature('there', date, 1)])
    const answer = nearbyWarmer(readings, 'here', 'there', NOW)!
    expect(answer).toMatchObject({ verdict: 'warmer', days: 30, here: 2, there: 1, difference: 1, unit: '°C', from, to })
    expect(answer.bars).toHaveLength(30)
    expect(answer.bars[0]).toEqual({ key: from, label: from, value: 1 })
  })

  it('is cooler where the other is warmer, and about the same within half a degree either way', () => {
    const at = (here: number, there: number) => nearbyWarmer(allDays.flatMap(date => [temperature('here', date, here), temperature('there', date, there)]), 'here', 'there', NOW)!
    expect(at(1, 3).verdict).toBe('cooler')
    expect(at(1, 1.4).verdict).toBe('same')
    expect(at(1.5, 1).verdict).toBe('same')
    expect(at(1.6, 1).verdict).toBe('warmer')
    expect(nearbyVerdict(-0.5)).toBe('same')
    expect(nearbyVerdict(0.51)).toBe('warmer')
  })

  it('averages only the days both have: a day one station lacks is left out of both means', () => {
    // the other station has no value on ten days, which are exactly the days here is 10 degrees warmer
    const readings = allDays.flatMap((date, index) => index < 10
      ? [temperature('here', date, 12)]
      : [temperature('here', date, 2), temperature('there', date, 1)])
    const answer = nearbyWarmer(readings, 'here', 'there', NOW)!
    expect(answer).toMatchObject({ days: 20, here: 2, there: 1, difference: 1 })
    expect(answer.bars.slice(0, 10).every(bar => bar.value === null)).toBe(true)
  })

  it('has no answer with fewer than two thirds of the days', () => {
    const readings = allDays.slice(0, NEARBY_MIN_DAYS - 1).flatMap(date => [temperature('here', date, 2), temperature('there', date, 1)])
    expect(nearbyWarmer(readings, 'here', 'there', NOW)).toBeNull()
    expect(nearbyDaysWithBoth(readings, 'here', 'there', NOW)).toBe(NEARBY_MIN_DAYS - 1)
    // a day outside the window is no day of it
    expect(nearbyDaysWithBoth([temperature('here', '2026-01-01', 1), temperature('there', '2026-01-01', 1)], 'here', 'there', NOW)).toBe(0)
  })

  it('judges in degrees Celsius and writes the difference in the degrees of the answer\'s unit: 1 K is 1.8 °F', () => {
    // 35.6 °F is 2 °C and 33.8 °F is 1 °C: a degree warmer, which is 1.8 °F
    const readings = allDays.flatMap(date => [temperature('here', date, 35.6), temperature('there', date, 33.8)])
    expect(nearbyWarmer(readings, 'here', 'there', NOW, '°F')).toMatchObject({ verdict: 'warmer', here: 35.6, there: 33.8, difference: 1.8, unit: '°F' })
  })

  it('ignores the readings of another station', () => {
    const readings = [...allDays.flatMap(date => [temperature('here', date, 2), temperature('there', date, 1)]), ...allDays.map(date => temperature('third', date, 30))]
    expect(nearbyWarmer(readings, 'here', 'there', NOW)!.difference).toBe(1)
  })
})
