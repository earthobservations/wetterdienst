import { describe, expect, it } from 'vitest'
import { findStations, matches, normalise, queryForms } from '../../app/utils/palette'

describe('the palette\'s matching', () => {
  it('compares without case and accents', () => {
    expect(normalise('  Météo-France ')).toBe('meteo-france')
    expect(matches('meteo', 'Météo-France')).toBe(true)
    expect(matches('GLOSS', 'Glossary')).toBe(true)
    expect(matches('radar', 'Glossary', 'What each parameter means')).toBe(false)
  })

  it('finds everything for an empty query', () => {
    expect(matches('', 'anything')).toBe(true)
    expect(matches('   ', 'anything')).toBe(true)
  })

  it('looks for a German name as the station list writes it, without umlauts', () => {
    expect(queryForms('München')).toEqual(['munchen', 'muenchen'])
    expect(queryForms('Gießen')).toEqual(['gießen', 'giessen'])
  })
})

describe('findStations', () => {
  const stations = [
    { station_id: '10865', name: 'MUENCHEN-STADT' },
    { station_id: '10870', name: 'MUENCHEN-FL.' },
    { station_id: '10384', name: 'BERLIN-TEMPELHOF' },
    { station_id: '01001', name: 'JAN MAYEN' },
    { station_id: 'P0120', name: 'HAMBURG-NEUENG.' },
  ]

  it('finds a place by its name in either spelling, and by its identifier', () => {
    expect(findStations(stations, 'München').map(s => s.station_id)).toEqual(['10870', '10865'])
    expect(findStations(stations, 'tempel').map(s => s.station_id)).toEqual(['10384'])
    expect(findStations(stations, '01001').map(s => s.station_id)).toEqual(['01001'])
    expect(findStations(stations, 'p01').map(s => s.station_id)).toEqual(['P0120'])
  })

  it('puts the names that start with the query first', () => {
    expect(findStations(stations, 'en').map(s => s.name)).toEqual(['HAMBURG-NEUENG.', 'JAN MAYEN', 'MUENCHEN-FL.', 'MUENCHEN-STADT'])
    expect(findStations(stations, 'ber')[0]!.name).toBe('BERLIN-TEMPELHOF')
  })

  it('needs two letters, and gives at most as many as asked', () => {
    expect(findStations(stations, 'm')).toEqual([])
    expect(findStations(stations, 'en', 2)).toHaveLength(2)
  })
})
