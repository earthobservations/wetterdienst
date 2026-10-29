import { describe, expect, it } from 'vitest'
import { findStations, matchesQuery, normalizeForSearch, queryWords, STATION_RESULTS_MAX } from '../../app/utils/palette'

// What the app's search (CommandPalette.vue, GH-3518) finds for what was typed

describe('the words of a query', () => {
  it('are compared without case and accents', () => {
    expect(normalizeForSearch('  München   Stadt ')).toBe('munchen stadt')
    expect(queryWords('Čeština')).toEqual(['cestina'])
  })

  it('are none for a query of space', () => {
    expect(queryWords('   ')).toEqual([])
  })
})

describe('a match', () => {
  it('needs every word, in any order and in any of the texts', () => {
    expect(matchesQuery(queryWords('stripes climate'), 'Climate stripes', 'A station\'s warming')).toBe(true)
    expect(matchesQuery(queryWords('warming'), 'Climate stripes', 'A station\'s warming')).toBe(true)
    expect(matchesQuery(queryWords('climate rain'), 'Climate stripes')).toBe(false)
  })

  it('is everything for an empty query', () => {
    expect(matchesQuery([], 'anything')).toBe(true)
  })
})

describe('the stations a query finds', () => {
  const stations = [
    { station_id: '10147', name: 'HAMBURG-FU.', region: null },
    { station_id: 'P0561', name: 'HAMBACH', region: null },
    { station_id: '07491', name: 'CHAMBERY - AIX', region: null },
    { station_id: '10865', name: 'MÜNCHEN-STADT', region: 'Bayern' },
  ]

  it('are none for a query shorter than two letters', () => {
    expect(findStations(stations, 'h')).toEqual([])
    expect(findStations(stations, ' ')).toEqual([])
  })

  it('put a name that starts with the query before one that holds it', () => {
    expect(findStations(stations, 'ham').map(s => s.station_id)).toEqual(['10147', 'P0561', '07491'])
  })

  it('find a station by its id, first', () => {
    expect(findStations(stations, '10865').map(s => s.station_id)).toEqual(['10865'])
  })

  it('find a station by its region and without its accents', () => {
    expect(findStations(stations, 'munchen bayern').map(s => s.station_id)).toEqual(['10865'])
  })

  it('are at most eight', () => {
    const many = Array.from({ length: 20 }, (_, i) => ({ station_id: String(i), name: `HAMBURG ${i}`, region: null }))
    expect(findStations(many, 'hamburg')).toHaveLength(STATION_RESULTS_MAX)
  })
})
