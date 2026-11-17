/**
 * What the meteogram says in words and numbers besides the chart: the summary row, and the table of the values the
 * chart draws with the sentence that describes it (WCAG 1.1.1, 1.3.1).
 */
import type { PanelToggle } from './meteogram-geometry'
import type { SeriesMap } from './meteogram-series'
import type { MeteogramUnits, Translate } from './meteogram-units'
import { DateTime } from 'luxon'
import { formatNumber } from './format'
import { METEOGRAM_SERIES } from './meteogram'
import { planPrecipitation, precipitationTotal } from './meteogram-precipitation'
import { findFirstAvailable } from './meteogram-series'
import { snowChanceAmount } from './meteogram-units'
import { withUnit } from './units'

export interface MeteogramSummary {
  temp: { min: string, max: string } | null
  /** `atLeast`: some hours of the run have no amount, which are not 0, so the total is the least the forecast says */
  precip: { value: string, unit: string, atLeast: boolean }
  gust: { value: string, unit: string }
  cloud: { value: string, unit: string }
  pressure: { range: string, unit: string } | null
}

/** The minimum and maximum temperature, the largest gust, the rain, the mean cloud cover and the pressure range of the run */
export function meteogramSummary(series: SeriesMap, units: MeteogramUnits, locale: string): MeteogramSummary | null {
  if (!series.size)
    return null
  const available = new Set(series.keys())
  const valid = (key: string | undefined) => (key ? series.get(key)?.y ?? [] : []).filter(v => v !== null && !Number.isNaN(v))

  const temperatures = valid(findFirstAvailable(METEOGRAM_SERIES.temperature, available))
  const minTemp = temperatures.length ? Math.min(...temperatures) : Number.POSITIVE_INFINITY
  const maxTemp = temperatures.length ? Math.max(...temperatures) : Number.NEGATIVE_INFINITY
  // the rain of the run: the sum of the blocks that account for MOSMIX's totals (`planPrecipitation`), where the hourly amount alone left the late days dry
  const plan = planPrecipitation(series, amount => units.canon('precipitation', amount))
  const runEnd = Math.max(...[...series.values()].flatMap(s => s.x.map(d => d.getTime())))
  const totalPrecip = plan ? precipitationTotal(plan, runEnd) : { amount: 0, missing: 0 }
  const maxGust = Math.max(0, ...valid(findFirstAvailable(METEOGRAM_SERIES.gust, available)))
  const clouds = valid(findFirstAvailable(METEOGRAM_SERIES.cloudCover, available))
  const avgCloud = clouds.length ? clouds.reduce((sum, v) => sum + v, 0) / clouds.length : 0
  const pressures = valid(findFirstAvailable(METEOGRAM_SERIES.pressure, available))
  const minPres = pressures.length ? Math.min(...pressures) : Number.POSITIVE_INFINITY
  const maxPres = pressures.length ? Math.max(...pressures) : Number.NEGATIVE_INFINITY

  // a whole number is written plain, as it was (`1013`, not `1,013`), a fraction with the language's separator
  const rounded = (value: number, places: number) => places === 0 ? String(Math.round(value)) : formatNumber(value, locale, places)
  const temperature = units.unitOf('temperature')
  const pressureDigits = Math.max(0, units.digits('pressure') - 1)
  return {
    // the lower end has a degree sign where the unit has one (`10° / 14°C`), and none where it has not (`283 / 287 K`)
    temp: Number.isFinite(minTemp)
      ? {
          min: temperature.startsWith('°') ? `${Math.round(minTemp)}°` : String(Math.round(minTemp)),
          max: withUnit(String(Math.round(maxTemp)), temperature),
        }
      : null,
    precip: { value: rounded(totalPrecip.amount, 1), unit: units.unitName('precipitation'), atLeast: totalPrecip.missing > 0 },
    gust: { value: rounded(maxGust, 1), unit: units.unitName('speed') },
    // nothing after a number that is a decimal, as everywhere a number is written with its unit
    cloud: { value: rounded(avgCloud, units.digits('fraction')), unit: units.unitOf('fraction') === '-' ? '' : units.unitName('fraction') },
    pressure: Number.isFinite(minPres) ? { range: `${rounded(minPres, pressureDigits)}–${rounded(maxPres, pressureDigits)}`, unit: units.unitName('pressure') } : null,
  }
}

/** The table's columns of the rain as the chart draws it: the amount of each block, and the hours it covers */
const PLAN_AMOUNT = 'precipitation (blocks)'
const PLAN_HOURS = 'precipitation (hours of a block)'

export interface MeteogramTable {
  columns: string[]
  rows: string[][]
  summary: string
}

export interface TableContext {
  panels: Record<PanelToggle, boolean>
  /** the hours of the run that are shown, from its start; null for all of it */
  horizonHours: number | null
  zone: string
  formatLanguage: string
  locale: string
  units: MeteogramUnits
  t: Translate
  /** the widget has the table below the chart, the page chooses it with the view control above */
  widget: boolean
}

/**
 * What the chart draws, as a table and a sentence: the panels that are shown, one column for each series they plot, one
 * row for each time the forecast has a value, as far as the horizon chosen reaches. The values are the forecast's own, in
 * the units the answer reports them in, not the chart's resampled curve.
 */
export function meteogramTable(series: SeriesMap, { panels, horizonHours, zone, formatLanguage, locale, units, t, widget }: TableContext): MeteogramTable | null {
  if (!series.size)
    return null
  const { named, digits, unitName } = units
  // The rain is the blocks the chart draws (`planPrecipitation`), one value at the end of each: the hourly amounts while they carry
  // the rain, then the 6, 12 or 24 hour totals, with a column that says how many hours each covers where there are any
  const plan = planPrecipitation(series, amount => units.canon('precipitation', amount))
  const withPlan: SeriesMap = new Map(series)
  if (plan) {
    withPlan.set(PLAN_AMOUNT, { x: plan.blocks.map(block => new Date(block.end)), y: plan.blocks.map(block => block.amount) })
    if (plan.longest > 1)
      withPlan.set(PLAN_HOURS, { x: plan.blocks.map(block => new Date(block.end)), y: plan.blocks.map(block => block.hours) })
  }
  const available = new Set(withPlan.keys())
  const pick = (names: readonly string[]) => findFirstAvailable(names, available)
  const specs: { shown: boolean, key: string | undefined, label: string, digits: number, main?: boolean }[] = [
    { shown: panels.temp, key: pick(METEOGRAM_SERIES.temperature), label: named('meteogram.chart.seriesTemperature', 'temperature'), digits: digits('temperature'), main: true },
    { shown: panels.temp, key: pick(METEOGRAM_SERIES.temperatureMax), label: named('meteogram.chart.seriesMaxTemp', 'temperature'), digits: digits('temperature') },
    { shown: panels.temp, key: pick(METEOGRAM_SERIES.temperatureMin), label: named('meteogram.chart.seriesMinTemp', 'temperature'), digits: digits('temperature') },
    { shown: panels.temp, key: pick(METEOGRAM_SERIES.dewPoint), label: `${t('meteogram.chart.seriesDewPoint')} ${unitName('temperature')}`, digits: digits('temperature') },
    { shown: panels.wind, key: pick(METEOGRAM_SERIES.windSpeed), label: named('meteogram.chart.seriesWind', 'speed'), digits: digits('speed') },
    { shown: panels.wind, key: pick(METEOGRAM_SERIES.windDirection), label: `${t('meteogram.chart.seriesDirection')} ${unitName('angle')}`, digits: digits('angle') },
    { shown: panels.wind, key: pick(METEOGRAM_SERIES.gust), label: named('meteogram.chart.seriesWindGust', 'speed'), digits: digits('speed') },
    { shown: panels.precip, key: pick([PLAN_AMOUNT]), label: `${t('meteogram.chart.panelPrecipitation')} ${unitName('precipitation')}`, digits: digits('precipitation') },
    { shown: panels.precip, key: pick([PLAN_HOURS]), label: t('meteogram.chart.tableBlockHours'), digits: 0 },
    // the snow forecast (GH-4091), whose steps are the 3-hourly ones: a row of another hour has a dash
    { shown: panels.snow, key: pick(METEOGRAM_SERIES.snowNew), label: named('meteogram.chart.seriesSnowNew', 'length_short'), digits: digits('length_short') },
    { shown: panels.snow, key: pick(METEOGRAM_SERIES.snowDepth), label: named('meteogram.chart.seriesSnowDepth', 'length_short'), digits: digits('length_short') },
    { shown: panels.snow, key: pick(METEOGRAM_SERIES.snowChance), label: t('meteogram.chart.seriesSnowChance', { amount: snowChanceAmount(units), unit: unitName('fraction') }).trim(), digits: digits('fraction') },
    { shown: panels.cloud, key: pick(METEOGRAM_SERIES.cloudCover), label: named('meteogram.chart.seriesTotalCloud', 'fraction'), digits: digits('fraction') },
    { shown: panels.cloud, key: pick(METEOGRAM_SERIES.cloudCoverLow), label: named('meteogram.chart.seriesLowClouds', 'fraction'), digits: digits('fraction') },
    { shown: panels.cloud, key: pick(METEOGRAM_SERIES.cloudCoverMid), label: named('meteogram.chart.seriesMidClouds', 'fraction'), digits: digits('fraction') },
    { shown: panels.cloud, key: pick(METEOGRAM_SERIES.cloudCoverHigh), label: named('meteogram.chart.seriesHighClouds', 'fraction'), digits: digits('fraction') },
    { shown: panels.pressure, key: pick(METEOGRAM_SERIES.pressure), label: named('meteogram.chart.seriesPressure', 'pressure'), digits: digits('pressure') },
  ]
  const columns = specs.filter((spec): spec is typeof spec & { key: string } => spec.shown && spec.key !== undefined)
  if (!columns.length)
    return null

  const firstTime = Math.min(...[...series.values()].flatMap(s => s.x.map(d => d.getTime())))
  const lastShown = horizonHours !== null ? firstTime + horizonHours * 3_600_000 : Number.POSITIVE_INFINITY
  // a block that begins within the horizon is a row of the table, as the chart draws it, though its stamp is after it
  const blocksShown = new Set((plan?.blocks ?? []).filter(block => block.start < lastShown).map(block => block.end))
  const byTime = new Map<number, (number | null)[]>()
  columns.forEach((column, index) => {
    const s = withPlan.get(column.key)!
    const ofPlan = column.key === PLAN_AMOUNT || column.key === PLAN_HOURS
    s.x.forEach((date, i) => {
      const ms = date.getTime()
      if (ms > lastShown && !(ofPlan && blocksShown.has(ms)))
        return
      const row = byTime.get(ms) ?? Array.from<number | null>({ length: columns.length }).fill(null)
      row[index] = s.y[i]!
      byTime.set(ms, row)
    })
  })
  const times = [...byTime.keys()].sort((a, b) => a - b)
  if (!times.length)
    return null

  const writeTime = (ms: number) => DateTime.fromMillis(ms, { zone }).setLocale(formatLanguage).toLocaleString(DateTime.DATETIME_SHORT)
  const main = columns.findIndex(column => column.main)
  const temperatures = main < 0 ? [] : times.map(ms => byTime.get(ms)![main]).filter((v): v is number => v !== null && v !== undefined)
  return {
    columns: [t('meteogram.chart.tableTime', { zone }), ...columns.map(column => column.label)],
    // written when it is read: the table of the values is a view of its own, and the chart's sentence needs no row
    get rows() {
      return times.map(ms => [
        writeTime(ms),
        ...byTime.get(ms)!.map((value, index) => value === null ? '–' : formatNumber(value, locale, columns[index]!.digits)),
      ])
    },
    summary: [
      t('meteogram.chart.summaryRange', { from: writeTime(times[0]!), to: writeTime(times.at(-1)!) }),
      ...(temperatures.length
        ? [t('meteogram.chart.summaryTemperature', { min: formatNumber(Math.min(...temperatures), locale, 1), max: formatNumber(Math.max(...temperatures), locale, 1), unit: unitName('temperature') })]
        : []),
      // the page chooses the table with the view control above the chart; the widget has the table below it
      widget ? t('common.chartTableHint') : t('meteogram.chart.summaryTableHint'),
    ].join(' '),
  }
}
