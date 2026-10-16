/**
 * Meteogram utility functions for series alignment, interpolation, and precipitation classification.
 */

/**
 * Find the index of the nearest date to a target timestamp using binary search.
 * @param dates Sorted array of Date objects
 * @param targetMs Target timestamp in milliseconds
 * @returns Index of the nearest date
 */
export function findNearestIndex(dates: Date[], targetMs: number): number {
  if (!dates || dates.length === 0)
    return -1
  let lo = 0
  let hi = dates.length - 1
  if (targetMs <= dates[0]!.getTime())
    return 0
  if (targetMs >= dates[hi]!.getTime())
    return hi
  while (lo <= hi) {
    const mid = Math.floor((lo + hi) / 2)
    const midMs = dates[mid]!.getTime()
    if (midMs === targetMs)
      return mid
    if (midMs < targetMs)
      lo = mid + 1
    else hi = mid - 1
  }
  // lo is first index > target, hi is last index < target
  const leftIdx = Math.max(0, hi)
  const rightIdx = Math.min(dates.length - 1, lo)
  const leftDiff = Math.abs(dates[leftIdx]!.getTime() - targetMs)
  const rightDiff = Math.abs(dates[rightIdx]!.getTime() - targetMs)
  return leftDiff <= rightDiff ? leftIdx : rightIdx
}

/**
 * Linear interpolation for numeric series. Returns value at targetMs or null.
 * @param dates Sorted array of Date objects
 * @param values Corresponding array of numeric values
 * @param targetMs Target timestamp in milliseconds
 * @returns Interpolated value or null
 */
export function interpSeries(dates: Date[], values: number[], targetMs: number): number | null {
  if (!dates || dates.length === 0)
    return null
  const n = dates.length
  if (targetMs <= dates[0]!.getTime())
    return values[0] ?? null
  if (targetMs >= dates[n - 1]!.getTime())
    return values[n - 1] ?? null
  // binary search for right-hand index
  let lo = 0
  let hi = n - 1
  while (lo <= hi) {
    const mid = Math.floor((lo + hi) / 2)
    const midMs = dates[mid]!.getTime()
    if (midMs === targetMs)
      return values[mid] ?? null
    if (midMs < targetMs)
      lo = mid + 1
    else hi = mid - 1
  }
  const i = Math.min(n - 1, lo)
  const j = Math.max(0, i - 1)
  const t0 = dates[j]!.getTime()
  const t1 = dates[i]!.getTime()
  const v0 = values[j] ?? null
  const v1 = values[i] ?? null
  if (v0 === null || v0 === undefined)
    return v1 ?? null
  if (v1 === null || v1 === undefined)
    return v0 ?? null
  const frac = (targetMs - t0) / (t1 - t0)
  return v0 + frac * (v1 - v0)
}

/**
 * Return the value in `values` at the index nearest to `targetMs`.
 */
export function nearestNeighbor(dates: Date[], values: number[], targetMs: number): number | null {
  const idx = findNearestIndex(dates, targetMs)
  if (idx === -1)
    return null
  return values[idx] ?? null
}

/**
 * The hours a maximum or minimum temperature series covers, read from its name: `_last_12h` and the
 * raw `tx6` or `tn12` name it, and MOSMIX's `tx` and `tn` without a number, which the older backend
 * serves as `temperature_air_max_2m` and `temperature_air_min_2m`, cover 12.
 */
export function extremeWindowHours(key: string): number {
  const named = /(?:_last_|^t[xn])(\d+)h?$/.exec(key)
  return named ? Number(named[1]) : 12
}

/**
 * A maximum or minimum, drawn over the hours it covers. MOSMIX gives `tx` and `tn` once for each
 * window, stamped at its end, the maximum or minimum of the hours before it: drawn as a line between
 * those few stamps, as every other series is, the band ran from one window's extreme to the next
 * one's and let the hourly temperature curve out of it, at 23 to 43 of 247 hours of each of six
 * stations by up to 3.2 degrees (GH-2647). Held across its window instead, each value is the bound
 * the temperature stays inside, and the step from one window to the next is where the bound changes.
 *
 * A window is the `windowMs` before its stamp, cut off at the one before it where they overlap and
 * at `fromMs` and `toMs`, the span the chart shows. Each date has one point, the value of the window
 * that ends at or after it, so a hover at the stamp reads the window that ends there, and between a
 * window's ends it has a point at each multiple of `stepMs`, as the curve it is drawn with has, so a
 * hover finds the bound at any hour. Drawn with Plotly's `vh` line shape, each point's value is held
 * back to the point before it and the step is at the stamp. Two windows with a window left out
 * between them (a stamp without a value) are parted by a null, which breaks the line.
 * @param dates Sorted dates of the stamps
 * @param values The extreme stamped at each date
 * @returns The points to draw, with a null value where the line breaks
 */
export function extremeWindowSteps(
  dates: Date[],
  values: number[],
  windowMs: number,
  fromMs: number,
  toMs: number,
  stepMs: number,
): { x: Date[], y: (number | null)[] } {
  const x: Date[] = []
  const y: (number | null)[] = []
  let previousEnd = Number.NEGATIVE_INFINITY
  let lastX = Number.NaN
  for (let i = 0; i < dates.length; i++) {
    const value = values[i]
    const end = dates[i]!.getTime()
    if (value === null || value === undefined || Number.isNaN(value))
      continue
    // the window's own span, open at its start, and what of it the chart shows, closed at both ends:
    // a window whose end is the chart's first moment is shown as that moment alone
    const open = Math.max(end - windowMs, previousEnd)
    previousEnd = end
    if (end < fromMs || open >= toMs || open >= end)
      continue
    const start = Math.max(open, fromMs)
    const stop = Math.min(end, toMs)
    // a window that begins where the one before it ended goes on from its last point; any other,
    // the first or one after a gap, has a point of its own at its start
    if (start !== lastX) {
      if (x.length > 0) {
        // between the two windows' dates, which a date of its own keeps it from being one of theirs
        x.push(new Date((lastX + start) / 2))
        y.push(null)
      }
      x.push(new Date(start))
      y.push(value)
    }
    for (let t = Math.ceil((start + 1) / stepMs) * stepMs; t < stop; t += stepMs) {
      x.push(new Date(t))
      y.push(value)
    }
    if (stop > start) {
      x.push(new Date(stop))
      y.push(value)
    }
    lastX = stop
  }
  return { x, y }
}

/**
 * The cadence the meteogram resamples its series to: hourly, every 3 hours past 5 days.
 */
export function resampleCadenceMs(minTime: number, maxTime: number): number {
  return (maxTime - minTime) / 3_600_000 > 120 ? 3 * 3_600_000 : 3_600_000
}

/**
 * Approximate wet-bulb temperature using Stull (2011) approximation.
 * Valid for T in °C, RH in %.
 * @param T Temperature in Celsius
 * @param RH Relative humidity in percent (0-100)
 * @returns Estimated wet-bulb temperature in Celsius
 */
export function wetBulbApprox(T: number, RH: number): number {
  // T: degC, RH: percent 0-100
  const Tw = T * Math.atan(0.151977 * Math.sqrt(RH + 8.313659))
    + Math.atan(T + RH)
    - Math.atan(RH - 1.676331)
    + 0.00391838 * RH ** 1.5 * Math.atan(0.023101 * RH)
    - 4.686035
  return Tw
}

/**
 * Classify precipitation type based on temperature and optional wet-bulb.
 * @param temperature Temperature in Celsius
 * @param humidity Optional relative humidity (0-100 or 0-1)
 * @returns 'rain' | 'mixed' | 'snow'
 */
export function classifyPrecip(temperature: number, humidity?: number): 'rain' | 'mixed' | 'snow' {
  let tw = temperature

  if (humidity !== undefined) {
    let rhPct = humidity
    // Normalize to percent if needed
    if (rhPct <= 1)
      rhPct = rhPct * 100
    tw = wetBulbApprox(temperature, rhPct)
  }

  if (tw <= 0.5)
    return 'snow'
  if (tw <= 2.0)
    return 'mixed'
  return 'rain'
}

/**
 * The parameter names each meteogram series is drawn from, in order of preference: the first one
 * found among the values wins, and a series none of them matches is left out without an error.
 * Each list leads with a canonical name: for a series the meteogram's MOSMIX request carries, the
 * name it comes back under. `tests/unit/meteogram.test.ts` holds that first choice to the app
 * glossary, so a canonical rename that misses this table fails a test instead of losing a panel.
 * The names after it are other canonical names, or raw and older names carried over from before;
 * the test does not check them.
 */
export const METEOGRAM_SERIES = {
  weather: ['weather_significant', 'significant_weather', 'ww', 'weather'],
  precipitation: ['precipitation_amount_significant_weather_last_1h', 'precipitation_amount_last_1h', 'rr1', 'rr1c'],
  temperature: ['temperature_air_2m', 'temperature_air_mean_2m', 'ttt'],
  temperatureMax: ['temperature_air_max_2m_last_12h', 'temperature_air_max_2m', 'tx', 'tx12', 'tx6'],
  temperatureMin: ['temperature_air_min_2m_last_12h', 'temperature_air_min_2m', 'tn', 'tn12', 'tn6'],
  dewPoint: ['temperature_dew_point_2m', 'temperature_dew_point_mean_2m', 'dew_point', 'td', 'tdt', 'dew_point_2m'],
  humidity: ['humidity_relative', 'relative_humidity', 'rh', 'r'],
  windSpeed: ['wind_speed', 'ff'],
  windDirection: ['wind_direction', 'dd'],
  gust: ['wind_gust_max_last_1h', 'wind_gust_max', 'wind_gust', 'ffx', 'fx', 'wind_gust_max_last_3h', 'fx1', 'fx3'],
  cloudCover: ['cloud_cover_total', 'n'],
  cloudCoverLow: ['cloud_cover_below_2km', 'nl'],
  cloudCoverMid: ['cloud_cover_between_2km_and_7km', 'cloud_cover_2_7km', 'nm'],
  cloudCoverHigh: ['cloud_cover_above_7km', 'nh'],
  pressure: ['pressure_air_sea_level', 'pressure_air_site_reduced', 'air_pressure_at_sea_level', 'mslp', 'pressure', 'pmsl', 'pressure_mean', 'pppp'],
} as const satisfies Record<string, readonly string[]>

/**
 * The settings the meteogram's `/api/values` request sends, so that its answer comes in the layout
 * the meteogram reads whatever the server sets in its `WD_TS_*` variables: long rows keyed by the
 * canonical names of `METEOGRAM_SERIES`, every station kept, and values in the units the charts
 * label them in. `unit_targets` names each quantity the meteogram draws: the server's
 * `WD_TS_UNIT_TARGETS` entries are merged into the ones a request gives, so only a quantity the
 * request names is sure of its unit. The cloud cover's `decimal` is the default, which the charts
 * scale to percent.
 */
export const METEOGRAM_VALUES_SETTINGS = {
  shape: 'long',
  humanize: 'true',
  convert_units: 'true',
  unit_targets: JSON.stringify({
    angle: 'degree',
    fraction: 'decimal',
    precipitation: 'millimeter',
    pressure: 'hectopascal',
    speed: 'meter_per_second',
    temperature: 'degree_celsius',
  }),
  skip_empty: 'false',
} as const satisfies Record<string, string>
