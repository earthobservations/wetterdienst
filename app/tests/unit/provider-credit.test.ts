import { describe, expect, it } from 'vitest'
import { creditLines, safeHref, termsOfProvider } from '../../app/utils/provider-credit'

// What the app writes beside provider data and into a file of it (GH-4255): the provider's own terms, from `GET /api/providers`.

const providers = [
  { provider: 'dwd', attribution: 'Source: Deutscher Wetterdienst', license: { name: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' } },
  { provider: 'aemet', attribution: null, license: null },
]
const licence = (name: string, url: string) => `Licence: ${name} (${url})`

describe('termsOfProvider', () => {
  it('finds the credit line and the licence of the provider, as the list gives them', () => {
    expect(termsOfProvider(providers, 'dwd')).toEqual({ attribution: 'Source: Deutscher Wetterdienst', license: providers[0]!.license })
    expect(termsOfProvider(providers, 'aemet')).toEqual({ attribution: null, license: null })
  })

  it('is null for a provider the list does not have, for no list yet and for no provider', () => {
    expect(termsOfProvider(providers, 'nope')).toBeNull()
    expect(termsOfProvider(undefined, 'dwd')).toBeNull()
    expect(termsOfProvider(providers, null)).toBeNull()
  })
})

describe('safeHref', () => {
  it('lets an http(s) address through and nothing else, as the text is the API\'s', () => {
    expect(safeHref('https://example.org/terms')).toBe('https://example.org/terms')
    expect(safeHref('http://example.org/terms')).toBe('http://example.org/terms')
    expect(safeHref('javascript:alert(1)')).toBeNull()
    expect(safeHref('')).toBeNull()
    expect(safeHref(null)).toBeNull()
  })
})

describe('creditLines', () => {
  it('is the credit line, the licence and the note, in that order', () => {
    expect(creditLines(termsOfProvider(providers, 'dwd'), licence, 'Processed.')).toEqual([
      'Source: Deutscher Wetterdienst',
      'Licence: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)',
      'Processed.',
    ])
  })

  it('leaves out what the provider does not state, and says the note and the fallback line all the same', () => {
    expect(creditLines(termsOfProvider(providers, 'aemet'), licence, 'Processed.')).toEqual(['Processed.'])
    expect(creditLines(null, licence, 'Processed.', 'Source: NOAA')).toEqual(['Source: NOAA', 'Processed.'])
  })
})
