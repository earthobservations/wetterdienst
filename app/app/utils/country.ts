/** The `country_code` the backend gives a provider of several countries, which has no flag of its own */
export const MULTINATIONAL = 'ZZ'

/**
 * The flag of a country as an emoji, from its ISO 3166-1 alpha-2 code: two regional indicator symbols,
 * which a system with the flag draws as one. The code of a provider of several countries gets a globe,
 * and anything that is no code gets nothing, so a card never shows two stray letters.
 *
 * @example
 * flagEmoji('DE') // '🇩🇪'
 */
export function flagEmoji(countryCode: string): string {
  if (countryCode === MULTINATIONAL)
    return '🌐'
  if (!/^[A-Z]{2}$/.test(countryCode))
    return ''
  const offset = 0x1F1E6 - 'A'.charCodeAt(0)
  return String.fromCodePoint(...[...countryCode].map(letter => letter.charCodeAt(0) + offset))
}
