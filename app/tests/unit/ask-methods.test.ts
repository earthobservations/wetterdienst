import type { ChipEnv } from '../../app/utils/ask/chip'
import { DateTime } from 'luxon'
import { describe, expect, it } from 'vitest'
import {
  beaufort,
  BEAUFORT,
  DAY_WINDOW_DAYS,
  FALLBACK_MIN_SEASONS,
  lastSeason,
  NORMAL_FIRST_TO,
  NORMAL_MIN_SEASONS,
  NORMAL_YEARS,
  RAIN_AMOUNT,
  RAIN_MAYBE_CHANCE,
  RAIN_MAYBE_MM,
  RAIN_MIN_HOURS,
  RAIN_WET_HOUR_MM,
  RAIN_YES_CHANCE,
  RAIN_YES_MM,
  rainTomorrow,
  USUAL_BAND,
  WIND_FORCES_OF_GUST,
  WIND_FORCES_OF_MEAN,
  windOnDay,
} from '../../app/utils/answers'
import { fill, numberLineText, placeholders, ruleParams, valueText } from '../../app/utils/ask/method-text'
import { CHIPS } from '../../app/utils/ask/registry'
import { WORK_IDS, WORKS } from '../../app/utils/ask/works'
import {
  DAY_PARAMETERS,
  FROST_DAY_MIN_BELOW,
  HOT_DAY_MAX_FROM,
  ICE_DAY_MAX_BELOW,
  RAIN_DRY_BELOW_MM,
  RAIN_VERY_WET_FROM_MM,
  RAIN_WET_FROM_MM,
  rainOnDay,
  rainVerdictOf,
  SNOW_LIES_ABOVE_CM,
  snowOnDay,
  SUMMER_DAY_MAX_FROM,
  SUN_SHARE_DULL_BELOW,
  SUN_SHARE_SUNNY_FROM,
  sunOnDay,
  sunVerdictOf,
  temperatureOnDay,
  TROPICAL_NIGHT_MIN_FROM,
} from '../../app/utils/day'
import { isTopic } from '../../app/utils/measurement'
import { methods as de } from '../../i18n/methods/de'
import { methods as en } from '../../i18n/methods/en'

// The explanations of "Ask the weather" (GH-3764, steps 1b and 1c): every chip has one, every period, band, statistic and
// fallback in it cites a published work or is marked as wetterdienst's own with the reasoning, and the German and English texts
// say the same, with the numbers of the code. A new chip cannot be in the registry without all of it.

const NOW = DateTime.fromISO('2026-10-29T10:00:00', { zone: 'Europe/Berlin' })
const KINDS = ['period', 'band', 'statistic', 'fallback', 'window', 'selection']
const TEXTS = { en, de }

describe('the explanation of every chip', () => {
  describe.each(CHIPS.map(chip => [chip.id, chip] as const))('%s', (id, chip) => {
    const explanation = chip.explanation

    it('has steps, rules and limits, and terms that are entries of "How weather is measured"', () => {
      expect(explanation.steps.length).toBeGreaterThan(0)
      expect(explanation.rules.length).toBeGreaterThan(0)
      expect(explanation.limits.length).toBeGreaterThan(0)
      expect(explanation.topics.length).toBeGreaterThan(0)
      for (const topic of explanation.topics)
        expect(isTopic(topic), topic).toBe(true)
      expect(new Set(explanation.topics).size).toBe(explanation.topics.length)
    })

    it('has rules with a name each, a kind, and a published source or the mark that it is wetterdienst\'s own', () => {
      const names = explanation.rules.map(rule => rule.id)
      expect(new Set(names).size).toBe(names.length)
      for (const rule of explanation.rules) {
        expect(rule.id, rule.id).toMatch(/^[a-z]+(?:-[a-z]+)*$/)
        expect(KINDS, rule.id).toContain(rule.kind)
        // a source, or the mark: no number of an answer is left without one
        expect(rule.cites.length > 0 || rule.own === true, `${id}/${rule.id} cites no work and is not marked as wetterdienst's own`).toBe(true)
        for (const citation of rule.cites) {
          expect(WORK_IDS, `${id}/${rule.id}`).toContain(citation.work)
          // where in the work: a rule that cites a work names the place in it, except a page of a provider as a whole
          if (!WORKS[citation.work].short.startsWith('DWD'))
            expect(citation.at, `${id}/${rule.id} cites ${citation.work} with no place in it`).toBeTruthy()
        }
        // a rule that is not its own is a rule of its source: its values are those of the code
        if (rule.own !== true)
          expect(rule.cites.length).toBeGreaterThan(0)
      }
    })

    it('has a scale of verdicts only with a band that says it', () => {
      // a chip with no scale needs no band: the implication is the assertion, so that such a chip is held to it too
      const hasScale = Object.keys(chip.scale).length > 0
      const hasBand = explanation.rules.some(rule => rule.kind === 'band')
      expect(!hasScale || hasBand, `${id} has verdicts and no band`).toBe(true)
    })

    for (const language of ['en', 'de'] as const) {
      const text = () => TEXTS[language].chips[id]!

      it(`has its words in ${language}, for each step, formula, rule and limit it lists and for no other`, () => {
        expect(text(), `${language} has no text for ${id}`).toBeDefined()
        expect(text().title).toBeTruthy()
        expect(text().summary).toBeTruthy()
        expect(text().data).toBeTruthy()
        expect(Object.keys(text().steps).sort()).toEqual([...explanation.steps].sort())
        expect(Object.keys(text().formulas).sort()).toEqual([...explanation.formulas].sort())
        expect(Object.keys(text().rules).sort()).toEqual(explanation.rules.map(rule => rule.id).sort())
        expect(Object.keys(text().limits).sort()).toEqual([...explanation.limits].sort())
      })

      it(`says in ${language} what each source says and why each own choice was made`, () => {
        for (const rule of explanation.rules) {
          const words = text().rules[rule.id]!
          expect(words.text.length, `${rule.id}`).toBeGreaterThan(10)
          if (rule.cites.length > 0)
            expect(words.says, `${language} ${id}/${rule.id}: a cited work is said in plain words`).toBeTruthy()
          else
            expect(words.says, `${language} ${id}/${rule.id}: a rule with no work says nothing of one`).toBeUndefined()
          if (rule.own)
            expect(words.reason, `${language} ${id}/${rule.id}: an own choice has its reasoning`).toBeTruthy()
          else
            expect(words.reason, `${language} ${id}/${rule.id}: a sourced rule has no reasoning of its own`).toBeUndefined()
        }
      })

      it(`uses in ${language} only the numbers the rules of the chip hold`, () => {
        const known = new Set(Object.keys(ruleParams(explanation.rules, language)))
        const words = text()
        const all = [
          words.data,
          ...Object.values(words.steps),
          ...Object.values(words.formulas),
          ...Object.values(words.limits),
          ...Object.values(words.rules).flatMap(rule => [rule.text, rule.says ?? '', rule.reason ?? '']),
        ]
        for (const one of all)
          expect(placeholders(one).filter(name => !known.has(name)), `${language} ${id}: ${one}`).toEqual([])
      })
    }

    it('says the same in German and in English: the same keys, the same names, the same figures', () => {
      const a = en.chips[id]!
      const b = de.chips[id]!
      const figures = (text: string) => (text.replace(/\{\w+\}/g, '').match(/\d+(?:[.,]\d+)?/g) ?? []).map(figure => figure.replace(',', '.'))
      const pairs: Array<[string, string, string]> = [
        ['data', a.data, b.data],
        ...Object.keys(a.steps).map(key => [`steps.${key}`, a.steps[key]!, b.steps[key] ?? ''] as [string, string, string]),
        ...Object.keys(a.formulas).map(key => [`formulas.${key}`, a.formulas[key]!, b.formulas[key] ?? ''] as [string, string, string]),
        ...Object.keys(a.limits).map(key => [`limits.${key}`, a.limits[key]!, b.limits[key] ?? ''] as [string, string, string]),
        ...Object.keys(a.numbers).map(key => [`numbers.${key}`, a.numbers[key]!, b.numbers[key] ?? ''] as [string, string, string]),
        ...Object.keys(a.rules).flatMap(key => (['text', 'says', 'reason'] as const).map(part => [`rules.${key}.${part}`, a.rules[key]![part] ?? '', b.rules[key]?.[part] ?? ''] as [string, string, string])),
      ]
      expect(Object.keys(a.numbers).sort()).toEqual(Object.keys(b.numbers).sort())
      for (const [where, english, german] of pairs) {
        expect(placeholders(german), `${id} ${where}`).toEqual(placeholders(english))
        expect(figures(german), `${id} ${where}`).toEqual(figures(english))
        expect(german === '', `${id} ${where}: one language has no text`).toBe(english === '')
      }
    })
  })
})

describe('the numbers of an answer', () => {
  // an English environment: the numbers a definition writes are as the page writes them
  const number = (value: number, digits = 1) => value.toFixed(digits)
  const env = (language: string): ChipEnv => ({
    t: key => key,
    place: { id: '02564', name: 'Kiel-Holtenau', latitude: 54.3776, longitude: 10.1424 },
    number,
    percent: value => `${Math.round(value * 100)} %`,
    unitText: unit => unit,
    dayText: day => `${language}:${day}`,
    now: () => NOW,
  })

  function summers(first: number, last: number, base: (year: number) => number) {
    return Array.from({ length: last - first + 1 }, (_, index) => first + index).flatMap(year => [6, 7, 8].map(month => ({
      parameter: 'temperature_air_mean_2m',
      timestamp: `${year}-0${month}-01T00:00:00.000000+00:00`,
      value: base(year),
    })))
  }

  const readings = Array.from({ length: 48 }, (_, index) => ({ parameter: RAIN_AMOUNT, timestamp: DateTime.fromISO('2026-10-29T12:00:00Z', { zone: 'utc' }).plus({ hours: index }).toISO()!, value: index === 26 ? 1.5 : 0 }))
  const rain = rainTomorrow(readings, 'Europe/Berlin', NOW)!
  const dayReadings = (parameter: string, value: number) => [{ parameter, timestamp: '2025-12-26T00:00:00+00:00', value }, { parameter, timestamp: '2025-12-27T00:00:00+00:00', value: value / 2 }]
  const gusts = [{ parameter: 'wind_gust_max', timestamp: '2025-12-26T00:00:00+00:00', value: 22 }, { parameter: 'wind_gust_max', timestamp: '2025-12-27T00:00:00+00:00', value: 9 }]
  const means = [{ parameter: 'wind_speed_mean', timestamp: '2025-12-26T00:00:00+00:00', value: 9.5 }]
  const cases = {
    rain: { result: rain, loaded: { point: { station_id: '10382', name: 'Berlin-Tegel', distance: 3.2 }, readings, units: {} }, choices: {} },
    season: { result: lastSeason(summers(1986, 2026, year => year === 2026 ? 18 : 16), NOW, { season: 'summer', normal: '1991-2020' })!, loaded: null, choices: { season: 'summer', ref: '1991-2020' } },
    seasonFallback: { result: lastSeason(summers(2005, 2026, () => 16), NOW, { season: 'summer', normal: '1991-2020' })!, loaded: null, choices: { season: 'summer', ref: '1991-2020' }, id: 'season' },
    wind: { result: { measure: 'wind', answer: windOnDay([...gusts, ...means], '2025-12-26')! }, loaded: null, choices: { measure: 'wind', day: '2025-12-26' }, id: 'day' },
    windMeanOnly: { result: { measure: 'wind', answer: windOnDay(means, '2025-12-26')! }, loaded: null, choices: { measure: 'wind', day: '2025-12-26' }, id: 'day' },
    sun: { result: { measure: 'sun', answer: sunOnDay(dayReadings(DAY_PARAMETERS.sun, 3.5), '2025-12-26', 54.38)! }, loaded: null, choices: { measure: 'sun', day: '2025-12-26' }, id: 'day' },
    dayRain: { result: { measure: 'rain', answer: rainOnDay(dayReadings(DAY_PARAMETERS.rain, 4.2), '2025-12-26')! }, loaded: null, choices: { measure: 'rain', day: '2025-12-26' }, id: 'day' },
    heat: { result: { measure: 'temperature', answer: temperatureOnDay([...dayReadings(DAY_PARAMETERS.tmax, 31), ...dayReadings(DAY_PARAMETERS.tmin, 21)], '2025-12-26')! }, loaded: null, choices: { measure: 'temperature', day: '2025-12-26' }, id: 'day' },
    cold: { result: { measure: 'temperature', answer: temperatureOnDay([...dayReadings(DAY_PARAMETERS.tmax, 12), ...dayReadings(DAY_PARAMETERS.tmin, 4)], '2025-12-26')! }, loaded: null, choices: { measure: 'temperature', day: '2025-12-26' }, id: 'day' },
    snow: { result: { measure: 'snow', answer: snowOnDay([...dayReadings(DAY_PARAMETERS.snow, 12), ...dayReadings(DAY_PARAMETERS.newSnow, 4)], '2025-12-26')! }, loaded: null, choices: { measure: 'snow', day: '2025-12-26' }, id: 'day' },
    snowNoFresh: { result: { measure: 'snow', answer: snowOnDay(dayReadings(DAY_PARAMETERS.snow, 0), '2025-12-26')! }, loaded: null, choices: { measure: 'snow', day: '2025-12-26' }, id: 'day' },
    download: { result: [{ provider: 'dwd' }, { provider: 'noaa' }], loaded: [{ provider: 'dwd' }, { provider: 'noaa' }], choices: {} },
  } as Record<string, { result: unknown, loaded: unknown, choices: Record<string, string>, id?: string }>

  describe.each(Object.entries(cases))('%s', (name, fixture) => {
    const chip = CHIPS.find(each => each.id === (fixture.id ?? name))!
    const lines = chip.explanation.numbers(fixture.result, fixture.loaded, env('en'), fixture.choices)

    it('are lines whose texts exist in both languages, with every number they say given', () => {
      expect(lines.length).toBeGreaterThan(0)
      for (const line of lines) {
        for (const language of ['en', 'de'] as const) {
          const text = TEXTS[language].chips[chip.id]!.numbers[line.id]
          expect(text, `${language} ${chip.id} numbers.${line.id}`).toBeTruthy()
          expect(placeholders(text!).filter(key => !(key in line.params)), `${language} ${line.id}`).toEqual([])
          expect(fill(text!, line.params)).not.toMatch(/\{\w+\}/)
        }
      }
    })
  })

  it('say the station, and for a fallback say that it is no WMO normal', () => {
    const season = CHIPS.find(chip => chip.id === 'season')!
    const ids = (fixture: typeof cases[string]) => season.explanation.numbers(fixture.result, fixture.loaded, env('en'), fixture.choices).map(line => line.id)
    expect(ids(cases.season!)).toContain('reference')
    expect(ids(cases.seasonFallback!)).toContain('referenceFallback')
    expect(ids(cases.season!)).toContain('station')
  })

  it('write the season, its months and its plural in the language of the texts, whatever the language of the page', () => {
    const season = CHIPS.find(chip => chip.id === 'season')!
    const winter = lastSeason(
      Array.from({ length: 66 }, (_, index) => 1961 + index).flatMap(year => [[year - 1, 12], [year, 1], [year, 2]].map(([calendarYear, month]) => ({ parameter: 'temperature_air_mean_2m', timestamp: `${calendarYear}-${String(month).padStart(2, '0')}-01T00:00:00.000000+00:00`, value: year === 2026 ? 3 : 0 }))),
      NOW,
      { season: 'winter', normal: '1961-1990' },
    )!
    const lines = season.explanation.numbers(winter, null, env('en'), { season: 'winter', ref: '1961-1990' })
    const said = (texts: typeof en) => lines.map(line => numberLineText(texts, season, line))
    expect(said(en)).toContain('In winter 2025/26 (December to February) the mean was 3.0 °C.')
    expect(said(en)).toContain('Compared with the winters of 1960/61 to 1989/90: the mean of 30 winters, 0.0 °C.')
    expect(said(de)).toContain('Im Winter 2025/26 (Dezember bis Februar) lag das Mittel bei 3.0 °C.')
    expect(said(de)).toContain('Verglichen mit dem Mittel der Winter von 1960/61 bis 1989/90: 30 Winter, 0.0 °C.')
    // every season has its words in both languages, for each name the lines give the season by
    for (const texts of [en, de]) {
      for (const name of ['season', 'seasons', 'months'])
        expect(Object.keys(texts.chips.season!.terms![name]!).sort(), name).toEqual(['autumn', 'spring', 'summer', 'winter'])
    }
  })

  it('say the scale a wind verdict was read by: the gust where there is one, else the mean', () => {
    const wind = CHIPS.find(chip => chip.id === 'day')!
    const ids = (fixture: typeof cases[string]) => wind.explanation.numbers(fixture.result, fixture.loaded, env('en'), fixture.choices).map(line => line.id)
    expect(ids(cases.wind!)).toContain('scaleGust')
    expect(ids(cases.windMeanOnly!)).toContain('scaleMean')
  })
})

describe('what is marked as wetterdienst\'s own', () => {
  // The choices that no published source makes, which the maintainer has to accept (GH-3764): a change to this list is a change to
  // what the page says is the project's own, so it is a line of a diff that is read.
  const OWN: Record<string, string[]> = {
    rain: ['nearest-point', 'day', 'min-hours', 'day-total', 'maybe-amount', 'chance-bands', 'highest-chance'],
    season: ['winter-year', 'only-over', 'default-season', 'default-normal', 'normal-mean', 'min-seasons', 'fallback-period', 'fallback-minimum', 'usual-band', 'rank'],
    day: ['default-day', 'default-measure', 'measure-reading', 'gust-first', 'gust-words', 'mean-words', 'sun-bands', 'rain-trace', 'rain-wet-day', 'rain-very-wet', 'tropical-daily-minimum', 'class-order', 'around-window', 'stronger-count'],
    warnings: ['in-force', 'edge', 'named-only', 'coverage', 'language', 'order', 'refresh'],
    download: ['networks', 'hourly-temperature', 'order'],
  }

  it('is these rules, and no others', () => {
    for (const chip of CHIPS) {
      const own = chip.explanation.rules.filter(rule => rule.own).map(rule => rule.id)
      expect(own, chip.id).toEqual(OWN[chip.id])
    }
    expect(Object.keys(OWN).sort()).toEqual(CHIPS.map(chip => chip.id).sort())
  })
})

describe('the works cited', () => {
  it('are each cited by a rule, and each rule cites a work that is there', () => {
    const cited = new Set(CHIPS.flatMap(chip => chip.explanation.rules.flatMap(rule => rule.cites.map(citation => citation.work))))
    expect([...cited].sort()).toEqual([...WORK_IDS].sort())
  })

  it('have a plain-words text in both languages, and a formal citation, a link and an issuer', () => {
    for (const id of WORK_IDS) {
      const work = WORKS[id]
      expect(en.works[id].plain.length, id).toBeGreaterThan(40)
      expect(de.works[id].plain.length, id).toBeGreaterThan(40)
      expect(work.citation, id).toMatch(/\d{4}/)
      expect(work.href, id).toMatch(/^https:\/\//)
      expect(['wmo', 'dwd']).toContain(work.issuer)
    }
    expect(Object.keys(en.works).sort()).toEqual([...WORK_IDS].sort())
    expect(Object.keys(de.works).sort()).toEqual([...WORK_IDS].sort())
  })

  it('say the same in German and English: the same figures and names', () => {
    const figures = (text: string) => (text.match(/\d+(?:[.,]\d+)?/g) ?? []).map(figure => figure.replace(',', '.'))
    for (const id of WORK_IDS) {
      expect(placeholders(de.works[id].plain), id).toEqual(placeholders(en.works[id].plain))
      expect(figures(de.works[id].plain), id).toEqual(figures(en.works[id].plain))
    }
  })

  it('have anchors that are plain lower case words', () => {
    for (const id of WORK_IDS)
      expect(id).toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/)
  })

  it('name each chip of the registry once in the texts, and no other', () => {
    expect(Object.keys(en.chips).sort()).toEqual(CHIPS.map(chip => chip.id).sort())
    expect(Object.keys(de.chips).sort()).toEqual(CHIPS.map(chip => chip.id).sort())
  })
})

describe('the numbers of the rules are the ones the code judges by', () => {
  const rule = (chip: string, id: string) => CHIPS.find(each => each.id === chip)!.explanation.rules.find(each => each.id === id)!

  it('for the rain: a millimetre, 0.2 mm, 0.1 mm, 70 % and 30 %, and 18 hours', () => {
    expect([RAIN_YES_MM, RAIN_MAYBE_MM, RAIN_WET_HOUR_MM, RAIN_YES_CHANCE, RAIN_MAYBE_CHANCE, RAIN_MIN_HOURS]).toEqual([1, 0.2, 0.1, 0.7, 0.3, 18])
    expect(rule('rain', 'yes-amount').values).toEqual({ yesMm: 1 })
    expect(rule('rain', 'maybe-amount').values).toEqual({ maybeMm: 0.2 })
    expect(rule('rain', 'wet-hour').values).toEqual({ wetMm: 0.1 })
    expect(rule('rain', 'chance-bands').values).toEqual({ yesChance: 70, maybeChance: 30 })
    expect(rule('rain', 'min-hours').values).toEqual({ hours: 18 })
  })

  /** The rain of a day of 24 hours, with `chance` in one hour and `millimetres` in another, and the verdict that comes of it */
  function verdictOf(millimetres: number, chance?: number) {
    const start = DateTime.fromISO('2026-10-29T12:00:00Z', { zone: 'utc' })
    const stamp = (index: number) => start.plus({ hours: index }).toISO()!
    const amounts = Array.from({ length: 48 }, (_, index) => ({ parameter: RAIN_AMOUNT, timestamp: stamp(index), value: index === 26 ? millimetres : 0 }))
    const chances = chance === undefined ? [] : [{ parameter: 'probability_precipitation_amount_gt_0_1mm_last_1h', timestamp: stamp(28), value: chance }]
    return rainTomorrow([...amounts, ...chances], 'Europe/Berlin', NOW, { fraction: '-' })!.verdict
  }

  it('for the rain: the lines are where the verdict changes', () => {
    expect(verdictOf(RAIN_YES_MM)).toBe('yes')
    expect(verdictOf(0.9)).toBe('maybe')
    expect(verdictOf(RAIN_MAYBE_MM)).toBe('maybe')
    expect(verdictOf(0.1)).toBe('no')
    expect(verdictOf(0, RAIN_YES_CHANCE)).toBe('yes')
    expect(verdictOf(0, 0.69)).toBe('maybe')
    expect(verdictOf(0, RAIN_MAYBE_CHANCE)).toBe('maybe')
    expect(verdictOf(0, 0.29)).toBe('no')
  })

  it('for the season: normals from 1961-1990 on, 20 of 30 seasons, 10 for the fallback and half a degree', () => {
    expect([NORMAL_FIRST_TO, NORMAL_YEARS, NORMAL_MIN_SEASONS, FALLBACK_MIN_SEASONS, USUAL_BAND]).toEqual([1990, 30, 20, 10, 0.5])
    expect(rule('season', 'reference-choices').values).toEqual({ firstFrom: 1961, firstTo: 1990, years: 30 })
    expect(rule('season', 'min-seasons').values).toEqual({ minSeasons: 20, ofSeasons: 30 })
    expect(rule('season', 'fallback-minimum').values).toEqual({ fallbackMin: 10 })
    expect(rule('season', 'usual-band').values).toEqual({ band: 0.5 })
  })

  /** A summer `anomaly` degrees above the normal of 1991 to 2020 of a station that has all of it */
  function summerVerdict(anomaly: number) {
    const readings = Array.from({ length: 41 }, (_, index) => 1986 + index).flatMap(year => [6, 7, 8].map(month => ({
      parameter: 'temperature_air_mean_2m',
      timestamp: `${year}-0${month}-01T00:00:00.000000+00:00`,
      value: year === 2026 ? 16 + anomaly : 16,
    })))
    return lastSeason(readings, NOW, { season: 'summer', normal: '1991-2020' })!.verdict
  }

  it('for the season: the band is where the verdict changes, and a station with 19 of the 30 summers falls back', () => {
    expect(summerVerdict(USUAL_BAND)).toBe('warmer')
    expect(summerVerdict(0.4)).toBe('usual')
    expect(summerVerdict(-USUAL_BAND)).toBe('cooler')
    const summers = (from: number, to: number) => Array.from({ length: to - from + 1 }, (_, index) => from + index).flatMap(year => [6, 7, 8].map(month => ({ parameter: 'temperature_air_mean_2m', timestamp: `${year}-0${month}-01T00:00:00.000000+00:00`, value: 16 })))
    const lastSummer = (readings: ReturnType<typeof summers>) => lastSeason(readings, NOW, { season: 'summer', normal: '1991-2020' })!
    expect(lastSummer(summers(2002, 2026)).fallback).toBe(true)
    expect(lastSummer(summers(2002, 2026)).referenceCount).toBe(24)
    expect(lastSummer(summers(2000, 2026)).fallback).toBe(false)
  })

  it('for the wind: the lower edges of the Beaufort table of WMO-No. 8, Volume I, Table 5.1 (2024)', () => {
    // read from the table of the official PDF: force 1 from 0.3 m/s, 2 from 1.6, 3 from 3.4, 4 from 5.5, 5 from 8.0, 6 from 10.8, 7 from 13.9, 8 from 17.2, 9 from 20.8, 10 from 24.5, 11 from 28.5, 12 from 32.7
    expect([...BEAUFORT]).toEqual([0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7])
    expect(rule('day', 'beaufort').values).toEqual({ edges: BEAUFORT })
    expect(BEAUFORT.map((edge, index) => beaufort(edge) === index + 1)).toEqual(Array.from({ length: 12 }).fill(true))
    expect(beaufort(0.2)).toBe(0)
  })

  it('for the wind: the forces of the words, by the gust and by the mean, and a week either side', () => {
    expect(WIND_FORCES_OF_GUST).toEqual({ breezy: 5, windy: 7, stormy: 9 })
    expect(WIND_FORCES_OF_MEAN).toEqual({ breezy: 4, windy: 6, stormy: 8 })
    expect(DAY_WINDOW_DAYS).toBe(7)
    expect(rule('day', 'gust-words').values).toEqual({ gustBreezy: 5, gustWindy: 7, gustStormy: 9 })
    expect(rule('day', 'mean-words').values).toEqual({ meanBreezy: 4, meanWindy: 6, meanStormy: 8 })
    expect(rule('day', 'around-window').values).toEqual({ days: 7 })
    const day = (parameter: string, value: number) => windOnDay([{ parameter, timestamp: '2025-12-26T00:00:00+00:00', value }], '2025-12-26')!.verdict
    // the edge of each force: the lowest speed of it, which is the word's line
    const gust = (force: number) => day('wind_gust_max', BEAUFORT[force - 1]!)
    expect([gust(4), gust(5), gust(6), gust(7), gust(8), gust(9), gust(12)]).toEqual(['calm', 'breezy', 'breezy', 'windy', 'windy', 'stormy', 'stormy'])
    const mean = (force: number) => day('wind_speed_mean', BEAUFORT[force - 1]!)
    expect([mean(3), mean(4), mean(5), mean(6), mean(7), mean(8)]).toEqual(['calm', 'breezy', 'breezy', 'windy', 'windy', 'stormy'])
  })
})

describe('the numbers of the rules of the day question are the ones the code judges by', () => {
  const rule = (id: string) => CHIPS.find(each => each.id === 'day')!.explanation.rules.find(each => each.id === id)!

  it('for the sun: below 30 % dull and from 70 % sunny, the edges of WMO-No. 8, §8.1.3', () => {
    expect([SUN_SHARE_DULL_BELOW, SUN_SHARE_SUNNY_FROM]).toEqual([0.3, 0.7])
    expect(rule('sun-bands').values).toEqual({ dullBelow: 30, sunnyFrom: 70 })
    expect([sunVerdictOf(0.2999), sunVerdictOf(0.3), sunVerdictOf(0.6999), sunVerdictOf(0.7)]).toEqual(['dull', 'mixed', 'mixed', 'sunny'])
  })

  it('for the rain: 0.1 mm, 1 mm and 10 mm', () => {
    expect([RAIN_DRY_BELOW_MM, RAIN_WET_FROM_MM, RAIN_VERY_WET_FROM_MM]).toEqual([0.1, 1, 10])
    expect(rule('rain-trace').values).toEqual({ dryMm: 0.1 })
    expect(rule('rain-wet-day').values).toEqual({ wetMm: 1 })
    expect(rule('rain-very-wet').values).toEqual({ veryWetMm: 10 })
    expect([0.09, 0.1, 0.99, 1, 9.99, 10].map(rainVerdictOf)).toEqual(['dry', 'light', 'light', 'wet', 'wet', 'veryWet'])
  })

  it('for heat and cold: the days of DWD, 25, 30, 20 and 0 °C', () => {
    expect([SUMMER_DAY_MAX_FROM, HOT_DAY_MAX_FROM, TROPICAL_NIGHT_MIN_FROM, ICE_DAY_MAX_BELOW, FROST_DAY_MIN_BELOW]).toEqual([25, 30, 20, 0, 0])
    expect(rule('heat-days').values).toEqual({ summerDay: 25, hotDay: 30 })
    expect(rule('cold-days').values).toEqual({ frostBelow: 0, iceBelow: 0 })
    expect(rule('tropical-night').values).toEqual({ tropicalFrom: 20 })
  })

  it('for the snow: above 0 cm', () => {
    expect(SNOW_LIES_ABOVE_CM).toBe(0)
    expect(rule('snow-lies').values).toEqual({ snowAboveCm: 0 })
  })

  it('cite the work and the place in it that the scale is taken from', () => {
    const cites = (id: string) => rule(id).cites.map(citation => `${citation.work}${citation.at ? ` ${citation.at}` : ''}`)
    expect(cites('sun-bands')).toEqual(['wmo-8-i §8.1.3'])
    expect(cites('rain-trace')).toEqual(['wmo-8-i §6.1.2'])
    expect(cites('rain-wet-day')).toEqual(['wmo-1203 Table 1'])
    expect(cites('heat-days')).toEqual(['dwd-kenntage', 'wmo-1203 Table 1'])
    expect(cites('tropical-night')).toEqual(['dwd-tropennacht'])
    expect(cites('snow-lies')).toEqual(['wmo-1203 Table 1'])
  })
})

describe('the disclosure of an answer shows the rules of the measure that was asked, and the page of the methods all of them', () => {
  const day = CHIPS.find(each => each.id === 'day')!
  const scope = (measure: string) => day.explanation.scope!({ measure, day: '2025-12-26' })
  const all = day.explanation.rules.map(rule => rule.id)

  it('lists the rules of the shared part and of the one measure, and no other measure\'s', () => {
    expect(scope('sun').rules).toEqual(expect.arrayContaining(['daily-values', 'default-day', 'around-window', 'sun-share', 'day-length', 'sun-bands']))
    expect(scope('sun').rules).not.toContain('beaufort')
    expect(scope('wind').rules).toContain('beaufort')
    expect(scope('wind').rules).not.toContain('sun-bands')
  })

  it('has every rule, limit and topic of the chip in the scope of some measure, so that none is only on the page', () => {
    const measures = ['wind', 'sun', 'rain', 'temperature', 'snow']
    expect([...new Set(measures.flatMap(measure => scope(measure).rules))].sort()).toEqual([...all].sort())
    expect([...new Set(measures.flatMap(measure => scope(measure).limits))].sort()).toEqual([...day.explanation.limits].sort())
    expect([...new Set(measures.flatMap(measure => scope(measure).topics))].sort()).toEqual([...day.explanation.topics].sort())
  })

  it('names the fresh snow with the dataset it is read from', () => {
    expect(scope('snow').parameters).toEqual(['snow_depth', 'snow_depth_new (daily/precipitation_more)'])
    expect(scope('sun').parameters).toEqual(['sunshine_duration'])
  })
})

describe('the texts are filled in', () => {
  it('a number as a language writes it, a list of them with commas, a year with no grouping', () => {
    expect(valueText(0.2, 'en')).toBe('0.2')
    expect(valueText(0.2, 'de')).toBe('0,2')
    expect(valueText(1991, 'de')).toBe('1991')
    expect(valueText([0.3, 1.6, 32.7], 'de')).toBe('0,3, 1,6, 32,7')
    expect(valueText('70 %', 'de')).toBe('70 %')
  })

  it('and a name with no value is left as it is, so that a test finds it', () => {
    expect(fill('{a} and {b}', { a: 1 })).toBe('1 and {b}')
    expect(placeholders('{b} {a} {b}')).toEqual(['a', 'b'])
  })
})
