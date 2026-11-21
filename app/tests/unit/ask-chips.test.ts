import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { DateTime } from 'luxon'
import { describe, expect, it } from 'vitest'
import { acceptsChoice, queryOfChoice, queryOfPress, readChoices } from '../../app/utils/ask/chip'
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
  it('holds the four chips of the home page, in the order it offers them', () => {
    expect(CHIPS.map(chip => chip.id)).toEqual(['rain', 'summer', 'wind', 'download'])
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

  it('has no explanation yet: step 1b of GH-3764 writes it', () => {
    expect(chip.explanation).toBeUndefined()
  })

  it('names each choice once in the link, and none of another chip\'s', () => {
    const own = (chip.choices ?? []).map(choice => choice.param)
    expect(new Set(own).size).toBe(own.length)
    for (const other of CHIPS.filter(each => each !== chip))
      expect((other.choices ?? []).map(choice => choice.param).filter(param => own.includes(param))).toEqual([])
  })
})

describe('the choices of the wind chip, in the link', () => {
  const wind = chipOf('wind')!
  const NOW = DateTime.fromISO('2026-11-21T10:00:00', { zone: 'Europe/Berlin' })

  it('read the day of `&day=`, and the last 26 December where the link has none or none that is a day', () => {
    expect(readChoices(wind, { day: '2025-12-26' }, NOW)).toEqual({ day: '2025-12-26' })
    expect(readChoices(wind, {}, NOW)).toEqual({ day: '2025-12-26' })
    for (const day of ['2025-13-45', '2025-02-30', 'yesterday', ''])
      expect(readChoices(wind, { day }, NOW)).toEqual({ day: '2025-12-26' })
    expect(readChoices(wind, { day: '2024-03-01' }, NOW)).toEqual({ day: '2024-03-01' })
  })

  it('are none for a chip without them', () => {
    expect(readChoices(chipOf('rain')!, { day: '2025-12-26' }, NOW)).toEqual({})
  })

  it('take a day up to yesterday', () => {
    const [day] = wind.choices!
    expect(acceptsChoice(day!, '2026-11-20', NOW)).toBe(true)
    expect(acceptsChoice(day!, '2026-11-21', NOW)).toBe(false)
    expect(acceptsChoice(day!, '', NOW)).toBe(false)
    expect(acceptsChoice(day!, 'x', NOW)).toBe(false)
  })

  it('are kept by a press on the wind chip, closing it too, and taken out by a press on any other', () => {
    const link = { ask: 'wind', day: '2025-12-26', place: '02564' }
    expect(queryOfPress(link, CHIPS, 'wind', 'wind')).toEqual({ day: '2025-12-26', place: '02564' })
    expect(queryOfPress({ ask: 'rain', day: '2025-12-26' }, CHIPS, 'wind', 'rain')).toEqual({ ask: 'wind', day: '2025-12-26' })
    expect(queryOfPress({ ask: 'rain' }, CHIPS, 'wind', 'rain')).toEqual({ ask: 'wind' })
    expect(queryOfPress(link, CHIPS, 'summer', 'wind')).toEqual({ ask: 'summer', place: '02564' })
    expect(queryOfPress({ place: '02564' }, CHIPS, 'rain', null)).toEqual({ ask: 'rain', place: '02564' })
  })

  it('are written by a change of the day, which opens the wind chip', () => {
    expect(queryOfChoice({ ask: 'wind', day: '2025-12-26', place: '02564' }, 'wind', 'day', '2024-01-05')).toEqual({ ask: 'wind', day: '2024-01-05', place: '02564' })
  })
})
