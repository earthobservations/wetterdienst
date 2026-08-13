import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// Guards the catalogs against drift: every key present in one locale must exist in all of the
// others, so no string silently falls back or goes missing when the user switches language.
// English is the reference, being the one every key is written in first.

const localesDir = fileURLToPath(new URL('../../i18n/locales', import.meta.url))
const glossaryDir = fileURLToPath(new URL('../../i18n/glossary', import.meta.url))

const locales = readdirSync(localesDir)
  .filter(name => name.endsWith('.json'))
  .map(name => name.replace(/\.json$/, ''))
  .sort()

function load(locale: string): Record<string, unknown> {
  return JSON.parse(readFileSync(`${localesDir}/${locale}.json`, 'utf-8'))
}

function flatten(obj: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    return value && typeof value === 'object' && !Array.isArray(value)
      ? flatten(value as Record<string, unknown>, path)
      : [path]
  })
}

/** The keys of one `export const <name>` record in a glossary module. */
function glossaryKeys(locale: string, name: string): string[] {
  const source = readFileSync(`${glossaryDir}/${locale}.ts`, 'utf-8')
  const block = source.split(`export const ${name}`)[1]?.split('export const')[0] ?? ''
  // keys are quoted when they start with a digit ('1_minute'), bare otherwise
  return [...block.matchAll(/^ {2}'?([a-z0-9_]+)'?:/gm)].map(match => match[1] as string).sort()
}

describe('i18n catalog parity', () => {
  const english = flatten(load('en')).sort()

  it('ships more than just english and german', () => {
    // the guard used to cover de and en only, while nine further catalogs went unchecked
    expect(locales.length).toBeGreaterThan(2)
    expect(locales).toContain('en')
  })

  it.each(locales.filter(locale => locale !== 'en'))('has the same set of keys as en in %s', (locale) => {
    const keys = flatten(load(locale)).sort()
    expect(keys.filter(key => !english.includes(key)), `keys in ${locale}.json missing from en.json`).toEqual([])
    expect(english.filter(key => !keys.includes(key)), `keys in en.json missing from ${locale}.json`).toEqual([])
  })

  it.each(locales)('has no empty translations in %s', (locale) => {
    const data = load(locale)
    for (const key of flatten(data)) {
      const value = key.split('.').reduce<any>((acc, part) => acc?.[part], data)
      expect(typeof value === 'string' && value.trim().length > 0, `${locale}: ${key} is empty`).toBe(true)
    }
  })
})

describe('glossary label parity', () => {
  // the curated labels are a separate catalog from the UI strings, and drift the same way: a label
  // added in one language and not the other leaves that locale showing a prettified raw id
  const records = ['parameters', 'resolutions', 'datasets']

  const glossaryLocales = readdirSync(glossaryDir)
    .filter(name => name.endsWith('.ts'))
    .map(name => name.replace(/\.ts$/, ''))
    .sort()

  it('ships a glossary for every ui locale', () => {
    // a locale without one silently falls back to english labels
    expect(glossaryLocales).toEqual(locales)
  })

  it.each(records)('has the same %s in every glossary locale', (record) => {
    const reference = glossaryKeys('en', record)
    expect(reference.length, `en glossary has no ${record}`).toBeGreaterThan(0)
    for (const locale of glossaryLocales) {
      expect(glossaryKeys(locale, record), `${locale} glossary ${record} differ from en`).toEqual(reference)
    }
  })

  it.each(glossaryLocales)('is actually translated in %s', (locale) => {
    if (locale === 'en')
      return
    // Not a per-label check: cognates are real (German "Wind", French "Observations"), so a label
    // matching english proves nothing. A whole catalog matching does -- that is a copied stub.
    const values = (text: string) =>
      [...text.matchAll(/^ {2}'?[a-z0-9_]+'?: '(.*)',$/gm)].map(match => match[1])
    const theirs = values(readFileSync(`${glossaryDir}/${locale}.ts`, 'utf-8'))
    const ours = values(readFileSync(`${glossaryDir}/en.ts`, 'utf-8'))
    const same = theirs.filter((label, index) => label === ours[index]).length
    expect(same / ours.length, `${locale} glossary is largely the english one`).toBeLessThan(0.5)
  })
})
