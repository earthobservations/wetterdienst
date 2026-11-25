import { readdirSync, readFileSync } from 'node:fs'
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
  topicTools,
} from '../../app/utils/measurement'
import { measurement as de } from '../../i18n/measurement/de'
import { measurement as en } from '../../i18n/measurement/en'

// The page "How weather is measured" (GH-3787): its anchors, which glossary parameter links to which entry, and the
// texts, which are written in German and English and have to say the same.

const APP = join(__dirname, '..', '..')
const catalogs = Object.fromEntries(
  ['en', 'de', 'fr', 'es', 'it', 'pl', 'nl', 'cs', 'da', 'lb', 'de-hh'].map(locale => [locale, JSON.parse(readFileSync(join(APP, 'i18n', 'locales', `${locale}.json`), 'utf8'))]),
)

/**
 * Every parameter the backend serves in its glossary: the canonical names of `PARAMETER_TABLE`, but the quality flags,
 * which `/api/glossary` leaves out (read as `tests/unit/glossary-translations.test.ts` reads them)
 */
const table = readFileSync(join(APP, '..', 'src', 'wetterdienst', 'metadata', 'parameter_table.py'), 'utf8')
const PARAMETERS = table
  .split(/^ {4}CanonicalParameter\(/m)
  .slice(1)
  .filter(block => !block.includes('quality_flag=True'))
  .map(block => /^\s*"([a-z0-9_]+)"/.exec(block)?.[1] as string)

function message(locale: string, key: string): unknown {
  return key.split('.').reduce<any>((node, part) => node?.[part], catalogs[locale])
}

describe('the anchors', () => {
  it('are plain lower case words, each once', () => {
    expect(new Set(TOPICS).size).toBe(TOPICS.length)
    for (const topic of TOPICS)
      expect(topic, topic).toMatch(/^[a-z]+(?:-[a-z]+)*$/)
  })

  it('are the twenty-three entries of the issue, in its order', () => {
    // the ids are in links that are printed and shared (and in the explanations of GH-3764): a rename is a breaking change
    expect([...TOPICS]).toEqual([
      'temperature',
      'pressure',
      'humidity',
      'wind',
      'precipitation',
      'radiation',
      'sunshine',
      'visibility',
      'evaporation',
      'soil-moisture',
      'present-weather',
      'clouds',
      'snow',
      'automatic-stations',
      'radar',
      'urban-stations',
      'road-stations',
      'from-measurement-to-value',
      'normals',
      'water-level',
      'time',
      'observation-forecast-derived',
      'data-quality',
    ])
  })

  it('are in the two sections of the page, each entry in one', () => {
    expect(TOPIC_GROUPS.flatMap(group => group.topics)).toEqual([...TOPICS])
    expect(TOPIC_GROUPS.map(group => group.id)).toEqual(['measured', 'reading'])
    // "Reading the data" holds the time, observation, forecast and derived data, and the quality of the data, after the measurements (the maintainer, 2026-11-20)
    expect(TOPIC_GROUPS[1]!.topics).toEqual(['time', 'observation-forecast-derived', 'data-quality'])
  })

  it('are told from other strings, and give the address of an entry', () => {
    expect(isTopic('wind')).toBe(true)
    expect(isTopic('Wind')).toBe(false)
    expect(isTopic('humidity')).toBe(true)
    expect(isTopic('evaporation')).toBe(true)
    expect(isTopic('soil-moisture')).toBe(true)
    expect(isTopic('road-stations')).toBe(true)
    expect(isTopic('from-measurement-to-value')).toBe(true)
    expect(isTopic('radar')).toBe(true)
    expect(isTopic('water-level')).toBe(true)
    expect(isTopic('data-quality')).toBe(true)
    expect(isTopic('hydrology')).toBe(false)
    expect(isTopic(undefined)).toBe(false)
    expect(isTopic(['wind'])).toBe(false)
    expect(measurementPath('wind')).toBe('/measurement#wind')
    expect(measurementPath('observation-forecast-derived')).toBe('/measurement#observation-forecast-derived')
  })

  it('have a short name in the catalog of every language, under a camel case key', () => {
    expect(topicLabelKey('observation-forecast-derived')).toBe('measurement.topics.observationForecastDerived')
    expect(topicLabelKey('from-measurement-to-value')).toBe('measurement.topics.fromMeasurementToValue')
    expect(topicLabelKey('road-stations')).toBe('measurement.topics.roadStations')
    expect(topicLabelKey('water-level')).toBe('measurement.topics.waterLevel')
    expect(topicLabelKey('data-quality')).toBe('measurement.topics.dataQuality')
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
    ['pressure_air_site', 'pressure'],
    ['pressure_air_site_mean', 'pressure'],
    ['pressure_air_site_delta_last_3h', 'pressure'],
    ['pressure_air_sea_level', 'pressure'],
    ['pressure_air_site_reduced', 'pressure'],
    ['humidity_relative', 'humidity'],
    ['humidity_relative_mean', 'humidity'],
    ['humidity_absolute', 'humidity'],
    ['temperature_dew_point_2m', 'humidity'],
    ['temperature_dew_point_mean_2m', 'humidity'],
    ['temperature_wet_mean_2m', 'humidity'],
    ['temperature_wet_ice_formation', 'humidity'],
    ['pressure_vapor', 'humidity'],
    ['vapor_pressure_deficit_mean', 'humidity'],
    ['wind_speed_mean', 'wind'],
    ['wind_gust_max', 'wind'],
    ['wind_gust_max_last_3h', 'wind'],
    ['wind_direction', 'wind'],
    ['wind_force_beaufort', 'wind'],
    ['precipitation_amount', 'precipitation'],
    ['precipitation_amount_last_6h', 'precipitation'],
    ['precipitation_intensity', 'precipitation'],
    ['radiation_global', 'radiation'],
    ['radiation_global_intensity_mean', 'radiation'],
    ['radiation_global_relative_last_1h', 'radiation'],
    ['radiation_sky_long_wave', 'radiation'],
    ['radiation_sky_short_wave_diffuse', 'radiation'],
    ['radiation_sky_short_wave_direct_perpendicular_intensity_mean', 'radiation'],
    ['radiation_long_wave_net_last_3h', 'radiation'],
    ['radiation_short_wave_net_last_3h', 'radiation'],
    ['sunshine_duration', 'sunshine'],
    ['sunshine_duration_relative', 'sunshine'],
    ['visibility', 'visibility'],
    ['visibility_mean', 'visibility'],
    ['visibility_index', 'visibility'],
    ['visibility_measurement_method', 'visibility'],
    ['evaporation_amount', 'evaporation'],
    ['evaporation_amount_grass_sand', 'evaporation'],
    ['evaporation_amount_multiday', 'evaporation'],
    ['temperature_water_evaporation_pan_min', 'evaporation'],
    ['evapotranspiration_last_24h', 'evaporation'],
    ['evapotranspiration_potential_grass_fao', 'evaporation'],
    ['evapotranspiration_potential_last_24h', 'evaporation'],
    ['soil_moisture_grass_loamy_silt_10cm_20cm', 'soil-moisture'],
    ['soil_moisture_corn_sand_00cm_60cm', 'soil-moisture'],
    ['soil_moisture_mean_winter_cereals_loamy_silt_00cm_60cm', 'soil-moisture'],
    ['weather', 'present-weather'],
    ['weather_past', 'present-weather'],
    ['weather_last_6h', 'present-weather'],
    ['weather_significant_optional_last_6h', 'present-weather'],
    ['weather_type_fog', 'present-weather'],
    ['weather_type_vicinity_thunder', 'present-weather'],
    ['soil_state_index', 'present-weather'],
    ['cloud_cover_total', 'clouds'],
    ['cloud_cover_total_mean_midnight_to_midnight_manual', 'clouds'],
    ['cloud_cover_total_measurement_method', 'clouds'],
    ['cloud_cover_layer1', 'clouds'],
    ['cloud_cover_below_2km', 'clouds'],
    ['cloud_height_layer3', 'clouds'],
    ['cloud_type_layer2', 'clouds'],
    ['road_surface_condition', 'road-stations'],
    ['water_film_thickness', 'road-stations'],
    ['temperature_surface', 'road-stations'],
    ['stage', 'water-level'],
    ['stage_max', 'water-level'],
    ['stage_mean', 'water-level'],
    ['stage_min', 'water-level'],
    ['discharge', 'water-level'],
    ['discharge_max', 'water-level'],
    ['discharge_mean', 'water-level'],
    ['discharge_min', 'water-level'],
    ['groundwater_level', 'water-level'],
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
    // the water: the entry on water level and discharge explains the level, the discharge and the groundwater level, and not
    // the temperature of the water, the speed or the direction of the current (WSV), the height of the gauge of GHCN-Daily
    // (NOAA's difference between the height of the river and of the gauge, which is no gauge zero), the clearance height under
    // a bridge or the content of a reservoir
    'temperature_water',
    'temperature_water_mean',
    'flow_speed',
    'flow_direction',
    'distance_river_gauge_height',
    'clearance_height',
    'volume_reservoir',
    // what the entries do not explain
    'precipitation_form',
    'precipitation_type_flags',
    'precipitation_index',
    'precipitation_duration',
    'probability_precipitation_convective_last_1h',
    'probability_wind_gust_ge_25kn_last_12h',
    'wind_movement',
    'uv_index_max',
    'probability_visibility_below_1000m',
    'error_absolute_pressure_air_site',
    'error_absolute_temperature_dew_point_2m',
    // what the entries on clouds, weather, evaporation and soil moisture do not explain
    'cloud_density',
    'count_days_cloud_cover_total_mean_gt_80pct',
    'count_weather_type_fog',
    'count_days_multiday_evaporation',
    'frozen_ground_layer_thickness',
    'thawing_thickness_bare_ground',
    // what the entries on the road stations and the urban stations do not explain: the road surface condition and the
    // surface temperature of a forecast, the surface temperature of a probe on grass (RMI), the radiant temperature
    // of DWD's urban stations (no source read for the page says what it is) and the form of the precipitation a road
    // station reports (a code of its own, whose bits the entry does not explain)
    'road_surface_condition_forecast',
    'temperature_surface_mean',
    'temperature_radiant_2m',
    'precipitation_type_flags',
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
    const families = /^(?:temperature_(?:air|soil|dew_point|wet)|pressure_(?:air|vapor)|humidity_|vapor_pressure|wind_(?:speed|gust|direction|force)|precipitation_(?:amount|intensity)|radiation_|sunshine_duration|visibility|evapo|soil_moisture|soil_state|weather|cloud_(?:cover|height|type)|snow_depth|water_equivalent_snow_depth|road_surface_condition$|water_film|temperature_surface$|stage|discharge|groundwater_level)/
    expect(PARAMETERS.filter(name => families.test(name) && topicOfParameter(name) === undefined)).toEqual([])
  })

  it('say in words which parameters an entry explains, none for those that explain none', () => {
    expect(parameterPatterns('wind')).toEqual(['wind_speed_*', 'wind_gust_*', 'wind_direction_*', 'wind_force_*'])
    expect(parameterPatterns('temperature')).toEqual(['temperature_air_*', 'temperature_soil_*'])
    expect(parameterPatterns('pressure')).toEqual(['pressure_air_*'])
    expect(parameterPatterns('humidity')).toEqual(['humidity_relative_*', 'humidity_absolute', 'temperature_dew_point_*', 'temperature_wet_*', 'pressure_vapor_*', 'vapor_pressure_deficit_*'])
    expect(parameterPatterns('radiation')).toEqual(['radiation_global_*', 'radiation_sky_*', 'radiation_long_wave_*', 'radiation_short_wave_*'])
    expect(parameterPatterns('visibility')).toEqual(['visibility_*'])
    expect(parameterPatterns('evaporation')).toEqual(['evaporation_amount_*', 'evapotranspiration_*', 'temperature_water_evaporation_pan_*'])
    expect(parameterPatterns('soil-moisture')).toEqual(['soil_moisture_*'])
    expect(parameterPatterns('present-weather')).toEqual(['weather', 'weather_*', 'soil_state_index'])
    expect(parameterPatterns('clouds')).toEqual(['cloud_cover_*', 'cloud_height_*', 'cloud_type_*'])
    expect(parameterPatterns('road-stations')).toEqual(['road_surface_condition', 'water_film_thickness', 'temperature_surface'])
    expect(parameterPatterns('water-level')).toEqual(['stage_*', 'discharge_*', 'groundwater_level'])
    // the entries on the kinds of station and on how a value is formed explain no parameter: a mean, a maximum or a
    // minimum is in the name of the parameter of every quantity, and the entry of that quantity says what it is
    expect(parameterPatterns('automatic-stations')).toEqual([])
    expect(parameterPatterns('urban-stations')).toEqual([])
    expect(parameterPatterns('radar')).toEqual([])
    expect(parameterPatterns('data-quality')).toEqual([])
    expect(parameterPatterns('from-measurement-to-value')).toEqual([])
    expect(parameterPatterns('normals')).toEqual(['*_normal'])
    expect(parameterPatterns('time')).toEqual([])
    expect(parameterPatterns('observation-forecast-derived')).toEqual([])
  })
})

describe.each([['en', en], ['de', de]] as const)('the text in %s', (locale, texts) => {
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
    for (const topic of ['temperature', 'pressure', 'humidity', 'wind', 'precipitation', 'radiation', 'sunshine', 'visibility', 'evaporation', 'soil-moisture', 'present-weather', 'clouds', 'snow', 'automatic-stations', 'radar', 'urban-stations', 'road-stations', 'from-measurement-to-value', 'water-level'] as const)
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

  it('cites the WMO Guide by the edition of each volume (I, II and III: 2024, V: 2023), by volume, chapter and section, and the normals by their number', () => {
    for (const topic of TOPICS) {
      for (const { citation } of texts[topic].sources.filter(source => source.citation.includes('WMO-No. 8'))) {
        expect(citation, topic).toMatch(/Volume (?:III|II|I|V)[ ,(].*Chapter \d.*sections? \d/)
        // the edition goes with the volume: the current one of each
        for (const volume of citation.matchAll(/Volume (III|II|I|V)\b/g)) {
          const year = volume[1] === 'V' ? '2023' : '2024'
          expect(citation, `${topic}: Volume ${volume[1]}`).toContain(`WMO (${year}).`)
          expect(citation, `${topic}: Volume ${volume[1]}`).toContain(`${year} edition`)
        }
      }
    }
    for (const topic of ['temperature', 'pressure', 'humidity', 'wind', 'precipitation', 'radiation', 'sunshine', 'visibility', 'evaporation', 'soil-moisture', 'present-weather', 'clouds', 'snow', 'automatic-stations', 'radar', 'urban-stations', 'road-stations', 'from-measurement-to-value'] as const)
      expect(texts[topic].sources[0]!.citation, topic).toContain('WMO-No. 8')
    // a source that cites Volume V cites it as its own edition, not in the same citation as a 2024 volume
    for (const topic of TOPICS) {
      for (const { citation } of texts[topic].sources)
        expect(citation.includes('Volume V') && citation.includes('2024 edition'), topic).toBe(false)
    }
    // the chapters of the table of the issue: pressure I-3 and V-3, humidity I-4 and V-3, radiation I-7, visibility I-9 and V-3
    expect(texts.pressure.sources[0]!.citation).toContain('Volume I, Chapter 3 (Measurement of atmospheric pressure)')
    expect(texts.humidity.sources[0]!.citation).toContain('Volume I, Chapter 4 (Measurement of humidity)')
    expect(texts.radiation.sources[0]!.citation).toContain('Volume I, Chapter 7 (Measurement of radiation)')
    expect(texts.visibility.sources[0]!.citation).toContain('Volume I, Chapter 9 (Measurement of visibility)')
    // evaporation I-10, soil moisture I-11, present weather and state of the ground I-14, clouds I-15
    expect(texts.evaporation.sources[0]!.citation).toContain('Volume I, Chapter 10 (Measurement of evaporation)')
    expect(texts['soil-moisture'].sources[0]!.citation).toContain('Volume I, Chapter 11 (Measurement of soil moisture)')
    expect(texts['present-weather'].sources[0]!.citation).toContain('Volume I, Chapter 14 (Observation of present and past weather; state of the ground)')
    expect(texts.clouds.sources[0]!.citation).toContain('Volume I, Chapter 15 (Observation and measurement of clouds)')
    // automatic stations III-1, urban stations III-9, road weather stations III-10, and from measurement to value V-2 and V-3 (with the table of Volume I, Chapter 1)
    expect(texts['automatic-stations'].sources[0]!.citation).toContain('Volume III (Observing systems), Chapter 1 (Measurements at automatic weather stations)')
    expect(texts['urban-stations'].sources[0]!.citation).toContain('Volume III (Observing systems), Chapter 9 (Urban observations)')
    expect(texts['road-stations'].sources[0]!.citation).toContain('Volume III (Observing systems), Chapter 10 (Road meteorological measurements)')
    const value = texts['from-measurement-to-value'].sources.map(source => source.citation).join(' ')
    expect(value).toContain('Volume V (Quality assurance and management of observing systems), Chapter 2 (Sampling meteorological variables)')
    expect(value).toContain('Chapter 3 (Data reduction)')
    expect(value).toContain('Volume I, Chapter 1 (General), Annex 1.A')
    for (const topic of ['pressure', 'humidity', 'visibility'] as const)
      expect(texts[topic].sources.map(source => source.citation).join(' '), topic).toContain('Volume V (Quality assurance and management of observing systems), Chapter 3 (Data reduction)')
    // radar III-7, and the data quality III-1 (sections 1.4.2 and 1.5) beside the pages of the library
    expect(texts.radar.sources[0]!.citation).toContain('Volume III (Observing systems), Chapter 7 (Radar measurements)')
    expect(texts['data-quality'].sources.map(source => source.citation).join(' ')).toContain('Volume III (Observing systems), Chapter 1 (Measurements at automatic weather stations), sections 1.4.2 and 1.5')
    // water level and discharge rest on the Guide to Hydrological Practices (WMO-No. 168, Volume I, 2008 edition updated in 2025), not on WMO-No. 8
    const hydrology = texts['water-level'].sources[0]!.citation
    expect(hydrology).toContain('WMO-No. 168')
    expect(hydrology).toContain('2008 edition, updated in 2025')
    expect(hydrology).toContain('Chapter 5 (Surface water quantity and sediment measurement)')
    expect(hydrology).toContain('Chapter 9 (Data processing and quality control), sections 9.6.2.1 to 9.6.2.4')
    expect(hydrology).not.toContain('WMO-No. 8')
    expect(texts.normals.sources[0]!.citation).toContain('WMO-No. 1203')
    expect(texts['observation-forecast-derived'].sources.map(source => source.citation).join(' ')).toContain('Volume V')
    expect(texts.temperature.sources.map(source => source.citation).join(' ')).toContain('WMO (2023)')
  })

  it('names the files of a provider by the folders they are in, which have no address of their own', () => {
    const files = JSON.stringify(texts.temperature.sources) + JSON.stringify(texts.wind.sources)
    expect(files).toContain('opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/recent/')
    expect(files).toContain('Metadaten_Parameter_klima_tag_')
  })

  it('names the edition of the Guide it uses, and has none of the provisional 2026 one', () => {
    for (const entry of Object.values(texts))
      expect(JSON.stringify(entry)).not.toMatch(/2026 edition|Ausgabe 2026/)
  })

  it('refers to another entry by the short name it has in the catalog of the language, and to one that exists', () => {
    const names = new Set(TOPICS.map(topic => message(locale, topicLabelKey(topic)) as string))
    const quoted = locale === 'en' ? /\b[Ss]ee "([^"]+)"/g : /\b[Ss]iehe „([^“]+)“/g
    const found: string[] = []
    for (const entry of Object.values(texts)) {
      for (const paragraph of entry.parts.flatMap(part => part.paragraphs))
        found.push(...[...paragraph.matchAll(quoted)].map(match => match[1]!))
    }
    expect(found.length).toBeGreaterThan(10)
    expect(found.filter(name => !names.has(name))).toEqual([])
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

describe('what the texts say about which provider has which parameter', () => {
  // the entries say that soil moisture is DWD's modelled one alone, that the weather types are NOAA's GHCN-Daily and that
  // the weather codes of a forecast are DWD's MOSMIX and DMO: a provider that adds one of these makes the sentence wrong
  const providers = join(APP, '..', 'src', 'wetterdienst', 'provider')
  const files = readdirSync(providers, { recursive: true, encoding: 'utf8' })
    .map(file => file.replaceAll('\\', '/'))
    .filter(file => file.endsWith('.py'))

  function providersOf(pattern: RegExp): string[] {
    return files.filter(file => pattern.test(readFileSync(join(providers, file), 'utf8'))).sort()
  }

  it('has soil moisture at DWD\'s derived network only', () => {
    expect(providersOf(/"soil_moisture/)).toEqual(['dwd/derived/metadata.py'])
  })

  it('has the weather types at NOAA\'s GHCN-Daily only, and the significant weather at DWD\'s two forecasts', () => {
    expect(providersOf(/"weather_type_/)).toEqual(['noaa/ghcn/metadata.py'])
    expect(providersOf(/"weather_significant/)).toEqual(['dwd/dmo/metadata.py', 'dwd/mosmix/metadata.py'])
    expect(providersOf(/"weather_last_6h"/)).toEqual(['dwd/dmo/metadata.py', 'dwd/mosmix/metadata.py'])
    // a provider declares its parameters in `metadata.py` or in `api.py`: both are scanned
    expect(files.length).toBeGreaterThan(100)
    expect(files.some(file => file.endsWith('/api.py'))).toBe(true)
  })

  it('has urban stations at DWD\'s observation network only, and the road weather stations at DWD\'s road network, whose names its forecast shares', () => {
    // the entries on the urban and the road weather stations say that wetterdienst has them from one provider
    expect(providersOf(/"urban_/)).toEqual(['dwd/observation/metadata.py'])
    expect(providersOf(/"road_surface_condition"/)).toEqual(['dwd/road/api.py'])
    expect(providersOf(/"water_film_thickness"/)).toEqual(['dwd/road/api.py'])
    // temperature_surface is a measurement of the stations and the forecast of DWD's SWSMOS: the entry says the name does not tell which
    expect(providersOf(/"temperature_surface"/)).toEqual(['dwd/road/api.py', 'dwd/swsmos/metadata.py'])
    expect(providersOf(/"road_surface_condition_forecast"/)).toEqual(['dwd/swsmos/metadata.py'])
  })

  it('names the folders of the DWD files that the entries on the automatic, urban and road weather stations rest on', () => {
    expect(JSON.stringify(en['automatic-stations'].sources)).toContain('climate/hourly/air_temperature/recent/')
    expect(JSON.stringify(en['urban-stations'].sources)).toContain('climate_urban/')
    expect(JSON.stringify(de['urban-stations'].sources)).toContain('10minutenwerte_TU_STADT_')
    expect(JSON.stringify(en['road-stations'].sources)).toContain('weather/weather_reports/road_weather_stations/')
    expect(JSON.stringify(de['road-stations'].sources)).toContain('SH10')
  })

  it('names the folders of the DWD files that the entries on clouds and present weather rest on', () => {
    expect(JSON.stringify(en.clouds.sources)).toContain('climate/hourly/cloudiness/recent/')
    expect(JSON.stringify(en['present-weather'].sources)).toContain('climate/hourly/weather_phenomena/recent/')
    expect(JSON.stringify(de.clouds.sources)).toContain('climate/hourly/cloud_type/recent/')
    expect(JSON.stringify(de['present-weather'].sources)).toContain('subdaily/soil/recent/')
  })

  it('has radar data at DWD only: the entry says wetterdienst has radar from one provider, and lists the sites of other countries without data', () => {
    // the radar sites of other countries are a list (EUMETNET OPERA), which is no values class
    expect(providersOf(/class \w*Radar\w*Values\b/)).toEqual(['dwd/radar/api.py'])
    expect(files.some(file => file.startsWith('eumetnet/opera/'))).toBe(true)
    expect(providersOf(/class \w*Opera\w*(?:Request|Values)\b/)).toEqual([])
  })

  it('has water level and discharge at four providers, and the groundwater level at two: the entry on water level names them', () => {
    // the entry says that wetterdienst has a stage and a discharge from WSV, the Environment Agency, Hub'Eau and IMGW, and
    // names the groundwater level of WSV and of the Environment Agency: a provider that adds one makes the sentence wrong
    expect(providersOf(/"stage"/)).toEqual(['ea/hydrology/api.py', 'eaufrance/hubeau/api.py', 'imgw/hydrology/api.py', 'wsv/pegel/api.py'])
    expect(providersOf(/"discharge"/)).toEqual(['ea/hydrology/api.py', 'eaufrance/hubeau/api.py', 'imgw/hydrology/api.py', 'wsv/pegel/api.py'])
    expect(providersOf(/"groundwater_level"/)).toEqual(['ea/hydrology/api.py', 'wsv/pegel/api.py'])
    // the gauge zero is in the station list of WSV, Hub'Eau and IMGW, and not in the Environment Agency's
    expect(providersOf(/"gauge_zero"/)).toEqual(['eaufrance/hubeau/api.py', 'imgw/hydrology/api.py', 'wsv/pegel/api.py'])
    expect(providersOf(/"gauge_zero_datum"/)).toEqual(['eaufrance/hubeau/api.py', 'imgw/hydrology/api.py', 'wsv/pegel/api.py'])
    for (const text of [en['water-level'], de['water-level']]) {
      const body = JSON.stringify(text.parts)
      for (const provider of ['wsv/pegel', 'ea/hydrology', 'eaufrance/hubeau', 'imgw/hydrology'])
        expect(body, provider).toContain(provider)
    }
  })

  it('gives the range of the precipitation scan as 180 km since 24 November 2026, and names what that rests on (GH-4404)', () => {
    // DWD extended it from 150 km on that day (its Open Data news of 3 November, its German page and the sheet of the scan say 180 km); its English
    // page still says 150 km, so the entry rests on the other three and says why the English page is not followed
    const scan = (text: typeof en) => text.radar.parts.flatMap(part => part.paragraphs).find(paragraph => /150 km/.test(paragraph) && /180 km/.test(paragraph))!
    expect(scan(en)).toContain('the antenna follows the terrain (range 180 km, extended from 150 km on 24 November 2026)')
    expect(scan(de)).toContain('bei dem die Antenne dem Gelände folgt (Reichweite 180 km, am 24. November 2026 von 150 km erweitert)')
    for (const text of [en, de]) {
      const body = JSON.stringify(text.radar.parts)
      // the 150 km of the entry is the one before the change, and the entry has no other
      expect(body.match(/150 km/g)).toHaveLength(1)
      expect(body).not.toMatch(/(?:range|Reichweite) 150 km/)
      const sources = JSON.stringify(text.radar.sources)
      expect(sources).toContain('opendata_november2026_1.html')
      expect(sources).toContain('standortprodukt_sweep_niederschlagsscan.pdf')
      expect(sources).toMatch(/25\.? November 2026/)
    }
    expect(JSON.stringify(en.radar.sources)).toContain('English page still gave the range of the precipitation scan as 150 km')
  })

  it('names the pages of the services and of DWD that the entries on radar and on water level rest on', () => {
    expect(JSON.stringify(en.radar.sources)).toContain('radar_products/radar_products.html')
    expect(JSON.stringify(de.radar.sources)).toContain('radarprodukte/radarprodukte.html')
    expect(JSON.stringify(en.radar.sources)).toContain('radvor/radvor.html')
    expect(JSON.stringify(en.radar.sources)).toContain('radolan/radolan.html')
    for (const texts of [en, de]) {
      const hydrology = JSON.stringify(texts['water-level'].sources)
      for (const page of ['pegelonline.wsv.de/gast/hilfe', 'environment.data.gov.uk/hydrology/doc/reference', 'hubeau.eaufrance.fr/page/api-hydrometrie', 'danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/'])
        expect(hydrology, page).toContain(page)
    }
  })

  describe('the quality of the data', () => {
    // the entry says that there are nine checks, that the check `source` reads the verdict of ten providers, and which
    // providers return no flag: the page of the documentation that the entry rests on says it, and the entry follows it
    const docs = join(APP, '..', 'docs', 'data')
    const plausibility = readFileSync(join(docs, 'plausibility.md'), 'utf8')
    const flags = readFileSync(join(docs, 'quality-flags.md'), 'utf8')

    it('has nine checks in the documentation', () => {
      const table = plausibility.slice(plausibility.indexOf('## The checks'), plausibility.indexOf('### The limit of a run'))
      const checks = [...table.matchAll(/^\| `([a-z]+)` \|/gm)].map(match => match[1])
      expect(checks).toEqual(['range', 'elevation', 'stuck', 'step', 'relations', 'consistency', 'floor', 'limits', 'source'])
      // and the entry names each of them, in the words of the documentation
      for (const check of checks)
        expect(JSON.stringify(en['data-quality'].parts), check).toContain(check)
    })

    it('has the check `source` at ten providers', () => {
      const coverage = plausibility.slice(plausibility.indexOf('<!-- coverage:start -->'), plausibility.indexOf('<!-- coverage:end -->'))
      const providers = new Set([...coverage.matchAll(/^\| `source` \| `([a-z]+)\//gm)].map(match => match[1]))
      expect([...providers].sort()).toEqual(['chmi', 'dmi', 'dwd', 'ea', 'eaufrance', 'meteofrance', 'metno', 'metoffice', 'noaa', 'nws'])
    })

    it('has no flag for the providers the entry says return none, and QN for DWD\'s observation', () => {
      const row = flags.split('\n').find(line => line.startsWith('| IMGW hydrology, WSV, FMI, KNMI, IPMA, LHMT, MeteoSwiss, AEMET, Geosphere, Météo-France synop |'))
      expect(row).toContain('| null (apart from the `suspect:`/`rejected:` and `raw:` tokens)')
      expect(flags).toContain('| DWD mosmix, dmo, poi, swsmos, radar and the other DWD networks | null')
      expect(flags).toMatch(/\| DWD observation \| `QN`, the quality control level/)
    })
  })

  it('points the entry on radar to the Radar tool, in the words of every language, and to nothing else', () => {
    expect(topicTools('radar')).toEqual([{ to: '/radar', labelKey: 'measurement.toolRadar' }])
    for (const topic of TOPICS.filter(topic => topic !== 'radar'))
      expect(topicTools(topic), topic).toEqual([])
    for (const locale of Object.keys(catalogs))
      expect(typeof message(locale, 'measurement.toolRadar'), locale).toBe('string')
    // the page is there
    expect(readdirSync(join(APP, 'app', 'pages'))).toContain('radar.vue')
  })
})
