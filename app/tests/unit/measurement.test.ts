import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  isTopic,
  measurementPath,
  parameterPatterns,
  TOPIC_GROUPS,
  TOPIC_RULES,
  topicLabelKey,
  topicOfParameter,
  TOPICS,
} from '../../app/utils/measurement'
import { measurement as de } from '../../i18n/measurement/de'
import { measurement as en } from '../../i18n/measurement/en'

// The page "How weather is measured" (GH-3787): its anchors, which glossary parameter links to which entry, and the
// texts, which are written in German and English and have to say the same.

const APP = join(__dirname, '..', '..')
const catalogs = Object.fromEntries(
  ['en', 'de', 'fr', 'es', 'it', 'pl', 'nl', 'cs', 'da', 'lb', 'de-hh'].map(locale => [locale, JSON.parse(readFileSync(join(APP, 'i18n', 'locales', `${locale}.json`), 'utf8'))]),
)

/** Every parameter the glossary labels, which are the canonical names of the backend (`tests/unit/glossary-translations.test.ts`) */
const glossary = readFileSync(join(APP, 'i18n', 'glossary', 'en.ts'), 'utf8')
const PARAMETERS = [...(glossary.split('export const parameters')[1]?.split('export const resolutions')[0] ?? '').matchAll(/^ {2}([a-z0-9_]+):/gm)].map(match => match[1] as string)

function message(locale: string, key: string): unknown {
  return key.split('.').reduce<any>((node, part) => node?.[part], catalogs[locale])
}

describe('the anchors', () => {
  it('are plain lower case words, each once', () => {
    expect(new Set(TOPICS).size).toBe(TOPICS.length)
    for (const topic of TOPICS)
      expect(topic, topic).toMatch(/^[a-z]+(?:-[a-z]+)*$/)
  })

  it('are the eight entries of the first phase, in the order of the issue', () => {
    // the ids are in links that are printed and shared (and in the explanations of GH-3764): a rename is a breaking change
    expect([...TOPICS]).toEqual(['temperature', 'wind', 'precipitation', 'sunshine', 'snow', 'normals', 'time', 'observation-forecast-derived'])
  })

  it('are in the two sections of the page, each entry in one', () => {
    expect(TOPIC_GROUPS.flatMap(group => group.topics)).toEqual([...TOPICS])
    expect(TOPIC_GROUPS.map(group => group.id)).toEqual(['measured', 'reading'])
    // "Reading the data" holds the time, and observation, forecast and derived data, after the measurements (the maintainer, 2026-11-20)
    expect(TOPIC_GROUPS[1]!.topics).toEqual(['time', 'observation-forecast-derived'])
  })

  it('are told from other strings, and give the address of an entry', () => {
    expect(isTopic('wind')).toBe(true)
    expect(isTopic('Wind')).toBe(false)
    expect(isTopic('humidity')).toBe(false)
    expect(isTopic(undefined)).toBe(false)
    expect(isTopic(['wind'])).toBe(false)
    expect(measurementPath('wind')).toBe('/measurement#wind')
    expect(measurementPath('observation-forecast-derived')).toBe('/measurement#observation-forecast-derived')
  })

  it('have a short name in the catalog of every language, under a camel case key', () => {
    expect(topicLabelKey('observation-forecast-derived')).toBe('measurement.topics.observationForecastDerived')
    for (const locale of Object.keys(catalogs)) {
      for (const topic of TOPICS)
        expect(typeof message(locale, topicLabelKey(topic)), `${locale} ${topic}`).toBe('string')
    }
  })
})

describe('the glossary parameters of an entry', () => {
  it.each([
    ['temperature_air_mean_2m', 'temperature'],
    ['temperature_air_min_0_05m', 'temperature'],
    ['temperature_air', 'temperature'],
    ['temperature_soil_mean_0_05m', 'temperature'],
    ['temperature_soil_max_bare_ground_0_1m', 'temperature'],
    ['wind_speed_mean', 'wind'],
    ['wind_gust_max', 'wind'],
    ['wind_gust_max_last_3h', 'wind'],
    ['wind_direction', 'wind'],
    ['wind_force_beaufort', 'wind'],
    ['precipitation_amount', 'precipitation'],
    ['precipitation_amount_last_6h', 'precipitation'],
    ['precipitation_intensity', 'precipitation'],
    ['sunshine_duration', 'sunshine'],
    ['sunshine_duration_relative', 'sunshine'],
    ['snow_depth', 'snow'],
    ['snow_depth_new', 'snow'],
    ['snow_cover', 'snow'],
    ['water_equivalent_snow_depth', 'snow'],
    // a normal is a normal of whatever it is the normal of
    ['sunshine_duration_normal', 'normals'],
    ['precipitation_amount_normal', 'normals'],
    ['temperature_air_mean_minmax_2m_normal', 'normals'],
    ['snow_depth_new_normal', 'normals'],
  ])('send %s to %s', (name, topic) => {
    expect(topicOfParameter(name)).toBe(topic)
  })

  it.each([
    // humidity, pressure, water: entries that are not written yet
    'temperature_dew_point_mean_2m',
    'temperature_wet_mean_2m',
    'temperature_water',
    'temperature_surface',
    'humidity_relative',
    'pressure_air_site',
    'discharge',
    // what the entries do not explain
    'precipitation_form',
    'precipitation_type_flags',
    'precipitation_index',
    'precipitation_duration',
    'probability_precipitation_height_gt_0_0mm_last_1h',
    'probability_wind_gust_ge_25kn_last_12h',
    'soil_moisture_corn_sand_00cm_60cm',
    'wind_movement',
    'cloud_cover_total',
    'visibility',
  ])('give %s no entry', (name) => {
    expect(topicOfParameter(name)).toBeUndefined()
  })

  it('take every rule at least one parameter of the glossary, and name them in the words the page shows', () => {
    for (const rule of TOPIC_RULES) {
      const taken = PARAMETERS.filter(name => topicOfParameter(name) === rule.topic)
      expect(taken.length, `the rule for ${rule.topic} takes nothing`).toBeGreaterThan(0)
      expect(rule.shown.length, rule.topic).toBeGreaterThan(0)
      // what the page shows stands for what the rule takes: every name it takes begins (or ends) like one of the patterns
      for (const name of PARAMETERS.filter(parameter => rule.pattern.test(parameter) && topicOfParameter(parameter) === rule.topic)) {
        const looksLikeOne = rule.shown.some((shown) => {
          if (shown.startsWith('*'))
            return name.endsWith(shown.slice(1))
          // `wind_gust_*` is `wind_gust` and every name that goes on with an underscore
          const family = shown.replace(/_?\*$/, '')
          return name === family || name.startsWith(`${family}_`)
        })
        expect(looksLikeOne, `${name} is taken by the rule for ${rule.topic} but is not shown as one of ${rule.shown.join(', ')}`).toBe(true)
      }
    }
  })

  it('send each parameter to one entry only, and to one that exists', () => {
    for (const name of PARAMETERS) {
      const topic = topicOfParameter(name)
      if (topic !== undefined)
        expect(TOPICS, name).toContain(topic)
    }
    // the first rule wins: the order is what makes a normal a normal and not a temperature
    expect(TOPIC_RULES[0]!.topic).toBe('normals')
  })

  it('leave most of the glossary to entries that follow, but a family that has one is not left out', () => {
    // a parameter of a quantity the first phase explains has its entry: counting these is how a family that a new
    // parameter name starts is noticed (the pattern would not take it), here for the names that exist
    const families = /^(?:temperature_(?:air|soil)|wind_(?:speed|gust|direction|force)|precipitation_(?:amount|intensity)|sunshine_duration|snow_depth|water_equivalent_snow_depth)/
    expect(PARAMETERS.filter(name => families.test(name) && topicOfParameter(name) === undefined)).toEqual([])
  })

  it('say in words which parameters an entry explains, none for those that explain none', () => {
    expect(parameterPatterns('wind')).toEqual(['wind_speed_*', 'wind_gust_*', 'wind_direction_*', 'wind_force_*'])
    expect(parameterPatterns('temperature')).toEqual(['temperature_air_*', 'temperature_soil_*'])
    expect(parameterPatterns('normals')).toEqual(['*_normal'])
    expect(parameterPatterns('time')).toEqual([])
    expect(parameterPatterns('observation-forecast-derived')).toEqual([])
  })
})

describe.each([['en', en], ['de', de]] as const)('the text in %s', (_locale, texts) => {
  it('has an entry for each anchor, and no other', () => {
    expect(Object.keys(texts).sort()).toEqual([...TOPICS].sort())
  })

  it('has no empty string', () => {
    const strings = Object.values(texts).flatMap(entry => [
      entry.title,
      entry.summary,
      ...entry.parts.flatMap(part => [part.title, ...part.paragraphs]),
      ...entry.sources.flatMap(source => [source.plain, source.citation, source.href]),
    ])
    expect(strings.filter(text => !text.trim())).toEqual([])
  })

  it('has the four parts the issue asks for in every entry that is a measurement', () => {
    for (const topic of ['temperature', 'wind', 'precipitation', 'sunshine', 'snow'] as const)
      expect(texts[topic].parts, topic).toHaveLength(4)
  })

  it('names a source for every entry, in plain words and then by citation, at an address that opens', () => {
    for (const [topic, entry] of Object.entries(texts)) {
      expect(entry.sources.length, topic).toBeGreaterThan(0)
      for (const source of entry.sources) {
        expect(source.href, topic).toMatch(/^https:\/\/[a-z0-9.-]+\//)
        expect(source.plain.length, `${topic}: ${source.href}`).toBeGreaterThan(40)
        expect(source.citation.length, `${topic}: ${source.href}`).toBeGreaterThan(40)
      }
    }
  })

  it('cites the WMO Guide by edition, volume and chapter, and the normals by their number', () => {
    for (const topic of ['temperature', 'wind', 'precipitation', 'sunshine', 'snow'] as const) {
      const wmo = texts[topic].sources[0]!.citation
      expect(wmo, topic).toContain('WMO-No. 8')
      expect(wmo, topic).toContain('2024 edition')
      expect(wmo, topic).toMatch(/Volume (?:I|II)[ ,].*Chapter \d+/)
    }
    expect(texts.normals.sources[0]!.citation).toContain('WMO-No. 1203')
    expect(texts['observation-forecast-derived'].sources.map(source => source.citation).join(' ')).toContain('Volume V')
  })

  it('names the edition of the Guide it uses, and has none of the provisional 2026 one', () => {
    for (const entry of Object.values(texts))
      expect(JSON.stringify(entry)).not.toMatch(/2026 edition|Ausgabe 2026/)
  })

  it('has no placeholder text', () => {
    const text = JSON.stringify(texts)
    expect(text).not.toMatch(/TODO|FIXME|lorem|\?\?\?/i)
  })
})

describe('the two texts', () => {
  it('say the same, entry for entry: the same parts, the same number of paragraphs, the same sources', () => {
    for (const topic of TOPICS) {
      const a = en[topic]
      const b = de[topic]
      expect(b.parts.map(part => part.paragraphs.length), topic).toEqual(a.parts.map(part => part.paragraphs.length))
      expect(b.sources.length, topic).toBe(a.sources.length)
    }
  })

  it('cite the works of WMO the same way in both languages, whose titles stay in their language', () => {
    for (const topic of TOPICS) {
      en[topic].sources.forEach((source, index) => {
        const other = de[topic].sources[index]!
        // the WMO works: the citation is the same text; the files of a provider are named in the language of the page
        if (source.href.includes('library.wmo.int')) {
          expect(other.citation, topic).toBe(source.citation)
          expect(other.href, topic).toBe(source.href)
        }
      })
    }
  })

  it('give the same numbers in every entry, as the English text does', () => {
    // a figure that one language has and the other has not is a claim that only one of them makes; the figures that
    // are numbers of a source (years, heights, thresholds) are compared as digits, the decimal comma aside
    const digits = (text: string) => [...text.replace(/(\d),(\d)/g, '$1.$2').matchAll(/\d+(?:\.\d+)?/g)].map(match => match[0]).sort()
    for (const topic of TOPICS) {
      const body = (entry: typeof en[typeof topic]) => entry.parts.flatMap(part => part.paragraphs).join(' ')
      expect(digits(body(de[topic])), topic).toEqual(digits(body(en[topic])))
    }
  })

  it('speak to the reader of German in the informal singular (GH-3157)', () => {
    // a capital "Sie" at the start of a sentence is "it" or "they" here, so only the forms that cannot be anything else
    expect(JSON.stringify(de)).not.toMatch(/\b(?:Ihnen|Ihrem|Ihren|Ihrer)\b|\bSie (?:können|müssen|sollten|haben|sind|finden)\b/)
  })
})
