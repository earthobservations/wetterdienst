import { readdirSync, readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { creditLines, localizedCredit, safeHref, termsOfProvider } from '../../app/utils/provider-credit'

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

// The leading label of a credit line in the reader's language (GH-4333): the label is the app's, the provider's words after it stay.

const GERMAN = { source: 'Quelle', dataSource: 'Datenquelle', colon: ':' }
const FRENCH = { source: 'Source', dataSource: 'Source des données', colon: ' :' }

describe('localizedCredit', () => {
  it('writes a known leading label in the language of the reader and keeps the provider\'s words after it', () => {
    expect(localizedCredit('Source: Deutscher Wetterdienst', GERMAN)).toBe('Quelle: Deutscher Wetterdienst')
    expect(localizedCredit('Source: IPMA (Instituto Português do Mar e da Atmosfera)', GERMAN)).toBe('Quelle: IPMA (Instituto Português do Mar e da Atmosfera)')
    expect(localizedCredit('Data Source: Environment and Climate Change Canada. Contains information licenced under the Data Server End-use Licence of Environment and Climate Change Canada.', GERMAN))
      .toBe('Datenquelle: Environment and Climate Change Canada. Contains information licenced under the Data Server End-use Licence of Environment and Climate Change Canada.')
  })

  it('takes the colon of the language: French sets a no-break space before it', () => {
    expect(localizedCredit('Source: Deutscher Wetterdienst', FRENCH)).toBe('Source : Deutscher Wetterdienst')
    expect(localizedCredit('Data Source: Environment Canada', FRENCH)).toBe('Source des données : Environment Canada')
  })

  it('leaves a credit line with no known label as the provider wrote it', () => {
    const lines = ['© SMHI', 'GeoSphere Austria', 'Český hydrometeorologický ústav (ČHMÚ)', 'Met Office (2019): Met Office MIDAS Open: UK Land Surface Stations Data (1853-current).', 'Sources of the data: Foo', 'Open Source: Foo']
    for (const line of lines)
      expect(localizedCredit(line, GERMAN)).toBe(line)
  })

  it('leaves a label in another language alone, and a label that is all there is', () => {
    expect(localizedCredit('Quelle: Deutscher Wetterdienst', FRENCH)).toBe('Quelle: Deutscher Wetterdienst')
    expect(localizedCredit('Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej', GERMAN)).toBe('Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej')
    expect(localizedCredit('Source:', GERMAN)).toBe('Source:')
    expect(localizedCredit('Source:  ', GERMAN)).toBe('Source:  ')
  })

  it('is not case sensitive about the label and does not mind a space before the colon', () => {
    expect(localizedCredit('SOURCE: DWD', GERMAN)).toBe('Quelle: DWD')
    expect(localizedCredit('Source : DWD', GERMAN)).toBe('Quelle: DWD')
  })
})

describe('the words of the label in every locale', () => {
  const localesDir = new URL('../../i18n/locales/', import.meta.url)
  const codes = readdirSync(localesDir).filter(file => file.endsWith('.json')).map(file => file.replace(/\.json$/, ''))

  it('is the word the climate stripes\' own source line starts with, so the two never disagree', () => {
    expect(codes.length).toBe(11)
    for (const code of codes) {
      const messages = JSON.parse(readFileSync(new URL(`${code}.json`, localesDir), 'utf8'))
      const labels = { source: messages.credit.source, dataSource: messages.credit.dataSource, colon: messages.common.colon }
      expect(localizedCredit('Source: Deutscher Wetterdienst', labels), code).toBe(messages.stripes.plotSource)
    }
  })
})
