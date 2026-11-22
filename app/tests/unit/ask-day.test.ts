import type { Reading } from '../../app/utils/answers'
import { describe, expect, it } from 'vitest'
import {
  DAY_PARAMETERS,
  dayLengthHours,
  FROST_DAY_MIN_BELOW,
  HOT_DAY_MAX_FROM,
  ICE_DAY_MAX_BELOW,
  isMeasure,
  MEASURES,
  measuresWithData,
  RAIN_DRY_BELOW_MM,
  RAIN_VERY_WET_FROM_MM,
  RAIN_WET_FROM_MM,
  rainOnDay,
  rainVerdictOf,
  SNOW_LIES_ABOVE_CM,
  snowOnDay,
  solarDeclination,
  SUMMER_DAY_MAX_FROM,
  SUN_SHARE_DULL_BELOW,
  SUN_SHARE_SUNNY_FROM,
  sunOnDay,
  sunVerdictOf,
  temperatureClasses,
  temperatureOnDay,
  TROPICAL_NIGHT_MIN_FROM,
} from '../../app/utils/day'

// The day question's measures besides the wind (GH-3764, step 2b): each verdict scale at its boundaries, the length of the day against
// printed tables, and which measures a station has a reading of. The answers say nothing the data does not.

const DAY = '2025-12-26'
const stamp = (day: string) => `${day}T00:00:00+00:00`
/** The readings of one parameter on a few days, by day */
function readings(parameter: string, values: Record<string, number | null>): Reading[] {
  return Object.entries(values).map(([day, value]) => ({ parameter, timestamp: stamp(day), value }))
}

describe('the length of the day', () => {
  // Sunrise and sunset of Berlin (52.52 N, 13.405 E) as printed by timeanddate.com, "Sun in Berlin" (read on 22 November 2026): the length
  // of the day from sunrise to sunset, which counts the Sun up from 50 arcminutes under the horizon (refraction and the Sun's radius).
  // The function takes that horizon as an argument, so that the table is a check of the formula; its default is the mathematical horizon.
  const BERLIN = 52.52
  const SUNRISE = -0.833
  const TABLE: Array<[string, string]> = [
    ['2025-06-21', '16:50:03'],
    ['2025-06-01', '16:30:09'],
    ['2025-12-21', '7:39:06'],
    ['2025-12-01', '8:01:19'],
  ]
  const seconds = (text: string) => text.split(':').map(Number).reduce((total, part) => total * 60 + part, 0)

  it.each(TABLE)('is within three minutes of the printed table on %s (%s)', (day, printed) => {
    const computed = dayLengthHours(BERLIN, day, SUNRISE) * 3600
    expect(Math.abs(computed - seconds(printed))).toBeLessThan(180)
  })

  it('is half the day at the equinoxes, at every latitude that has a night, on a mathematical horizon', () => {
    for (const latitude of [0, 30, 47.5, 55, 65])
      expect(dayLengthHours(latitude, '2025-03-20'), String(latitude)).toBeCloseTo(12, 0)
    // the days are 12 hours at the equator all year, and 24 and 0 hours where the Sun does not set or rise
    for (const day of ['2025-01-15', '2025-06-21', '2025-12-21'])
      expect(dayLengthHours(0, day), day).toBeCloseTo(12, 0)
    expect(dayLengthHours(69.65, '2025-06-21')).toBe(24)
    expect(dayLengthHours(69.65, '2025-12-21')).toBe(0)
    expect(dayLengthHours(-69.65, '2025-12-21')).toBe(24)
  })

  it('is longer in the north in summer, shorter in winter, and the same either side of a solstice', () => {
    expect(dayLengthHours(54.4, '2025-06-21')).toBeGreaterThan(dayLengthHours(47.8, '2025-06-21'))
    expect(dayLengthHours(54.4, '2025-12-21')).toBeLessThan(dayLengthHours(47.8, '2025-12-21'))
    expect(dayLengthHours(52.5, '2025-06-11')).toBeCloseTo(dayLengthHours(52.5, '2025-07-01'), 1)
  })

  it('has the Sun\'s declination of WMO-No. 8, Annex 7.F: +23.44 degrees at the June solstice, about 0 at the equinox, -23.44 at the December one', () => {
    const degrees = (day: string) => solarDeclination(day) * 180 / Math.PI
    expect(degrees('2025-06-21')).toBeCloseTo(23.44, 1)
    expect(degrees('2025-12-21')).toBeCloseTo(-23.44, 1)
    expect(Math.abs(degrees('2025-03-20'))).toBeLessThan(0.5)
    // the declination changes by about 0.4 degrees a day at an equinox
    expect(degrees('2025-03-21') - degrees('2025-03-20')).toBeGreaterThan(0.3)
  })
})

describe('the sun', () => {
  it('has its edges where WMO-No. 8 (§8.1.3) has them: below 0.3 cloudy, from 0.3 scattered, from 0.7 fair', () => {
    expect([SUN_SHARE_DULL_BELOW, SUN_SHARE_SUNNY_FROM]).toEqual([0.3, 0.7])
    expect([0, 0.29, 0.2999].map(sunVerdictOf)).toEqual(['dull', 'dull', 'dull'])
    expect([0.3, 0.5, 0.6999].map(sunVerdictOf)).toEqual(['mixed', 'mixed', 'mixed'])
    expect([0.7, 0.9, 1].map(sunVerdictOf)).toEqual(['sunny', 'sunny', 'sunny'])
  })

  it('is the share of the day that was possible at the latitude of the station', () => {
    // 26 December at Kiel-Holtenau (54.38 N): a day of about 7 hours on a flat horizon
    const possible = dayLengthHours(54.38, DAY)
    expect(possible).toBeGreaterThan(6.5)
    expect(possible).toBeLessThan(7.5)
    const answer = sunOnDay(readings(DAY_PARAMETERS.sun, { [DAY]: 3.5 }), DAY, 54.38)!
    expect(answer.possible).toBeCloseTo(possible, 6)
    expect(answer.share).toBeCloseTo(3.5 / possible, 6)
    expect(answer.verdict).toBe('mixed')
    // the same hours of sun are a sunnier day where the possible day is short, and a duller one where it is long
    expect(sunOnDay(readings(DAY_PARAMETERS.sun, { '2025-06-21': 3.5 }), '2025-06-21', 54.38)!.verdict).toBe('dull')
    expect(sunOnDay(readings(DAY_PARAMETERS.sun, { [DAY]: 6.4 }), DAY, 54.38)!.verdict).toBe('sunny')
    expect(sunOnDay(readings(DAY_PARAMETERS.sun, { [DAY]: 0 }), DAY, 54.38)!.verdict).toBe('dull')
  })

  it('is not above 100 % of the day, whatever the recorder says', () => {
    const answer = sunOnDay(readings(DAY_PARAMETERS.sun, { [DAY]: 9 }), DAY, 54.38)!
    expect(answer.share).toBe(1)
    expect(answer.hours).toBe(9)
  })

  it('reads a duration in minutes or seconds as hours', () => {
    expect(sunOnDay(readings(DAY_PARAMETERS.sun, { [DAY]: 210 }), DAY, 54.38, 'min')!.hours).toBe(3.5)
    expect(sunOnDay(readings(DAY_PARAMETERS.sun, { [DAY]: 12600 }), DAY, 54.38, 's')!.hours).toBe(3.5)
  })

  it('has no answer without a reading, or on a day with no sunrise, and draws the days around it', () => {
    expect(sunOnDay(readings(DAY_PARAMETERS.sun, { '2025-12-25': 2 }), DAY, 54.38)).toBeNull()
    expect(sunOnDay(readings(DAY_PARAMETERS.sun, { [DAY]: null }), DAY, 54.38)).toBeNull()
    expect(sunOnDay(readings(DAY_PARAMETERS.sun, { [DAY]: 0 }), DAY, 69.65)).toBeNull()
    const answer = sunOnDay(readings(DAY_PARAMETERS.sun, { '2025-12-25': 1, [DAY]: 2, '2025-12-27': null }), DAY, 54.38)!
    expect(answer.bars.map(bar => [bar.key, bar.value, bar.highlight])).toEqual([['2025-12-25', 1, false], [DAY, 2, true], ['2025-12-27', null, false]])
  })
})

describe('the rain', () => {
  it('has its edges where WMO has them: 0.1 mm (WMO-No. 8, §6.1.2), 1 mm and 10 mm (WMO-No. 1203, Table 1)', () => {
    expect([RAIN_DRY_BELOW_MM, RAIN_WET_FROM_MM, RAIN_VERY_WET_FROM_MM]).toEqual([0.1, 1, 10])
    expect([0, 0.05, 0.09].map(rainVerdictOf)).toEqual(['dry', 'dry', 'dry'])
    expect([0.1, 0.5, 0.9].map(rainVerdictOf)).toEqual(['light', 'light', 'light'])
    expect([1, 4.9, 9.9].map(rainVerdictOf)).toEqual(['wet', 'wet', 'wet'])
    expect([10, 25, 80].map(rainVerdictOf)).toEqual(['veryWet', 'veryWet', 'veryWet'])
  })

  it('judges in millimetres whatever unit the answer is in, and reports it in the unit it came in', () => {
    const answer = rainOnDay(readings(DAY_PARAMETERS.rain, { [DAY]: 1 }), DAY, 'l/m²')!
    expect(answer.verdict).toBe('wet')
    expect(answer.unit).toBe('l/m²')
    expect(rainOnDay(readings(DAY_PARAMETERS.rain, { [DAY]: 0 }), DAY)!.verdict).toBe('dry')
  })

  it('has no answer without a reading', () => {
    expect(rainOnDay(readings(DAY_PARAMETERS.rain, { '2025-12-25': 2 }), DAY)).toBeNull()
    expect(rainOnDay(readings(DAY_PARAMETERS.rain, { [DAY]: null }), DAY)).toBeNull()
  })
})

describe('heat and cold', () => {
  it('has the days DWD names: 25 and 30 °C, below 0 °C twice, and a night from 20 °C', () => {
    expect([SUMMER_DAY_MAX_FROM, HOT_DAY_MAX_FROM, ICE_DAY_MAX_BELOW, FROST_DAY_MIN_BELOW, TROPICAL_NIGHT_MIN_FROM]).toEqual([25, 30, 0, 0, 20])
  })

  it('names a day by the class at its boundary, from 25.0 up and from 30.0 up, below 0.0 only', () => {
    // [highest, lowest] -> classes, in the order the day is named by
    const cases: Array<[number, number, string[]]> = [
      [24.9, 12, []],
      [25, 12, ['summer']],
      [29.9, 12, ['summer']],
      [30, 12, ['hot', 'summer']],
      [31, 20, ['hot', 'summer', 'tropical']],
      [24, 20, ['tropical']],
      [24, 19.9, []],
      [0, -3, ['frost']],
      [-0.1, -3, ['ice', 'frost']],
      [5, -0.1, ['frost']],
      [5, 0, []],
    ]
    for (const [max, min, classes] of cases)
      expect(temperatureClasses(max, min), `${max}/${min}`).toEqual(classes)
  })

  const both = (max: number | null, min: number | null) => [...readings(DAY_PARAMETERS.tmax, { [DAY]: max }), ...readings(DAY_PARAMETERS.tmin, { [DAY]: min })]

  it('says the first class a day is, and lists the others', () => {
    const hot = temperatureOnDay(both(33.1, 21), DAY)!
    expect(hot.verdict).toBe('hot')
    expect(hot.classes).toEqual(['hot', 'summer', 'tropical'])
    expect(temperatureOnDay(both(26, 14), DAY)!.verdict).toBe('summer')
    expect(temperatureOnDay(both(-2, -8), DAY)!.verdict).toBe('ice')
    expect(temperatureOnDay(both(-2, -8), DAY)!.classes).toEqual(['ice', 'frost'])
    expect(temperatureOnDay(both(4, -1), DAY)!.verdict).toBe('frost')
    expect(temperatureOnDay(both(12, 4), DAY)!.verdict).toBe('ordinary')
    expect(temperatureOnDay(both(12, 4), DAY)!.classes).toEqual([])
  })

  it('judges in °C whatever unit the answer is in', () => {
    // 77 °F is 25 °C, 32 °F is 0 °C: a summer day, and a day that is not a frost day
    expect(temperatureOnDay(both(77, 50), DAY, '°F')!.verdict).toBe('summer')
    expect(temperatureOnDay(both(50, 32), DAY, '°F')!.verdict).toBe('ordinary')
    expect(temperatureOnDay(both(50, 31.9), DAY, '°F')!.verdict).toBe('frost')
    expect(temperatureOnDay(both(298.15, 285), DAY, 'K')!.verdict).toBe('summer')
  })

  it('draws the lowest temperature on a frost day and the highest on any other', () => {
    const rows = [...readings(DAY_PARAMETERS.tmax, { '2025-12-25': 3, [DAY]: 4 }), ...readings(DAY_PARAMETERS.tmin, { '2025-12-25': -2, [DAY]: -1 })]
    expect(temperatureOnDay(rows, DAY)!.barsAre).toBe('min')
    expect(temperatureOnDay(rows, DAY)!.bars.map(bar => bar.value)).toEqual([-2, -1])
    expect(temperatureOnDay(both(-3, -9), DAY)!.barsAre).toBe('max')
    expect(temperatureOnDay(both(20, 10), DAY)!.barsAre).toBe('max')
  })

  it('has no answer without both readings: a frost day cannot be ruled out without the lowest', () => {
    expect(temperatureOnDay(both(20, null), DAY)).toBeNull()
    expect(temperatureOnDay(both(null, 10), DAY)).toBeNull()
    expect(temperatureOnDay(readings(DAY_PARAMETERS.tmax, { [DAY]: 20 }), DAY)).toBeNull()
  })
})

describe('the snow', () => {
  it('lies from the first centimetre: above 0 cm (WMO-No. 1203, Table 1)', () => {
    expect(SNOW_LIES_ABOVE_CM).toBe(0)
    expect(snowOnDay(readings(DAY_PARAMETERS.snow, { [DAY]: 0 }), DAY)!.verdict).toBe('none')
    expect(snowOnDay(readings(DAY_PARAMETERS.snow, { [DAY]: 1 }), DAY)!.verdict).toBe('cover')
    expect(snowOnDay(readings(DAY_PARAMETERS.snow, { [DAY]: 0.4 }), DAY)!.verdict).toBe('cover')
    expect(snowOnDay(readings(DAY_PARAMETERS.snow, { [DAY]: 35 }), DAY)!.verdict).toBe('cover')
  })

  it('adds the fresh snow where the station reports it, and says none where it does not', () => {
    const rows = [...readings(DAY_PARAMETERS.snow, { [DAY]: 12 }), ...readings(DAY_PARAMETERS.newSnow, { [DAY]: 4 })]
    expect(snowOnDay(rows, DAY)!.fresh).toBe(4)
    expect(snowOnDay(readings(DAY_PARAMETERS.snow, { [DAY]: 12 }), DAY)!.fresh).toBeNull()
  })

  it('judges in centimetres whatever unit the answer is in', () => {
    // 10 mm of snow is 1 cm
    expect(snowOnDay(readings(DAY_PARAMETERS.snow, { [DAY]: 10 }), DAY, 'mm')!.verdict).toBe('cover')
    expect(snowOnDay(readings(DAY_PARAMETERS.snow, { [DAY]: 0.01 }), DAY, 'm')!.verdict).toBe('cover')
    expect(snowOnDay(readings(DAY_PARAMETERS.snow, { [DAY]: 0 }), DAY, 'm')!.verdict).toBe('none')
  })

  it('has no answer without a depth: fresh snow alone is no cover', () => {
    expect(snowOnDay(readings(DAY_PARAMETERS.newSnow, { [DAY]: 4 }), DAY)).toBeNull()
    expect(snowOnDay(readings(DAY_PARAMETERS.snow, { [DAY]: null }), DAY)).toBeNull()
  })
})

describe('which measures a station has a reading of', () => {
  const all: Reading[] = [
    ...readings('wind_gust_max', { [DAY]: 8 }),
    ...readings(DAY_PARAMETERS.sun, { [DAY]: 2 }),
    ...readings(DAY_PARAMETERS.rain, { [DAY]: 0 }),
    ...readings(DAY_PARAMETERS.tmax, { [DAY]: 4 }),
    ...readings(DAY_PARAMETERS.tmin, { [DAY]: 1 }),
    ...readings(DAY_PARAMETERS.snow, { [DAY]: 0 }),
  ]

  it('are the five, in the order of the control, where every parameter is there', () => {
    expect(MEASURES).toEqual(['wind', 'sun', 'rain', 'temperature', 'snow'])
    expect(measuresWithData(all, DAY)).toEqual([...MEASURES])
  })

  it('leave out a measure whose reading is missing for the day, null or not there', () => {
    expect(measuresWithData(all.filter(row => row.parameter !== DAY_PARAMETERS.snow), DAY)).toEqual(['wind', 'sun', 'rain', 'temperature'])
    expect(measuresWithData(all.map(row => row.parameter === DAY_PARAMETERS.sun ? { ...row, value: null } : row), DAY)).toEqual(['wind', 'rain', 'temperature', 'snow'])
    // the temperature needs both, the wind either of two
    expect(measuresWithData(all.filter(row => row.parameter !== DAY_PARAMETERS.tmin), DAY)).toEqual(['wind', 'sun', 'rain', 'snow'])
    expect(measuresWithData([...all, ...readings('wind_speed_mean', { [DAY]: 3 })].filter(row => row.parameter !== 'wind_gust_max'), DAY)).toContain('wind')
  })

  it('look at the day asked about, and at no other', () => {
    expect(measuresWithData(all, '2025-12-27')).toEqual([])
  })

  it('know a measure by its name in the link', () => {
    for (const measure of MEASURES)
      expect(isMeasure(measure)).toBe(true)
    for (const other of ['', 'Wind', 'heat', undefined, null, ['sun']])
      expect(isMeasure(other)).toBe(false)
  })
})
