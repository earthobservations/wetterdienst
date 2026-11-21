// A position typed into the search (GH-3790): `52.52, 13.40`, `-33.87 151.21`, `52°31'N 13°24'E`, `N 52° 31.2' E 13° 24'`.
// Pure, so that a test holds every form; the search shows a place that leads to the map at that point.

export interface Coordinates {
  latitude: number
  longitude: number
}

/**
 * The letters a language writes the east and the west with, besides N and S. East is E everywhere, and where a language
 * writes it with another letter as well (German and Dutch `O` for Ost/Oost, Danish `Ø`) that one is east too; where `O`
 * is the west (French, Spanish and Italian: Ouest, Oeste, Ovest) it is that.
 */
export interface Hemispheres {
  east: string
  west: string
}

export const HEMISPHERES: Hemispheres = { east: 'E', west: 'W' }

/** The hemisphere letters of a locale of the app (`de-hh` and `lb` write `O` for east, as German does) */
export function hemispheresOf(locale: string): Hemispheres {
  const language = locale.split('-')[0]!
  if (['de', 'nl', 'lb'].includes(language))
    return { east: 'EO', west: 'W' }
  if (language === 'da')
    return { east: 'EØ', west: 'W' }
  if (['fr', 'es', 'it'].includes(language))
    return { east: 'E', west: 'WO' }
  return HEMISPHERES
}

const NUMBER = String.raw`\d+(?:[.,]\d+)?`

function numberOf(text: string): number {
  return Number(text.replace(',', '.'))
}

/** The point, or null for a latitude beyond 90 or a longitude beyond 180 */
function inRange(latitude: number, longitude: number): Coordinates | null {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude))
    return null
  if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180)
    return null
  return { latitude, longitude }
}

/** The signs and marks that are typed in many ways, as one: `−` `º` `′` `’` `″` `''` */
function normalise(text: string): string {
  return text
    .trim()
    .replace(/[\u2212\u2012\u2013\u2014\u2015]/g, '-')
    .replace(/[\u00BA\u02DA\u2218]/g, '°')
    .replace(/[\u2032\u2019\u2018\u00B4`]/g, '\'')
    .replace(/[″”“]/g, '"')
    .replace(/''/g, '"')
    .replace(/\s+/g, ' ')
}

/** A pair of signed decimal degrees: `52.52, 13.40`, `52.52 13.40`, `52,52 13,40`, `52.52; 13.40`, `52.52° 13.40°` */
function decimalPair(text: string): Coordinates | null {
  const plain = text.replace(/ ?°/g, '')
  const signed = String.raw`[-+]?${NUMBER}`
  let match: RegExpMatchArray | null
  // a semicolon separates, and either number may have a decimal comma
  if ((match = plain.match(new RegExp(String.raw`^(${signed}) ?; ?(${signed})$`))))
    return inRange(numberOf(match[1]!), numberOf(match[2]!))
  // a comma separates, where the numbers have a decimal point or none: `52.52, 13.40`, `52,13`
  if ((match = plain.match(/^([-+]?\d+(?:\.\d+)?) ?, ?([-+]?\d+(?:\.\d+)?)$/)))
    return inRange(numberOf(match[1]!), numberOf(match[2]!))
  // numbers with a decimal comma, separated by a comma and a space: `52,52, 13,40`
  if ((match = plain.match(/^([-+]?\d+,\d+), ([-+]?\d+,\d+)$/)))
    return inRange(numberOf(match[1]!), numberOf(match[2]!))
  // only a space separates: one of the numbers has decimals, so that two whole numbers ("2024 11") are no point
  if ((match = plain.match(new RegExp(String.raw`^(${signed}) (${signed})$`))) && /[.,]\d/.test(plain))
    return inRange(numberOf(match[1]!), numberOf(match[2]!))
  return null
}

/** One half of a position, without its letter: degrees, and where written minutes and seconds (`52°31'12"`, `52 31`, `52.52`) */
function degrees(text: string): number | null {
  const parts = text.replace(/^[\s,;]+|[\s,;]+$/g, '').split(/[°'"\s]+/).filter(Boolean)
  if (parts.length < 1 || parts.length > 3 || !parts.every(part => new RegExp(`^${NUMBER}$`).test(part)))
    return null
  // a part is whole where a smaller one follows it: `52.5° 31'` is no angle
  if (parts.slice(0, -1).some(part => !Number.isInteger(numberOf(part))))
    return null
  const [d, m = 0, s = 0] = parts.map(numberOf)
  if (m >= 60 || s >= 60)
    return null
  return d! + m / 60 + s / 3600
}

/**
 * A position with its hemisphere letters, in either order: `52°31'N 13°24'E`, `52.52N, 13.40E`, `N 52° 31.2' E 13° 24'`,
 * `52°31'12"N 13°24'18"E`, `13.40E 52.52N`. The letters give the sign, so a minus beside one is no position.
 */
function withLetters(text: string, hemispheres: Hemispheres): Coordinates | null {
  const known = `NS${hemispheres.east}${hemispheres.west}`.toUpperCase()
  const found = [...text.matchAll(/[a-zöø]/gi)]
  if (found.length !== 2 || found.some(letter => !known.includes(letter[0]!.toUpperCase())))
    return null
  const [one, two] = found as [RegExpMatchArray, RegExpMatchArray]
  const closes = text.slice(0, one.index).replace(/[ ,;]/g, '') !== ''
  // the letter closes the first half (`52°31'N 13°24'E`), or both open theirs (`N 52° E 13°`)
  const split = closes ? one.index! + 1 : two.index!
  const parts = [
    { text: text.slice(0, split), letter: one[0].toUpperCase() },
    { text: text.slice(split), letter: two[0].toUpperCase() },
  ].map(part => ({ letter: part.letter, value: degrees(part.text.replace(/[a-zöø]/gi, '')) }))
  const [first, second] = parts as [{ letter: string, value: number | null }, { letter: string, value: number | null }]
  if (first.value === null || second.value === null)
    return null
  const northSouth = (letter: string) => letter === 'N' || letter === 'S'
  // one half is the latitude and the other the longitude
  if (northSouth(first.letter) === northSouth(second.letter))
    return null
  const signed = (half: { letter: string, value: number | null }) => ['S', ...hemispheres.west.toUpperCase().split('')].includes(half.letter) ? -half.value! : half.value!
  const [latitude, longitude] = northSouth(first.letter) ? [first, second] : [second, first]
  return inRange(signed(latitude!), signed(longitude!))
}

/**
 * The position a text names, or null where it is none. Latitude comes first unless hemisphere letters say otherwise. Two
 * whole numbers with only a space between are not taken (a year and a month, two station numbers). Degrees, minutes and
 * seconds need their hemisphere letters; without them the position is in decimal degrees.
 *
 * @param text What was typed
 * @param hemispheres The letters the language writes the east and the west with
 * @example
 * parseCoordinates('52.52, 13.40') // { latitude: 52.52, longitude: 13.4 }
 * parseCoordinates('52°31\'N 13°24\'E') // { latitude: 52.5166…, longitude: 13.4 }
 */
export function parseCoordinates(text: string, hemispheres: Hemispheres = HEMISPHERES): Coordinates | null {
  const normal = normalise(text)
  if (!normal || normal.length > 60 || !/\d/.test(normal))
    return null
  if (/[a-zöø]/i.test(normal))
    return withLetters(normal, hemispheres)
  if (/['"]/.test(normal))
    return null
  return decimalPair(normal)
}

/** A position as the search shows it: signed degrees with four decimals, as the map's address writes them */
export function coordinatesText(point: Coordinates): string {
  return `${point.latitude.toFixed(4)}, ${point.longitude.toFixed(4)}`
}

/** The address of the map at a point (`/map?lat=52.5200&lon=13.4000`) */
export function mapAtPoint(point: Coordinates): string {
  return `/map?lat=${point.latitude.toFixed(4)}&lon=${point.longitude.toFixed(4)}`
}
