import type { SearchDoc } from '../../app/utils/search-index'
import { describe, expect, it } from 'vitest'
import { fold } from '../../app/utils/palette'
import { bestPerTarget, buildIndex, excerpt, searchIndex, tokenize } from '../../app/utils/search-index'

// The full-text index of the app's own pages (GH-3790): what it keeps, what a query finds, in which order

const doc = (title: string, extra: Partial<SearchDoc> = {}): SearchDoc => ({ kind: 'test', title, to: `/${fold(title).replace(/\W+/g, '-')}`, ...extra })

describe('the words of a text', () => {
  it('folds case and accents and splits at everything that is no letter or digit', () => {
    expect(tokenize('Müller-Čeština, 2 m/s; Wind-Geschwindigkeit')).toEqual(['muller', 'cestina', '2', 'wind', 'geschwindigkeit'])
  })

  it('drops words of one letter and keeps a digit', () => {
    expect(tokenize('a b 7 xy')).toEqual(['7', 'xy'])
  })

  it('writes an excerpt that ends at a word, with an ellipsis where it was cut', () => {
    expect(excerpt('Short.')).toBe('Short.')
    const cut = excerpt('word '.repeat(60), 40)
    expect(cut.length).toBeLessThanOrEqual(41)
    expect(cut.endsWith('…')).toBe(true)
    expect(cut).not.toMatch(/wor…$/)
  })
})

describe('the index', () => {
  const docs: SearchDoc[] = [
    doc('Humidity and dew point', { summary: 'Relative humidity is a percentage', text: 'The dew point is the temperature at which air is saturated' }),
    doc('Wind', { summary: 'Anemometers', text: 'Wind speed and gusts. Humidity does not matter here.' }),
    doc('Taupunkttemperatur', { text: 'Die Temperatur, bei der die Luft gesättigt ist' }),
    doc('Pressure', { keywords: 'Luftdruck barometer', text: 'A {placeholder} of {n} hPa' }),
  ]
  const index = buildIndex(docs)

  it('is the same for the same documents, and a plain JSON value', () => {
    expect(JSON.stringify(buildIndex(docs))).toBe(JSON.stringify(index))
    expect(JSON.parse(JSON.stringify(index))).toEqual(index)
  })

  it('keeps no text, only what is shown, and the terms once, sorted', () => {
    expect(index.docs[0]).toEqual(['test', 'Humidity and dew point', '', 'Relative humidity is a percentage', '/humidity-and-dew-point'])
    expect(JSON.stringify(index.docs)).not.toContain('saturated')
    expect(JSON.stringify(index)).not.toContain('temperature at which')
    expect(index.terms).toEqual([...new Set(index.terms)].sort())
  })

  it('does not index the names the texts are filled in with', () => {
    expect(searchIndex(index, 'placeholder')).toEqual([])
    expect(searchIndex(index, 'hpa').map(hit => hit.title)).toEqual(['Pressure'])
  })

  it('wants every word of the query in the document, in any order', () => {
    expect(searchIndex(index, 'dew point').map(hit => hit.title)).toEqual(['Humidity and dew point'])
    expect(searchIndex(index, 'point dew').map(hit => hit.title)).toEqual(['Humidity and dew point'])
    expect(searchIndex(index, 'dew gusts')).toEqual([])
  })

  it('finds a term that holds the word, as German compounds need', () => {
    expect(searchIndex(index, 'taupunkt').map(hit => hit.title)).toEqual(['Taupunkttemperatur'])
    expect(searchIndex(index, 'temperatur').map(hit => hit.title)).toContain('Taupunkttemperatur')
  })

  it('ignores case and accents in the document and in the query', () => {
    expect(searchIndex(index, 'GESÄTTIGT').map(hit => hit.title)).toEqual(['Taupunkttemperatur'])
    expect(searchIndex(index, 'gesattigt').map(hit => hit.title)).toEqual(['Taupunkttemperatur'])
  })

  it('finds by the keywords, which it does not show', () => {
    const hit = searchIndex(index, 'barometer')[0]!
    expect(hit.title).toBe('Pressure')
    expect(JSON.stringify(index.docs)).not.toContain('barometer')
  })

  it('puts a title above the text, and the start of a word above the middle of one', () => {
    // "humidity" is the title of the first and in the text of the second
    expect(searchIndex(index, 'humidity').map(hit => hit.title)).toEqual(['Humidity and dew point', 'Wind'])
    const order = buildIndex([doc('Overhumidity'), doc('Humidity'), doc('Nothing', { text: 'humidity' })])
    expect(searchIndex(order, 'humid').map(hit => hit.title)).toEqual(['Humidity', 'Overhumidity', 'Nothing'])
  })

  it('keeps the order of the documents where they score alike', () => {
    const alike = buildIndex([doc('Alpha rain'), doc('Beta rain'), doc('Gamma rain')])
    expect(searchIndex(alike, 'rain').map(hit => hit.title)).toEqual(['Alpha rain', 'Beta rain', 'Gamma rain'])
  })

  it('finds nothing for a query with no word', () => {
    for (const query of ['', '   ', 'a', '!?'])
      expect(searchIndex(index, query)).toEqual([])
  })

  it('finds a title that is also in the text once, as a title', () => {
    const both = buildIndex([doc('Wind', { text: 'Wind wind wind' }), doc('Other', { text: 'wind' })])
    expect(searchIndex(both, 'wind').map(hit => hit.title)).toEqual(['Wind', 'Other'])
  })

  it('shows the entry once for the parts of it that lead to one anchor', () => {
    const parts = buildIndex([
      doc('Wind', { context: 'How it is measured', to: '/measurement#wind', text: 'speed' }),
      doc('Wind', { context: 'Where providers differ', to: '/measurement#wind', text: 'speed speed' }),
      doc('Gust', { to: '/measurement#gust', text: 'speed' }),
    ])
    const hits = searchIndex(parts, 'speed')
    expect(hits).toHaveLength(3)
    expect(bestPerTarget(hits).map(hit => hit.to)).toEqual(['/measurement#wind', '/measurement#gust'])
    expect(bestPerTarget(hits)[0]!.context).toBe('How it is measured')
  })
})
