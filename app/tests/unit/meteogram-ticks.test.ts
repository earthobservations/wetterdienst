import { describe, expect, it } from 'vitest'
import { fitAxisTitle, plotWidth, TICK_SPACING, tickStepHours } from '../../app/utils/meteogram-ticks'

/** The gap between two labels in px: the plot's width over the range, for `step` hours */
const gap = (step: number, range: number, plot: number) => plot * step / range

describe('tickStepHours (GH-3558)', () => {
  it('has the plot of a chart without its margins', () => {
    expect(plotWidth(254)).toBe(178)
    expect(plotWidth(40)).toBe(0)
  })

  it('leaves 40 px or more between the labels of a 239 h run on a phone', () => {
    // 254 and 294 px are the charts of a 320 and a 360 px window; the run is MOSMIX's ten days
    for (const chart of [254, 294]) {
      const plot = plotWidth(chart)
      const step = tickStepHours(239, plot)
      expect(gap(step, 239, plot), `${chart} px: a label every ${step} h`).toBeGreaterThanOrEqual(40)
    }
    expect(tickStepHours(239, plotWidth(254))).toBe(96)
    expect(tickStepHours(239, plotWidth(294))).toBe(72)
  })

  it('takes the coarsest step where none fits, and never fails', () => {
    expect(tickStepHours(239, 0)).toBe(120)
    expect(tickStepHours(10_000, 100)).toBe(120)
  })

  it('shows a 72 h run as it did: a label every 6 h on a wide chart, fewer on a narrow one', () => {
    expect(tickStepHours(72, plotWidth(820))).toBe(6)
    expect(tickStepHours(72, plotWidth(390))).toBe(12)
  })

  it('shows 24 h and 48 h runs by the hour or three hours where the labels have room', () => {
    expect(tickStepHours(24, plotWidth(1200))).toBe(1)
    expect(tickStepHours(24, plotWidth(820))).toBe(3)
    expect(tickStepHours(48, plotWidth(820))).toBe(3)
  })

  it('keeps every label of every width and range at TICK_SPACING or more apart, down to a step of 120 h', () => {
    for (const range of [24, 48, 72, 120, 168, 239]) {
      for (const chart of [254, 294, 390, 600, 820, 1200]) {
        const plot = plotWidth(chart)
        const step = tickStepHours(range, plot)
        // the coarsest step may leave less than the spacing for a range wider than 120 h on a plot narrower than two labels
        if (step < 120)
          expect(gap(step, range, plot), `${range} h on ${chart} px`).toBeGreaterThanOrEqual(TICK_SPACING)
      }
    }
  })
})

describe('fitAxisTitle (GH-3558)', () => {
  // a panel of the 540 px chart is 88 px tall, and the titles are 12 px
  it('keeps a title that fits on one line', () => {
    expect(fitAxisTitle('Wind m/s', 88, 12)).toEqual({ text: 'Wind m/s', lines: 1 })
    expect(fitAxisTitle('Bewölkung %', 88, 12)).toEqual({ text: 'Bewölkung %', lines: 1 })
  })

  it('breaks the long titles of the languages that have them at the space nearest the middle', () => {
    expect(fitAxisTitle('Niederschlag mm', 88, 12)).toEqual({ text: 'Niederschlag<br>mm', lines: 2 })
    expect(fitAxisTitle('Temperatur °C', 88, 12)).toEqual({ text: 'Temperatur<br>°C', lines: 2 })
    expect(fitAxisTitle('Pressure hPa', 70, 12)).toEqual({ text: 'Pressure<br>hPa', lines: 2 })
  })

  it('leaves a title of one word, and a panel of no known height, as they are', () => {
    expect(fitAxisTitle('Niederschlagsmenge', 88, 12)).toEqual({ text: 'Niederschlagsmenge', lines: 1 })
    expect(fitAxisTitle('Niederschlag mm', Infinity, 12).lines).toBe(1)
  })
})
