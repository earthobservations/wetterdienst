import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { hasPollenNames, regionName, stateName } from '../../app/utils/pollen-names'
import { pollenPartsOfState, statesOfRegion } from '../../app/utils/uv-pollen'
import { POLLEN_NAMES, POLLEN_REGIONS, POLLEN_STATES, POLLEN_WORDS } from '../../i18n/pollen-names'
import { POLLEN_REGION_STATIONS } from '../helpers/uv-pollen'

// The names of DWD's states and pollen regions in the reader's language (GH-4508): the 16 states and the 27 regions have a name in every
// locale, German shows DWD's own, and a name that no table has is DWD's.

const localesDir = fileURLToPath(new URL('../../i18n/locales', import.meta.url))
// every locale of the app, by its catalog: a language added later is held to all of this without being listed
const locales = Object.keys(import.meta.glob('../../i18n/locales/*.json')).map(path => path.slice(path.lastIndexOf('/') + 1).replace(/\.json$/, '')).sort()
/** The German-speaking locales, which show DWD's names as they are */
const GERMAN = ['de', 'de-hh', 'lb']
const translated = locales.filter(locale => !GERMAN.includes(locale))

/** The 27 part-regions as the panel finds them: the part's name without its region's, for each of the 16 states */
const panelRegions = [...new Set(POLLEN_STATES.flatMap(state => pollenPartsOfState(state, POLLEN_REGION_STATIONS).map(part => part.label)))]

describe('what is named', () => {
  it('finds the locales', () => {
    expect(locales).toContain('en')
    expect(locales.length).toBeGreaterThanOrEqual(11)
    expect(readFileSync(`${localesDir}/en.json`, 'utf-8')).toContain('"dwdName"')
  })

  it('names the 16 states and 27 regions that the panel can show', () => {
    expect(panelRegions).toHaveLength(27)
    expect([...panelRegions].sort()).toEqual([...POLLEN_REGIONS].sort())
    const statesOfDwd = new Set(POLLEN_REGION_STATIONS.flatMap(region => statesOfRegion(region.region)))
    expect([...statesOfDwd].sort()).toEqual([...POLLEN_STATES].sort())
    expect(POLLEN_STATES).toHaveLength(16)
  })

  it('names the regions as the backend does', () => {
    // the names of `dwd/pollen`, which the table is keyed by: a part-region DWD renames is DWD's name until the table has it
    const source = readFileSync(fileURLToPath(new URL('../../../src/wetterdienst/provider/dwd/pollen/regions.py', import.meta.url)), 'utf-8')
    const names = [...source.matchAll(/PollenRegion\(\s*\d+\s*,\s*-?\d+\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"\s*(?:,\s*)?\)/g)].map(match => match[2] || match[1]!)
    expect(names).toEqual([...POLLEN_REGIONS])
  })
})

describe.each(translated)('the names in %s', (locale) => {
  const table = POLLEN_NAMES[locale]

  it('has a table', () => {
    expect(table).toBeDefined()
    expect(hasPollenNames(locale)).toBe(true)
  })

  it.each(POLLEN_STATES)('names the state %s', (state) => {
    const name = stateName(state, locale)
    expect(name.trim()).not.toBe('')
    expect(name).toBe(name.trim())
  })

  it.each(POLLEN_REGIONS)('names the region %s', (region) => {
    const name = regionName(region, locale)
    expect(name.trim()).not.toBe('')
    expect(name).toBe(name.trim())
    // every slot of the template is a word or a state of the table
    expect(name).not.toMatch(/[{}]/)
    expect(table!.regions[region]).toBeDefined()
    // a name starts with a capital, whatever its first word is
    expect(name.charAt(0)).toBe(name.charAt(0).toLocaleUpperCase(locale))
  })

  it('has no word that no name uses', () => {
    const used = POLLEN_REGIONS.flatMap(region => [...table!.regions[region].matchAll(/\{([^{}]+)\}/g)].map(match => match[1]))
    expect(POLLEN_WORDS.filter(word => !used.includes(word))).toEqual([])
  })

  it('gives the two parts of a state two names that differ', () => {
    for (const state of POLLEN_STATES) {
      const names = pollenPartsOfState(state, POLLEN_REGION_STATIONS).map(part => regionName(part.label, locale))
      expect(new Set(names).size, `${locale} ${state}: ${names}`).toBe(names.length)
    }
  })
})

describe.each(GERMAN)('the names in %s', (locale) => {
  it('are DWD\'s, unchanged', () => {
    expect(hasPollenNames(locale)).toBe(false)
    for (const state of POLLEN_STATES)
      expect(stateName(state, locale)).toBe(state)
    for (const region of POLLEN_REGIONS)
      expect(regionName(region, locale)).toBe(region)
  })
})

describe('names that no table has', () => {
  it.each(locales)('are DWD\'s own in %s: a future region, a state that is none of the sixteen', (locale) => {
    expect(regionName('Neuland Atlantis', locale)).toBe('Neuland Atlantis')
    expect(stateName('Atlantis', locale)).toBe('Atlantis')
    expect(regionName('', locale)).toBe('')
  })

  it('are DWD\'s own for a locale that has no table', () => {
    expect(regionName('Tiefland Sachsen', 'xx')).toBe('Tiefland Sachsen')
    expect(stateName('Sachsen', 'xx')).toBe('Sachsen')
    // a name of Object's own is no entry
    expect(regionName('constructor', 'en')).toBe('constructor')
    expect(stateName('toString', 'en')).toBe('toString')
    expect(stateName('Sachsen', 'constructor')).toBe('Sachsen')
  })

  it('are DWD\'s own where a template has a slot that no table fills', () => {
    // the table is mended, not the chip: it shows DWD's name rather than a brace
    const en = POLLEN_NAMES.en!
    const saved = en.regions.Harz
    en.regions.Harz = 'Mountains of {nowhere}'
    try {
      expect(regionName('Harz', 'en')).toBe('Harz')
    }
    finally {
      en.regions.Harz = saved
    }
  })
})

describe('english', () => {
  // what a reader of English sees for each of DWD's names: the generic words are English, the place names are DWD's
  it.each([
    ['Sachsen', 'Saxony'],
    ['Niedersachsen', 'Lower Saxony'],
    ['Bayern', 'Bavaria'],
    ['Thüringen', 'Thuringia'],
    ['Hessen', 'Hesse'],
    ['Mecklenburg-Vorpommern', 'Mecklenburg-Western Pomerania'],
    ['Nordrhein-Westfalen', 'North Rhine-Westphalia'],
    ['Rheinland-Pfalz', 'Rhineland-Palatinate'],
    ['Baden-Württemberg', 'Baden-Württemberg'],
    ['Schleswig-Holstein', 'Schleswig-Holstein'],
  ])('writes the state %s as %s', (state, name) => {
    expect(stateName(state, 'en')).toBe(name)
  })

  it.each([
    ['Inseln und Marschen', 'Islands and marshes'],
    ['Geest,Schleswig-Holstein und Hamburg', 'Geest of Schleswig-Holstein and Hamburg'],
    ['Mecklenburg-Vorpommern', 'Mecklenburg-Western Pomerania'],
    ['Westl. Niedersachsen/Bremen', 'Western Lower Saxony/Bremen'],
    ['Östl. Niedersachsen', 'Eastern Lower Saxony'],
    ['Rhein.-Westfäl. Tiefland', 'Rhein.-Westfäl. lowlands'],
    ['Ostwestfalen', 'Ostwestfalen'],
    ['Mittelgebirge NRW', 'Uplands of North Rhine-Westphalia'],
    ['Brandenburg und Berlin', 'Brandenburg and Berlin'],
    ['Tiefland Sachsen-Anhalt', 'Lowlands of Saxony-Anhalt'],
    ['Harz', 'Harz'],
    ['Tiefland Thüringen', 'Lowlands of Thuringia'],
    ['Mittelgebirge Thüringen', 'Uplands of Thuringia'],
    ['Tiefland Sachsen', 'Lowlands of Saxony'],
    ['Mittelgebirge Sachsen', 'Uplands of Saxony'],
    ['Nordhessen und hess. Mittelgebirge', 'Nordhessen and Hessian uplands'],
    ['Rhein-Main', 'Rhein-Main'],
    ['Rhein, Pfalz, Nahe und Mosel', 'Rhein, Pfalz, Nahe and Mosel'],
    ['Mittelgebirgsbereich Rheinland-Pfalz', 'Uplands of Rhineland-Palatinate'],
    ['Saarland', 'Saarland'],
    ['Oberrhein und unteres Neckartal', 'Oberrhein and lower Neckartal'],
    ['Hohenlohe/mittlerer Neckar/Oberschwaben', 'Hohenlohe/central Neckar/Oberschwaben'],
    ['Mittelgebirge Baden-Württemberg', 'Uplands of Baden-Württemberg'],
    ['Allgäu/Oberbayern/Bay. Wald', 'Allgäu/Oberbayern/Bay. Wald'],
    ['Donauniederungen', 'Donauniederungen'],
    ['Bayern nördl. der Donau, o. Bayr. Wald, o. Mainfranken', 'Bavaria north of the Donau, excluding Bayr. Wald and Mainfranken'],
    ['Mainfranken', 'Mainfranken'],
  ])('writes the region %s as %s', (region, name) => {
    expect(regionName(region, 'en')).toBe(name)
  })
})

describe('place names', () => {
  // the rule has no exception: a place name is DWD's in every language, the river and the abbreviated adjective included
  it.each(translated)('stay as DWD writes them in %s', (locale) => {
    expect(regionName('Bayern nördl. der Donau, o. Bayr. Wald, o. Mainfranken', locale)).toContain('Donau, ')
    expect(regionName('Bayern nördl. der Donau, o. Bayr. Wald, o. Mainfranken', locale)).not.toMatch(/Danub|Dunaj/)
    expect(regionName('Rhein.-Westfäl. Tiefland', locale)).toContain('Rhein.-Westfäl.')
    expect(regionName('Oberrhein und unteres Neckartal', locale)).toMatch(/^Oberrhein .*Neckartal/)
    expect(regionName('Hohenlohe/mittlerer Neckar/Oberschwaben', locale)).toMatch(/^Hohenlohe\/.*Neckar.*\/Oberschwaben$/)
  })
})

describe('other languages', () => {
  it.each([
    ['fr', 'Tiefland Sachsen', 'Plaine de Saxe'],
    ['fr', 'Inseln und Marschen', 'Îles et marais'],
    ['fr', 'Westl. Niedersachsen/Bremen', 'Basse-Saxe occidentale/Brême'],
    ['es', 'Mittelgebirge Sachsen', 'Media montaña de Sajonia'],
    ['it', 'Mittelgebirge Baden-Württemberg', 'Media montagna del Baden-Württemberg'],
    ['nl', 'Hohenlohe/mittlerer Neckar/Oberschwaben', 'Hohenlohe/Midden-Neckar/Oberschwaben'],
    ['pl', 'Tiefland Sachsen', 'Nizina Saksonii'],
    ['cs', 'Mittelgebirge NRW', 'Středohoří Severního Porýní-Vestfálska'],
    ['da', 'Östl. Niedersachsen', 'Øst-Niedersachsen'],
    ['da', 'Inseln und Marschen', 'Øer og marsk'],
    ['da', 'Hohenlohe/mittlerer Neckar/Oberschwaben', 'Hohenlohe/Midt-Neckar/Oberschwaben'],
    ['fr', 'Geest,Schleswig-Holstein und Hamburg', 'Geest du Schleswig-Holstein et de Hambourg'],
    ['it', 'Geest,Schleswig-Holstein und Hamburg', 'Geest dello Schleswig-Holstein e di Amburgo'],
    ['it', 'Oberrhein und unteres Neckartal', 'Oberrhein e basso Neckartal'],
    ['it', 'Hohenlohe/mittlerer Neckar/Oberschwaben', 'Hohenlohe/medio Neckar/Oberschwaben'],
    ['es', 'Oberrhein und unteres Neckartal', 'Oberrhein y bajo Neckartal'],
    ['es', 'Hohenlohe/mittlerer Neckar/Oberschwaben', 'Hohenlohe/medio Neckar/Oberschwaben'],
    ['nl', 'Westl. Niedersachsen/Bremen', 'West-Nedersaksen/Bremen'],
    ['nl', 'Östl. Niedersachsen', 'Oost-Nedersaksen'],
    ['nl', 'Nordhessen und hess. Mittelgebirge', 'Nordhessen en Hessisch middelgebergte'],
    ['nl', 'Oberrhein und unteres Neckartal', 'Oberrhein en Beneden-Neckartal'],
    ['nl', 'Inseln und Marschen', 'Eilanden en marsland'],
    ['nl', 'Bayern nördl. der Donau, o. Bayr. Wald, o. Mainfranken', 'Beieren ten noorden van de Donau, met uitzondering van Bayr. Wald en Mainfranken'],
  ])('writes %s of %s as %s', (locale, region, name) => {
    expect(regionName(region, locale)).toBe(name)
  })

  it.each([
    ['fr', 'Sachsen', 'Saxe'],
    ['es', 'Sachsen', 'Sajonia'],
    ['it', 'Sachsen', 'Sassonia'],
    ['nl', 'Sachsen', 'Saksen'],
    ['pl', 'Sachsen', 'Saksonia'],
    ['cs', 'Sachsen', 'Sasko'],
    ['da', 'Sachsen', 'Sachsen'],
  ])('writes the state of %s in %s as %s', (locale, state, name) => {
    expect(stateName(state, locale)).toBe(name)
  })
})
