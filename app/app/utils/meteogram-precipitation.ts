/**
 * The precipitation of a MOSMIX forecast, as blocks of the hours each covers (GH-4175).
 *
 * MOSMIX-L gives the amount of rain four times, over windows of 1, 6, 12 and 24 hours (`RR1c`, `RR6c`, `RRhc`, `RRdc`), each stamped at the
 * end of its window. The windows nest, and so the four give the same rain: over the first days the sum of the hourly amounts of a
 * 24 hour window is within 3 % of `RRdc`. But the finer the window, the more of the rain a late day loses: from about 100 hours into a
 * run the hourly amount is 0.0 for most hours, where `RR6c` has some of the rain and `RRhc` and `RRdc` all of it (measured on twelve
 * runs of four stations: `tests/unit/meteogram-precipitation.test.ts`). The zeros are real values, not missing ones, and a chart that
 * reads only the hourly amount shows days 6 to 10 dry where DWD's own 24 hour total has 1 to 2 mm.
 *
 * So the amount of each window of the coarsest total is taken from the finest series that still accounts for it: the hourly
 * amounts while their sum is within rounding of the coarse total, then the 6 hour totals, then the 12 hour ones, then the 24 hour
 * one, and once a window has gone to coarser totals the later ones never go back to finer ones. A plan is those blocks, in time
 * order, and where the cadence changes. What it picks depends on what the series agree on, and never on how much rain there is: a
 * dry window (a total of 0.3 mm or less) is the same in every series and so takes the cadence the window before it had.
 */
import type { SeriesMap } from './meteogram-series'
import { METEOGRAM_SERIES } from './meteogram'
import { findFirstAvailable } from './meteogram-series'

const HOUR_MS = 3_600_000

/** The amount over one window, in the unit of the series: `start` is the open end of the window, `end` the stamp */
export interface PrecipBlock {
  start: number
  end: number
  /** the hours the amount covers */
  hours: number
  amount: number
}

/** Where a block of another cadence than the one before it begins */
export interface PrecipChange {
  at: number
  hours: number
}

export interface PrecipPlan {
  /** in time order, none over another */
  blocks: PrecipBlock[]
  changes: PrecipChange[]
  /** the hours of the longest block */
  longest: number
}

/**
 * How far a sum of finer amounts may fall short of the coarse total and still agree with it. The amounts are rounded to 0.1 mm, so a
 * sum of n of them and the total they are compared with are off by two standard deviations of n + 1 roundings, `AGREE_ROUNDING_MM`
 * times the square root of n + 1 (0.3 mm for the 24 hourly amounts of a day, 0.13 for four 6 hour ones, 0.1 for two 12 hour ones), and
 * the hourly amounts of a rainy day run up to 3.5 % under or over `RRdc`, hence `AGREE_SHARE` of the total as well.
 */
export const AGREE_ROUNDING_MM = 0.06
export const AGREE_SHARE = 0.05
/** A window whose total is no more than this is dry: the rounding says nothing of it, every series agrees with it, and it keeps the cadence of the window before */
export const TRACE_MM = 0.3

interface Level {
  hours: number
  at: Map<number, number>
}

const LEVELS = [
  { hours: 1, names: METEOGRAM_SERIES.precipitation },
  { hours: 6, names: METEOGRAM_SERIES.precipitation6h },
  { hours: 12, names: METEOGRAM_SERIES.precipitation12h },
  { hours: 24, names: METEOGRAM_SERIES.precipitation24h },
] as const

/** The series of each cadence the forecast has, finest first */
function levelsOf(series: SeriesMap): Level[] {
  const available = new Set(series.keys())
  return LEVELS.flatMap(({ hours, names }) => {
    const key = findFirstAvailable(names, available)
    const s = key ? series.get(key) : undefined
    return s?.x.length ? [{ hours, at: new Map(s.x.map((date, i) => [date.getTime(), s.y[i]!])) }] : []
  })
}

/** The stamps of a cadence in the window ending at `end`, first to last */
function stampsIn(hours: number, start: number, end: number): number[] {
  const out: number[] = []
  for (let stamp = start + hours * HOUR_MS; stamp <= end; stamp += hours * HOUR_MS)
    out.push(stamp)
  return out
}

/**
 * The precipitation blocks of a forecast, where the cadence of each stretch is the finest one whose amounts account for the coarsest
 * series' total over it (see the top of the file); null where the forecast has no precipitation at all.
 *
 * The coarsest series gives the windows. A window that begins before the run does (the first 24 hour window of a run issued at
 * 03 UTC begins at 06 UTC the day before) cannot be compared with hours the run has none of, so the stretch before the first whole
 * window has the hourly amounts, as the first hours of a run are reliable. After the last window, the hours are of the cadence the
 * last window had: hourly amounts go on, and a coarse cadence ends where its last total does, so that the hourly zeros after it are not
 * read as dry hours.
 *
 * A series that gives a window only in part (an hour missing) is no candidate for it, and the missing hour is never made a 0.
 * @param series The forecast's series
 * @param canon Converts an amount to millimetres, in which the agreement is judged
 */
export function planPrecipitation(series: SeriesMap, canon: (amount: number) => number = amount => amount): PrecipPlan | null {
  const levels = levelsOf(series)
  if (!levels.length)
    return null
  const hourly = levels[0]!.hours === 1 ? levels[0]! : null
  const anchor = levels[levels.length - 1]!
  const blocks: PrecipBlock[] = []
  const block = (level: Level, end: number): PrecipBlock => ({ start: end - level.hours * HOUR_MS, end, hours: level.hours, amount: level.at.get(end)! })
  const hourlyBlocks = (from: number, to: number) => {
    for (const end of [...(hourly?.at.keys() ?? [])].sort((a, b) => a - b)) {
      if (end - HOUR_MS >= from && end <= to)
        blocks.push(block(hourly!, end))
    }
  }

  // the first hour whose amount the run gives: the hourly amounts are the run's own, and a window that began before it is not compared
  const runStart = hourly ? Math.min(...hourly.at.keys()) - HOUR_MS : Number.NEGATIVE_INFINITY
  if (anchor.hours === 1) {
    hourlyBlocks(Number.NEGATIVE_INFINITY, Number.POSITIVE_INFINITY)
    return finish(blocks)
  }

  const windows = [...anchor.at.keys()].filter(end => end - anchor.hours * HOUR_MS >= runStart).sort((a, b) => a - b)
  if (hourly)
    hourlyBlocks(runStart, windows.length ? windows[0]! - anchor.hours * HOUR_MS : Number.POSITIVE_INFINITY)
  let previous = hourly ? 1 : null
  for (const end of windows) {
    const start = end - anchor.hours * HOUR_MS
    const total = canon(anchor.at.get(end)!)
    // the series that give the whole window and agree with its total, finest first; the coarsest series itself always does
    const agreeing: { level: Level, sum: number }[] = []
    for (const level of levels.slice(0, -1)) {
      const stamps = stampsIn(level.hours, start, end)
      if (!stamps.every(stamp => level.at.has(stamp)))
        continue
      const sum = stamps.reduce((sum, stamp) => sum + canon(level.at.get(stamp)!), 0)
      const tolerance = AGREE_ROUNDING_MM * Math.sqrt(stamps.length + 1) + AGREE_SHARE * total
      if (total <= TRACE_MM || sum >= total - tolerance)
        agreeing.push({ level, sum })
    }
    agreeing.push({ level: anchor, sum: total })
    // Once coarser, always: a window never goes back to finer blocks than the window before it had, so the panel changes its cadence at
    // most three times and the late days are of one kind. A dry window (a total of `TRACE_MM` or less) is the same in every series, so
    // it takes the cadence of the window before it, or the finest one that is complete where it is the first
    const pool = previous !== null && previous > 1 ? agreeing.filter(candidate => candidate.level.hours >= previous!) : agreeing
    const chosen = pool[0]!
    for (const stamp of stampsIn(chosen.level.hours, start, end))
      blocks.push(block(chosen.level, stamp))
    previous = chosen.level.hours
  }

  // after the last window: the cadence the last window had, for as far as its series goes
  const last = windows.length ? windows[windows.length - 1]! : null
  if (last !== null && previous !== null) {
    const level = levels.find(candidate => candidate.hours === previous)!
    for (const end of [...level.at.keys()].sort((a, b) => a - b)) {
      if (end - level.hours * HOUR_MS >= last)
        blocks.push(block(level, end))
    }
  }
  return finish(blocks)
}

function finish(blocks: PrecipBlock[]): PrecipPlan | null {
  if (!blocks.length)
    return null
  blocks.sort((a, b) => a.end - b.end)
  const changes: PrecipChange[] = []
  blocks.forEach((block, i) => {
    if (i > 0 && block.hours !== blocks[i - 1]!.hours)
      changes.push({ at: block.start, hours: block.hours })
  })
  return { blocks, changes, longest: Math.max(...blocks.map(block => block.hours)) }
}

/** What a plan holds of a span of time (`from` to `to`, ms), the amount of each block shared out evenly over its hours */
export interface PrecipOver {
  /** in the unit of the series; null where the plan gives no hour of the span */
  amount: number | null
  /** the hours of the span the plan gives an amount for */
  given: number
  /** the hours of the longest block that adds to the amount: 1 where every hour is its own amount */
  longest: number
  /** the hours of the span, between the plan's first and last, that it gives no amount for (a missing amount is not a 0) */
  missing: number
}

/**
 * The amount over a span of time: each block adds its amount by the share of its hours that lie in the span. A block cut by the span
 * (a 6 hour block over a local midnight) is cut evenly, which is all the block says of where in its hours the rain falls. The hours of
 * the span that the plan has no block for are not 0: they are counted as `missing`, but only between its first block and its last,
 * since a forecast that ends before the span does is `partial` for that, not for a missing amount.
 */
export function precipitationOver(plan: PrecipPlan, from: number, to: number): PrecipOver {
  let amount = 0
  let given = 0
  let longest = 0
  for (const block of plan.blocks) {
    const overlap = Math.min(block.end, to) - Math.max(block.start, from)
    if (overlap <= 0)
      continue
    amount += block.amount * (overlap / (block.hours * HOUR_MS))
    given += overlap / HOUR_MS
    longest = Math.max(longest, block.hours)
  }
  const first = plan.blocks[0]!.start
  const last = plan.blocks[plan.blocks.length - 1]!.end
  const inside = Math.max(0, Math.min(to, last) - Math.max(from, first)) / HOUR_MS
  const missing = Math.max(0, inside - given)
  return { amount: given > 0 ? amount : null, given, longest, missing: missing < 1e-6 ? 0 : missing }
}

/** The sum of the plan's amounts: the rain of the whole run, and the hours of its blocks it has no amount for */
export function precipitationTotal(plan: PrecipPlan): { amount: number, missing: number } {
  return {
    amount: plan.blocks.reduce((sum, block) => sum + block.amount, 0),
    missing: precipitationOver(plan, plan.blocks[0]!.start, plan.blocks[plan.blocks.length - 1]!.end).missing,
  }
}
