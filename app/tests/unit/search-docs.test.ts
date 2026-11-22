import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { gzipSync } from 'node:zlib'
import { describe, expect, it } from 'vitest'
import { WORK_IDS, workAnchor } from '../../app/utils/ask/works'
import { TOPICS } from '../../app/utils/measurement'
import { prettifyId } from '../../app/utils/prettify-id'
import { glossaryDocs, longTextLanguage, messageOf } from '../../app/utils/search-docs'
import { bestPerTarget, buildIndex, matchesQuery, searchIndex } from '../../app/utils/search-index'
import { MESSAGE_SOURCES } from '../../app/utils/search-sources'
import { UNIT_TARGET_TYPES } from '../../app/utils/unit-targets'
import { SEARCH_LOCALES, searchIndexFor, searchLabelsFor } from '../../modules/search-index/build'

// The documents the search is built from (GH-3790): every locale has an index, every result leads to an anchor that its page
// has, and a reader finds what they see in the language they see it in

const APP = join(__dirname, '..', '..')
const page = (name: string) => readFileSync(join(APP, 'app', 'pages', `${name}.vue`), 'utf-8')
const catalog = (locale: string) => JSON.parse(readFileSync(join(APP, 'i18n', 'locales', `${locale}.json`), 'utf-8'))

const find = (locale: string, query: string) => bestPerTarget(searchIndex(searchIndexFor(locale), query))

describe('the index of each language', () => {
  it('is built for every locale of the app', () => {
    expect(SEARCH_LOCALES).toHaveLength(11)
    for (const locale of SEARCH_LOCALES) {
      const index = searchIndexFor(locale)
      expect(index.docs.length, locale).toBeGreaterThan(100)
      expect(index.terms.length, locale).toBeGreaterThan(1000)
    }
  })

  it('is built from the long texts the reader sees: German for German, Low German and Luxembourgish, English for the rest', () => {
    for (const locale of SEARCH_LOCALES)
      expect(longTextLanguage(locale)).toBe(['de', 'de-hh', 'lb'].includes(locale) ? 'de' : 'en')
    // the entry of the humidity is "Luftfeuchte und Taupunkt" for German and "Humidity and dew point" for French, as the page shows them
    expect(find('de', 'taupunkt')[0]!.title).toBe('Luftfeuchte und Taupunkt')
    expect(find('de-hh', 'taupunkt')[0]!.title).toBe('Luftfeuchte und Taupunkt')
    expect(find('fr', 'dew point')[0]!.title).toBe('Humidity and dew point')
  })

  it('finds an entry by its name in the language of the interface too, where the text is in another', () => {
    const hits = find('fr', 'humidité')
    expect(hits.some(hit => hit.to === '/measurement#humidity')).toBe(true)
  })

  it('indexes the sentence in plain words of a source and not its formal citation, which is file names and addresses', () => {
    expect(find('en', '10minutenwerte')).toEqual([])
    expect(find('de', 'Metadaten_Geraete_Lufttemperatur')).toEqual([])
  })

  // 40 kB until the four entries on the kinds of station and on how a value is formed (GH-3787) took Luxembourgish, which
  // is shown the German texts and is the largest, to 44.6 kB (German 43.9 kB). The formal citations (file names, folders and
  // addresses, which nobody searches for) are no longer indexed, which gives 42.9 kB for Luxembourgish and 42.2 kB for German.
  // Each further entry added about 1.7 kB in German, until the last three (radar, water level and discharge, and the quality of the
  // data) took Luxembourgish to 50.7 kB, Low German to 50.5 and German to 49.8: the three are long (the one on water level rests
  // on four services and a WMO guide). 55 kB is the budget since, with room for the entry on phenology that is left for later
  it('stays small enough to load when the search is opened: 55 kB gzipped for a language, with the labels of its parameters', () => {
    for (const locale of SEARCH_LOCALES)
      expect(gzipSync(JSON.stringify({ index: searchIndexFor(locale), labels: searchLabelsFor(locale) })).length, locale).toBeLessThan(55_000)
  })

  it('has the labels of the glossary\'s parameters in its own language, which the glossary results are shown by', () => {
    expect(searchLabelsFor('en').temperature_dew_point_mean_2m).toBe('Dew point (2 m)')
    expect(searchLabelsFor('de').temperature_dew_point_mean_2m).toBe('Taupunkt (2 m)')
    for (const locale of SEARCH_LOCALES)
      expect(Object.keys(searchLabelsFor(locale)).length, locale).toBeGreaterThan(100)
  })

  it('is the same on every build', () => {
    expect(JSON.stringify(searchIndexFor('de'))).toBe(JSON.stringify(searchIndexFor('de')))
  })
})

describe('what it finds and where it leads', () => {
  it('finds an entry of "How weather is measured" at its anchor', () => {
    const hit = find('en', 'dew point')[0]!
    expect(hit).toMatchObject({ kind: 'measurement', to: '/measurement#humidity' })
    expect(find('en', 'normal')[0]).toMatchObject({ to: '/measurement#normals' })
  })

  it('finds a method, a section of it and a work, at the anchors of the page of the methods', () => {
    // the summer question became the season question (GH-3764): "summer" still finds it
    const season = find('en', 'summer').find(hit => hit.kind === 'method')!
    expect(season.to).toBe('/methods#season')
    const work = find('en', 'WMO-No. 1203').find(hit => hit.to.startsWith('/methods#work-'))!
    expect(work.to).toBe('/methods#work-wmo-1203')
  })

  it('finds the cards of About and Support, and each setting at its own anchor', () => {
    expect(find('en', 'donations')[0]!.to).toBe('/support#support-donate')
    // the entry on water level and discharge says hydrology too, and comes first; the card that names the maintainer's hydrology is found as well
    expect(find('en', 'hydrology').map(hit => hit.to)).toContain('/about#about-people')
    expect(find('en', 'convert').map(hit => hit.to)).toContain('/settings#settings-convert-units')
    expect(find('de', 'Windgeschwindigkeit').map(hit => hit.to)).toContain('/settings#settings-unit-speed')
    // a reader of German finds the English name of a setting as well
    expect(find('de', 'units').map(hit => hit.to)).toContain('/settings#settings-convert-units')
  })

  it('shows no placeholder of a text that the code fills in', () => {
    for (const locale of ['en', 'de']) {
      for (const [, title, context, summary] of searchIndexFor(locale).docs)
        expect(`${title} ${context} ${summary}`, locale).not.toMatch(/\{\w+\}/)
    }
  })

  it('has an anchor for every entry, every method and every work', () => {
    const targets = new Set(searchIndexFor('en').docs.map(doc => doc[4]))
    for (const topic of TOPICS)
      expect(targets.has(`/measurement#${topic}`), topic).toBe(true)
    for (const id of WORK_IDS)
      expect(targets.has(`/methods#${workAnchor(id)}`), id).toBe(true)
    for (const chip of ['rain', 'season', 'day', 'download'])
      expect(targets.has(`/methods#${chip}`), chip).toBe(true)
  })
})

describe('the cards of the pages', () => {
  it('have every key in every catalog', () => {
    for (const locale of SEARCH_LOCALES) {
      const messages = catalog(locale)
      for (const source of MESSAGE_SOURCES) {
        for (const key of [source.title, ...(source.context ? [source.context] : []), ...source.text])
          expect(messageOf(messages, key), `${locale}: ${key}`).toBeTypeOf('string')
      }
    }
  })

  it('lead to an anchor that their page has', () => {
    for (const source of MESSAGE_SOURCES) {
      const [path, anchor] = source.to.split('#')
      const html = page(path!.slice(1))
      // a unit row has its id from the list of the unit types: the page makes it from `settings-unit-${type}`
      if (anchor!.startsWith('settings-unit-'))
        expect(html, anchor).toMatch(/`settings-unit-\$\{group\.type\}`/)
      else
        expect(html, source.to).toMatch(new RegExp(`id="${anchor}"`))
    }
  })

  it('have a row for every unit type of the settings page', () => {
    const anchors = MESSAGE_SOURCES.map(source => source.to)
    for (const unitType of UNIT_TARGET_TYPES)
      expect(anchors, unitType.type).toContain(`/settings#settings-unit-${unitType.type}`)
  })
})

describe('the glossary', () => {
  const entries = [
    { name: 'temperature_dew_point_mean_2m', description: 'Temperature at which the air is saturated', unit_symbol: '°C' },
    { name: 'wind_speed', description: 'Mean speed of the wind', unit_symbol: 'km/h' },
  ]
  const labels: Record<string, string> = { temperature_dew_point_mean_2m: 'Taupunkt (2 m)', wind_speed: 'Windgeschwindigkeit' }
  const index = buildIndex(glossaryDocs(entries, name => labels[name]!))

  it('is found by the label the reader sees, the name (English words) and what it says, and leads to the entry', () => {
    for (const query of ['taupunkt', 'dew point', 'temperature_dew_point', 'saturated', 'dew_point_mean'])
      expect(searchIndex(index, query)[0], query).toMatchObject({ kind: 'glossary', title: 'Taupunkt (2 m)', to: '/glossary#temperature_dew_point_mean_2m' })
  })

  it('is found by the unit symbol where it has a word', () => {
    expect(searchIndex(index, 'km')[0]).toMatchObject({ title: 'Windgeschwindigkeit' })
  })

  it('shows an id with no label as the words of it, as the glossary page does', () => {
    const docs = glossaryDocs([{ name: 'wind_gust_max', description: 'Highest gust' }], name => prettifyId(name))
    expect(docs[0]!.title).toBe('Wind Gust Max')
  })

  // "5 more in Glossary" opens the page with the query in its field: the page filters by `matchesQuery`, which has to give the
  // entries the search counted, whatever the words, their order, their accents or what they are found in
  it('is filtered by the page as the search finds it, for the same words', () => {
    const rows = [
      { name: 'temperature_dew_point_mean_2m', description: 'Temperature at which the air is saturated', unit_symbol: '°C' },
      { name: 'wind_speed', description: 'Mean speed of the wind', unit_symbol: 'km/h' },
      { name: 'wind_gust_max', description: 'Highest gust of the wind', unit_symbol: 'm/s' },
      { name: 'sunshine_duration', description: 'Duration of sunshine', unit_symbol: 'h' },
    ]
    const cs: Record<string, string> = { temperature_dew_point_mean_2m: 'Rosný bod (2 m)', wind_speed: 'Rychlost větru', wind_gust_max: 'Náraz větru', sunshine_duration: 'Délka slunečního svitu' }
    const label = (name: string) => cs[name] ?? name
    const found = buildIndex(glossaryDocs(rows, label))
    for (const query of ['rosny bod', 'BOD ROSNY', 'rosný', 'naraz vetru', 'vetru naraz', 'wind', 'km', 'gust_max', 'mean 2m', 'saturated air', 'zzz', 'slunecniho']) {
      const byPage = rows.filter(row => matchesQuery(query, [label(row.name), row.name, row.unit_symbol, row.description])).map(row => `/glossary#${row.name}`)
      const bySearch = searchIndex(found, query).map(hit => hit.to)
      expect([...bySearch].sort(), query).toEqual([...byPage].sort())
    }
    expect(matchesQuery('rosny bod', [label('temperature_dew_point_mean_2m')])).toBe(true)
    expect(matchesQuery('bod rosny', ['Rosný bod (2 m)'])).toBe(true)
    // no word of its own: the field filters nothing
    expect(matchesQuery('a', ['Wind'])).toBe(true)
  })
})
