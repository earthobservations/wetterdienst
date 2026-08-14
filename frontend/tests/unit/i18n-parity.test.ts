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

describe('unit type labels', () => {
  // The glossary filter and the Explorer unit-target rows name the quantity a parameter is measured
  // in. Six of the backend's types had no label at all and fell through to the raw id, so the filter
  // read "energy per area" and "wind scale" in every language. This is the list the backend serves
  // via GET /api/glossary; a new quantity there needs a label here.
  const unitTypes = [
    'angle',
    'concentration',
    'conductivity',
    'degree_day',
    'degree_hour',
    'dimensionless',
    'energy_per_area',
    'fraction',
    'length_long',
    'length_medium',
    'length_short',
    'mass_per_volume',
    'power_per_area',
    'precipitation',
    'precipitation_intensity',
    'pressure',
    'significant_weather',
    'speed',
    'temperature',
    'time',
    'turbidity',
    'volume_per_time',
    'wind_scale',
  ]

  /** `energy_per_area` -> `unitEnergyPerArea`, the key `useUnitTypeLabel` builds. */
  function settingsKey(type: string): string {
    return `unit${type.replace(/(?:^|_)(\w)/g, (_, c: string) => c.toUpperCase())}`
  }

  it.each(locales)('names every quantity in %s', (locale) => {
    const settings = (load(locale).settings ?? {}) as Record<string, string>
    const missing = unitTypes.filter(type => !settings[settingsKey(type)]?.trim())
    expect(missing, `${locale} has no label for these unit types`).toEqual([])
  })
})

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

  it('labels every parameter the backend serves', () => {
    // Before this, 464 of the 514 fell through to a prettified raw id -- "Chlorid Concentration"
    // -- which reads as English in every language. The count is asserted rather than the list, so
    // adding a parameter upstream fails here instead of quietly regressing to the fallback.
    // Refresh with: curl -s localhost:3000/api/glossary | jq 'map(.name) | unique | length'
    expect(glossaryKeys('en', 'parameters').length).toBeGreaterThanOrEqual(514)
  })

  it.each(records)('has the same %s in every glossary locale', (record) => {
    const reference = glossaryKeys('en', record)
    expect(reference.length, `en glossary has no ${record}`).toBeGreaterThan(0)
    for (const locale of glossaryLocales) {
      expect(glossaryKeys(locale, record), `${locale} glossary ${record} differ from en`).toEqual(reference)
    }
  })

  /** The `key: 'label'` pairs of one record in a glossary module. */
  function glossaryLabels(locale: string, name: string): Record<string, string> {
    const source = readFileSync(`${glossaryDir}/${locale}.ts`, 'utf-8')
    const block = source.split(`export const ${name}`)[1]?.split('export const')[0] ?? ''
    return Object.fromEntries(
      [...block.matchAll(/^ {2}'?([a-z0-9_]+)'?: '(.*)',$/gm)].map(match => [match[1], match[2]]),
    )
  }

  it.each(glossaryLocales)('is actually translated in %s', (locale) => {
    if (locale === 'en')
      return
    // Not a per-label check: cognates are real (German "Wind", French "Observations"), so one label
    // matching english proves nothing. A whole catalog matching does -- that is a copied stub.
    // Compared key by key, and per record, so reordering a copy cannot slip through.
    for (const record of records) {
      const theirs = glossaryLabels(locale, record)
      const ours = glossaryLabels('en', record)
      const keys = Object.keys(ours)
      const same = keys.filter(key => theirs[key] === ours[key]).length
      expect(
        same / keys.length,
        `${locale} ${record} are largely the english ones`,
      ).toBeLessThan(0.5)
    }
  })
})
