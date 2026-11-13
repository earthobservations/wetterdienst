/**
 * What the forecast chart draws, worked out from the forecast's series, in the units of the answer and the words of the
 * page: the lines, bars and barbs of each panel with their ranges, the day bands and the hours of the time axis, and
 * the weather of each hour. A plain function of its input, with no chart library and no DOM, so that what is drawn is
 * held by tests; `meteogram-option.ts` turns it into the chart's option.
 */
import type { SunTimes } from 'suncalc'
import type { PanelName } from './meteogram-geometry'
import type { Series, SeriesMap } from './meteogram-series'
import type { MeteogramUnits, Translate } from './meteogram-units'
import type { Quantity } from './units'
import type { WeatherKind } from './weather-kind'
import type { Sky } from './weather-symbols'
import { DateTime } from 'luxon'
import { formatDayMonth, weekdayShort } from './format'
import { extremeWindowHours, extremeWindowSteps, findNearestIndex, interpSeries, METEOGRAM_SERIES, resampleCadenceMs, wetBulbApprox } from './meteogram'
import { HOUR_MS, PANEL_HEIGHT, PANEL_ORDER } from './meteogram-geometry'
import { findFirstAvailable } from './meteogram-series'
import { fitAxisTitle } from './meteogram-ticks'
import { weatherCodeToKind } from './weather-kind'

/** The sun, as `suncalc` has it: loaded when the chart is first drawn */
export interface SunLibrary {
  getTimes: (date: Date, latitude: number, longitude: number) => SunTimes
  getPosition: (date: Date, latitude: number, longitude: number) => { altitude: number }
}

/** The colours of the series: each is a key of the table in `meteogram-option.ts` */
export type Tone = 'temp' | 'tempMax' | 'tempMin' | 'dew' | 'rain' | 'mixed' | 'snow' | 'wind' | 'gust' | 'pressure' | 'cloudHigh' | 'cloudMid' | 'cloudLow' | 'cloudTotal'

/** A series drawn in a panel, as points of time (ms) and value, a null value breaking the line */
export interface DrawnSeries {
  id: string
  panel: PanelName
  kind: 'line' | 'step' | 'bar'
  tone: Tone
  /** the name in the series' axis and the table, with its unit */
  name: string
  /** the name the readout writes before the value */
  hover: string
  /** `Max Temp` held across 12 hours is drawn dashed */
  dashed: boolean
  width: number
  area: boolean
  data: [number, number | null][]
  quantity: Quantity
  /** the decimals the readout writes its value with */
  digits: number
}

export interface DayBand {
  /** local midnight of the day and of the next */
  start: number
  end: number
  /** local noon: where the day's name is */
  noon: number
  /** the band of daylight, null at the polar night */
  light: [number, number] | null
  /** the share of the sky that is cloud at noon, 0 to 1, which fades the band */
  cloud: number
  weekday: string
  dayMonth: string
  weekend: boolean
}

export interface BarbPoint {
  t: number
  /** the direction the wind comes from, in degrees */
  dir: number
  knots: number
  /** the speed in the chart's unit: where on the wind panel the barb stands */
  speed: number
  /** the hours to the next stamp, and the index to thin by (`every` in `meteogram-geometry.ts`) */
  cadence: number
  index: number
}

export interface SymbolPoint {
  t: number
  kind: WeatherKind
  night: boolean
  precipitationMm: number | null
  sky: Sky
  cadence: number
  index: number
}

export interface HourLabel { t: number, hour: number }

export interface AxisSpec {
  panel: PanelName
  range: [number, number]
  /** the title along the axis, `\n` where it is broken into two lines */
  title: string
  titleLines: 1 | 2
  /** the label colour is the series' (key of `SERIES_LABEL`), or the muted text's for the clouds */
  label: 'cyan' | 'blue' | 'slate' | 'red' | 'lime'
  /** the decimals the labels are written with at most */
  decimals: number
  /** the number of divisions the axis aims at */
  splits: number
}

/** A row of the readout: a series' value at one time */
export interface ReadoutSeries {
  id: string
  panel: PanelName
  tone: Tone
  hover: string
  digits: number
  unit: string
  /** the series' own stamps and values, in time order */
  x: number[]
  y: number[]
  /** between two stamps: the line's own value (`line`), the stamp before's (`held`, a direction), or none (`exact`, a bar) */
  mode: 'line' | 'held' | 'exact'
}

/**
 * The value of a readout series at `t`: at its stamp, between two as the line is drawn, and for a held value the one
 * of the stamp before; null outside the series or where it has a gap of more than 3 hours.
 */
export function readoutValue(series: ReadoutSeries, t: number): number | null {
  const { x, y } = series
  if (!x.length || t < x[0]! || t > x.at(-1)!)
    return null
  let lo = 0
  let hi = x.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (x[mid]! <= t)
      lo = mid
    else hi = mid - 1
  }
  const next = x[lo + 1]
  if (x[lo] === t || next === undefined)
    return x[lo] === t ? (y[lo] ?? null) : null
  if (series.mode === 'exact' || next - x[lo]! > 3 * HOUR_MS)
    return null
  if (series.mode === 'held')
    return y[lo] ?? null
  const frac = (t - x[lo]!) / (next - x[lo]!)
  return y[lo]! + frac * (y[lo + 1]! - y[lo]!)
}

export interface MeteogramModel {
  /** the first and last time shown, in ms */
  minTime: number
  maxTime: number
  /** the grid the series are on, in ms: an hour, and three past 5 days */
  stepMs: number
  /** every time of the grid, which the arrow keys step through */
  stamps: number[]
  panels: PanelName[]
  axes: Partial<Record<PanelName, AxisSpec>>
  series: DrawnSeries[]
  barbs: BarbPoint[]
  symbols: SymbolPoint[]
  hours: HourLabel[]
  days: DayBand[]
  /** the freezing point in the unit of the chart, a line in the temperature panel where it is on the axis */
  freezing: number | null
  /** the readout's series, and the weather of each stamp */
  readout: ReadoutSeries[]
  weather: Map<number, WeatherKind>
  /** whether the forecast has a weather code or a cloud cover to draw a symbol row from */
  hasSymbols: boolean
}

export interface ModelInput {
  series: SeriesMap
  panels: Record<PanelName, boolean>
  horizonHours: number | null
  zone: string
  language: string
  coords: { latitude: number | null, longitude: number | null } | null | undefined
  sun: SunLibrary | null
  units: MeteogramUnits
  t: Translate
}

/** The dew point by Magnus' formula, in degrees Celsius, of a temperature in degrees Celsius and a humidity in percent */
export function dewPointMagnus(celsius: number, humidityPercent: number): number {
  const a = 17.27
  const b = 237.7
  const alpha = (a * celsius) / (b + celsius) + Math.log(humidityPercent / 100)
  return (b * alpha) / (a - alpha)
}

/** The kind of precipitation of an hour: snow at a wet bulb of 0.5 degrees or less, mixed up to 2, else rain. In degrees Celsius and percent */
export function precipPhase(celsius: number, humidityPercent: number | null): 'rain' | 'mixed' | 'snow' {
  const wet = humidityPercent === null ? celsius : wetBulbApprox(celsius, humidityPercent)
  if (wet <= 0.5)
    return 'snow'
  if (wet <= 2)
    return 'mixed'
  return 'rain'
}

function calendarDays(startMs: number, endMs: number, zone: string): DateTime[] {
  const days: DateTime[] = []
  let dt = DateTime.fromMillis(startMs, { zone }).startOf('day')
  const end = DateTime.fromMillis(endMs, { zone }).startOf('day')
  while (dt.toMillis() <= end.toMillis()) {
    days.push(dt)
    dt = dt.plus({ days: 1 })
  }
  return days
}

/** Adds each point's gap to the next in hours and an index to thin by, aligned to the clock of the zone where the grid allows */
function thinning(times: number[], zone: string): { cadence: number, index: number }[] {
  return times.map((t, i) => {
    const next = times[i + 1] ?? t + (t - (times[i - 1] ?? t - HOUR_MS))
    const cadence = Math.max(1, Math.round((next - t) / HOUR_MS))
    const offset = DateTime.fromMillis(t, { zone }).offset * 60_000
    return { cadence, index: Math.round((t + offset) / (cadence * HOUR_MS)) }
  })
}

/** Everything the chart draws; null where the forecast has no value to draw */
export function buildMeteogramModel(input: ModelInput): MeteogramModel | null {
  const { series, panels: shownPanels, horizonHours, zone, language, coords, sun, units, t } = input
  const { canon, shown, stretch, named } = units
  const available = new Set(series.keys())
  const key = (names: readonly string[]) => findFirstAvailable(names, available)

  const tempKey = key(METEOGRAM_SERIES.temperature)
  const precipKey = key(METEOGRAM_SERIES.precipitation)
  const windKey = key(METEOGRAM_SERIES.windSpeed)
  const windDirKey = key(METEOGRAM_SERIES.windDirection)
  const gustKey = key(METEOGRAM_SERIES.gust)
  const cloudKey = key(METEOGRAM_SERIES.cloudCover)
  const cloudLowKey = key(METEOGRAM_SERIES.cloudCoverLow)
  const cloudMidKey = key(METEOGRAM_SERIES.cloudCoverMid)
  const cloudHighKey = key(METEOGRAM_SERIES.cloudCoverHigh)
  const humidityKey = key(METEOGRAM_SERIES.humidity)
  const dewKey = key(METEOGRAM_SERIES.dewPoint)
  const pressureKey = key(METEOGRAM_SERIES.pressure)
  const txKey = key(METEOGRAM_SERIES.temperatureMax)
  const tnKey = key(METEOGRAM_SERIES.temperatureMin)
  const weatherKey = key(METEOGRAM_SERIES.weather)

  const allTimes = [...series.values()].flatMap(s => s.x.map(d => d.getTime()))
  if (!allTimes.length)
    return null
  let minTime = Number.POSITIVE_INFINITY
  let maxTime = Number.NEGATIVE_INFINITY
  for (const time of allTimes) {
    minTime = Math.min(minTime, time)
    maxTime = Math.max(maxTime, time)
  }
  const displayMax = horizonHours !== null ? Math.min(maxTime, minTime + horizonHours * HOUR_MS) : maxTime
  const stepMs = resampleCadenceMs(minTime, displayMax)

  // The forecast's own stamps, as far as the horizon reaches: nothing is resampled, so every hourly rain amount is a
  // bar and a direction is never the mean of two compass points
  const at = (k: string | undefined): Series | undefined => {
    const s = k ? series.get(k) : undefined
    if (!s)
      return undefined
    const count = s.x.findIndex(d => d.getTime() > displayMax)
    return count < 0 ? s : { x: s.x.slice(0, count), y: s.y.slice(0, count) }
  }
  const points = (s: Series): [number, number][] => s.x.map((d, i) => [d.getTime(), s.y[i]!])

  const panels = PANEL_ORDER.filter((panel) => {
    if (!shownPanels[panel])
      return false
    return { wind: !!windKey, precip: !!precipKey, cloud: !!cloudKey, temp: !!tempKey, pressure: !!pressureKey }[panel]
  })

  const drawn: DrawnSeries[] = []
  const readout: ReadoutSeries[] = []
  const lookup = (s: Series) => new Map(s.x.map((d, i) => [d.getTime(), s.y[i]!]))
  const push = (spec: DrawnSeries, unit: string, mode: ReadoutSeries['mode'] = 'line') => {
    drawn.push(spec)
    const valid = spec.data.filter((p): p is [number, number] => p[1] !== null)
    readout.push({ id: spec.id, panel: spec.panel, tone: spec.tone, hover: spec.hover, digits: spec.digits, unit, x: valid.map(p => p[0]), y: valid.map(p => p[1]), mode })
  }
  const unitOfQ = (q: Quantity) => units.unitOf(q)

  // axis ranges, as the chart has always chosen them
  const range: Partial<Record<PanelName, [number, number]>> = {}

  // -- temperature and dew point
  const freezing = shown('temperature', 0)
  let tempMinY = freezing
  let tempMaxY = shown('temperature', 25)
  const tempSeries = at(tempKey)
  if (tempKey && tempSeries && shownPanels.temp) {
    tempMinY = Math.min(freezing, ...tempSeries.y)
    tempMaxY = Math.max(...tempSeries.y)

    // The maximum and minimum are held across the hours each covers, not resampled to a line between their few
    // stamps, which let the curve out of the band (GH-2647)
    const extremeSteps = (k: string | undefined) => {
      const raw = k ? series.get(k) : undefined
      return raw ? extremeWindowSteps(raw.x, raw.y, extremeWindowHours(k!) * HOUR_MS, minTime, displayMax, stepMs) : null
    }
    const sTx = extremeSteps(txKey)
    const sTn = extremeSteps(tnKey)
    const hasTxTn = !!(sTx?.x.length && sTn?.x.length)

    push({
      id: 'temp',
      panel: 'temp',
      kind: 'line',
      tone: 'temp',
      name: hasTxTn ? named('meteogram.chart.seriesMeanTemp', 'temperature') : named('meteogram.chart.seriesTemperature', 'temperature'),
      hover: hasTxTn ? t('meteogram.chart.hoverMeanTemp') : t('meteogram.chart.hoverTemperature'),
      dashed: false,
      width: 2,
      area: true,
      data: points(tempSeries),
      quantity: 'temperature',
      digits: units.digits('temperature'),
    }, unitOfQ('temperature'))

    if (hasTxTn && sTx && sTn) {
      const held = (id: string, tone: Tone, s: typeof sTx, name: string, hover: string): DrawnSeries => ({
        id,
        panel: 'temp',
        kind: 'step',
        tone,
        name,
        hover,
        dashed: true,
        width: 1.5,
        area: false,
        data: s.x.map((d, i) => [d.getTime(), s.y[i] ?? null]),
        quantity: 'temperature',
        digits: units.digits('temperature'),
      })
      push(held('tempMax', 'tempMax', sTx, named('meteogram.chart.seriesMaxTemp', 'temperature'), t('meteogram.chart.hoverMaxTemp')), unitOfQ('temperature'))
      push(held('tempMin', 'tempMin', sTn, named('meteogram.chart.seriesMinTemp', 'temperature'), t('meteogram.chart.hoverMinTemp')), unitOfQ('temperature'))
      tempMinY = Math.min(tempMinY, ...sTn.y.filter((v): v is number => v !== null))
      tempMaxY = Math.max(tempMaxY, ...sTx.y.filter((v): v is number => v !== null))
    }

    // the dew point is the series, or worked out from the humidity (Magnus' formula, in degrees Celsius and percent, and
    // the result back in the unit of the chart)
    let dew: [number, number][] = []
    const dewSeries = at(dewKey)
    const humiditySeries = at(humidityKey)
    if (dewSeries) {
      dew = points(dewSeries)
    }
    else if (humiditySeries) {
      for (let i = 0; i < tempSeries.x.length; i++) {
        const time = tempSeries.x[i]!.getTime()
        const rh = interpSeries(humiditySeries.x, humiditySeries.y, time)
        const reading = tempSeries.y[i]
        const rhPercent = rh === null ? Number.NaN : canon('fraction', rh)
        if (rh === null || reading === undefined || Number.isNaN(reading) || !(rhPercent > 0))
          continue
        dew.push([time, shown('temperature', dewPointMagnus(canon('temperature', reading), rhPercent))])
      }
    }
    if (dew.length) {
      push({
        id: 'dew',
        panel: 'temp',
        kind: 'line',
        tone: 'dew',
        name: t('meteogram.chart.seriesDewPoint'),
        hover: t('meteogram.chart.hoverDewPoint'),
        dashed: false,
        width: 1.6,
        area: false,
        data: dew,
        quantity: 'temperature',
        digits: units.digits('temperature'),
      }, unitOfQ('temperature'))
      tempMinY = Math.min(tempMinY, ...dew.map(p => p[1]))
      tempMaxY = Math.max(tempMaxY, ...dew.map(p => p[1]))
    }
  }

  // the stamps of the grid, and the precipitation of each, whether or not its panel is shown: the symbols read it
  const precipSeries = at(precipKey)
  const humiditySeries = at(humidityKey)
  const phaseAt = (time: number): 'rain' | 'mixed' | 'snow' => {
    if (!tempSeries)
      return 'rain'
    const reading = interpSeries(tempSeries.x, tempSeries.y, time)
    if (reading === null || Number.isNaN(reading))
      return 'rain'
    const rh = humiditySeries ? interpSeries(humiditySeries.x, humiditySeries.y, time) : null
    return precipPhase(canon('temperature', reading), rh === null ? null : canon('fraction', rh))
  }

  // -- precipitation
  if (precipKey && precipSeries && shownPanels.precip) {
    const rain: [number, number | null][] = []
    const mixed: [number, number | null][] = []
    const snow: [number, number | null][] = []
    precipSeries.x.forEach((d, i) => {
      const time = d.getTime()
      const amount = precipSeries.y[i] ?? 0
      const phase = phaseAt(time)
      // every stamp has a point, null where it is no part of the stack: the bars are as wide as the stamps are apart
      rain.push([time, phase === 'rain' ? amount : null])
      mixed.push([time, phase === 'mixed' ? amount : null])
      snow.push([time, phase === 'snow' ? amount : null])
    })
    const bar = (id: string, tone: Tone, data: [number, number | null][], name: string, hover: string): DrawnSeries => ({
      id,
      panel: 'precip',
      kind: 'bar',
      tone,
      name,
      hover,
      dashed: false,
      width: 0,
      area: false,
      data,
      quantity: 'precipitation',
      digits: units.digits('precipitation'),
    })
    push(bar('rain', 'rain', rain, t('meteogram.chart.seriesRain'), t('meteogram.chart.hoverRain')), unitOfQ('precipitation'), 'exact')
    push(bar('mixed', 'mixed', mixed, t('meteogram.chart.seriesMixed'), t('meteogram.chart.hoverMixed')), unitOfQ('precipitation'), 'exact')
    push(bar('snow', 'snow', snow, t('meteogram.chart.seriesSnow'), t('meteogram.chart.hoverSnow')), unitOfQ('precipitation'), 'exact')
    const pMax = Math.max(0, ...precipSeries.y.map(v => v ?? 0))
    range.precip = [0, Math.max(shown('precipitation', 1), pMax * 1.15)]
  }
  else {
    range.precip = [0, shown('precipitation', 1)]
  }

  // -- pressure
  let pressureMin = shown('pressure', 1000)
  let pressureMax = shown('pressure', 1020)
  const pressureSeries = at(pressureKey)
  if (pressureKey && pressureSeries && shownPanels.pressure) {
    push({
      id: 'pressure',
      panel: 'pressure',
      kind: 'line',
      tone: 'pressure',
      name: named('meteogram.chart.seriesPressure', 'pressure'),
      hover: t('meteogram.chart.hoverPressure'),
      dashed: false,
      width: 1.6,
      area: true,
      data: points(pressureSeries),
      quantity: 'pressure',
      digits: units.digits('pressure'),
    }, unitOfQ('pressure'))
    pressureMin = Math.min(...pressureSeries.y)
    pressureMax = Math.max(...pressureSeries.y)
  }

  // -- wind, gusts and barbs
  let windMaxY = shown('speed', 10)
  const barbs: BarbPoint[] = []
  const windSeries = at(windKey)
  if (windKey && windSeries && shownPanels.wind) {
    windMaxY = Math.max(...windSeries.y, shown('speed', 5))
    const gustSeries = at(gustKey)
    if (gustSeries)
      windMaxY = Math.max(windMaxY, ...gustSeries.y)

    push({
      id: 'wind',
      panel: 'wind',
      kind: 'line',
      tone: 'wind',
      name: named('meteogram.chart.seriesWind', 'speed'),
      hover: t('meteogram.chart.hoverWind'),
      dashed: false,
      width: 2,
      area: true,
      data: points(windSeries),
      quantity: 'speed',
      digits: units.digits('speed'),
    }, unitOfQ('speed'))
    if (gustSeries) {
      push({
        id: 'gust',
        panel: 'wind',
        kind: 'line',
        tone: 'gust',
        name: named('meteogram.chart.seriesWindGust', 'speed'),
        hover: t('meteogram.chart.hoverWindGust'),
        dashed: true,
        width: 1.6,
        area: false,
        data: points(gustSeries),
        quantity: 'speed',
        digits: units.digits('speed'),
      }, unitOfQ('speed'))
    }

    const dirSeries = at(windDirKey)
    if (dirSeries) {
      // the direction is a reading of its own in the readout, in the unit the answer has it in
      readout.push({ id: 'direction', panel: 'wind', tone: 'wind', hover: t('meteogram.chart.seriesDirection'), digits: units.digits('angle'), unit: unitOfQ('angle'), x: dirSeries.x.map(d => d.getTime()), y: dirSeries.y, mode: 'held' })
      const dirLookup = lookup(dirSeries)
      const stamps = windSeries.x.map(d => d.getTime())
      const thin = thinning(stamps, zone)
      stamps.forEach((time, i) => {
        // the barb points from the direction in degrees and has the knots of the speed in metres per second
        const dir = canon('angle', dirLookup.get(time) ?? dirSeries.y[0] ?? 0)
        const speed = windSeries.y[i] ?? 0
        barbs.push({ t: time, dir, knots: (canon('speed', speed) * 3600) / 1852, speed, ...thin[i]! })
      })
    }
    range.wind = [0, windMaxY * 1.6]
  }
  else {
    range.wind = [0, windMaxY * 1.6]
  }

  // -- clouds
  const cloudSeries = at(cloudKey)
  if (cloudKey && cloudSeries && shownPanels.cloud) {
    const layer = (id: string, tone: Tone, k: string | undefined, name: string, hover: string) => {
      const s = at(k)
      if (!s)
        return
      push({ id, panel: 'cloud', kind: 'line', tone, name, hover, dashed: false, width: 1, area: true, data: points(s), quantity: 'fraction', digits: units.digits('fraction') }, unitOfQ('fraction'))
    }
    layer('cloudHigh', 'cloudHigh', cloudHighKey, named('meteogram.chart.seriesHighClouds', 'fraction'), t('meteogram.chart.hoverHighClouds'))
    layer('cloudMid', 'cloudMid', cloudMidKey, named('meteogram.chart.seriesMidClouds', 'fraction'), t('meteogram.chart.hoverMidClouds'))
    layer('cloudLow', 'cloudLow', cloudLowKey, named('meteogram.chart.seriesLowClouds', 'fraction'), t('meteogram.chart.hoverLowClouds'))
    push({ id: 'cloudTotal', panel: 'cloud', kind: 'line', tone: 'cloudTotal', name: named('meteogram.chart.seriesTotalCloud', 'fraction'), hover: t('meteogram.chart.hoverTotalCloud'), dashed: false, width: 2, area: false, data: points(cloudSeries), quantity: 'fraction', digits: units.digits('fraction') }, unitOfQ('fraction'))
  }

  // the cloud cover's axis is the whole of the scale: 0 to 100 %, 0 to 1, 0 to 8 oktas
  const cloudTop = shown('fraction', 100)
  // a degree and a hectopascal, in the unit of the chart: a degree is 1.8 degrees Fahrenheit, a hectopascal 100 pascals
  const degree = stretch('temperature', 1)
  const hectopascal = stretch('pressure', 1)
  range.cloud = [0, cloudTop]
  range.temp = [tempMinY - degree, tempMaxY + 3 * degree]
  range.pressure = [pressureMin - 2 * hectopascal, pressureMax + 2 * hectopascal]

  // the axes' titles: along their panel, which a long one does not fit (German "Niederschlag mm"): broken into two lines
  const titleTexts: Record<PanelName, string> = {
    wind: named('meteogram.chart.axisWind', 'speed'),
    precip: named('meteogram.chart.axisPrecip', 'precipitation'),
    cloud: named('meteogram.chart.axisCloud', 'fraction'),
    temp: named('meteogram.chart.axisTemp', 'temperature'),
    pressure: named('meteogram.chart.axisPressure', 'pressure'),
  }
  const labelColour: Record<PanelName, AxisSpec['label']> = { wind: 'cyan', precip: 'blue', cloud: 'slate', temp: 'red', pressure: 'lime' }
  const decimalsOf = (panel: PanelName, quantity: Quantity) => ({ wind: Math.min(1, units.digits(quantity)), precip: Math.min(2, units.digits(quantity) + 1), cloud: 0, temp: 0, pressure: 0 })[panel]
  const quantityOf: Record<PanelName, Quantity> = { wind: 'speed', precip: 'precipitation', cloud: 'fraction', temp: 'temperature', pressure: 'pressure' }
  const splitsOf: Record<PanelName, number> = { wind: 3, precip: 2, cloud: 2, temp: 3, pressure: 2 }
  const axes: Partial<Record<PanelName, AxisSpec>> = {}
  for (const panel of panels) {
    const fit = fitAxisTitle(titleTexts[panel], PANEL_HEIGHT[panel], 12)
    axes[panel] = {
      panel,
      range: range[panel]!,
      title: fit.text.replace('<br>', '\n'),
      titleLines: fit.lines,
      label: labelColour[panel],
      decimals: decimalsOf(panel, quantityOf[panel]),
      splits: splitsOf[panel],
    }
  }

  // -- the days: bands of daylight from the sun at the station, a whole day or none at the poles, and the names
  const dayList = calendarDays(minTime, displayMax, zone)
  const cloudAt = (time: number) => {
    const s = cloudSeries
    if (!s)
      return 0
    const index = findNearestIndex(s.x, time)
    return index < 0 ? 0 : canon('fraction', s.y[index] ?? 0) / 100
  }
  const lat = coords?.latitude ?? null
  const lon = coords?.longitude ?? null
  const days: DayBand[] = dayList.map((day) => {
    const start = day.toMillis()
    const end = day.plus({ days: 1 }).toMillis()
    const noon = day.plus({ hours: 12 }).toMillis()
    let light: [number, number] | null
    if (sun && lat !== null && lon !== null) {
      const times = sun.getTimes(new Date(noon), lat, lon)
      const rise = (times.sunrise ?? times.sunriseEnd)?.getTime()
      const set = (times.sunset ?? times.sunsetStart)?.getTime()
      if (rise !== undefined && set !== undefined && Number.isFinite(rise) && Number.isFinite(set))
        light = [rise, set]
      // inside the polar circle the sun does not rise or does not set: the day is all light, or none
      else
        light = sun.getPosition(new Date(noon), lat, lon).altitude > 0 ? [start, end] : null
    }
    else {
      light = [day.plus({ hours: 4 }).toMillis(), day.plus({ hours: 20 }).toMillis()]
    }
    return {
      start,
      end,
      noon,
      light,
      cloud: cloudAt(noon),
      weekday: weekdayShort(day, language),
      dayMonth: formatDayMonth(day, language),
      weekend: day.weekday >= 6,
    }
  })

  // -- the hours of the time axis, one for each hour from the first on the clock
  const hours: HourLabel[] = []
  for (let time = Math.ceil(minTime / HOUR_MS) * HOUR_MS; time <= displayMax; time += HOUR_MS)
    hours.push({ t: time, hour: DateTime.fromMillis(time, { zone }).hour })

  // -- the grid every series is on, and the weather of each stamp
  const stampSet = new Set<number>()
  for (const s of [tempSeries, windSeries, precipSeries, cloudSeries, pressureSeries, at(weatherKey)]) {
    for (const d of s?.x ?? [])
      stampSet.add(d.getTime())
  }
  const stamps = [...stampSet].sort((a, b) => a - b)

  const weatherSeries = at(weatherKey)
  const weatherLookup = weatherSeries ? lookup(weatherSeries) : new Map<number, number>()
  const hasSymbols = !!(weatherSeries || cloudSeries || precipSeries)
  const weather = new Map<number, WeatherKind>()
  const symbolStamps = (precipSeries ?? cloudSeries ?? weatherSeries ?? windSeries ?? tempSeries)?.x.map(d => d.getTime()) ?? []
  const precipLookup = precipSeries ? lookup(precipSeries) : new Map<number, number>()
  const symbolThin = thinning(symbolStamps, zone)
  const symbols: SymbolPoint[] = []
  const nightAt = (time: number) => {
    const day = days.find(d => time >= d.start && time < d.end)
    if (!day)
      return false
    return day.light ? time < day.light[0] || time > day.light[1] : true
  }
  symbolStamps.forEach((time, i) => {
    const cloudShare = cloudSeries ? cloudAt(time) * 100 : null
    const sky: Sky = cloudShare === null ? 'partlyCloudy' : cloudShare >= 70 ? 'cloudy' : cloudShare >= 30 ? 'partlyCloudy' : 'clear'
    const mm = precipSeries ? canon('precipitation', precipLookup.get(time) ?? 0) : null
    const code = weatherLookup.get(time)
    const fromCode = code === undefined ? null : weatherCodeToKind(code)
    let kind: WeatherKind
    if (fromCode && fromCode !== 'clear' && fromCode !== 'partlyCloudy' && fromCode !== 'cloudy') {
      // a phenomenon the code names
      kind = fromCode
    }
    else if (mm !== null && mm >= 0.1) {
      const phase = phaseAt(time)
      kind = phase === 'snow' ? 'snow' : phase === 'mixed' ? 'sleet' : 'rain'
    }
    else {
      // the sky: the cloud cover where there is one, else what the code says of it
      kind = cloudShare !== null ? sky : (fromCode ?? 'partlyCloudy')
    }
    weather.set(time, kind)
    symbols.push({ t: time, kind, night: nightAt(time), precipitationMm: mm, sky, ...symbolThin[i]! })
  })

  return {
    minTime,
    maxTime: displayMax,
    stepMs,
    stamps,
    panels,
    axes,
    series: drawn,
    barbs,
    symbols: hasSymbols ? symbols : [],
    hours,
    days,
    freezing: freezing >= range.temp[0] && freezing <= range.temp[1] && panels.includes('temp') ? freezing : null,
    readout,
    weather,
    hasSymbols,
  }
}
