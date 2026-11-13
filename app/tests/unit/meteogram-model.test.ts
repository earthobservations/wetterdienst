import type { ModelInput } from '../../app/utils/meteogram-model'
import * as SunCalc from 'suncalc'
import { describe, expect, it } from 'vitest'
import { buildMeteogramModel, dewPointMagnus, precipPhase, readoutValue } from '../../app/utils/meteogram-model'
import { buildSeries } from '../../app/utils/meteogram-series'
import { meteogramUnits } from '../../app/utils/meteogram-units'
import { yrSymbolFor } from '../../app/utils/weather-symbols'
import { FORECAST_UNITS, forecastValues } from '../helpers/meteogram-forecast'

const HOUR = 3_600_000
const t = (key: string, named?: Record<string, unknown>) => key + (named?.unit ? ` ${named.unit}` : '')

function input(overrides: Partial<ModelInput> & { values?: ReturnType<typeof forecastValues>, units?: Record<string, string> } = {}): ModelInput {
  const { values = forecastValues(), units = FORECAST_UNITS, ...rest } = overrides
  return {
    series: buildSeries(values as any),
    panels: { temp: true, wind: true, precip: true, cloud: true, pressure: true },
    horizonHours: null,
    zone: 'Europe/Berlin',
    language: 'en-GB',
    coords: { latitude: 52.5, longitude: 13.4 },
    sun: SunCalc as any,
    units: meteogramUnits(units, t),
    t,
    ...rest,
  }
}
const model = (overrides: Parameters<typeof input>[0] = {}) => buildMeteogramModel(input(overrides))!

describe('what the chart draws', () => {
  it('is none for a forecast with no values', () => {
    expect(buildMeteogramModel(input({ values: [] }))).toBeNull()
  })

  it('has the panels in their order, and the series of each', () => {
    const m = model()
    expect(m.panels).toEqual(['wind', 'precip', 'cloud', 'temp', 'pressure'])
    const ids = (panel: string) => m.series.filter(s => s.panel === panel).map(s => s.id)
    expect(ids('temp')).toEqual(['temp', 'tempMax', 'tempMin', 'dew'])
    expect(ids('wind')).toEqual(['wind', 'gust'])
    expect(ids('precip')).toEqual(['rain', 'mixed', 'snow'])
    expect(ids('cloud')).toEqual(['cloudHigh', 'cloudMid', 'cloudLow', 'cloudTotal'])
    expect(ids('pressure')).toEqual(['pressure'])
  })

  it('leaves out the panel that is off and the panel whose series the forecast lacks', () => {
    expect(model({ panels: { temp: true, wind: false, precip: true, cloud: true, pressure: false } }).panels).toEqual(['precip', 'cloud', 'temp'])
    expect(model({ values: forecastValues({ without: ['pressure_air_sea_level'] }) }).panels).not.toContain('pressure')
  })

  it('uses the forecast\'s own stamps: every hour of the first five days, every third after', () => {
    const m = model()
    const wind = m.series.find(s => s.id === 'wind')!
    expect(wind.data).toHaveLength(121 + 40)
    const gaps = new Set(wind.data.slice(1).map((p, i) => p[0] - wind.data[i]![0]))
    expect(gaps).toEqual(new Set([HOUR, 3 * HOUR]))
    expect(m.stamps).toHaveLength(161)
  })

  it('cuts the forecast at the horizon', () => {
    const m = model({ horizonHours: 24 })
    expect(m.maxTime - m.minTime).toBe(24 * HOUR)
    expect(m.stamps.at(-1)! - m.stamps[0]!).toBe(24 * HOUR)
  })
})

describe('the temperature panel', () => {
  it('holds each maximum and minimum across the hours it covers, as steps that break between windows', () => {
    const m = model()
    const max = m.series.find(s => s.id === 'tempMax')!
    expect(max.kind).toBe('step')
    expect(max.dashed).toBe(true)
    const t0 = Date.UTC(2026, 9, 1)
    // the fixture stamps a maximum at hours 11, 23, ...: each is the value of the 12 hours before its stamp (the first is cut at the chart's start)
    const stamped = (hour: number) => forecastValues().find(v => v.parameter === 'temperature_air_max_2m_last_12h' && v.timestamp === new Date(t0 + hour * HOUR).toISOString().replace('Z', '+00:00'))!.value
    const heldAt = (hour: number) => max.data.filter(p => p[0] === t0 + hour * HOUR).map(p => p[1])
    for (const hour of [0, 3, 9, 11])
      expect(heldAt(hour)).toEqual([stamped(11)])
    for (const hour of [12, 15, 21, 23])
      expect(heldAt(hour)).toEqual([stamped(23)])
  })

  it('draws no band, and calls the curve the temperature, where the maximum and minimum hold no value', () => {
    const m = model({ values: forecastValues({ without: ['temperature_air_max_2m_last_12h', 'temperature_air_min_2m_last_12h'] }) })
    expect(m.series.map(s => s.id)).not.toContain('tempMax')
    expect(m.series.find(s => s.id === 'temp')!.hover).toBe('meteogram.chart.hoverTemperature')
  })

  it('works the dew point out from the humidity where the forecast has none, in the unit of the chart', () => {
    const values = forecastValues({ without: ['temperature_dew_point_2m'] })
    values.push(...values.filter(v => v.parameter === 'temperature_air_2m').map(v => ({ ...v, parameter: 'humidity_relative', value: 0.6 })))
    const m = model({ values, units: { ...FORECAST_UNITS, humidity_relative: '-' } })
    const dew = m.series.find(s => s.id === 'dew')!
    const temp = m.series.find(s => s.id === 'temp')!
    expect(dew).toBeDefined()
    expect(dew.data[10]![1]).toBeCloseTo(dewPointMagnus(temp.data[10]![1]!, 60), 6)
  })

  it('has an axis from a degree under the lowest to three above the highest, holding the freezing point', () => {
    const m = model()
    const [low, high] = m.axes.temp!.range
    const values = m.series.filter(s => s.panel === 'temp').flatMap(s => s.data.map(p => p[1]!).filter(v => v !== null))
    expect(low).toBeCloseTo(Math.min(0, ...values) - 1, 6)
    expect(high).toBeCloseTo(Math.max(...values) + 3, 6)
    expect(m.freezing).toBe(0)
  })

  it('has the range in degrees Fahrenheit, a degree being 1.8 of them, and the freezing point 32', () => {
    const units = { ...FORECAST_UNITS, temperature_air_2m: '°F', temperature_dew_point_2m: '°F', temperature_air_max_2m_last_12h: '°F', temperature_air_min_2m_last_12h: '°F' }
    const values = forecastValues().map(v => v.parameter.startsWith('temperature') ? { ...v, value: v.value === null ? null : v.value * 1.8 + 32 } : v)
    const m = model({ values, units })
    const celsius = model()
    expect(m.freezing).toBe(32)
    expect(m.axes.temp!.range[0]).toBeCloseTo(32 + (celsius.axes.temp!.range[0] - 0) * 1.8, 5)
  })
})

describe('the precipitation panel', () => {
  it('has one bar for each stamp in one of three stacks by the kind of the precipitation, and a null in the others', () => {
    const m = model()
    const [rain, mixed, snow] = ['rain', 'mixed', 'snow'].map(id => m.series.find(s => s.id === id)!)
    expect(rain!.data).toHaveLength(mixed!.data.length)
    for (let i = 0; i < rain!.data.length; i++)
      expect([rain!.data[i]![1], mixed!.data[i]![1], snow!.data[i]![1]].filter(v => v !== null)).toHaveLength(1)
  })

  it('tells snow from rain by the wet bulb: a cold night is snow, a mild day rain', () => {
    expect(precipPhase(-3, 80)).toBe('snow')
    expect(precipPhase(3, 80)).toBe('mixed')
    expect(precipPhase(3.5, 95)).toBe('rain')
    expect(precipPhase(12, 60)).toBe('rain')
    // without a humidity the temperature itself is judged
    expect(precipPhase(0.4, null)).toBe('snow')
    expect(precipPhase(1.9, null)).toBe('mixed')
    expect(precipPhase(2.1, null)).toBe('rain')
  })

  it('draws rain as snow in the fixture\'s cold hours', () => {
    const values = forecastValues().map(v => v.parameter === 'temperature_air_2m' ? { ...v, value: -4 } : v)
    const m = model({ values })
    const snow = m.series.find(s => s.id === 'snow')!
    expect(snow.data.some(p => (p[1] ?? 0) > 0)).toBe(true)
    expect(m.series.find(s => s.id === 'rain')!.data.some(p => (p[1] ?? 0) > 0)).toBe(false)
  })

  it('has the axis from nothing to a seventh above the largest amount, and at least a millimetre', () => {
    const m = model()
    const largest = Math.max(...m.series.filter(s => s.panel === 'precip').flatMap(s => s.data.map(p => p[1] ?? 0)))
    expect(m.axes.precip!.range).toEqual([0, Math.max(1, largest * 1.15)])
    expect(model({ values: forecastValues({ without: ['precipitation_amount_significant_weather_last_1h'] }) }).panels).not.toContain('precip')
  })
})

describe('the wind panel', () => {
  it('has a barb for each stamp, from the direction the wind comes from, with the force in knots of the speed', () => {
    const m = model()
    expect(m.barbs).toHaveLength(161)
    const first = m.barbs[0]!
    const wind = m.series.find(s => s.id === 'wind')!
    expect(first.dir).toBe(200)
    expect(first.speed).toBe(wind.data[0]![1])
    expect(first.knots).toBeCloseTo(wind.data[0]![1]! * 3600 / 1852, 6)
  })

  it('judges the barb in knots whatever unit the speed is in: the same wind in km/h has the same barb', () => {
    const kmh = forecastValues().map(v => v.parameter.startsWith('wind_speed') || v.parameter.startsWith('wind_gust') ? { ...v, value: v.value === null ? null : v.value * 3.6 } : v)
    const a = model()
    const b = model({ values: kmh, units: { ...FORECAST_UNITS, wind_speed: 'km/h', wind_gust_max_last_1h: 'km/h' } })
    expect(b.barbs[5]!.knots).toBeCloseTo(a.barbs[5]!.knots, 6)
    // and the point it stands at is the speed in the unit of the chart
    expect(b.barbs[5]!.speed).toBeCloseTo(a.barbs[5]!.speed * 3.6, 6)
  })

  it('reads a direction in radians as degrees, a nearest stamp and never a mean of two', () => {
    const rad = forecastValues().map(v => v.parameter === 'wind_direction' ? { ...v, value: v.value === null ? null : v.value * Math.PI / 180 } : v)
    const m = model({ values: rad, units: { ...FORECAST_UNITS, wind_direction: 'rad' } })
    expect(m.barbs[0]!.dir).toBeCloseTo(200, 3)
  })

  it('has headroom above the highest wind or gust for the barbs', () => {
    const m = model()
    const top = Math.max(...m.series.filter(s => s.panel === 'wind').flatMap(s => s.data.map(p => p[1]!)))
    expect(m.axes.wind!.range).toEqual([0, top * 1.6])
  })

  it('has no barbs where there is no direction, and still the wind', () => {
    const m = model({ values: forecastValues({ without: ['wind_direction'] }) })
    expect(m.barbs).toEqual([])
    expect(m.series.some(s => s.id === 'wind')).toBe(true)
  })

  it('has a index to thin by that is aligned to the clock of the station and a cadence of the stamps', () => {
    const m = model()
    expect(m.barbs[0]!.cadence).toBe(1)
    expect(m.barbs.at(-2)!.cadence).toBe(3)
    // Berlin is UTC+2 in October: 00:00 UTC is 02:00, local hour 2, index 2 of the day's hourly stamps
    expect(m.barbs[0]!.index).toBe(Math.round((Date.UTC(2026, 9, 1) + 2 * HOUR) / HOUR))
  })
})

describe('the cloud and pressure panels', () => {
  it('has the cloud axis over the whole scale: 0 to 100 % or to 1 or to 8 oktas', () => {
    expect(model().axes.cloud!.range).toEqual([0, 100])
    const fractions = forecastValues().map(v => v.parameter.startsWith('cloud_cover') ? { ...v, value: v.value === null ? null : v.value / 100 } : v)
    expect(model({ values: fractions, units: { ...FORECAST_UNITS, cloud_cover_total: '-', cloud_cover_below_2km: '-', cloud_cover_between_2km_and_7km: '-', cloud_cover_above_7km: '-' } }).axes.cloud!.range).toEqual([0, 1])
  })

  it('has the pressure axis two hectopascals either side of the range', () => {
    const m = model()
    const values = m.series.find(s => s.id === 'pressure')!.data.map(p => p[1]!)
    expect(m.axes.pressure!.range[0]).toBeCloseTo(Math.min(...values) - 2, 6)
    expect(m.axes.pressure!.range[1]).toBeCloseTo(Math.max(...values) + 2, 6)
  })

  it('breaks the title of an axis in two where it does not fit its panel', () => {
    const m = model({ t: (key, named) => key === 'meteogram.chart.axisPrecip' ? `A very long title of the precipitation axis ${named?.unit}` : t(key, named) })
    expect(m.axes.precip!.titleLines).toBe(2)
    expect(m.axes.precip!.title).toContain('\n')
  })
})

describe('the days', () => {
  it('has a day for each calendar day at the station, from local midnight to local midnight', () => {
    const m = model()
    // 00:00 UTC on 1 October is 02:00 in Berlin: the first day starts at local midnight, 22:00 UTC the day before
    expect(m.days[0]!.start).toBe(Date.UTC(2026, 8, 30, 22))
    expect(m.days[0]!.end - m.days[0]!.start).toBe(24 * HOUR)
    expect(m.days).toHaveLength(11)
  })

  it('takes the band of daylight from the sun at the station: Berlin in October', () => {
    const day = model().days[1]!
    const [rise, set] = day.light!
    const hours = (set - rise) / HOUR
    expect(hours).toBeGreaterThan(10)
    expect(hours).toBeLessThan(12)
    expect(rise).toBeGreaterThan(day.start)
    expect(set).toBeLessThan(day.end)
  })

  it('is all light in the polar summer and none in the polar night, where the sun neither rises nor sets', () => {
    const summer = model({ coords: { latitude: 78.2, longitude: 15.6 }, values: forecastValues({ start: '2026-06-21T00:00:00+00:00' }), zone: 'UTC' })
    expect(summer.days[1]!.light).toEqual([summer.days[1]!.start, summer.days[1]!.end])
    const winter = model({ coords: { latitude: 78.2, longitude: 15.6 }, values: forecastValues({ start: '2026-12-21T00:00:00+00:00' }), zone: 'UTC' })
    expect(winter.days[1]!.light).toBeNull()
  })

  it('has four to twenty o\'clock without a station\'s position', () => {
    const day = model({ coords: null }).days[1]!
    expect(day.light).toEqual([day.start + 4 * HOUR, day.start + 20 * HOUR])
  })

  it('fades the band by the cloud at noon', () => {
    const clear = model({ values: forecastValues().map(v => v.parameter === 'cloud_cover_total' ? { ...v, value: 0 } : v) }).days[1]!
    const cloudy = model({ values: forecastValues().map(v => v.parameter === 'cloud_cover_total' ? { ...v, value: 100 } : v) }).days[1]!
    expect(clear.cloud).toBe(0)
    expect(cloudy.cloud).toBe(1)
  })

  it('names each day in the language, and the weekend', () => {
    const days = model().days
    expect(days[0]!.weekday).toBe('Thu')
    expect(days.filter(d => d.weekend).map(d => d.weekday)).toEqual(['Sat', 'Sun', 'Sat', 'Sun'])
    expect(days[0]!.dayMonth).toBe('01/10')
  })
})

describe('the hours', () => {
  it('has one for each hour, on the clock of the station', () => {
    const m = model()
    expect(m.hours).toHaveLength(241)
    // 00:00 UTC is 02:00 in Berlin in October
    expect(m.hours[0]!.hour).toBe(2)
    expect(m.hours.every((h, i) => i === 0 || h.t - m.hours[i - 1]!.t === HOUR)).toBe(true)
  })

  it('is on the half hour clock for a zone that has one: India', () => {
    const m = model({ zone: 'Asia/Kolkata', values: forecastValues({ start: '2026-10-01T00:30:00+00:00' }) })
    // 00:30 UTC is 06:00 in India: the first full hour of the grid is 01:00 UTC, 06:30 there: the clock reads the zone's
    expect(m.hours[0]!.hour).toBe(6)
  })
})

describe('the weather of each hour', () => {
  it('is the phenomenon the code names: the thunderstorm of hour 44', () => {
    const m = model()
    const time = Date.UTC(2026, 9, 1) + 44 * HOUR
    expect(m.weather.get(time)).toBe('thunderstorm')
    expect(m.symbols.find(s => s.t === time)!.kind).toBe('thunderstorm')
  })

  it('is rain where it rains and the code says rain, and the sky by the cloud cover otherwise, not the code\'s state of the sky', () => {
    const m = model()
    const at = (h: number) => m.weather.get(Date.UTC(2026, 9, 1) + h * HOUR)
    expect(at(42)).toBe('rain')
    // hour 0: cloud cover 55 %: partly cloudy, though the code says 0 (clear)
    expect(at(0)).toBe('partlyCloudy')
    // a clear sky where the cloud cover is under 30 %
    const clearHour = m.symbols.find(s => s.sky === 'clear' && s.precipitationMm === 0)
    expect(clearHour?.kind).toBe('clear')
  })

  it('is snow, not rain, for the rain of a cold hour, by the wet bulb', () => {
    const cold = forecastValues().map(v => v.parameter === 'temperature_air_2m' ? { ...v, value: -4 } : v.parameter === 'weather_significant' ? { ...v, value: null } : v)
    const m = model({ values: cold })
    expect(m.weather.get(Date.UTC(2026, 9, 1) + 42 * HOUR)).toBe('snow')
  })

  it('has the night variants after sunset and before sunrise at the station', () => {
    const m = model()
    const noon = m.symbols.find(s => s.t === Date.UTC(2026, 9, 1) + 10 * HOUR)!
    const midnight = m.symbols.find(s => s.t === Date.UTC(2026, 9, 1) + 22 * HOUR)!
    expect(noon.night).toBe(false)
    expect(midnight.night).toBe(true)
  })

  it('has no symbols for a forecast with no weather, cloud or rain to draw them from', () => {
    const m = model({ values: forecastValues({ without: ['weather_significant', 'cloud_cover_total', 'cloud_cover_below_2km', 'cloud_cover_between_2km_and_7km', 'cloud_cover_above_7km', 'precipitation_amount_significant_weather_last_1h'] }) })
    expect(m.hasSymbols).toBe(false)
    expect(m.symbols).toEqual([])
  })

  it('draws the symbol of a kind and a night of the Yr set, and the sky for the kinds Yr has none', () => {
    const base = { night: false, precipitationMm: null, sky: 'clear' as const }
    expect(yrSymbolFor({ ...base, kind: 'thunderstorm' })).toBe('22')
    expect(yrSymbolFor({ ...base, kind: 'clear' })).toBe('01d')
    expect(yrSymbolFor({ ...base, kind: 'clear', night: true })).toBe('01n')
    expect(yrSymbolFor({ ...base, kind: 'cloudy' })).toBe('04')
    expect(yrSymbolFor({ ...base, kind: 'fog' })).toBe('15')
    expect(yrSymbolFor({ ...base, kind: 'rain', precipitationMm: 0.2 })).toBe('46')
    expect(yrSymbolFor({ ...base, kind: 'rain', precipitationMm: 1 })).toBe('09')
    expect(yrSymbolFor({ ...base, kind: 'rain', precipitationMm: 5 })).toBe('10')
    expect(yrSymbolFor({ ...base, kind: 'snow', precipitationMm: 0.1 })).toBe('49')
    expect(yrSymbolFor({ ...base, kind: 'snow', precipitationMm: 1 })).toBe('13')
    expect(yrSymbolFor({ ...base, kind: 'snow', precipitationMm: 3 })).toBe('50')
    expect(yrSymbolFor({ ...base, kind: 'sleet' })).toBe('12')
    expect(yrSymbolFor({ ...base, kind: 'drizzle' })).toBe('46')
    // no symbol of Yr's for these: the sky the cloud cover makes, and light snow for the drift
    expect(yrSymbolFor({ ...base, kind: 'wind', sky: 'cloudy' })).toBe('04')
    expect(yrSymbolFor({ ...base, kind: 'dust', sky: 'partlyCloudy', night: true })).toBe('03n')
    expect(yrSymbolFor({ ...base, kind: 'funnelCloud' })).toBe('01d')
    expect(yrSymbolFor({ ...base, kind: 'blowingSnow' })).toBe('49')
  })
})

describe('the readout of an hour', () => {
  const series = { id: 'x', panel: 'temp' as const, tone: 'temp' as const, hover: 'x', digits: 1, unit: '', x: [0, HOUR, 2 * HOUR, 6 * HOUR], y: [10, 20, 30, 70] }

  it('is the series\' value at its stamp, and between two as the line is drawn', () => {
    expect(readoutValue({ ...series, mode: 'line' }, HOUR)).toBe(20)
    expect(readoutValue({ ...series, mode: 'line' }, 1.5 * HOUR)).toBe(25)
  })

  it('is the stamp before\'s for a held value, and none for a bar that has no stamp there', () => {
    expect(readoutValue({ ...series, mode: 'held' }, 1.5 * HOUR)).toBe(20)
    expect(readoutValue({ ...series, mode: 'exact' }, 1.5 * HOUR)).toBeNull()
    expect(readoutValue({ ...series, mode: 'exact' }, 2 * HOUR)).toBe(30)
  })

  it('is none outside the series and across a gap of more than three hours', () => {
    expect(readoutValue({ ...series, mode: 'line' }, -1)).toBeNull()
    expect(readoutValue({ ...series, mode: 'line' }, 7 * HOUR)).toBeNull()
    expect(readoutValue({ ...series, mode: 'line' }, 4 * HOUR)).toBeNull()
  })

  it('is in the model for each value the hour has, in the unit of the answer', () => {
    const m = model()
    const time = Date.UTC(2026, 9, 1) + 10 * HOUR
    const temp = m.readout.find(r => r.id === 'temp')!
    expect(temp.unit).toBe('°C')
    expect(readoutValue(temp, time)).toBe(m.series.find(s => s.id === 'temp')!.data.find(p => p[0] === time)![1])
    const dir = m.readout.find(r => r.id === 'direction')!
    expect(dir.unit).toBe('°')
    expect(readoutValue(dir, time)).toBe((200 + 6 * 10) % 360)
  })
})
