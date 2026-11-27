import { describe, expect, it } from 'vitest'
import { EMPTY_CHART_THEME } from '../../app/utils/chart-theme'
import { durationLabel, KOSTRA_DURATIONS, parseKostra } from '../../app/utils/kostra'
import { buildKostraOption, curveColour, kostraHeight, kostraReadoutRows, kostraTicks, nearestDurationIndex, pixelOfDuration, xOfDuration } from '../../app/utils/kostra-option'
import { depthOf, kostraAnswer } from '../helpers/kostra-answer'

// The option of the Heavy-rainfall chart (GH-4500): one curve for each return period, a logarithmic duration axis labelled in min, h and d.

function t(key: string, named: Record<string, unknown> = {}) {
  return ({ 'kostra.duration.minutes': `${named.n} min`, 'kostra.duration.hours': `${named.n} h`, 'kostra.duration.days': `${named.n} d` })[key] ?? key
}
const table = parseKostra(kostraAnswer())!

/** The option as a plain object: the test reads it by the ids and the keys ECharts takes, which its union of series does not offer */
interface Loose { series: any[], xAxis: any, yAxis: any }
function option(overrides: Partial<Parameters<typeof buildKostraOption>[0]> = {}): Loose {
  return buildKostraOption({
    table,
    quantity: 'depth',
    theme: { ...EMPTY_CHART_THEME, paper: 'rgb(255, 255, 255)' },
    width: 800,
    height: 360,
    cursor: null,
    format: (value, digits) => value.toFixed(digits),
    durationLabel: minutes => durationLabel(minutes, t),
    ...overrides,
  }) as Loose
}

describe('the curves', () => {
  it('are nine, one for each return period, named by it', () => {
    const { series } = option()
    expect(series.map(item => item.id)).toEqual(['curve-1', 'curve-2', 'curve-3', 'curve-5', 'curve-10', 'curve-20', 'curve-30', 'curve-50', 'curve-100'])
    expect(series.map(item => item.name)).toEqual(['1', '2', '3', '5', '10', '20', '30', '50', '100'])
  })

  it('have a point for each of the 22 durations, at the logarithm of its minutes, and the depth of the table', () => {
    const curve = option().series.find(item => item.id === 'curve-100')!
    expect(curve.data).toHaveLength(22)
    expect(curve.data[0]).toEqual([Math.log10(5), depthOf(5, 100)])
    expect(curve.data.at(-1)).toEqual([Math.log10(10080), depthOf(10080, 100)])
  })

  it('rise with the duration, and the longer the return period the higher the curve', () => {
    const { series } = option()
    for (const curve of series) {
      const depths = curve.data.map((point: number[]) => point[1] as number)
      expect([...depths].sort((a, b) => a - b)).toEqual(depths)
    }
    for (let i = 1; i < 9; i++) {
      series[i]!.data.forEach((point: number[], at: number) => expect(point[1] as number).toBeGreaterThan(series[i - 1]!.data[at]![1] as number))
    }
  })

  it('draw the intensity when that is the quantity: the same curves with the intensity of the table', () => {
    const curve = option({ quantity: 'intensity' }).series.find(item => item.id === 'curve-1')!
    const entry = table.rows[0]![0]!
    expect(curve.data[0]![1]).toBe(entry.intensity)
    expect(curve.data[0]![1]).not.toBe(entry.depthMm)
  })

  it('leave a gap where DWD gives no value, and no zero', () => {
    const gappy = parseKostra(kostraAnswer({ missing: [[60, 100]] }))!
    const curve = option({ table: gappy }).series.find(item => item.id === 'curve-100')!
    expect(curve.data[KOSTRA_DURATIONS.indexOf(60)]).toEqual([Math.log10(60), null])
  })

  it('are one hue in the order of the return periods, in the colours of the scheme', () => {
    const light = option().series.slice(0, 9).map(item => item.lineStyle.color)
    expect(light).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8].map(index => curveColour(index, false)))
    const dark = option({ theme: { ...EMPTY_CHART_THEME, dark: true } }).series.slice(0, 9).map(item => item.lineStyle.color)
    expect(dark).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8].map(index => curveColour(index, true)))
    expect(dark).not.toEqual(light)
  })
})

describe('the axes', () => {
  it('has the duration on a logarithmic scale from 5 minutes to 7 days', () => {
    const { xAxis } = option()
    expect(xAxis.min).toBeCloseTo(Math.log10(5))
    expect(xAxis.max).toBeCloseTo(Math.log10(10080))
  })

  it('is labelled in min, h and d at ticks of its own: 5 min, 15 min, 1 h, 6 h, 1 d and 7 d on a wide chart', () => {
    const { xAxis } = option({ width: 800 })
    const labels = xAxis.axisLabel.customValues.map((value: number) => xAxis.axisLabel.formatter(value))
    expect(labels).toEqual(['5 min', '15 min', '1 h', '6 h', '1 d', '7 d'])
    expect(xAxis.axisTick.customValues).toEqual(xAxis.axisLabel.customValues)
  })

  it('is labelled at fewer ticks on a phone, where 5 and 15 minutes would run together', () => {
    const { xAxis } = option({ width: 360 })
    expect(xAxis.axisLabel.customValues.map((value: number) => xAxis.axisLabel.formatter(value))).toEqual(['5 min', '1 h', '6 h', '1 d', '7 d'])
    expect(kostraTicks(519)).toHaveLength(5)
    expect(kostraTicks(520)).toHaveLength(6)
  })

  it('has the quantity on a linear axis that starts at 0, its numbers written as the page writes them', () => {
    const { yAxis } = option({ format: value => `<${value}>` })
    expect(yAxis.type).toBe('value')
    expect(yAxis.min).toBe(0)
    expect(yAxis.axisLabel.formatter(120)).toBe('<120>')
  })

  it('is lower on a phone than on a desktop', () => {
    expect(kostraHeight(360)).toBeLessThan(kostraHeight(800))
  })
})

describe('the crosshair', () => {
  it('is none until a duration is read', () => {
    expect(option().series).toHaveLength(9)
  })

  it('is a line at the duration and a mark on each curve in the curve\'s colour', () => {
    const index = KOSTRA_DURATIONS.indexOf(60)
    const { series } = option({ cursor: index })
    expect(series).toHaveLength(11)
    const line = series.find(item => item.id === 'cursor-line')!
    expect(line.data[0]).toEqual([Math.log10(60), 0])
    expect(line.data[1]![0]).toBe(Math.log10(60))
    const marks = series.find(item => item.id === 'cursor-points')!
    expect(marks.data).toHaveLength(9)
    expect(marks.data[8]!.value).toEqual([Math.log10(60), depthOf(60, 100)])
    expect(marks.data[0]!.itemStyle.color).toBe(curveColour(0, false))
    // the paper round each mark, so that the nine marks of near curves stay apart
    expect(marks.data[0]!.itemStyle.borderColor).toBe('rgb(255, 255, 255)')
  })

  it('does not lift the axis: the line goes no higher than the highest value', () => {
    const line = option({ cursor: 3 }).series.find(item => item.id === 'cursor-line')!
    expect(line.data[1]![1]).toBe(depthOf(10080, 100))
  })

  it('has no mark for a curve with no value there', () => {
    const gappy = parseKostra(kostraAnswer({ missing: [[60, 100]] }))!
    const marks = option({ table: gappy, cursor: KOSTRA_DURATIONS.indexOf(60) }).series.find(item => item.id === 'cursor-points')!
    expect(marks.data).toHaveLength(8)
  })
})

describe('the place of a duration on the chart', () => {
  it('is nearest, as the axis shows it: the logarithm', () => {
    // the first and the last durations are at the ends of the plot
    expect(pixelOfDuration(5, 800)).toBeCloseTo(48)
    expect(pixelOfDuration(10080, 800)).toBeCloseTo(800 - 14)
    expect(nearestDurationIndex(0, 800)).toBe(0)
    expect(nearestDurationIndex(5000, 800)).toBe(21)
    for (const [index, minutes] of KOSTRA_DURATIONS.entries())
      expect(nearestDurationIndex(pixelOfDuration(minutes, 800), 800)).toBe(index)
  })

  it('changes at the middle of the logarithms of two durations, not at the middle of their minutes', () => {
    // 60 and 90 minutes: the middle of the minutes is 75, but the axis puts the middle of the two at the square root of 60 x 90 = 73.5
    const middle = (pixelOfDuration(60, 800) + pixelOfDuration(90, 800)) / 2
    expect(nearestDurationIndex(middle - 0.5, 800)).toBe(KOSTRA_DURATIONS.indexOf(60))
    expect(nearestDurationIndex(middle + 0.5, 800)).toBe(KOSTRA_DURATIONS.indexOf(90))
    expect(xOfDuration(Math.sqrt(60 * 90))).toBeCloseTo((xOfDuration(60) + xOfDuration(90)) / 2)
  })
})

describe('the readout rows', () => {
  it('are the nine values of a duration, one for each return period, null where DWD gives none', () => {
    const gappy = parseKostra(kostraAnswer({ missing: [[60, 100]] }))!
    const rows = kostraReadoutRows(gappy, 'depth', KOSTRA_DURATIONS.indexOf(60))
    expect(rows.map(row => row.years)).toEqual([1, 2, 3, 5, 10, 20, 30, 50, 100])
    expect(rows[7]!.value).toBe(depthOf(60, 50))
    expect(rows[8]!.value).toBeNull()
    expect(rows.map(row => row.colourIndex)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8])
  })
})
