import type { StationMatch } from '../../app/utils/station-search'
import type { StationIdsStation } from '../../shared/types/api'
import { describe, expect, it } from 'vitest'
import { mapSearchLink, mapStationLink, searchFromQuery, stateFromQuery } from '../../app/utils/map-tool'
import { itemOfIdRow, itemOfStation, moreStationsLink, parseStationId, sortedIdRows, stationIdLink, stationLine } from '../../app/utils/station-hits'

// What the search of the header does with a station (GH-3790): what a station found by name leads to, and the ids it asks every network for.

const WORDS = { network: (network: string) => ({ forecast: 'MOSMIX forecast', measured: 'measurements', ghcn: 'GHCN daily' })[network]!, ended: (year: number) => `ended ${year}` }

const match = (extra: Partial<StationMatch> = {}): StationMatch => ({ station_id: '01975', name: 'Hamburg-Fuhlsbüttel', latitude: 53.63, longitude: 10, wmo_id: '10147', first_year: 1891, last_year: null, reporting: true, ...extra })

function row(extra: Partial<StationIdsStation> = {}): StationIdsStation {
  return { provider: 'dwd', network: 'observation', resolution: 'daily', dataset: 'climate_summary', station_id: '01975', name: 'Hamburg-Fuhlsbüttel', latitude: 53.63, longitude: 10, elevation: 11, wmo_id: '10147', wigos_id: null, icao_id: 'EDDH', matched_by: 'wmo_id', match: 'direct', ...extra }
}

describe('a station found by name', () => {
  it('names the provider, the network and the id of the network on its line, and is an item that leads to the map', () => {
    expect(itemOfStation('measured', match(), WORDS, 'i-ph-x')).toEqual({
      id: 'station-measured-01975',
      label: 'Hamburg-Fuhlsbüttel',
      description: 'DWD · measurements · 01975',
      icon: 'i-ph-x',
      to: '/map?layer=measured&station=01975',
    })
    expect(stationLine('forecast', match({ station_id: '10147' }), WORDS)).toBe('DWD · MOSMIX forecast · 10147')
    expect(stationLine('ghcn', match({ station_id: 'GM000010147' }), WORDS)).toBe('NOAA · GHCN daily · GM000010147')
  })

  it('leads to the layer of its network with the station picked, as the map reads it', () => {
    for (const [network, layer] of [['forecast', 'forecast'], ['measured', 'measured'], ['ghcn', 'ghcn']] as const) {
      const to = itemOfStation(network, match({ station_id: 'A 1' }), WORDS, 'i').to!
      const query = Object.fromEntries(new URL(to, 'http://x').searchParams)
      expect(new URL(to, 'http://x').pathname).toBe('/map')
      expect(stateFromQuery(query)).toMatchObject({ layer, stationId: 'A 1' })
    }
    // the forecast is the map's default layer
    expect(mapStationLink('forecast', '10147')).toBe('/map?station=10147')
    expect(mapStationLink('ghcn', 'GM000010147')).toBe('/map?layer=ghcn&station=GM000010147')
  })

  it('says the year a station that has stopped reporting ended in, and nothing for one that reports', () => {
    expect(stationLine('measured', match({ reporting: false, last_year: 1997 }), WORDS)).toBe('DWD · measurements · 01975 · ended 1997')
    expect(stationLine('measured', match({ reporting: true, last_year: 2026 }), WORDS)).toBe('DWD · measurements · 01975')
  })

  it('has a station with no name by its id', () => {
    expect(itemOfStation('ghcn', match({ name: null, station_id: 'USW00094728' }), WORDS, 'i').label).toBe('USW00094728')
  })

  it('leads on to the map\'s own search of the layer, started on the query', () => {
    expect(moreStationsLink('ghcn', 'hamburg')).toBe('/map?layer=ghcn&q=hamburg')
    expect(moreStationsLink('forecast', 'bad ü&?')).toBe('/map?q=bad+%C3%BC%26%3F')
    expect(mapSearchLink('measured', 'x')).toBe('/map?layer=measured&q=x')
  })

  it('is read back by the map: the text of the address starts its search, and what is no text starts none', () => {
    expect(searchFromQuery({ q: 'hamburg' })).toBe('hamburg')
    expect(searchFromQuery({ q: ['a', 'b'] })).toBe('a')
    expect(searchFromQuery({})).toBe('')
    expect(searchFromQuery({ q: 5 })).toBe('')
    expect(searchFromQuery({ q: 'x'.repeat(300) })).toHaveLength(100)
  })
})

describe('an id typed in', () => {
  it('is a WMO number when it is five digits, as it is written with its leading zeros', () => {
    expect(parseStationId('10381')).toEqual({ kind: 'wmo', id: '10381', param: 'wmo_id' })
    expect(parseStationId(' 01001 ')).toEqual({ kind: 'wmo', id: '01001', param: 'wmo_id' })
  })

  it('is a WIGOS identifier when it has its four parts', () => {
    expect(parseStationId('0-20000-0-10381')).toEqual({ kind: 'wigos', id: '0-20000-0-10381', param: 'wigos_id' })
    expect(parseStationId('0-276-3-EDDH')).toMatchObject({ kind: 'wigos', param: 'wigos_id' })
    expect(parseStationId('0-056-0-ABC.1')).toMatchObject({ kind: 'wigos' })
  })

  it('is an ICAO code when it is four letters, in capitals as the backend has it', () => {
    expect(parseStationId('EDDH')).toEqual({ kind: 'icao', id: 'EDDH', param: 'icao_id' })
    expect(parseStationId('eddh')).toEqual({ kind: 'icao', id: 'EDDH', param: 'icao_id' })
  })

  it.each(['1038', '103810', '1038a', 'EDD', 'EDDHH', 'Köln', 'hamburg', '0-20000-0', '20000-0-10381', '52.52, 13.40', '', 'ED DH'])('is no id: %s', (typed) => {
    expect(parseStationId(typed)).toBeNull()
  })
})

describe('where a station of the id search leads', () => {
  it('is the map for the networks it shows, with the layer of the network and, for DWD\'s measurements, the dataset of the list', () => {
    expect(stationIdLink(row({ provider: 'dwd', network: 'mosmix', resolution: 'hourly', dataset: 'large', station_id: '10147' }))).toEqual({ to: '/map?station=10147', map: true })
    expect(stationIdLink(row())).toEqual({ to: '/map?layer=measured&station=01975', map: true })
    expect(stationIdLink(row({ resolution: 'hourly', dataset: 'temperature_air' }))).toEqual({ to: '/map?layer=measured&resolution=hourly&dataset=temperature_air&station=01975', map: true })
    expect(stationIdLink(row({ provider: 'noaa', network: 'ghcn', resolution: 'daily', dataset: 'data', station_id: 'GM000010147' }))).toEqual({ to: '/map?layer=ghcn&station=GM000010147', map: true })
  })

  it('is the Explorer for any other network, with the provider, network, resolution, dataset and the station chosen, which the map cannot show', () => {
    const { to, map } = stationIdLink(row({ provider: 'metoffice', network: 'observation', resolution: 'daily', dataset: 'midas', station_id: '03772' }))
    expect(map).toBe(false)
    const url = new URL(to, 'http://x')
    expect(url.pathname).toBe('/explorer')
    expect(Object.fromEntries(url.searchParams)).toEqual({ provider: 'metoffice', network: 'observation', resolution: 'daily', dataset: 'midas', mode: 'station', stations: '03772' })
  })

  it('names the provider, the network and the id on the item of each, and says that it opens the Explorer where it does', () => {
    const icons = { map: 'i-map', explorer: 'i-exp' }
    const words = { provider: 'DWD', network: WORDS.network, opensExplorer: 'opens the Explorer' }
    expect(itemOfIdRow(row(), words, icons)).toMatchObject({ label: 'Hamburg-Fuhlsbüttel', description: 'DWD · measurements · 01975', icon: 'i-map', to: '/map?layer=measured&station=01975' })
    // the three networks the search matches by name are named as its groups name them
    expect(itemOfIdRow(row({ provider: 'noaa', network: 'ghcn', resolution: 'daily', dataset: 'data', station_id: 'GM000010147' }), { ...words, provider: 'NOAA' }, icons).description).toBe('NOAA · GHCN daily · GM000010147')
    expect(itemOfIdRow(row({ provider: 'dwd', network: 'mosmix', resolution: 'hourly', dataset: 'large', station_id: '10147' }), words, icons).description).toBe('DWD · MOSMIX forecast · 10147')
    // DWD's other networks are the backend's names, and open the Explorer
    expect(itemOfIdRow(row({ provider: 'dwd', network: 'dmo', resolution: 'hourly', dataset: 'icon', station_id: '10147' }), words, icons).description).toBe('DWD · dmo · 10147 · opens the Explorer')
    const other = itemOfIdRow(row({ provider: 'metoffice', station_id: '03772', name: null }), { ...words, provider: 'Met Office' }, icons)
    expect(other).toMatchObject({ label: '03772', description: 'Met Office · observation · 03772 · opens the Explorer', icon: 'i-exp' })
    expect(other.to).toMatch(/^\/explorer\?/)
  })

  it('lists the stations that carry the id asked for before those that carry an equivalent one, each in the backend\'s order', () => {
    const rows = [row({ station_id: 'a', match: 'equivalent' }), row({ station_id: 'b', match: 'direct' }), row({ station_id: 'c', match: 'equivalent' }), row({ station_id: 'd', match: 'direct' })]
    expect(sortedIdRows(rows).map(entry => entry.station_id)).toEqual(['b', 'd', 'a', 'c'])
    expect(rows.map(entry => entry.station_id)).toEqual(['a', 'b', 'c', 'd'])
  })
})
