import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// Guards the German/English catalogs against drift: every key present in one
// locale must exist in the other, so no string silently falls back or goes
// missing when the user switches language.

function load(locale: string): Record<string, unknown> {
  const url = new URL(`../../i18n/locales/${locale}.json`, import.meta.url)
  return JSON.parse(readFileSync(fileURLToPath(url), 'utf-8'))
}

function flatten(obj: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    return value && typeof value === 'object' && !Array.isArray(value)
      ? flatten(value as Record<string, unknown>, path)
      : [path]
  })
}

describe('i18n catalog parity', () => {
  const de = flatten(load('de')).sort()
  const en = flatten(load('en')).sort()

  it('has the same set of keys in de and en', () => {
    const missingInEn = de.filter(k => !en.includes(k))
    const missingInDe = en.filter(k => !de.includes(k))
    expect(missingInEn, 'keys present in de.json but missing in en.json').toEqual([])
    expect(missingInDe, 'keys present in en.json but missing in de.json').toEqual([])
  })

  it('has no empty translations', () => {
    for (const locale of ['de', 'en']) {
      const data = load(locale)
      for (const key of flatten(data)) {
        const value = key.split('.').reduce<any>((acc, part) => acc?.[part], data)
        expect(typeof value === 'string' && value.trim().length > 0, `${locale}: ${key} is empty`).toBe(true)
      }
    }
  })
})
