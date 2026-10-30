import { describe, expect, it } from 'vitest'
import { plotlyDictionary, plotlyDictionaryCode, plotlyLocaleConfig, plotlyLocaleConfigOrFailure, plotlyText } from '../../app/utils/plotly-locale'

// The language of a Plotly chart (GH-3625): Plotly's own translations of its buttons, for the app's locales
// (nuxt.config.ts), and the names of the dates in the language's tag.

describe('the translation Plotly has for a locale of the app', () => {
  it.each(['de', 'fr', 'es', 'it', 'nl', 'cs'])('is its own for %s', (code) => {
    expect(plotlyDictionaryCode(code)).toBe(code)
  })

  it('is German for Luxembourgish and for Hamburg\'s German, which Plotly has none of', () => {
    expect(plotlyDictionaryCode('lb')).toBe('de')
    expect(plotlyDictionaryCode('de-hh')).toBe('de')
  })

  it('is none for English, which is Plotly\'s own, and for Polish and Danish, which Plotly ships empty', () => {
    expect(plotlyDictionaryCode('en')).toBeUndefined()
    expect(plotlyDictionaryCode('pl')).toBeUndefined()
    expect(plotlyDictionaryCode('da')).toBeUndefined()
  })

  it.each([
    ['de', 'Pan', 'Verschieben'],
    ['fr', 'Zoom out', 'Zoom extérieur'],
    ['es', 'Zoom out', 'Reducir'],
    ['it', 'Zoom out', 'Riduci'],
    ['nl', 'Zoom', 'Inzoomen'],
    ['cs', 'Zoom out', 'Zmenšit'],
    ['lb', 'Pan', 'Verschieben'],
    ['de-hh', 'Pan', 'Verschieben'],
  ])('writes the button of %s named "%s" as "%s"', async (code, button, expected) => {
    expect((await plotlyDictionary(code))?.[button]).toBe(expected)
  })

  // Plotly ships polish and danish with the names of the dates only, and dutch with a part of its texts: their
  // buttons stay English, as Plotly's own, and nothing is loaded for an empty dictionary
  it.each(['pl', 'da'])('loads nothing for %s, whose buttons Plotly has none of: the dates are Intl\'s', async (code) => {
    expect(await plotlyDictionary(code)).toBeUndefined()
    const { config, failed } = await plotlyLocaleConfigOrFailure(code, `${code}-XX`)
    expect(failed).toBe(false)
    expect(config.locales[`${code}-XX`]!.dictionary).toBeUndefined()
  })
})

describe('the config of a chart in a language', () => {
  it('names the locale by the language\'s tag and holds its buttons and its dates', async () => {
    const config = await plotlyLocaleConfig('de', 'de-DE')
    expect(config.locale).toBe('de-DE')
    expect(Object.keys(config.locales)).toEqual(['de-DE'])
    expect(config.locales['de-DE']!.dictionary?.Zoom).toBe('Zoom')
    expect(config.locales['de-DE']!.dictionary?.['Reset axes']).toBe('Achsen zurücksetzen')
    // Sunday first, as Plotly has it
    expect(config.locales['de-DE']!.format.shortDays).toHaveLength(7)
    expect(config.locales['de-DE']!.format.shortDays[4]).toMatch(/^Do/)
  })

  it('writes Luxembourgish\'s dates and German buttons for it', async () => {
    const config = await plotlyLocaleConfig('lb', 'lb-LU')
    expect(config.locale).toBe('lb-LU')
    expect(config.locales['lb-LU']!.dictionary?.Pan).toBe('Verschieben')
  })

  it('has English no buttons of its own: Plotly\'s are English', async () => {
    const config = await plotlyLocaleConfig('en', 'en-GB')
    expect(config.locale).toBe('en-GB')
    expect(config.locales['en-GB']!.dictionary).toBeUndefined()
    expect(config.locales['en-GB']!.format.months).toHaveLength(12)
  })
})

describe('the name of a button the app adds', () => {
  it('is Plotly\'s word for it in the language, and the English where there is none', async () => {
    expect(plotlyText(await plotlyLocaleConfig('de', 'de-DE'), 'Download plot as a PNG')).toBe('Graphen als PNG herunterladen')
    expect(plotlyText(await plotlyLocaleConfig('lb', 'lb-LU'), 'Download plot as a PNG')).toBe('Graphen als PNG herunterladen')
    expect(plotlyText(await plotlyLocaleConfig('pl', 'pl-PL'), 'Download plot as a PNG')).toBe('Download plot as a PNG')
    expect(plotlyText(await plotlyLocaleConfig('en', 'en-GB'), 'Download plot as a PNG')).toBe('Download plot as a PNG')
  })
})

describe('a language whose buttons could not be loaded', () => {
  it('is told, so that no one keeps the English fallback as its config', async () => {
    const { vi } = await import('vitest')
    vi.resetModules()
    vi.doMock('plotly.js-locales/it', () => {
      throw new Error('chunk failed to load')
    })
    const fresh = await import('../../app/utils/plotly-locale')
    const failed = await fresh.plotlyLocaleConfigOrFailure('it', 'it-IT')
    expect(failed.failed).toBe(true)
    expect(failed.config.locales['it-IT']!.dictionary).toBeUndefined()
    // not remembered as the answer: where the chunk loads, the next ask has it
    vi.doUnmock('plotly.js-locales/it')
    const loaded = await fresh.plotlyLocaleConfigOrFailure('it', 'it-IT')
    expect(loaded.failed).toBe(false)
    expect(loaded.config.locales['it-IT']!.dictionary?.Pan).toBe('Sposta')
  })
})
