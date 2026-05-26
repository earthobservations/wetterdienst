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
