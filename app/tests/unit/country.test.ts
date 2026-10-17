import { describe, expect, it } from 'vitest'
import { flagEmoji, MULTINATIONAL } from '../../app/utils/country'

describe('flagEmoji', () => {
  it('draws the flag of a country from its code', () => {
    expect(flagEmoji('DE')).toBe('🇩🇪')
    expect(flagEmoji('GB')).toBe('🇬🇧')
    expect(flagEmoji('US')).toBe('🇺🇸')
  })

  it('gives a provider of several countries a globe, not a flag', () => {
    expect(MULTINATIONAL).toBe('ZZ')
    expect(flagEmoji(MULTINATIONAL)).toBe('🌐')
  })

  it.each(['', 'de', 'DEU', 'D1', ' D'])('draws nothing for %j, which is no code', (code) => {
    expect(flagEmoji(code)).toBe('')
  })
})
