/**
 * The thunderstorm band of the forecast (GH-4090): the hours in which MOSMIX gives a thunderstorm a probability worth showing.
 *
 * The element is `wwT` (`probability_thunder_last_1h`): the probability, in whole percent, that a thunderstorm occurs within the hour
 * before the stamp, given for every hour of MOSMIX-L from +1 h to +247 h (measured on the runs of 2026-11-17, `docs/_ext/mosmix_cadence.py`
 * in the backend). It does not thin out late in the run, as the 6, 12 and 24 h probabilities (`wwT6`, `wwTh`, `wwTd`) do: `wwT6` goes from
 * hourly to every third hour at some stations, `wwTh` is given every 6 hours and `wwTd` every 12. It does not fall to a zero tail, as the
 * hourly rain amount does (GH-4175), either: its values stay a real probability to the last step. So the band is drawn from the hourly
 * element alone, an hour for each hour, and the coarser ones are not asked for.
 *
 * A plain function of the series, with no chart library and no DOM, so that tests hold what is drawn.
 */
import type { SeriesMap } from './meteogram-series'
import { METEOGRAM_SERIES } from './meteogram'
import { HOUR_MS } from './meteogram-geometry'
import { findFirstAvailable } from './meteogram-series'

/**
 * The least probability, in percent, of an hour that is drawn. MOSMIX writes whole percents and gives 1 % on hours of a week with no
 * thunderstorm in sight (5 and 14 of the 247 hours of the two stations of the run of 2026-11-17, whose highest hour is 1 %), so a band that
 * drew every hour with a value would be marks of no news. From 10 % on, an hour is one a forecaster would mention.
 */
export const THUNDER_THRESHOLD = 10

/**
 * Where the shades step up, in percent: from 10, from 30 and from 60. The height of a bar says the probability to the percent, the shade
 * says the class, so the two cues agree and neither is the colour alone (WCAG 1.4.1).
 */
export const THUNDER_LEVELS = [10, 30, 60] as const
export type ThunderLevel = 1 | 2 | 3

/** The class of a probability in percent: 0 under the threshold, then 1, 2 or 3 */
export function thunderLevel(percent: number): ThunderLevel | 0 {
  if (percent >= THUNDER_LEVELS[2])
    return 3
  if (percent >= THUNDER_LEVELS[1])
    return 2
  return percent >= THUNDER_LEVELS[0] ? 1 : 0
}

/** One hour of the band: the window it covers (the hour before its stamp, which DWD writes it at) and its probability */
export interface ThunderCell {
  start: number
  end: number
  /** the probability in the unit of the answer, as the readout writes it */
  value: number
  /** the same in percent, which the classes are of */
  percent: number
  level: ThunderLevel
}

export interface ThunderPlan {
  /** the hours of the probability of `THUNDER_THRESHOLD` or more, in time order */
  cells: ThunderCell[]
  /** the likeliest of them (the first of equals) */
  peak: ThunderCell
}

/**
 * The band the forecast has for thunderstorms: each hour of the hourly probability that reaches the threshold, over the hour it covers.
 * Null where the forecast has no such series or no hour reaches it, so that there is no panel (a calm chart: no thunderstorm risk, no row).
 * @param series The forecast's series
 * @param percentOf A value of the answer, in percent
 * @param until Only the hours that begin before this moment (ms) count: the horizon the chart shows
 */
export function planThunder(series: SeriesMap, percentOf: (value: number) => number, until = Number.POSITIVE_INFINITY): ThunderPlan | null {
  const key = findFirstAvailable(METEOGRAM_SERIES.thunder, new Set(series.keys()))
  const source = key ? series.get(key) : undefined
  if (!source)
    return null
  const cells: ThunderCell[] = []
  source.x.forEach((date, i) => {
    const value = source.y[i]!
    const percent = percentOf(value)
    const level = thunderLevel(percent)
    const end = date.getTime()
    if (!level || !Number.isFinite(percent) || end - HOUR_MS >= until)
      return
    cells.push({ start: end - HOUR_MS, end, value, percent, level })
  })
  if (!cells.length)
    return null
  return { cells, peak: cells.reduce((best, cell) => cell.percent > best.percent ? cell : best) }
}

/** Whether the forecast has the hourly probability at all, which a panel that is on lists in the table whether or not an hour reaches the threshold */
export function hasThunderSeries(series: SeriesMap): boolean {
  return findFirstAvailable(METEOGRAM_SERIES.thunder, new Set(series.keys())) !== undefined
}
