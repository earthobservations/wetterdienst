import { describe, expect, it } from 'vitest'
import { coordinatesText, hemispheresOf, mapAtPoint, parseCoordinates } from '../../app/utils/coordinates'

// A position typed into the search (GH-3790)

function near(text: string, latitude: number, longitude: number, hemispheres = hemispheresOf('en')) {
  const point = parseCoordinates(text, hemispheres)
  expect(point, text).not.toBeNull()
  expect(point!.latitude, text).toBeCloseTo(latitude, 4)
  expect(point!.longitude, text).toBeCloseTo(longitude, 4)
}

describe('a position in decimal degrees', () => {
  it('reads a pair with a comma, a semicolon or a space between', () => {
    near('52.52, 13.40', 52.52, 13.4)
    near('52.52,13.40', 52.52, 13.4)
    near('52.52; 13.40', 52.52, 13.4)
    near('52.52 13.40', 52.52, 13.4)
    near('  52.52   13.40  ', 52.52, 13.4)
  })

  it('reads signs, so that the south and the west are negative', () => {
    near('-33.87, 151.21', -33.87, 151.21)
    near('40.71 -74.01', 40.71, -74.01)
    near('+52.52, +13.4', 52.52, 13.4)
    near('−33.87, 151.21', -33.87, 151.21)
  })

  it('reads a decimal comma where a semicolon or a space or a comma and a space separate', () => {
    near('52,52 13,40', 52.52, 13.4)
    near('52,52; 13,40', 52.52, 13.4)
    near('52,52, 13,40', 52.52, 13.4, hemispheresOf('de'))
  })

  it('does not read two whole numbers, whatever is between them: a year and a month, two station numbers, a decimal comma', () => {
    for (const locale of ['en', 'de', 'fr', 'nl', 'pl', 'cs', 'da', 'es', 'it', 'lb', 'de-hh']) {
      for (const text of ['52 13', '2024 11', '52, 13', '1,5', '0,5', '10,20', '00011, 00044', '52;13', '10384 10147'])
        expect(parseCoordinates(text, hemispheresOf(locale)), `${locale}: ${text}`).toBeNull()
    }
  })

  it('reads whole numbers that carry a degree sign', () => {
    near('52°, 13°', 52, 13)
    near('52° 13°', 52, 13)
  })

  it('reads a decimal point in every language, with a comma or without one', () => {
    for (const locale of ['en', 'de', 'fr', 'cs', 'da']) {
      near('52.5, 13.4', 52.5, 13.4, hemispheresOf(locale))
      near('52.5,13.4', 52.5, 13.4, hemispheresOf(locale))
      near('52.5 13', 52.5, 13, hemispheresOf(locale))
    }
  })

  it('reads a decimal comma with a comma and a space between only where the language writes one', () => {
    for (const locale of ['de', 'fr', 'nl', 'pl', 'cs', 'da', 'es', 'it', 'lb', 'de-hh'])
      near('52,52, 13,40', 52.52, 13.4, hemispheresOf(locale))
    expect(parseCoordinates('52,52, 13,40', hemispheresOf('en'))).toBeNull()
    // no space: `52,5,13,4` is a list of numbers
    expect(parseCoordinates('52,5,13,4', hemispheresOf('de'))).toBeNull()
  })

  it('reads a degree sign after the numbers', () => {
    near('52.52° 13.40°', 52.52, 13.4)
    near('52.52°, -13.40°', 52.52, -13.4)
  })

  it('does not read a latitude beyond 90 or a longitude beyond 180', () => {
    expect(parseCoordinates('91.0, 13.4')).toBeNull()
    expect(parseCoordinates('52.5, 181.0')).toBeNull()
    near('90.0, 180.0', 90, 180)
    near('-90.0, -180.0', -90, -180)
  })

  it('does not read what is no pair', () => {
    for (const text of ['', ' ', 'Berlin', '52.52', '52.52, 13.4, 100', '10384', '00011', '1.2.3, 4', 'dew point', '12:30', '52.52,', ',13.4'])
      expect(parseCoordinates(text), text).toBeNull()
  })
})

describe('a position with hemisphere letters', () => {
  it('reads degrees, minutes and seconds', () => {
    near('52°31\'N 13°24\'E', 52 + 31 / 60, 13.4)
    near('52°31\'12"N 13°24\'18"E', 52 + 31 / 60 + 12 / 3600, 13 + 24 / 60 + 18 / 3600)
    near('52° 31\' N, 13° 24\' E', 52 + 31 / 60, 13.4)
    near('52 31 N 13 24 E', 52 + 31 / 60, 13.4)
  })

  it('reads decimal minutes and decimal degrees', () => {
    near('52°31.2\'N 13°24.5\'E', 52 + 31.2 / 60, 13 + 24.5 / 60)
    near('52.52N 13.40E', 52.52, 13.4)
    near('52.52° N, 13.40° E', 52.52, 13.4)
    near('52,52N 13,40E', 52.52, 13.4)
  })

  it('reads the letter before the numbers', () => {
    near('N 52° 31.2\' E 13° 24\'', 52 + 31.2 / 60, 13.4)
    near('N52.52 E13.40', 52.52, 13.4)
  })

  it('lets the letters give the sign: south and west are negative', () => {
    near('33.87S 151.21E', -33.87, 151.21)
    near('40.71N 74.01W', 40.71, -74.01)
    near('33°52\'S 151°12\'E', -(33 + 52 / 60), 151.2)
  })

  it('reads the longitude first where the letters say so, and lower case', () => {
    near('13.40E 52.52N', 52.52, 13.4)
    near('13.40e 52.52n', 52.52, 13.4)
  })

  it('reads typographic marks for the minutes, the seconds and the degrees', () => {
    near('52º31′N 13º24′E', 52 + 31 / 60, 13.4)
    near('52°31′ 12″N 13°24′ 18″E', 52 + 31 / 60 + 12 / 3600, 13 + 24 / 60 + 18 / 3600)
    near('52°31\'12\'\'N 13°24\'18\'\'E', 52 + 31 / 60 + 12 / 3600, 13 + 24 / 60 + 18 / 3600)
  })

  it('takes the letter a language writes the east and the west with', () => {
    // German and Dutch: O is east
    near('52°31\'N 13°24\'O', 52 + 31 / 60, 13.4, hemispheresOf('de'))
    near('52°31\'N 13°24\'O', 52 + 31 / 60, 13.4, hemispheresOf('lb'))
    // French, Spanish, Italian: O is west
    near('52°31\'N 13°24\'O', 52 + 31 / 60, -13.4, hemispheresOf('fr'))
    near('52°31\'N 13°24\'O', 52 + 31 / 60, -13.4, hemispheresOf('es'))
    // Danish: Ø is east
    near('52°31\'N 13°24\'Ø', 52 + 31 / 60, 13.4, hemispheresOf('da'))
    // English has no O
    expect(parseCoordinates('52°31\'N 13°24\'O', hemispheresOf('en'))).toBeNull()
  })

  it('takes the Danish V for the west and the Czech S, J, V and Z for north, south, east and west, in those languages only', () => {
    near('52°31\'N 13°24\'V', 52 + 31 / 60, -13.4, hemispheresOf('da'))
    near('33°52\'S 151°12\'Ø', -(33 + 52 / 60), 151.2, hemispheresOf('da'))
    // Czech: S is the north, and the south is J
    near('52°31\'S 13°24\'V', 52 + 31 / 60, 13.4, hemispheresOf('cs'))
    near('33°52\'J 151°12\'V', -(33 + 52 / 60), 151.2, hemispheresOf('cs'))
    near('40°43\'S 74°0\'Z', 40 + 43 / 60, -74, hemispheresOf('cs'))
    near('52.52 S 13.40 V', 52.52, 13.4, hemispheresOf('cs'))
    // the Czech letters are not English: S is the south there, and V and Z are no letters
    near('33.87S 151.21E', -33.87, 151.21, hemispheresOf('en'))
    expect(parseCoordinates('52°31\'N 13°24\'V', hemispheresOf('en'))).toBeNull()
    expect(parseCoordinates('33°52\'J 151°12\'E', hemispheresOf('en'))).toBeNull()
    expect(parseCoordinates('33°52\'J 151°12\'E', hemispheresOf('de'))).toBeNull()
    // Czech readers still write N, E and W
    near('52°31\'N 13°24\'E', 52 + 31 / 60, 13.4, hemispheresOf('cs'))
  })

  it('does not read a minus beside a letter, two latitudes, a letter that is no hemisphere or an angle that is none', () => {
    for (const text of ['-52.5N 13.4E', '52.5N 13.4N', '52.5E 13.4W', '52.5X 13.4E', '52°61\'N 13°24\'E', '52.5°31\'N 13°24\'E', '52.5N', '52.5N 13.4', 'N 52.5 13.4', '95N 13E', '52N 190E', 'Berlin 52.5N 13.4E', 'no 12 so 13'])
      expect(parseCoordinates(text), text).toBeNull()
  })

  it('does not read minutes and seconds without a letter: a list of numbers is no angle', () => {
    expect(parseCoordinates('52°31\' 13°24\'')).toBeNull()
  })
})

describe('what the search shows and where it leads', () => {
  it('writes the point as the map does, with four decimals and no letters', () => {
    expect(coordinatesText({ latitude: 52.52, longitude: -13.4 })).toBe('52.5200, -13.4000')
  })

  it('leads to the map at the point', () => {
    expect(mapAtPoint({ latitude: 52.52, longitude: 13.4 })).toBe('/map?lat=52.5200&lon=13.4000')
    expect(mapAtPoint({ latitude: -33.8688, longitude: 151.2093 })).toBe('/map?lat=-33.8688&lon=151.2093')
  })

  it('knows the letters of each locale of the app', () => {
    expect(hemispheresOf('de-hh').east).toContain('O')
    expect(hemispheresOf('nl').east).toContain('O')
    expect(hemispheresOf('pl')).toMatchObject({ east: 'E', west: 'W', decimalComma: true })
    expect(hemispheresOf('en').decimalComma).toBe(false)
    expect(hemispheresOf('de').decimalComma).toBe(true)
    expect(hemispheresOf('it').west).toContain('O')
  })
})
