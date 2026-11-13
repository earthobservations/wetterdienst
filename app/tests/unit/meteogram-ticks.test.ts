import { describe, expect, it } from 'vitest'
import { fitAxisTitle } from '../../app/utils/meteogram-ticks'

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
