/**
 * The flag of a country as an emoji, from its ISO 3166-1 alpha-2 code: two regional indicator symbols,
 * which a system with the flag draws as one. A provider of several countries has no code (the backend gives
 * `null`) and gets a globe, and anything else that is no code gets nothing, so a card never shows two stray
 * letters.
 *
 * @example
 * flagEmoji('DE') // '🇩🇪'
 */
export function flagEmoji(countryCode: string | null): string {
  if (countryCode === null)
    return '🌐'
  if (!/^[A-Z]{2}$/.test(countryCode))
    return ''
  const offset = 0x1F1E6 - 'A'.charCodeAt(0)
  return String.fromCodePoint(...[...countryCode].map(letter => letter.charCodeAt(0) + offset))
}
