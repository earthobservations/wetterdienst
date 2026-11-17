/**
 * What the forecast chart draws, worked out from the forecast's series, in the units of the answer and the words of the
 * page: the lines, bars and barbs of each panel with their ranges, the day bands and the hours of the time axis, and
 * the weather of each hour. A plain function of its input, with no chart library and no DOM, so that what is drawn is
 * held by tests; `meteogram-option.ts` turns it into the chart's option.
 */
import type { SunTimes } from 'suncalc'
import type { PanelName, PanelToggle } from './meteogram-geometry'
import type { Series, SeriesMap } from './meteogram-series'
import type { MeteogramUnits, Translate } from './meteogram-units'
import type { Quantity } from './units'
import type { WeatherKind } from './weather-kind'
import type { Sky } from './weather-symbols'
import { DateTime } from 'luxon'
import { formatDayMonth, weekdayShort } from './format'
import { extremeWindowHours, extremeWindowSteps, findNearestIndex, interpSeries, METEOGRAM_SERIES, wetBulbApprox } from './meteogram'
import { HOUR_MS, PANEL_ORDER, toggleOf } from './meteogram-geometry'
import { planPrecipitation } from './meteogram-precipitation'
import { findFirstAvailable } from './meteogram-series'
import { snowChanceAmount } from './meteogram-units'
import { weatherCodeToKind } from './weather-kind'

/** The sun, as `suncalc` has it: loaded when the chart is first drawn */
export interface SunLibrary {
  getTimes: (date: Date, latitude: number, longitude: number) => SunTimes
  getPosition: (date: Date, latitude: number, longitude: number) => { altitude: number }
}

/** The colours of the series: each is a key of the table in `meteogram-option.ts` */
export type Tone = 'temp' | 'tempMax' | 'tempMin' | 'dew' | 'rain' | 'mixed' | 'snow' | 'wind' | 'gust' | 'pressure' | 'snowNew' | 'snowDepth' | 'snowChance' | 'cloudHigh' | 'cloudMid' | 'cloudLow' | 'cloudTotal'

/** The hours the amount of a snow bar covers: the 3 h of `Sa3`. A precipitation bar covers the hours of its block (1, 6, 12 or 24: `meteogram-precipitation.ts`) */
export const SNOW_WINDOW_MS = 3 * HOUR_MS

/**
 * A bar over the window it covers. DWD stamps an amount at the end of its window (the new snow of (T - 3 h, T] at T) and the
 * readout and the table read it at that stamp, but a bar drawn at the stamp reads as the hours after it: it is drawn centred on the
 * middle of its window, so that the bar fills the hours it stands for and the hour label under its end is the end of it.
 */
export function overWindow(data: [number, number | null][], windowMs: number): [number, number | null][] {
  return data.map(([time, amount]) => [time - windowMs / 2, amount])
}

/** The longest step between two stamps of a line that is still drawn: no value is read across a longer one (`readoutValue`) */
export const LINE_GAP_MS = 3 * HOUR_MS

/**
 * `points` with a point of no value between two stamps that are more than `maxStepMs` apart, so that a line is not drawn across
 * hours the forecast has no value for, nor an area filled under it (GH-4100). The 3 hours of an element given every 3 hours
 * are no gap, and the readout already says there is no value across a longer one.
 */
export function breakAtGaps(points: [number, number][], maxStepMs: number = LINE_GAP_MS): [number, number | null][] {
  const out: [number, number | null][] = []
  points.forEach((point, i) => {
    const before = points[i - 1]
    if (before && point[0] - before[0] > maxStepMs)
      out.push([Math.round((before[0] + point[0]) / 2), null])
    out.push(point)
  })
  return out
}

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
  /** a line drawn as straight segments between its stamps, which a quantity given at a few steps is (the snow's), not smoothed */
  straight?: boolean
  width: number
  area: boolean
  data: [number, number | null][]
  quantity: Quantity
  /** the decimals the readout writes its value with */
  digits: number
  /** for a bar of blocks of different lengths (the precipitation): the hours each of `data` covers, in the same order */
  windows?: number[]
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
  label: 'cyan' | 'blue' | 'slate' | 'red' | 'lime' | 'indigo' | 'teal' | 'gold'
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
  /**
   * For blocks of 1, 6, 12 or 24 hours (the precipitation): the hours each value covers, in the order of `x`, which are the stamps
   * at the end of them. A block of more than an hour is read at every time it covers; one of an hour at its stamp.
   */
  windows?: number[]
}

/**
 * The value of a readout series at `t`: at its stamp, between two as the line is drawn, and for a held value the one
 * of the stamp before; null outside the series or where it has a gap of more than 3 hours.
 */
export function readoutValue(series: ReadoutSeries, t: number): number | null {
  const { x, y } = series
  if (series.windows) {
    const i = blockAt(series, t)
    return i < 0 ? null : y[i]!
  }
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
  if (series.mode === 'exact' || next - x[lo]! > LINE_GAP_MS)
    return null
  if (series.mode === 'held')
    return y[lo] ?? null
  const frac = (t - x[lo]!) / (next - x[lo]!)
  return y[lo]! + frac * (y[lo + 1]! - y[lo]!)
}

/** The index of the block of a series of blocks that covers `t`, or -1: an hour at its stamp, a longer block over the whole of its window */
function blockAt(series: ReadoutSeries, t: number): number {
  const { x, windows } = series
  let lo = 0
  let hi = x.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (x[mid]! < t)
      lo = mid + 1
    else hi = mid
  }
  const hours = windows![lo]
  if (hours === undefined)
    return -1
  return hours === 1 ? (x[lo] === t ? lo : -1) : t > x[lo]! - hours * HOUR_MS ? lo : -1
}

/** The hours of the block a readout series has at `t`: 1 for a value that is not a block's, and where it has none */
export function readoutHours(series: ReadoutSeries, t: number): number {
  const i = series.windows ? blockAt(series, t) : -1
  return i < 0 ? 1 : series.windows![i]!
}

export interface MeteogramModel {
  /** the first and last time shown, in ms */
  minTime: number
  maxTime: number
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
  /** where the precipitation panel goes from blocks of one length to another (an hour to 6): the first moment of the new blocks */
  precipChanges: { t: number, hours: number, label: string }[]
  /** the readout's series, and the weather of each stamp */
  readout: ReadoutSeries[]
  weather: Map<number, WeatherKind>
  /** whether the forecast has a weather code or a cloud cover to draw a symbol row from */
  hasSymbols: boolean
}

export interface ModelInput {
  series: SeriesMap
  panels: Record<PanelToggle, boolean>
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
  return phaseOfWetBulb(humidityPercent === null ? celsius : wetBulbApprox(celsius, humidityPercent))
}

/** The kind of precipitation at a wet bulb temperature in degrees Celsius: snow at 0.5 or less, mixed up to 2, else rain */
function phaseOfWetBulb(wet: number): 'rain' | 'mixed' | 'snow' {
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
  const { canon, shown, stretch, named, title, unitName } = units
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
  const snowNewKey = key(METEOGRAM_SERIES.snowNew)
  const snowDepthKey = key(METEOGRAM_SERIES.snowDepth)
  const snowChanceKey = key(METEOGRAM_SERIES.snowChance)
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

  // The precipitation as blocks of 1, 6, 12 or 24 hours: the finest series that accounts for MOSMIX's coarse totals gives each stretch
  // (`planPrecipitation`), and the chart draws each block over the hours it covers
  const precipPlan = planPrecipitation(series, amount => canon('precipitation', amount))

  const panels = PANEL_ORDER.filter((panel) => {
    if (!shownPanels[toggleOf(panel)])
      return false
    return { wind: !!windKey, precip: !!precipPlan, snow: !!snowNewKey, snowDepth: !!snowDepthKey, snowChance: !!snowChanceKey, cloud: !!cloudKey, temp: !!tempKey, pressure: !!pressureKey }[panel]
  })

  const drawn: DrawnSeries[] = []
  const readout: ReadoutSeries[] = []
  const lookup = (s: Series) => new Map(s.x.map((d, i) => [d.getTime(), s.y[i]!]))
  const push = (spec: DrawnSeries, unit: string, mode: ReadoutSeries['mode'] = 'line', readFrom: DrawnSeries['data'] = spec.data, readWindows?: number[]) => {
    drawn.push(spec)
    const valid = readFrom.flatMap((p, i) => p[1] === null ? [] : [{ time: p[0], value: p[1], hours: readWindows?.[i] }])
    readout.push({ id: spec.id, panel: spec.panel, tone: spec.tone, hover: spec.hover, digits: spec.digits, unit, x: valid.map(p => p.time), y: valid.map(p => p.value), mode, ...(readWindows ? { windows: valid.map(p => p.hours!) } : {}) })
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
      return raw ? extremeWindowSteps(raw.x, raw.y, extremeWindowHours(k!) * HOUR_MS, minTime, displayMax, HOUR_MS) : null
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
      data: breakAtGaps(points(tempSeries)),
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
        data: breakAtGaps(dew),
        quantity: 'temperature',
        digits: units.digits('temperature'),
      }, unitOfQ('temperature'))
      tempMinY = Math.min(tempMinY, ...dew.map(p => p[1]))
      tempMaxY = Math.max(tempMaxY, ...dew.map(p => p[1]))
    }
  }

  // the humidity and the temperature the kind of precipitation is judged by, and the hourly amount, which the symbols are drawn with:
  // they read an hour's own amount, and a block of more hours says nothing of any one of its hours
  const precipSeries = at(precipKey)
  const humiditySeries = at(humidityKey)
  // the wet bulb temperature at an hour, in degrees Celsius: the air's where there is no humidity; null where there is no temperature
  const wetBulbAt = (time: number): number | null => {
    if (!tempSeries)
      return null
    const reading = interpSeries(tempSeries.x, tempSeries.y, time)
    if (reading === null || Number.isNaN(reading))
      return null
    const rh = humiditySeries ? interpSeries(humiditySeries.x, humiditySeries.y, time) : null
    const celsius = canon('temperature', reading)
    return rh === null ? celsius : wetBulbApprox(celsius, canon('fraction', rh))
  }
  const phaseAt = (time: number): 'rain' | 'mixed' | 'snow' => {
    const wet = wetBulbAt(time)
    return wet === null ? 'rain' : phaseOfWetBulb(wet)
  }

  // -- precipitation: the blocks of the plan, each over the hours it covers
  const precipBlocks = precipPlan?.blocks.filter(block => block.end <= displayMax) ?? []
  const precipChanges = (precipPlan?.changes ?? []).filter(change => change.at < displayMax).map(change => ({ t: change.at, hours: change.hours, label: t('meteogram.chart.precipBlocks', { hours: change.hours }) }))
  // The kind of a block is the kind of the mean wet bulb temperature of its hours, by the thresholds an hour is judged by (an hour is
  // its own wet bulb): the amounts of the hours of a longer block are not known, so each hour counts the same
  const phaseOfBlock = (block: { start: number, end: number }): 'rain' | 'mixed' | 'snow' => {
    const wets: number[] = []
    for (let time = block.start + HOUR_MS; time <= block.end; time += HOUR_MS) {
      const wet = wetBulbAt(time)
      if (wet !== null)
        wets.push(wet)
    }
    return wets.length ? phaseOfWetBulb(wets.reduce((sum, wet) => sum + wet, 0) / wets.length) : 'rain'
  }
  if (precipPlan && shownPanels.precip) {
    const rain: [number, number | null][] = []
    const mixed: [number, number | null][] = []
    const snow: [number, number | null][] = []
    const windows = precipBlocks.map(block => block.hours)
    for (const block of precipBlocks) {
      const phase = phaseOfBlock(block)
      // every block has a point, null where it is no part of the stack: the readout reads the amount at the block's stamp
      rain.push([block.end, phase === 'rain' ? block.amount : null])
      mixed.push([block.end, phase === 'mixed' ? block.amount : null])
      snow.push([block.end, phase === 'snow' ? block.amount : null])
    }
    // a bar of no height is no element: the block keeps its point with no value, and the readout still says 0
    // each over the hours it covers, the amount of the hours before its stamp (the readout reads it at the stamp), centred on the middle of them
    const unseen = (data: [number, number | null][]): [number, number | null][] => data.map(([time, amount], i) => [time - (windows[i]! * HOUR_MS) / 2, amount || null])
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
      windows,
    })
    push(bar('rain', 'rain', unseen(rain), t('meteogram.chart.seriesRain'), t('meteogram.chart.hoverRain')), unitOfQ('precipitation'), 'exact', rain, windows)
    push(bar('mixed', 'mixed', unseen(mixed), t('meteogram.chart.seriesMixed'), t('meteogram.chart.hoverMixed')), unitOfQ('precipitation'), 'exact', mixed, windows)
    push(bar('snow', 'snow', unseen(snow), t('meteogram.chart.seriesSnow'), t('meteogram.chart.hoverSnow')), unitOfQ('precipitation'), 'exact', snow, windows)
    const pMax = Math.max(0, ...precipBlocks.map(block => block.amount))
    range.precip = [0, Math.max(shown('precipitation', 1), pMax * 1.15)]
  }
  else {
    range.precip = [0, shown('precipitation', 1)]
  }

  // -- the snow forecast (MOSMIX-SNOW, GH-4091): the new snow of the 3 hours before each step as bars, the snow depth as a line and
  // the chance of more than 10 cm of new snow within 24 hours as a line, each in a plot of its own, as their numbers are of
  // different sizes. Given at the 3-hourly steps only, and the readout says them for those hours alone
  const centimetres = (canonical: number) => shown('length_short', canonical)
  const snowNewSeries = at(snowNewKey)
  const snowDepthSeries = at(snowDepthKey)
  const snowChanceSeries = at(snowChanceKey)
  if (snowNewKey && snowNewSeries && shownPanels.snow) {
    const amounts = points(snowNewSeries)
    // a bar of no height is no element, as in the precipitation: the stamp keeps its point and the readout still says 0
    const unseenAmounts = overWindow(amounts.map(([time, amount]) => [time, amount || null]), SNOW_WINDOW_MS)
    push({
      id: 'snowNew',
      panel: 'snow',
      kind: 'bar',
      tone: 'snowNew',
      name: named('meteogram.chart.seriesSnowNew', 'length_short'),
      hover: t('meteogram.chart.hoverSnowNew'),
      dashed: false,
      width: 0,
      area: false,
      data: unseenAmounts,
      quantity: 'length_short',
      digits: units.digits('length_short'),
    }, unitOfQ('length_short'), 'exact', amounts)
    range.snow = [0, Math.max(centimetres(2), Math.max(0, ...snowNewSeries.y) * 1.15)]
  }
  if (snowDepthKey && snowDepthSeries && shownPanels.snow) {
    push({
      id: 'snowDepth',
      panel: 'snowDepth',
      kind: 'line',
      tone: 'snowDepth',
      name: named('meteogram.chart.seriesSnowDepth', 'length_short'),
      hover: t('meteogram.chart.hoverSnowDepth'),
      dashed: false,
      straight: true,
      width: 2,
      area: true,
      data: breakAtGaps(points(snowDepthSeries)),
      quantity: 'length_short',
      digits: units.digits('length_short'),
    }, unitOfQ('length_short'), 'exact')
    range.snowDepth = [0, Math.max(centimetres(10), Math.max(0, ...snowDepthSeries.y) * 1.15)]
  }
  // the threshold of the chance as the unit of the answer writes it: `10 cm`, `100 mm`
  const chanceAmount = snowChanceAmount(units)
  if (snowChanceKey && snowChanceSeries && shownPanels.snow) {
    push({
      id: 'snowChance',
      panel: 'snowChance',
      kind: 'line',
      tone: 'snowChance',
      name: t('meteogram.chart.seriesSnowChance', { amount: chanceAmount, unit: unitName('fraction') }).trim(),
      hover: t('meteogram.chart.hoverSnowChance', { amount: chanceAmount }),
      dashed: false,
      straight: true,
      width: 1.6,
      area: true,
      data: breakAtGaps(points(snowChanceSeries)),
      quantity: 'fraction',
      digits: units.digits('fraction'),
    }, unitOfQ('fraction'), 'exact')
  }
  range.snow ??= [0, centimetres(2)]
  range.snowDepth ??= [0, centimetres(10)]
  // a chance is the whole of the scale, 0 to 100 %, 0 to 1 or 0 to 8 oktas, as the cloud cover is
  range.snowChance = [0, shown('fraction', 100)]

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
      data: breakAtGaps(points(pressureSeries)),
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
      data: breakAtGaps(points(windSeries)),
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
        data: breakAtGaps(points(gustSeries)),
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
      push({ id, panel: 'cloud', kind: 'line', tone, name, hover, dashed: false, width: 1, area: true, data: breakAtGaps(points(s)), quantity: 'fraction', digits: units.digits('fraction') }, unitOfQ('fraction'))
    }
    layer('cloudHigh', 'cloudHigh', cloudHighKey, named('meteogram.chart.seriesHighClouds', 'fraction'), t('meteogram.chart.hoverHighClouds'))
    layer('cloudMid', 'cloudMid', cloudMidKey, named('meteogram.chart.seriesMidClouds', 'fraction'), t('meteogram.chart.hoverMidClouds'))
    layer('cloudLow', 'cloudLow', cloudLowKey, named('meteogram.chart.seriesLowClouds', 'fraction'), t('meteogram.chart.hoverLowClouds'))
    push({ id: 'cloudTotal', panel: 'cloud', kind: 'line', tone: 'cloudTotal', name: named('meteogram.chart.seriesTotalCloud', 'fraction'), hover: t('meteogram.chart.hoverTotalCloud'), dashed: false, width: 2, area: false, data: breakAtGaps(points(cloudSeries)), quantity: 'fraction', digits: units.digits('fraction') }, unitOfQ('fraction'))
  }

  // the cloud cover's axis is the whole of the scale: 0 to 100 %, 0 to 1, 0 to 8 oktas
  const cloudTop = shown('fraction', 100)
  // a degree and a hectopascal, in the unit of the chart: a degree is 1.8 degrees Fahrenheit, a hectopascal 100 pascals
  const degree = stretch('temperature', 1)
  const hectopascal = stretch('pressure', 1)
  range.cloud = [0, cloudTop]
  range.temp = [tempMinY - degree, tempMaxY + 3 * degree]
  range.pressure = [pressureMin - 2 * hectopascal, pressureMax + 2 * hectopascal]

  // the axes' titles: along their panel, the name on the first line and the unit on its own second line in every panel
  const titleTexts: Record<PanelName, string> = {
    wind: title('meteogram.chart.axisWind', 'speed'),
    precip: title('meteogram.chart.axisPrecip', 'precipitation'),
    cloud: title('meteogram.chart.axisCloud', 'fraction'),
    temp: title('meteogram.chart.axisTemp', 'temperature'),
    pressure: title('meteogram.chart.axisPressure', 'pressure'),
    snow: title('meteogram.chart.axisSnowNew', 'length_short'),
    snowDepth: title('meteogram.chart.axisSnowDepth', 'length_short'),
    // the threshold and "new" on the first line and the unit of the chance on the second, as every other title: the whole words are in the readout and the table
    snowChance: `${t('meteogram.chart.axisSnowChance', { amount: chanceAmount }).trim()}${unitName('fraction').trim() ? `\n${unitName('fraction').trim()}` : ''}`,
  }
  const labelColour: Record<PanelName, AxisSpec['label']> = { wind: 'cyan', precip: 'blue', snow: 'indigo', snowDepth: 'teal', snowChance: 'gold', cloud: 'slate', temp: 'red', pressure: 'lime' }
  const decimalsOf = (panel: PanelName, quantity: Quantity) => ({ wind: Math.min(1, units.digits(quantity)), precip: Math.min(2, units.digits(quantity) + 1), snow: units.digits(quantity), snowDepth: Math.max(0, units.digits(quantity) - 1), snowChance: 0, cloud: 0, temp: 0, pressure: 0 })[panel]
  const quantityOf: Record<PanelName, Quantity> = { wind: 'speed', precip: 'precipitation', snow: 'length_short', snowDepth: 'length_short', snowChance: 'fraction', cloud: 'fraction', temp: 'temperature', pressure: 'pressure' }
  const splitsOf: Record<PanelName, number> = { wind: 3, precip: 2, snow: 2, snowDepth: 2, snowChance: 2, cloud: 2, temp: 3, pressure: 2 }
  const axes: Partial<Record<PanelName, AxisSpec>> = {}
  for (const panel of panels) {
    axes[panel] = {
      panel,
      range: range[panel]!,
      title: titleTexts[panel],
      titleLines: titleTexts[panel].includes('\n') ? 2 : 1,
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
  // a symbol for every stamp of the grid, so that an hour the hourly amount lacks (MOSMIX-S has some) has its symbol, drawn from the
  // weather and the clouds, and no amount, which is not a dry hour (GH-4175)
  const symbolStamps = hasSymbols ? stamps : []
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
    // an hour the forecast gives no amount for has none: it is not a dry hour (GH-4175)
    const amount = precipLookup.get(time)
    const mm = amount === undefined ? null : canon('precipitation', amount)
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
    stamps,
    panels,
    axes,
    series: drawn,
    barbs,
    symbols: hasSymbols ? symbols : [],
    hours,
    days,
    precipChanges,
    freezing: freezing >= range.temp[0] && freezing <= range.temp[1] && panels.includes('temp') ? freezing : null,
    readout,
    weather,
    hasSymbols,
  }
}
