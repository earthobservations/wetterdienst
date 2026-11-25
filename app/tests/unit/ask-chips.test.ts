import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { DateTime } from 'luxon'
import { describe, expect, it } from 'vitest'
import { acceptsChoice, queryOfChoice, queryOfPress, readChoices, readExplicit } from '../../app/utils/ask/chip'
import { chipOf, CHIPS, isChip } from '../../app/utils/ask/registry'
import { TOOLS } from '../../app/utils/sections'

// "Ask the weather": a chip is ONE definition (utils/ask/chip.ts), and the home page renders whatever the registry holds
// (GH-3764). These hold the registry to the chips there are, and every definition to what it must carry for the page to
// need no code of its own for it: its texts in all eleven languages, a tool to lead into, and the way its choices are
// read from the link and written to it. The answers themselves are held by answers.test.ts, the page by
// tests/nuxt/components/AskTheWeather.test.ts.

const APP = join(__dirname, '..', '..')
const LOCALES = join(APP, 'i18n', 'locales')
const CHIPS_DIR = join(APP, 'app', 'utils', 'ask', 'chips')

const catalogs = readdirSync(LOCALES)
  .filter(name => name.endsWith('.json'))
  .map(name => ({ locale: name.replace(/\.json$/, ''), messages: JSON.parse(readFileSync(join(LOCALES, name), 'utf8')) as Record<string, unknown> }))

function has(messages: Record<string, unknown>, key: string): boolean {
  let node: unknown = messages
  for (const part of key.split('.')) {
    if (node === null || typeof node !== 'object' || !(part in node))
      return false
    node = (node as Record<string, unknown>)[part]
  }
  return typeof node === 'string'
}

describe('the registry', () => {
  it('holds the five chips of the home page, in the order it offers them', () => {
    expect(CHIPS.map(chip => chip.id)).toEqual(['rain', 'season', 'day', 'warnings', 'download'])
  })

  it('holds one definition for every file of chips/, and no id twice', () => {
    const files = readdirSync(CHIPS_DIR).filter(name => name.endsWith('.ts')).map(name => name.replace(/\.ts$/, '')).sort()
    expect(CHIPS.map(chip => chip.id).sort()).toEqual(files)
    expect(new Set(CHIPS.map(chip => chip.id)).size).toBe(CHIPS.length)
  })

  it('finds a chip by the name a link carries, and none by any other', () => {
    for (const chip of CHIPS) {
      expect(chipOf(chip.id)).toBe(chip)
      expect(isChip(chip.id)).toBe(true)
    }
    for (const other of ['', 'RAIN', 'sun', undefined, null, ['rain'], 'constructor'])
      expect(isChip(other)).toBe(false)
  })

  it('has eleven locales to hold the definitions to', () => {
    expect(catalogs.map(catalog => catalog.locale).sort()).toEqual(['cs', 'da', 'de', 'de-hh', 'en', 'es', 'fr', 'it', 'lb', 'nl', 'pl'])
  })
})

describe.each(CHIPS.map(chip => [chip.id, chip] as const))('the %s chip', (id, chip) => {
  it('leads into a tool of the app, and has an icon', () => {
    expect(TOOLS.map(tool => tool.key)).toContain(chip.tool)
    expect(chip.icon).toMatch(/^i-ph-[a-z-]+$/)
  })

  it('has every key it uses in all eleven locales', () => {
    expect(chip.i18n.length).toBeGreaterThan(0)
    for (const { locale, messages } of catalogs) {
      const missing = chip.i18n.filter(key => !has(messages, key))
      expect(missing, `${id} in ${locale}`).toEqual([])
    }
  })

  it('lists the keys of its question, its source line and its verdict scale', () => {
    expect(chip.i18n).toContain(chip.from)
    for (const key of Object.values(chip.scale))
      expect(chip.i18n).toContain(key)
    for (const choice of chip.choices ?? [])
      expect(chip.i18n).toContain(choice.label)
  })

  it('lists every key its file writes: a key it uses and does not list is held by no test', () => {
    const source = readFileSync(join(CHIPS_DIR, `${id}.ts`), 'utf8')
    const written = new Set([...source.matchAll(/'(ask\.[\w.]+)'/g)].map(match => match[1]!))
    expect([...written].filter(key => !chip.i18n.includes(key))).toEqual([])
  })

  it('has an explanation, which tests/unit/ask-methods.test.ts holds to its sources and its words', () => {
    expect(chip.explanation.rules.length).toBeGreaterThan(0)
  })

  it('names each choice once in the link, and none of another chip\'s', () => {
    const own = (chip.choices ?? []).map(choice => choice.param)
    expect(new Set(own).size).toBe(own.length)
    for (const other of CHIPS.filter(each => each !== chip))
      expect((other.choices ?? []).map(choice => choice.param).filter(param => own.includes(param))).toEqual([])
  })
})

describe('the choices of the day chip, in the link', () => {
  const day = chipOf('day')!
  const NOW = DateTime.fromISO('2026-11-21T10:00:00', { zone: 'Europe/Berlin' })

  it('read the day of `&day=`, and the same date last year where the link has none or none that is a day', () => {
    expect(readChoices(day, { day: '2025-12-26' }, NOW)).toEqual({ measure: 'wind', day: '2025-12-26' })
    expect(readChoices(day, {}, NOW)).toEqual({ measure: 'wind', day: '2025-11-21' })
    for (const bad of ['2025-13-45', '2025-02-30', 'yesterday', ''])
      expect(readChoices(day, { day: bad }, NOW)).toEqual({ measure: 'wind', day: '2025-11-21' })
    expect(readChoices(day, { day: '2024-03-01' }, NOW)).toEqual({ measure: 'wind', day: '2024-03-01' })
  })

  it('read the measure of `&measure=`, the wind where the link has none or none that is one', () => {
    for (const measure of ['wind', 'sun', 'rain', 'temperature', 'snow'])
      expect(readChoices(day, { measure, day: '2025-12-26' }, NOW).measure).toBe(measure)
    for (const measure of ['', 'Sun', 'heat', 'snowfall', 'constructor'])
      expect(readChoices(day, { measure, day: '2025-12-26' }, NOW).measure).toBe('wind')
  })

  it('keep the old link: `?ask=wind` is the day chip asking about the wind, and a measure of the link is its own', () => {
    expect(chipOf('wind')).toBe(day)
    expect(readExplicit(day, { ask: 'wind', day: '2025-12-26' }, NOW)).toEqual({ measure: 'wind', day: '2025-12-26' })
    // the wind and the day of an old link are what the reader sees, and a new measure is not taken away by the alias
    expect(readExplicit(day, { ask: 'wind', measure: 'sun' }, NOW)).toEqual({ measure: 'sun' })
    expect(readExplicit(day, { ask: 'day', day: '2025-12-26' }, NOW)).toEqual({ day: '2025-12-26' })
    expect(readChoices(day, { ask: 'wind', day: '2025-12-26' }, NOW)).toEqual({ measure: 'wind', day: '2025-12-26' })
  })

  it('are none for a chip without them', () => {
    expect(readChoices(chipOf('rain')!, { day: '2025-12-26' }, NOW)).toEqual({})
  })

  it('take a day up to yesterday, and one of the five measures', () => {
    const [measure, dayChoice] = day.choices!
    expect(acceptsChoice(dayChoice!, '2026-11-20', NOW)).toBe(true)
    expect(acceptsChoice(dayChoice!, '2026-11-21', NOW)).toBe(false)
    expect(acceptsChoice(dayChoice!, '', NOW)).toBe(false)
    expect(acceptsChoice(dayChoice!, 'x', NOW)).toBe(false)
    expect(['wind', 'sun', 'rain', 'temperature', 'snow'].map(value => acceptsChoice(measure!, value, NOW))).toEqual([true, true, true, true, true])
    expect(['', 'heat', 'Sun'].map(value => acceptsChoice(measure!, value, NOW))).toEqual([false, false, false])
  })

  it('are kept by a press on the day chip, closing it too, and taken out by a press on any other', () => {
    const link = { ask: 'day', measure: 'sun', day: '2025-12-26', place: '02564' }
    expect(queryOfPress(link, CHIPS, 'day', 'day')).toEqual({ measure: 'sun', day: '2025-12-26', place: '02564' })
    expect(queryOfPress({ ask: 'rain', day: '2025-12-26' }, CHIPS, 'day', 'rain')).toEqual({ ask: 'day', day: '2025-12-26' })
    expect(queryOfPress({ ask: 'rain' }, CHIPS, 'day', 'rain')).toEqual({ ask: 'day' })
    expect(queryOfPress(link, CHIPS, 'season', 'day')).toEqual({ ask: 'season', place: '02564' })
    expect(queryOfPress({ place: '02564' }, CHIPS, 'rain', null)).toEqual({ ask: 'rain', place: '02564' })
  })

  it('are written by a change of the day or the measure, which opens the day chip', () => {
    expect(queryOfChoice({ ask: 'day', day: '2025-12-26', place: '02564' }, 'day', 'day', '2024-01-05')).toEqual({ ask: 'day', day: '2024-01-05', place: '02564' })
    expect(queryOfChoice({ ask: 'day', day: '2025-12-26' }, 'day', 'measure', 'snow')).toEqual({ ask: 'day', day: '2025-12-26', measure: 'snow' })
    // an old link names the wind and no more: the link the page writes next says so
    expect(queryOfChoice({ ask: 'wind', day: '2025-12-26' }, 'day', 'day', '2024-01-05', { measure: 'wind', day: '2025-12-26' })).toEqual({ ask: 'day', day: '2024-01-05', measure: 'wind' })
  })
})
