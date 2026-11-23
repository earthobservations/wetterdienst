import { describe, expect, it } from 'vitest'
import { PLACE_LINK_TEXT_MAX, PLACE_QUERY_KEYS, placeOfQuery, queryOfPlace } from '../../app/utils/place-link'

// A place found by its name, in a link (GH-3791): `lat`, `lon`, `placeName` and `placeRegion`, so that a shared link shows the place without asking
// OpenStreetMap's search again. What a link carries is text of somebody's making: it is read strictly and shown as text.

const BAD_TOELZ = { name: 'Bad Tölz', region: 'Bayern, Germany', latitude: 47.7614, longitude: 11.5583 }

describe('the place of a link', () => {
  it('is written with its position to four decimals, as the map writes one, and its name and where it lies', () => {
    expect(queryOfPlace(BAD_TOELZ)).toEqual({ lat: '47.7614', lon: '11.5583', placeName: 'Bad Tölz', placeRegion: 'Bayern, Germany' })
    expect(queryOfPlace({ ...BAD_TOELZ, latitude: 47.76, longitude: 11.5 })).toMatchObject({ lat: '47.7600', lon: '11.5000' })
  })

  it('has no region key for a place that lies nowhere, a country itself', () => {
    expect(queryOfPlace({ name: 'France', region: null, latitude: 46.2, longitude: 2.2 })).toEqual({ lat: '46.2000', lon: '2.2000', placeName: 'France' })
  })

  it('is read back as it was written', () => {
    expect(placeOfQuery(queryOfPlace(BAD_TOELZ))).toEqual(BAD_TOELZ)
    expect(placeOfQuery(queryOfPlace({ name: 'France', region: null, latitude: 46.2, longitude: 2.2 }))).toEqual({ name: 'France', region: null, latitude: 46.2, longitude: 2.2 })
  })

  it('needs a position and a name: a position alone, which is what the map writes, is no place of this sort', () => {
    expect(placeOfQuery({ lat: '47.7614', lon: '11.5583' })).toBeNull()
    expect(placeOfQuery({ placeName: 'Bad Tölz' })).toBeNull()
    expect(placeOfQuery({ lat: '47.7614', placeName: 'Bad Tölz' })).toBeNull()
    expect(placeOfQuery({ lat: '47.7614', lon: '11.5583', placeName: '   ' })).toBeNull()
    expect(placeOfQuery({})).toBeNull()
  })

  it.each([
    ['not a number', { lat: 'abc', lon: '11.5' }],
    ['Infinity', { lat: '1e400', lon: '11.5' }],
    ['a latitude beyond the pole', { lat: '91', lon: '11.5' }],
    ['a longitude beyond the date line', { lat: '47.7', lon: '181' }],
    ['a number with text after it', { lat: '47.7abc', lon: '11.5' }],
    ['a position written in degrees', { lat: '47°45′', lon: '11.5' }],
  ])('is none where the position is %s', (_name, position) => {
    expect(placeOfQuery({ ...position, placeName: 'Bad Tölz' })).toBeNull()
  })

  it('reads the first of a key that is given more than once, and signed positions', () => {
    expect(placeOfQuery({ lat: ['-33.9', '1'], lon: '151.2', placeName: ['Sydney', 'Other'] })).toMatchObject({ name: 'Sydney', latitude: -33.9, longitude: 151.2 })
  })

  it('keeps text as text: a name with markup is a name, one run together from many lines is one line, and an over long one is none', () => {
    expect(placeOfQuery({ lat: '1', lon: '1', placeName: '<img src=x onerror=alert(1)>' })!.name).toBe('<img src=x onerror=alert(1)>')
    expect(placeOfQuery({ lat: '1', lon: '1', placeName: 'Bad\n  Tölz' })!.name).toBe('Bad Tölz')
    expect(placeOfQuery({ lat: '1', lon: '1', placeName: 'x'.repeat(PLACE_LINK_TEXT_MAX + 1) })).toBeNull()
    expect(placeOfQuery({ lat: '1', lon: '1', placeName: 'x'.repeat(PLACE_LINK_TEXT_MAX) })).not.toBeNull()
    // an over long region is left out, the place is kept
    expect(placeOfQuery({ lat: '1', lon: '1', placeName: 'A', placeRegion: 'x'.repeat(PLACE_LINK_TEXT_MAX + 1) })!.region).toBeNull()
  })

  it('has four keys, which a page takes out of its link where the place is no longer the one asked about', () => {
    expect([...PLACE_QUERY_KEYS]).toEqual(['lat', 'lon', 'placeName', 'placeRegion'])
    expect(Object.keys(queryOfPlace(BAD_TOELZ)).sort()).toEqual([...PLACE_QUERY_KEYS].sort())
  })
})
