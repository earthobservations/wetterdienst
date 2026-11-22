import { describe, expect, it } from 'vitest'
import { isPlaceQuery, MAX_PLACES, normalisePlaceQuery, photonLang, placeKindOf, placesOfPhoton } from '../../shared/utils/places'

// What the search shows of Photon's answer (GH-3790, GH-3791): the places among the hits, what each is, where it lies, and the language asked for.

const feature = (lon: unknown, lat: unknown, properties: Record<string, unknown>) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] }, properties })
const place = (name: string, osm_value: string, extra: Record<string, unknown> = {}, lon = 11.5, lat = 47.7) => feature(lon, lat, { osm_id: 1, osm_type: 'N', osm_key: 'place', osm_value, type: 'city', name, ...extra })

describe('the language the names are asked in', () => {
  it('is the reader\'s own where Photon has it (German, English, French), and English for every other locale', () => {
    expect(photonLang('de')).toBe('de')
    expect(photonLang('de-hh')).toBe('de')
    expect(photonLang('fr')).toBe('fr')
    expect(photonLang('en-GB')).toBe('en')
    for (const locale of ['cs', 'da', 'es', 'it', 'lb', 'nl', 'pl', '', undefined, null])
      expect(photonLang(locale), String(locale)).toBe('en')
  })
})

describe('the text that is searched for', () => {
  it('is one line of single spaces, composed', () => {
    expect(normalisePlaceQuery('  Bad \t Tölz\n')).toBe('Bad Tölz')
    // "ö" as "o" and a combining diaeresis is the same text composed
    expect(normalisePlaceQuery('Tölz')).toBe('Tölz')
  })

  it('is a name from three characters on that has a letter: a position, a number and two letters are none', () => {
    expect(isPlaceQuery('bad')).toBe(true)
    expect(isPlaceQuery('  Bad Tölz  ')).toBe(true)
    expect(isPlaceQuery('東京')).toBe(false)
    expect(isPlaceQuery('東京都')).toBe(true)
    expect(isPlaceQuery('ba')).toBe(false)
    expect(isPlaceQuery('52.5200, 13.4000')).toBe(false)
    expect(isPlaceQuery('10381')).toBe(false)
    expect(isPlaceQuery('0-20000-0-10381')).toBe(false)
  })
})

describe('what an OpenStreetMap object is', () => {
  it('is a settlement, a region, a country, a mountain, a water or an airport, and none of a street, a shop or a house', () => {
    expect(placeKindOf('place', 'city', 'city')).toBe('city')
    expect(placeKindOf('place', 'town', 'city')).toBe('town')
    expect(placeKindOf('place', 'suburb', 'district')).toBe('district')
    expect(placeKindOf('place', 'state', 'state')).toBe('region')
    expect(placeKindOf('place', 'country', 'country')).toBe('country')
    expect(placeKindOf('boundary', 'administrative', 'county')).toBe('county')
    expect(placeKindOf('boundary', 'administrative', 'state')).toBe('region')
    expect(placeKindOf('natural', 'peak', 'other')).toBe('mountain')
    expect(placeKindOf('natural', 'water', 'other')).toBe('water')
    expect(placeKindOf('aeroway', 'aerodrome', 'other')).toBe('airport')
    for (const [key, value, type] of [['highway', 'residential', 'street'], ['amenity', 'cafe', 'house'], ['shop', 'bakery', 'house'], ['railway', 'station', 'other'], ['building', 'yes', 'house'], ['place', 'square', 'other'], ['boundary', 'administrative', 'locality'], ['boundary', 'postal_code', 'other'], ['natural', 'tree', 'other']])
      expect(placeKindOf(key, value, type), `${key}=${value}`).toBeNull()
    expect(placeKindOf(undefined, undefined, undefined)).toBeNull()
  })
})

describe('the places of Photon\'s answer', () => {
  it('are the settlements and the like among the hits, in Photon\'s order, with the point as latitude and longitude and OpenStreetMap\'s own id', () => {
    const places = placesOfPhoton({ features: [
      feature(11.5583, 47.7614, { osm_id: 240109189, osm_type: 'N', osm_key: 'place', osm_value: 'town', type: 'city', name: 'Bad Tölz', state: 'Bayern', country: 'Deutschland' }),
      feature(11.55, 47.77, { osm_id: 51, osm_type: 'W', osm_key: 'highway', osm_value: 'residential', type: 'street', name: 'Bad Tölzer Straße', city: 'München', country: 'Deutschland' }),
      feature(11.5, 47.78, { osm_id: 5, osm_type: 'R', osm_key: 'boundary', osm_value: 'administrative', type: 'county', name: 'Landkreis Bad Tölz-Wolfratshausen', state: 'Bayern', country: 'Deutschland' }),
    ] })
    expect(places).toEqual([
      { id: 'N240109189', name: 'Bad Tölz', kind: 'town', region: 'Bayern, Deutschland', latitude: 47.7614, longitude: 11.5583 },
      { id: 'R5', name: 'Landkreis Bad Tölz-Wolfratshausen', kind: 'county', region: 'Bayern, Deutschland', latitude: 47.78, longitude: 11.5 },
    ])
  })

  it('say where a small place lies by the town or county it is in, then its state and country, and leave out what repeats the name or is not given', () => {
    const [village, region, country, city] = placesOfPhoton({ features: [
      place('Eurasburg', 'village', { county: 'Landkreis Bad Tölz-Wolfratshausen', state: 'Bayern', country: 'Deutschland' }, 11.4),
      place('Bayern', 'state', { state: 'Bayern', country: 'Deutschland' }, 11.3),
      place('Deutschland', 'country', { country: 'Deutschland' }, 10.4),
      place('Paris', 'city', { state: 'Île-de-France', country: 'France' }, 2.35, 48.85),
    ] })!
    expect(village!.region).toBe('Landkreis Bad Tölz-Wolfratshausen, Bayern, Deutschland')
    expect(region!.region).toBe('Deutschland')
    expect(country!.region).toBeNull()
    expect(city!.region).toBe('Île-de-France, France')
    // a district names the city it is a part of
    expect(placesOfPhoton({ features: [place('Schwabing', 'suburb', { city: 'München', state: 'Bayern', country: 'Deutschland' })] })![0]!.region).toBe('München, Bayern, Deutschland')
  })

  it('give the same place once where the node and the relation of one town are both hits, and not two places of one name that lie apart', () => {
    const places = placesOfPhoton({ features: [
      place('Paris', 'city', { state: 'Île-de-France', country: 'France' }, 2.3522, 48.8566),
      place('Paris', 'city', { state: 'Île-de-France', country: 'France', osm_type: 'R', osm_id: 2 }, 2.3524, 48.8567),
      place('Paris', 'city', { state: 'Texas', country: 'United States' }, -95.55, 33.66),
    ] })!
    expect(places.map(entry => entry.region)).toEqual(['Île-de-France, France', 'Texas, United States'])
    // a town drawn as a node (`place=town`) and as a relation (an administrative `city`) is one place, the first hit
    const twin = placesOfPhoton({ features: [
      place('Bad Tölz', 'town', { state: 'Bayern', country: 'Deutschland' }, 11.5583, 47.7614),
      feature(11.5584, 47.7615, { osm_id: 2, osm_type: 'R', osm_key: 'boundary', osm_value: 'administrative', type: 'city', name: 'Bad Tölz', state: 'Bayern', country: 'Deutschland' }),
    ] })!
    expect(twin.map(entry => [entry.kind, entry.id])).toEqual([['town', 'N1']])
    // a city and the state of the same name are two places
    expect(placesOfPhoton({ features: [place('Berlin', 'city', { country: 'Deutschland' }), place('Berlin', 'state', { state: 'Berlin', country: 'Deutschland' })] })!.map(entry => entry.kind)).toEqual(['city', 'region'])
  })

  it('are at most five by default, or the limit given', () => {
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
