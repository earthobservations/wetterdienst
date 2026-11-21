import type { Reading } from '../../app/utils/answers'
import type { ChipEnv } from '../../app/utils/ask/chip'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { DateTime } from 'luxon'
import { describe, expect, it } from 'vitest'
import {
  countIn,
  lastSeason,
  newestNormal,
  newestNormalEnd,
  normalAvailability,
  normalOf,
  normalsAt,
  SEASON_MONTHS,
  seasonLabel,
  seasonMeans,
  seasonOver,
  SEASONS,
} from '../../app/utils/answers'
import { acceptsChoice, queryOfChoice, queryOfPress, readChoices } from '../../app/utils/ask/chip'
import { season } from '../../app/utils/ask/chips/season'
import { chipIdOf, chipOf, CHIPS } from '../../app/utils/ask/registry'

// Ask the weather, step 2a (GH-3764): the season and the reference period are the reader's choices. These hold the windows of the
// seasons (the winter spans the turn of the year), which season is complete when, the list of normals (computed from the year, not
// written down), the normals a station has too few seasons of, how a link is read, and the question in the eleven languages.

const BERLIN = 'Europe/Berlin'
const at = (iso: string) => DateTime.fromISO(iso, { zone: 'utc' })

/** The monthly means of the months of a season in the years of `first` to `last` (the winter of a year has the December before it), each season `base(year)` */
function monthly(kind: typeof SEASONS[number], first: number, last: number, base: (year: number) => number = () => 10): Reading[] {
  return Array.from({ length: last - first + 1 }, (_, index) => first + index).flatMap(year => SEASON_MONTHS[kind].map((month) => {
    const calendarYear = kind === 'winter' && month === 12 ? year - 1 : year
    return { parameter: 'temperature_air_mean_2m', timestamp: `${calendarYear}-${String(month).padStart(2, '0')}-01T00:00:00.000000+00:00`, value: base(year) }
  }))
}

describe('the windows of the seasons', () => {
  it('are three whole months each, the winter with the December before it', () => {
    expect(SEASON_MONTHS).toEqual({ spring: [3, 4, 5], summer: [6, 7, 8], autumn: [9, 10, 11], winter: [12, 1, 2] })
  })

  it('are over on the first of the month after them: 1 June, 1 September, 1 December, and 1 March of the winter\'s own year', () => {
    expect(seasonOver('spring', 2026).toISODate()).toBe('2026-06-01')
    expect(seasonOver('summer', 2026).toISODate()).toBe('2026-09-01')
    expect(seasonOver('autumn', 2026).toISODate()).toBe('2026-12-01')
    expect(seasonOver('winter', 2026).toISODate()).toBe('2026-03-01')
    expect(seasonOver('winter', 2024).toISODate()).toBe('2024-03-01')
  })

  it('write a winter with both years and the others with one', () => {
    expect(seasonLabel('winter', 2026)).toBe('2025/26')
    expect(seasonLabel('winter', 2000)).toBe('1999/00')
    expect(seasonLabel('summer', 2026)).toBe('2026')
  })

  it('make a winter of the December of the year before and the January and February of the year', () => {
    // the December of 2024, the January and February of 2025: the winter 2025, which is 2024/25
    const readings: Reading[] = [
      { parameter: 'temperature_air_mean_2m', timestamp: '2024-12-01T00:00:00+00:00', value: 1 },
      { parameter: 'temperature_air_mean_2m', timestamp: '2025-01-01T00:00:00+00:00', value: 2 },
      { parameter: 'temperature_air_mean_2m', timestamp: '2025-02-01T00:00:00+00:00', value: 6 },
    ]
    expect(seasonMeans(readings, 'winter', at('2025-06-01T00:00:00Z'))).toEqual([{ year: 2025, mean: 3 }])
    // and not the winter of 2024, nor a summer
    expect(seasonMeans(readings, 'summer', at('2025-06-01T00:00:00Z'))).toEqual([])
  })

  it('leave a winter out where its December is missing, even where the January and February are there', () => {
    const readings = monthly('winter', 2024, 2025).filter(reading => !reading.timestamp.startsWith('2024-12'))
    expect(seasonMeans(readings, 'winter', at('2026-06-01T00:00:00Z')).map(each => each.year)).toEqual([2024])
  })
})

describe('which season is complete when', () => {
  const winter = monthly('winter', 2020, 2026)

  it('counts a winter from 1 March, not before: the last day of February is not enough', () => {
    expect(seasonMeans(winter, 'winter', at('2026-02-28T23:59:59Z')).at(-1)!.year).toBe(2025)
    expect(seasonMeans(winter, 'winter', at('2026-03-01T00:00:00Z')).at(-1)!.year).toBe(2026)
  })

  it('counts a summer from 1 September, an autumn from 1 December and a spring from 1 June', () => {
    const lastYear = (kind: typeof SEASONS[number], now: string) => seasonMeans(monthly(kind, 2020, 2026), kind, at(now)).at(-1)?.year
    expect(lastYear('summer', '2026-08-31T23:59:59Z')).toBe(2025)
    expect(lastYear('summer', '2026-09-01T00:00:00Z')).toBe(2026)
    expect(lastYear('autumn', '2026-11-30T23:59:59Z')).toBe(2025)
    expect(lastYear('autumn', '2026-12-01T00:00:00Z')).toBe(2026)
    expect(lastYear('spring', '2026-05-31T23:59:59Z')).toBe(2025)
    expect(lastYear('spring', '2026-06-01T00:00:00Z')).toBe(2026)
  })

  it('has on 21 November 2026 the spring and summer of 2026, the autumn of 2025 and the winter 2025/26 as the last', () => {
    const now = DateTime.fromISO('2026-11-21T10:00:00', { zone: BERLIN })
    const last = (kind: typeof SEASONS[number]) => seasonMeans(monthly(kind, 2000, 2026), kind, now).at(-1)!.year
    expect([last('spring'), last('summer'), last('autumn'), last('winter')]).toEqual([2026, 2026, 2025, 2026])
  })
})

describe('the normals to choose from', () => {
  const list = (iso: string) => normalsAt(at(iso)).map(normal => normal.key)

  it('are, in 2026, 1961-1990, 1971-2000, 1981-2010 and 1991-2020', () => {
    expect(list('2026-11-21T10:00:00Z')).toEqual(['1961-1990', '1971-2000', '1981-2010', '1991-2020'])
  })

  it('gain 2001-2030 on 1 January 2031, with no change to the code, and not a day before', () => {
    expect(list('2030-12-31T23:59:59Z')).toEqual(['1961-1990', '1971-2000', '1981-2010', '1991-2020'])
    expect(list('2031-01-01T00:00:00Z')).toEqual(['1961-1990', '1971-2000', '1981-2010', '1991-2020', '2001-2030'])
    expect(list('2031-06-15T12:00:00Z').at(-1)).toBe('2001-2030')
  })

  it('end in floor((year - 1) / 10) * 10: the 1991-2020 normal is new on 1 January 2021', () => {
    expect(newestNormalEnd(at('2020-12-31T12:00:00Z'))).toBe(2010)
    expect(newestNormalEnd(at('2021-01-01T00:00:00Z'))).toBe(2020)
    expect(newestNormalEnd(at('2026-11-21T00:00:00Z'))).toBe(2020)
    expect(newestNormalEnd(at('2041-01-01T00:00:00Z'))).toBe(2040)
  })

  it('are 30 years each, and the newest is the last of the list', () => {
    for (const normal of normalsAt(at('2045-05-05T00:00:00Z')))
      expect(normal.to - normal.from + 1).toBe(30)
    expect(newestNormal(at('2026-11-21T00:00:00Z')).key).toBe('1991-2020')
  })

  it('are found by the name a link carries, and none else: no whole record, no rolling 30 years, no normal still running', () => {
    const now = at('2026-11-21T00:00:00Z')
    expect(normalOf('1961-1990', now)).toMatchObject({ from: 1961, to: 1990 })
    for (const other of ['1962-1991', '1996-2025', '2001-2030', '1951-1980', '1991-2021', 'all', 'record', '', undefined, null])
      expect(normalOf(other, now)).toBeNull()
  })
})

describe('the normals a station has too few seasons of', () => {
  const now = at('2026-11-21T10:00:00Z')

  it('are the ones with fewer than 20 of their 30 seasons', () => {
    // a station that began its record in 1975
    const availability = normalAvailability(monthly('winter', 1975, 2026), 'winter', now)
    expect(availability.map(each => [each.normal.key, each.count, each.enough])).toEqual([
      ['1961-1990', 16, false],
      ['1971-2000', 26, true],
      ['1981-2010', 30, true],
      ['1991-2020', 30, true],
    ])
  })

  it('count the seasons of the kind: a station with summers only has none of the winters', () => {
    const summers = monthly('summer', 1961, 2026)
    expect(normalAvailability(summers, 'winter', now).every(each => each.count === 0)).toBe(true)
    expect(normalAvailability(summers, 'summer', now).every(each => each.enough)).toBe(true)
  })

  it('count a season of a normal by the year it is named for, a winter by its January', () => {
    const seasons = seasonMeans(monthly('winter', 1961, 2026), 'winter', now)
    expect(countIn(seasons, normalOf('1961-1990', now)!)).toBe(30)
  })
})

describe('the last season against a normal', () => {
  const now = DateTime.fromISO('2026-11-21T10:00:00', { zone: BERLIN })

  it('is the winter 2025/26 against 1961-1990, with the winter named in the bars', () => {
    const readings = monthly('winter', 1961, 2026, year => year === 2026 ? 3 : year <= 1990 ? 0 : 1)
    const answer = lastSeason(readings, now, { season: 'winter', normal: '1961-1990' })!
    expect(answer.season).toBe('winter')
    expect(answer.year).toBe(2026)
    expect([answer.normalFrom, answer.normalTo]).toEqual([1961, 1990])
    expect(answer.normal).toBe(0)
    expect(answer.anomaly).toBe(3)
    expect(answer.verdict).toBe('warmer')
    expect(answer.fallback).toBe(false)
    expect(answer.referenceCount).toBe(30)
    expect(answer.bars.find(bar => bar.highlight)).toMatchObject({ label: '2025/26', key: '2026', at: 2026, value: 3 })
    expect(answer.bars[0]).toMatchObject({ label: '1960/61' })
  })

  it('differs by the normal: the same winter is warmer than 1961-1990 and as usual against 1991-2020', () => {
    const readings = monthly('winter', 1961, 2026, year => year === 2026 ? 3 : year <= 1990 ? 0 : 2.8)
    expect(lastSeason(readings, now, { season: 'winter', normal: '1961-1990' })!.verdict).toBe('warmer')
    expect(lastSeason(readings, now, { season: 'winter', normal: '1991-2020' })!.verdict).toBe('usual')
  })

  it('answers each season with its own months', () => {
    for (const kind of SEASONS) {
      const answer = lastSeason(monthly(kind, 1961, 2026, year => year === 2026 ? 12 : 10), now, { season: kind, normal: '1991-2020' })
      // the autumn of 2026 is not over on 21 November, the others are (the winter of 2025/26 is named 2026)
      expect(answer!.year, kind).toBe(kind === 'autumn' ? 2025 : 2026)
    }
  })

  it('gives no answer for an older normal the station has too few seasons of: nothing stands in for it', () => {
    const readings = monthly('winter', 1975, 2026)
    expect(lastSeason(readings, now, { season: 'winter', normal: '1961-1990' })).toBeNull()
    expect(lastSeason(readings, now, { season: 'winter', normal: '1971-2000' })!.fallback).toBe(false)
  })

  it('lets the seasons before stand in for the newest normal alone, and says so', () => {
    const readings = monthly('winter', 2005, 2026)
    const answer = lastSeason(readings, now, { season: 'winter', normal: '1991-2020' })!
    expect(answer.fallback).toBe(true)
    expect([answer.normalFrom, answer.normalTo]).toEqual([2005, 2025])
    expect(answer.asked).toEqual({ from: 1991, to: 2020 })
    // the link that names no normal is the newest one, and the same
    expect(lastSeason(readings, now, { season: 'winter', normal: '' })!.fallback).toBe(true)
    // and with fewer than ten seasons before, none
    expect(lastSeason(monthly('winter', 2020, 2026), now, { season: 'winter', normal: '1991-2020' })).toBeNull()
  })

  it('takes the newest normal for a name that is no normal', () => {
    const readings = monthly('summer', 1961, 2026, year => year === 2026 ? 12 : 10)
    expect(lastSeason(readings, now, { season: 'summer', normal: 'nonsense' })!.asked).toEqual({ from: 1991, to: 2020 })
  })

  it('gives no answer where no season is complete', () => {
    expect(lastSeason([], now, { season: 'winter', normal: '1991-2020' })).toBeNull()
  })
})

describe('the answer for a station with gaps at the ends of the normal', () => {
  const now = DateTime.fromISO('2026-11-21T10:00:00', { zone: BERLIN })

  it('names the normal asked for and counts the seasons it has: summers 1994-2020 are 27 of 1991-2020', () => {
    const answer = lastSeason(monthly('summer', 1994, 2026, year => year === 2026 ? 12 : 10), now, { season: 'summer', normal: '1991-2020' })!
    expect([answer.normalFrom, answer.normalTo]).toEqual([1991, 2020])
    expect(answer.referenceCount).toBe(27)
    expect(answer.fallback).toBe(false)
  })

  it('writes the years of a winter normal as the winters, in the answer and its numbers', () => {
    const answer = lastSeason(monthly('winter', 1961, 2026), now, { season: 'winter', normal: '1961-1990' })!
    const t: ChipEnv['t'] = (key, params = {}) => `${key} ${params.from ?? ''}..${params.to ?? ''}`
    const env = { t, number: (value: number) => String(value), unitText: (unit: string) => unit, place: { id: '1', name: 'x', latitude: 0, longitude: 0 }, now: () => now } as unknown as ChipEnv
    const view = season.present(answer, null, env, { season: 'winter', ref: '1961-1990' })
    expect(view.details[0]).toContain('1960/61..1989/90')
    expect(view.chart!.caption).toContain('1960/61..1989/90')
    expect(season.explanation.numbers(answer, null, env, { season: 'winter', ref: '1961-1990' }).find(line => line.id === 'reference')!.params).toMatchObject({ from: '1960/61', to: '1989/90' })
  })

  it('says why there is no answer for a short older normal, and none of that for a station without any season', () => {
    const env = { t: ((key: string, params: Record<string, unknown> = {}) => `${key} ${params.count ?? ''}`) as ChipEnv['t'], now: () => now } as unknown as ChipEnv
    const choices = { season: 'winter', ref: '1961-1990' }
    expect(season.empty({ readings: monthly('winter', 1975, 2026), units: {} }, env, choices)).toBe('ask.season.noneNormal 16')
    expect(season.empty({ readings: [], units: {} }, env, choices)).toBe('ask.season.none ')
    // the newest, with too few before the last: the same reason
    expect(season.empty({ readings: monthly('winter', 2021, 2026), units: {} }, env, { season: 'winter', ref: '1991-2020' })).toBe('ask.season.noneNormal 0')
  })
})

describe('the choices of the season chip, in the link', () => {
  const NOW = DateTime.fromISO('2026-11-21T10:00:00', { zone: BERLIN })

  it('is the chip of `?ask=season`, and `?ask=summer` of the old link is the same chip', () => {
    expect(chipOf('season')).toBe(season)
    expect(chipOf('summer')).toBe(season)
    expect(chipIdOf('summer')).toBe('season')
    expect(chipIdOf('season')).toBe('season')
    expect(chipIdOf('winter')).toBeNull()
    expect(CHIPS.map(chip => chip.id)).not.toContain('summer')
  })

  it('reads an old link as it always meant: the summer, against the newest normal', () => {
    expect(readChoices(season, {}, NOW)).toEqual({ season: 'summer', ref: '1991-2020' })
  })

  it('reads `&season=winter&ref=1961-1990`', () => {
    expect(readChoices(season, { season: 'winter', ref: '1961-1990' }, NOW)).toEqual({ season: 'winter', ref: '1961-1990' })
    for (const kind of SEASONS)
      expect(readChoices(season, { season: kind }, NOW).season).toBe(kind)
    expect(readChoices(season, { ref: '1971-2000' }, NOW)).toEqual({ season: 'summer', ref: '1971-2000' })
  })

  it('falls back to the defaults for a value that is none, each choice alone', () => {
    for (const bad of ['Winter', 'WINTER', 'monsoon', '', 'summer,winter'])
      expect(readChoices(season, { season: bad, ref: '1961-1990' }, NOW)).toEqual({ season: 'summer', ref: '1961-1990' })
    for (const bad of ['1962-1991', '1991-2030', '2001-2030', '1991', 'all', '', '1991–2020'])
      expect(readChoices(season, { season: 'winter', ref: bad }, NOW)).toEqual({ season: 'winter', ref: '1991-2020' })
    // a name given twice in the link is a list, which no choice takes
    expect(readChoices(season, { season: ['winter', 'summer'] }, NOW).season).toBe('summer')
  })

  it('takes a normal in 2031 that it did not take in 2026, and the default moves with the year', () => {
    const later = DateTime.fromISO('2031-03-01T10:00:00', { zone: BERLIN })
    expect(readChoices(season, { ref: '2001-2030' }, NOW).ref).toBe('1991-2020')
    expect(readChoices(season, { ref: '2001-2030' }, later).ref).toBe('2001-2030')
    expect(readChoices(season, {}, later).ref).toBe('2001-2030')
  })

  it('accepts the values it lists, and no other', () => {
    const [seasonChoice, refChoice] = season.choices!
    expect(acceptsChoice(seasonChoice!, 'winter', NOW)).toBe(true)
    expect(acceptsChoice(seasonChoice!, 'monsoon', NOW)).toBe(false)
    expect(acceptsChoice(refChoice!, '1961-1990', NOW)).toBe(true)
    expect(acceptsChoice(refChoice!, '2001-2030', NOW)).toBe(false)
  })

  it('writes both choices to the link, which opens the chip, and keeps them on a press on it', () => {
    expect(queryOfChoice({ ask: 'summer', place: '02564' }, 'season', 'season', 'winter')).toEqual({ ask: 'season', season: 'winter', place: '02564' })
    expect(queryOfChoice({ ask: 'season', season: 'winter' }, 'season', 'ref', '1961-1990')).toEqual({ ask: 'season', season: 'winter', ref: '1961-1990' })
    const link = { ask: 'season', season: 'winter', ref: '1961-1990', place: '02564' }
    expect(queryOfPress(link, CHIPS, 'season', 'season')).toEqual({ season: 'winter', ref: '1961-1990', place: '02564' })
    // another chip takes them out
    expect(queryOfPress(link, CHIPS, 'rain', 'season')).toEqual({ ask: 'rain', place: '02564' })
    expect(queryOfPress({ ask: 'wind', day: '2025-12-26' }, CHIPS, 'season', 'wind')).toEqual({ ask: 'season' })
  })

  it('names its choices once, and none that load reads: the whole record is fetched whatever the season', () => {
    expect(season.choices!.map(choice => choice.param)).toEqual(['season', 'ref'])
    expect(season.loadedBy).toEqual([])
  })
})

describe('the options of the reference choice', () => {
  const now = DateTime.fromISO('2026-11-21T10:00:00', { zone: BERLIN })
  const env: ChipEnv = {
    t: (key, params) => `${key}${params ? JSON.stringify(params) : ''}`,
    place: { id: '02564', name: 'Kiel-Holtenau', latitude: 54.3776, longitude: 10.1424 },
    number: value => String(value),
    percent: value => `${value}`,
    unitText: unit => unit,
    dayText: day => day,
    now: () => now,
  }
  const [, ref] = season.choices!
  const options = (readings: Reading[] | null, kind = 'winter') => (ref as Extract<typeof ref, { kind: 'select' }>).options(env, readings ? { readings, units: {} } : null, { season: kind, ref: '1991-2020' })

  it('lists the normals, with none disabled before the data has come', () => {
    expect(options(null).map(option => [option.value, option.label, option.disabled])).toEqual([
      ['1961-1990', '1961–1990', undefined],
      ['1971-2000', '1971–2000', undefined],
      ['1981-2010', '1981–2010', undefined],
      ['1991-2020', '1991–2020', undefined],
    ])
  })

  it('offers a normal with too few seasons disabled, with the reason in its text', () => {
    const list = options(monthly('winter', 1975, 2026))
    expect(list.map(option => option.disabled)).toEqual([true, undefined, undefined, undefined])
    expect(list[0]!.label).toContain('ask.season.refShort')
    expect(list[0]!.label).toContain('"count":16')
    expect(list[0]!.label).toContain('"min":20')
    expect(list[0]!.label).toContain('"of":30')
    expect(list[1]!.label).toBe('1971–2000')
  })

  it('offers the newest normal, where it is short, with the substitute in its text and not disabled', () => {
    const list = options(monthly('winter', 2005, 2026))
    expect(list.map(option => option.disabled)).toEqual([true, true, true, undefined])
    expect(list[3]!.label).toContain('ask.season.refFallback')
  })

  it('disables the newest normal too where fewer than ten seasons stand before the last, since nothing could answer', () => {
    // a station since 2020: six winters in all, five before the last
    const list = options(monthly('winter', 2021, 2026))
    expect(list.map(option => option.disabled)).toEqual([true, true, true, true])
    expect(list[3]!.label).toContain('ask.season.refShort')
    // with ten before the last it can answer, and is not disabled
    const eleven = options(monthly('winter', 2016, 2026))
    expect(eleven[3]!.disabled).toBeUndefined()
    expect(eleven[3]!.label).toContain('ask.season.refFallback')
    expect(normalAvailability(monthly('winter', 2021, 2026), 'winter', now).at(-1)).toMatchObject({ enough: false, fallback: false })
  })

  it('writes the winters of a winter normal with both years, and keeps the normal as WMO writes it', () => {
    const short = options(monthly('winter', 1975, 2026))
    expect(short[0]!.label).toContain('1961\u20131990 = 1960/61\u20131989/90')
    expect(options(monthly('summer', 1975, 2026), 'summer')[0]!.label).toContain('"normal":"1961\u20131990"')
    expect(options(monthly('winter', 1961, 2026))[0]!.label).toBe('1961\u20131990')
  })

  it('follows the season: the same station has the summers it has no winters of', () => {
    const summers = monthly('summer', 1961, 2026)
    expect(options(summers, 'summer').every(option => option.disabled === undefined)).toBe(true)
    expect(options(summers, 'winter').filter(option => option.disabled).length).toBe(4)
  })
})

// ------------------------------------------------------------------------------------- the question, in eleven languages

const LOCALES = join(__dirname, '..', '..', 'i18n', 'locales')
const catalogs = Object.fromEntries(readdirSync(LOCALES).filter(name => name.endsWith('.json'))
  .map(name => [name.replace(/\.json$/, ''), JSON.parse(readFileSync(join(LOCALES, name), 'utf8')) as Record<string, unknown>]))

/** A translator over a catalog, filling `{name}` as vue-i18n does */
function translator(locale: string): ChipEnv['t'] {
  return (key, params = {}) => {
    let node: unknown = catalogs[locale]
    for (const part of key.split('.'))
      node = (node as Record<string, unknown> | undefined)?.[part]
    return typeof node === 'string' ? node.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? `{${name}}`)) : `<${key}>`
  }
}

describe('the question, which follows the season', () => {
  const NOW = DateTime.fromISO('2026-11-21T10:00:00', { zone: BERLIN })
  const questionOf = (locale: string, kind: string) => season.question({ t: translator(locale) } as ChipEnv, { season: kind, ref: '1991-2020' })

  it('says "Was last winter colder than usual here?" in English, and asks for the warm in the other seasons', () => {
    expect(questionOf('en', 'winter')).toBe('Was last winter colder than usual here?')
    expect(questionOf('en', 'summer')).toBe('Was last summer hotter than usual here?')
    expect(questionOf('en', 'spring')).toBe('Was last spring warmer than usual here?')
    expect(questionOf('en', 'autumn')).toBe('Was last autumn warmer than usual here?')
  })

  it('keeps the summer question of the old chip word for word in every language', () => {
    // the sentences as the catalogs had them before the choice was added
    const before: Record<string, string> = {
      'de': 'War der letzte Sommer hier heißer als sonst?',
      'de-hh': 'Weer de leste Sommer hier hitter as anners?',
      'fr': 'L\'été dernier a-t-il été plus chaud que d\'habitude ici\u00A0?',
      'es': '¿Fue el verano pasado más caluroso de lo normal aquí?',
      'it': 'L\'estate scorsa è stata più calda del solito qui?',
      'nl': 'Was de afgelopen zomer hier warmer dan normaal?',
      'da': 'Var sidste sommer varmere end normalt her?',
      'pl': 'Czy ostatnie lato było tu cieplejsze niż zwykle?',
      'lb': 'War de leschte Summer hei méi waarm wéi soss?',
    }
    for (const [locale, text] of Object.entries(before))
      expect(questionOf(locale, 'summer'), locale).toBe(text)
  })

  it('agrees in gender where the language needs it: Polish, Czech, Italian, Spanish', () => {
    expect(questionOf('pl', 'winter')).toBe('Czy ostatnia zima była tu zimniejsza niż zwykle?')
    expect(questionOf('pl', 'spring')).toBe('Czy ostatnia wiosna była tu cieplejsza niż zwykle?')
    expect(questionOf('cs', 'winter')).toBe('Byla minulá zima tady chladnější než obvykle?')
    expect(questionOf('cs', 'autumn')).toBe('Byl minulý podzim tady teplejší než obvykle?')
    expect(questionOf('it', 'autumn')).toBe('L\'autunno scorso è stato più caldo del solito qui?')
    expect(questionOf('it', 'winter')).toBe('L\'inverno scorso è stato più freddo del solito qui?')
    expect(questionOf('lb', 'spring')).toBe('War dat lescht Fréijoer hei méi waarm wéi soss?')
    expect(questionOf('lb', 'winter')).toBe('War de leschte Wanter hei méi kal wéi soss?')
    expect(questionOf('es', 'spring')).toBe('¿Fue la primavera pasada más cálida de lo normal aquí?')
    expect(questionOf('de', 'winter')).toBe('War der letzte Winter hier kälter als sonst?')
    expect(questionOf('fr', 'winter')).toBe('L\'hiver dernier a-t-il été plus froid que d\'habitude ici\u00A0?')
  })

  it.each(Object.keys(catalogs))('is whole in %s for every season, and the sentences of the answer have every word they are given', (locale) => {
    const t = translator(locale)
    for (const kind of SEASONS) {
      expect(questionOf(locale, kind), `${locale} ${kind}`).not.toMatch(/[{}<>]/)
      const readings = monthly(kind, 1961, 2026, year => year === 2026 ? 13 : 10)
      const answer = lastSeason(readings, NOW, { season: kind, normal: '1991-2020' })!
      const env = { t, number: (value: number) => String(value), unitText: (unit: string) => unit, place: { id: '1', name: 'x', latitude: 0, longitude: 0 }, now: () => NOW } as unknown as ChipEnv
      const view = season.present(answer, null, env, { season: kind, ref: '1991-2020' })
      const said = [view.verdict, ...view.details, view.chart!.caption, season.empty(null, env, { season: kind, ref: '1991-2020' })]
      for (const text of said)
        expect(text, `${locale} ${kind}`).not.toMatch(/[{}<>]/)
    }
  })

  it('says yes to "colder" where the winter was cooler, and no where it was warmer; and the other way round for the warm seasons', () => {
    const t = translator('en')
    const env = { t, number: (value: number) => String(Math.abs(value)), unitText: (unit: string) => unit, place: { id: '1', name: 'x', latitude: 0, longitude: 0 }, now: () => NOW } as unknown as ChipEnv
    const verdictOf = (kind: typeof SEASONS[number], value: number) => season.present(
      lastSeason(monthly(kind, 1961, 2026, year => year === 2026 ? value : 10), NOW, { season: kind, normal: '1991-2020' })!,
      null,
      env,
      { season: kind, ref: '1991-2020' },
    ).verdict
    expect(verdictOf('winter', 8)).toBe('Yes, 2 °C colder than usual.')
    expect(verdictOf('winter', 12)).toBe('No, 2 °C warmer than usual.')
    expect(verdictOf('winter', 10.2)).toBe('Not really: about as cold as usual.')
    expect(verdictOf('summer', 12)).toBe('Yes, 2 °C warmer than usual.')
    expect(verdictOf('summer', 8)).toBe('No, 2 °C cooler than usual.')
    expect(verdictOf('summer', 10.2)).toBe('Not really: about as warm as usual.')
  })
})
