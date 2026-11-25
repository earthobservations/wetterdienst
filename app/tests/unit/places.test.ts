import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { isPlaceQuery, looksLikePosition, MAX_PLACES, normalisePlaceQuery, photonLang, placeKindOf, placesOfPhoton } from '../../shared/utils/places'

// What the search shows of Photon's answer (GH-3790, GH-3791): the places among the hits, what each is, where it lies, and the language asked for. The
// answers of the two real texts are saved from komoot's server (tests/fixtures/photon-*.json).

const fixture = (name: string) => JSON.parse(readFileSync(new URL(`../fixtures/${name}.json`, import.meta.url), 'utf8'))
const feature = (lon: unknown, lat: unknown, properties: Record<string, unknown>) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] }, properties })
const place = (name: string, osm_value: string, extra: Record<string, unknown> = {}, lon = 11.5, lat = 47.7) => feature(lon, lat, { osm_id: 1, osm_type: 'N', osm_key: 'place', osm_value, type: 'city', name, ...extra })

describe('the language the names are asked in', () => {
  it('is the reader\'s own where Photon has it (German, English, French), Luxembourgish as German, and English for every other locale', () => {
    expect(photonLang('de')).toBe('de')
    expect(photonLang('de-hh')).toBe('de')
    expect(photonLang('lb')).toBe('de')
    expect(photonLang('fr')).toBe('fr')
    expect(photonLang('en-GB')).toBe('en')
    for (const locale of ['cs', 'da', 'es', 'it', 'nl', 'pl', '', undefined, null])
      expect(photonLang(locale), String(locale)).toBe('en')
  })
})

describe('the text that is searched for', () => {
  it('is one line of single spaces, composed', () => {
    expect(normalisePlaceQuery('  Bad \t Tölz\n')).toBe('Bad Tölz')
    // "ö" as "o" and a combining diaeresis is the same text composed
    expect(normalisePlaceQuery('Tölz')).toBe('Tölz')
  })

  it('is a name of at least three letters that is no position: two letters, a number and a code are none', () => {
    for (const name of ['bad', '  Bad Tölz  ', 'Saint-Étienne', 'Frankfurt am Main', 'Frankfurt (Oder)', 'Côte d\'Ivoire', 'L\'Aquila', 'Val-d\'Isère', '東京都', 'Route 66', 'Berlin 2'])
      expect(isPlaceQuery(name), name).toBe(true)
    for (const text of ['ba', '東京', '10381', '0-20000-0-10381', 'A12', 'B 1', 'N1', 'a b c'.slice(0, 3)])
      expect(isPlaceQuery(text), text).toBe(false)
  })

  it('is never a position, whole or partial: a decimal number, a degree or minute sign, two numbers, a compass letter at a number, a word for latitude or longitude', () => {
    const positions = [
      '52.5200, 13.4000',
      '47.76 N',
      '47.76 N 11.55',
      'N 47.7 E',
      '47°45′N',
      '47°45\'N 11°33\'E',
      '47°45′30″',
      'lat 47.7 lon 11.5',
      '47,7 N 11,5 O',
      '47.7, 11.5',
      '-33.87 151.21',
      '47 N 11 E',
      'lat 47 lon 11',
      'lat 47',
      'breite 47',
      'longitude 11',
      'N 47',
      '47 N',
      'W 3',
      '47° N',
      '47 deg N',
      'Lat. 47',
    ]
    for (const text of positions) {
      expect(looksLikePosition(text), text).toBe(true)
      expect(isPlaceQuery(text), text).toBe(false)
    }
    // names that have a number or an apostrophe are names
    for (const name of ['Route 66', 'Berlin 2', 'Frankfurt am Main', 'L\'Aquila', 'Saint-Étienne', 'Ostende'])
      expect(looksLikePosition(name), name).toBe(false)
  })
})

describe('what an OpenStreetMap object is', () => {
  it('is a settlement, a region, a country, a mountain, a water or an airport, and none of a street, a shop or a house', () => {
    expect(placeKindOf('place', 'city', 'city')).toBe('city')
    expect(placeKindOf('place', 'town', 'city')).toBe('town')
    expect(placeKindOf('place', 'suburb', 'district')).toBe('district')
    expect(placeKindOf('place', 'state', 'state')).toBe('region')
    expect(placeKindOf('place', 'country', 'country')).toBe('country')
    expect(placeKindOf('place', 'sea', 'other')).toBe('water')
    expect(placeKindOf('boundary', 'administrative', 'county')).toBe('county')
    expect(placeKindOf('boundary', 'administrative', 'state')).toBe('region')
    expect(placeKindOf('boundary', 'administrative', 'district')).toBe('district')
    expect(placeKindOf('natural', 'peak', 'other')).toBe('mountain')
    expect(placeKindOf('natural', 'water', 'other')).toBe('water')
    expect(placeKindOf('waterway', 'river', 'other')).toBe('water')
    expect(placeKindOf('waterway', 'canal', 'other')).toBe('water')
    expect(placeKindOf('aeroway', 'aerodrome', 'other')).toBe('airport')
    for (const [key, value, type] of [['highway', 'residential', 'street'], ['amenity', 'cafe', 'house'], ['shop', 'bakery', 'house'], ['railway', 'station', 'house'], ['building', 'industrial', 'house'], ['place', 'square', 'other'], ['boundary', 'administrative', 'locality'], ['boundary', 'political', 'other'], ['boundary', 'postal_code', 'other'], ['natural', 'tree', 'other'], ['waterway', 'fish_pass', 'other'], ['landuse', 'industrial', 'locality'], ['leisure', 'park', 'other']])
      expect(placeKindOf(key, value, type), `${key}=${value}`).toBeNull()
    expect(placeKindOf(undefined, undefined, undefined)).toBeNull()
  })

  it('finds a river by its name', () => {
    const [isar] = placesOfPhoton({ features: [feature(11.8, 48.5, { osm_id: 5, osm_type: 'R', osm_key: 'waterway', osm_value: 'river', type: 'other', name: 'Isar', country: 'Deutschland' })] })!
    expect(isar).toMatchObject({ name: 'Isar', kind: 'water', region: 'Deutschland' })
  })
})

describe('the places of Photon\'s answer', () => {
  it('are, for the real answer for "Bad Tölz", the town, the county once (as the node and as the relation) and the village, and no station, building, park or boundary of another sort', () => {
    const places = placesOfPhoton(fixture('photon-badtoelz'))!
    expect(places.map(entry => [entry.id, entry.name, entry.kind, entry.region])).toEqual([
      ['R935181', 'Bad Tölz', 'town', 'Bayern, Deutschland'],
      // the node `place=county` and the relation "Landkreis Bad Tölz-Wolfratshausen" (R62472) are one place: the first
      ['N240060717', 'Bad Tölz-Wolfratshausen', 'county', 'Bayern, Deutschland'],
      ['R935232', 'Bad Heilbrunn', 'village', 'Landkreis Bad Tölz-Wolfratshausen, Bayern, Deutschland'],
    ])
    // the point is Photon's `[longitude, latitude]`
    expect([places[0]!.latitude, places[0]!.longitude]).toEqual([47.7610013, 11.559607])
  })

  it('are, for the real answer for "Paris", the city once (the relation `place=city`, and not the two administrative boundaries of the same place) and the Parises of the United States', () => {
    const places = placesOfPhoton(fixture('photon-paris'), 12)!
    expect(places.map(entry => [entry.id, entry.kind, entry.region])).toEqual([
      ['R71525', 'city', 'Île-de-France, France'],
      ['R115357', 'town', 'Texas, United States'],
      ['R130722', 'city', 'Kentucky, United States'],
      ['R6678712', 'town', 'Arkansas, United States'],
      ['R126166', 'town', 'Illinois, United States'],
      ['R197171', 'city', 'Tennessee, United States'],
      ['R12165996', 'town', 'Maine, United States'],
      ['R3669583', 'village', 'Oneida, New York, United States'],
      ['R140787', 'city', 'Missouri, United States'],
      ['R121447', 'city', 'Idaho, United States'],
    ])
    // five by default
    expect(placesOfPhoton(fixture('photon-paris'))).toHaveLength(MAX_PLACES)
  })

  it('give a place the kind that `place=` says where a boundary is found first, and the boundary\'s own where nothing says more', () => {
    const boundary = feature(2.32, 48.8589, { osm_id: 7444, osm_type: 'R', osm_key: 'boundary', osm_value: 'administrative', type: 'district', name: 'Paris', city: 'Paris', state: 'Île-de-France', country: 'France' })
    const node = feature(2.3484, 48.8535, { osm_id: 71525, osm_type: 'R', osm_key: 'place', osm_value: 'city', type: 'city', name: 'Paris', state: 'Île-de-France', country: 'France' })
    expect(placesOfPhoton({ features: [boundary, node] })!.map(entry => [entry.id, entry.kind])).toEqual([['R71525', 'city']])
    expect(placesOfPhoton({ features: [boundary] })!.map(entry => [entry.id, entry.kind])).toEqual([['R7444', 'district']])
  })

  it('are one for a unit and its twin by another name: "Landkreis", "Kreis" and "Stadt" are no part of the name, and a name that holds the other is the other', () => {
    const at = (name: string, kind: string, lat: number, lon: number, extra: Record<string, unknown> = {}) => place(name, kind, { state: 'Bayern', country: 'Deutschland', ...extra }, lon, lat)
    expect(placesOfPhoton({ features: [at('Landkreis München', 'county', 48.0, 11.5), at('München', 'county', 48.01, 11.51, { osm_id: 2 })] })).toHaveLength(1)
    expect(placesOfPhoton({ features: [at('Stadt Hamm', 'city', 51.68, 7.82), at('Hamm', 'city', 51.69, 7.83, { osm_id: 2 })] })).toHaveLength(1)
    expect(placesOfPhoton({ features: [at('Kreis Soest', 'county', 51.5, 8.1), at('Soest', 'county', 51.52, 8.12, { osm_id: 2 })] })).toHaveLength(1)
    expect(placesOfPhoton({ features: [at('Paris', 'city', 48.85, 2.35), at('Paris 1er Arrondissement', 'suburb', 48.86, 2.34, { osm_id: 2 })] })).toHaveLength(1)
  })

  it('are two where the name matches but the level, the region or the distance does not: a city and a county, a city and a state, two towns of one name in two regions, two places 10 km apart', () => {
    const at = (name: string, kind: string, lat: number, lon: number, extra: Record<string, unknown> = {}) => place(name, kind, { state: 'Bayern', country: 'Deutschland', ...extra }, lon, lat)
    expect(placesOfPhoton({ features: [at('München', 'city', 48.14, 11.58), at('Landkreis München', 'county', 48.15, 11.59, { osm_id: 2 })] })).toHaveLength(2)
    expect(placesOfPhoton({ features: [place('Berlin', 'city', { country: 'Deutschland' }), place('Berlin', 'state', { state: 'Berlin', country: 'Deutschland' })] })!.map(entry => entry.kind)).toEqual(['city', 'region'])
    expect(placesOfPhoton({ features: [place('Paris', 'city', { state: 'Texas', country: 'United States' }), place('Paris', 'city', { state: 'Maine', country: 'United States', osm_id: 2 })] })).toHaveLength(2)
    expect(placesOfPhoton({ features: [at('Neustadt', 'town', 48.0, 11.0), at('Neustadt', 'town', 48.0, 11.12, { osm_id: 2 })] })).toHaveLength(2)
    // a mountain and a town of one name, or an airport named for its city, are no twins
    expect(placesOfPhoton({ features: [at('Paris', 'city', 48.85, 2.35), feature(2.36, 48.86, { osm_id: 3, osm_type: 'N', osm_key: 'natural', osm_value: 'peak', type: 'other', name: 'Paris', state: 'Bayern', country: 'Deutschland' })] })).toHaveLength(2)
  })

  it('say where a small place lies by the town or county it is in, then its state and country, and leave out what repeats the name or is not given', () => {
    const [village, region, country, city] = placesOfPhoton({ features: [
      place('Eurasburg', 'village', { county: 'Landkreis Bad Tölz-Wolfratshausen', state: 'Bayern', country: 'Deutschland' }, 11.4),
      place('Bayern', 'state', { state: 'Bayern', country: 'Deutschland' }, 11.3, 48.9),
      place('Deutschland', 'country', { country: 'Deutschland' }, 10.4, 51),
      place('Paris', 'city', { state: 'Île-de-France', country: 'France' }, 2.35, 48.85),
    ] })!
    expect(village!.region).toBe('Landkreis Bad Tölz-Wolfratshausen, Bayern, Deutschland')
    expect(region!.region).toBe('Deutschland')
    expect(country!.region).toBeNull()
    expect(city!.region).toBe('Île-de-France, France')
    // a district names the city it is a part of
    expect(placesOfPhoton({ features: [place('Schwabing', 'suburb', { city: 'München', state: 'Bayern', country: 'Deutschland' })] })![0]!.region).toBe('München, Bayern, Deutschland')
  })

  it('are at most the limit given', () => {
    const features = Array.from({ length: 10 }, (_, index) => place(`Town ${index}`, 'town', {}, index, index))
    expect(placesOfPhoton({ features })).toHaveLength(MAX_PLACES)
    expect(placesOfPhoton({ features }, 2)).toHaveLength(2)
  })

  it('skip a hit with no name, no point or a point outside the earth, and are null for an answer that is not Photon\'s', () => {
    expect(placesOfPhoton({ features: [
      place('', 'town'),
      feature(null, 47, { osm_key: 'place', osm_value: 'town', name: 'No longitude' }),
      feature(11, 91, { osm_key: 'place', osm_value: 'town', name: 'Beyond the pole' }),
      feature(Number.NaN, 47, { osm_key: 'place', osm_value: 'town', name: 'Not a number' }),
      { type: 'Feature', properties: { osm_key: 'place', osm_value: 'town', name: 'No geometry' } },
      null,
      place('Fine', 'town'),
    ] })!.map(entry => entry.name)).toEqual(['Fine'])
    expect(placesOfPhoton({ features: [] })).toEqual([])
    for (const body of [null, undefined, 'text', 42, {}, { features: 'many' }, []])
      expect(placesOfPhoton(body), JSON.stringify(body)).toBeNull()
  })

  it('give a place with no OpenStreetMap id one by its point', () => {
    expect(placesOfPhoton({ features: [feature(11.5, 47.7, { osm_key: 'place', osm_value: 'town', name: 'Anywhere' })] })![0]!.id).toBe('47.7000,11.5000')
  })
})
