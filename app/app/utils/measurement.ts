// The page "How weather is measured" (GH-3787): its entries, the anchor each one has, and which glossary parameters
// each one explains. The texts are in `i18n/measurement/` (a page of long text is not in the eleven catalogs of the
// interface, as the privacy policy is not); this file is what the page, the glossary and the explanations of
// "Ask the weather" (GH-3764) share, so that a link to an entry is built from one place.

/** The path of the page */
export const MEASUREMENT_PATH = '/measurement'

/** The entries, in the order of the page. The id is the anchor (`/measurement#wind`) and is never changed once released. */
export const TOPICS = [
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
] as const

export type TopicId = (typeof TOPICS)[number]

/** The two sections of the page: the measurements (and the normals that sum them up), and how to read the data */
export const TOPIC_GROUPS: readonly { id: 'measured' | 'reading', topics: readonly TopicId[] }[] = [
  { id: 'measured', topics: ['temperature', 'pressure', 'humidity', 'wind', 'precipitation', 'radiation', 'sunshine', 'visibility', 'evaporation', 'soil-moisture', 'present-weather', 'clouds', 'snow', 'automatic-stations', 'radar', 'urban-stations', 'road-stations', 'from-measurement-to-value', 'normals', 'water-level'] },
  { id: 'reading', topics: ['time', 'observation-forecast-derived', 'data-quality'] },
]

/** Whether a string is the id of an entry */
export function isTopic(value: unknown): value is TopicId {
  return typeof value === 'string' && (TOPICS as readonly string[]).includes(value)
}

/**
 * The address of an entry: the page and the anchor of the entry, for a link in the app.
 *
 * @param topic The id of the entry
 * @returns For example `/measurement#wind`
 */
export function measurementPath(topic: TopicId): string {
  return `${MEASUREMENT_PATH}#${topic}`
}

export interface TopicRule {
  topic: TopicId
  /** The names of the parameters the rule takes, as the glossary spells them */
  pattern: RegExp
  /** The same, in the words the page shows beside the entry (`temperature_air_*`) */
  shown: readonly string[]
}

/**
 * Which entry explains a parameter of the glossary (`/api/glossary`): by the parameter's name, in this order, the first
 * rule that matches. A parameter that no rule takes has no entry (yet) and the glossary shows no link for it.
 *
 * The names are the backend's canonical ones, which are built from the quantity first (`temperature_air_max_2m`), so a
 * pattern on the beginning of the name takes a family of them. What a rule leaves out is left out on purpose and
 * `tests/unit/measurement.test.ts` names it: the water temperature, the speed and the direction of the current and the
 * height of the gauge of GHCN-Daily (the entry on water level and discharge explains the level, the discharge and the
 * groundwater level, and these are none of them), the form of precipitation, the UV index, the cloud density, the counts
 * of days, the frozen and thawed layers of the ground, the radiant temperature of the urban stations, the road surface
 * condition of a forecast, the forecast probabilities and the forecast errors are not what the entries explain. The
 * entries on the kinds of station (automatic, urban, road), on radar, on how a value is formed and on the quality of the
 * data explain no parameter, except that of the road stations, which explains the road surface: a mean, a maximum or a
 * minimum is in the name of a parameter of any quantity, and its quantity's entry says what it is; radar has no parameter
 * of the glossary, and the quality flags are no parameters (`/api/glossary` leaves them out).
 *
 * A parameter whose name ends in `_normal` is a normal of the provider (`sunshine_duration_normal`), whatever it is a
 * normal of, so that rule comes first.
 */
export const TOPIC_RULES: readonly TopicRule[] = [
  { topic: 'normals', pattern: /_normal$/, shown: ['*_normal'] },
  { topic: 'temperature', pattern: /^temperature_(?:air|soil)(?:_|$)/, shown: ['temperature_air_*', 'temperature_soil_*'] },
  { topic: 'pressure', pattern: /^pressure_air(?:_|$)/, shown: ['pressure_air_*'] },
  { topic: 'humidity', pattern: /^(?:humidity_(?:relative|absolute)|temperature_(?:dew_point|wet)|pressure_vapor|vapor_pressure_deficit)(?:_|$)/, shown: ['humidity_relative_*', 'humidity_absolute', 'temperature_dew_point_*', 'temperature_wet_*', 'pressure_vapor_*', 'vapor_pressure_deficit_*'] },
  { topic: 'wind', pattern: /^wind_(?:speed|gust|direction|force)(?:_|$)/, shown: ['wind_speed_*', 'wind_gust_*', 'wind_direction_*', 'wind_force_*'] },
  { topic: 'precipitation', pattern: /^precipitation_(?:amount|intensity)(?:_|$)/, shown: ['precipitation_amount_*', 'precipitation_intensity_*'] },
  { topic: 'radiation', pattern: /^radiation_(?:global|sky|long_wave|short_wave)(?:_|$)/, shown: ['radiation_global_*', 'radiation_sky_*', 'radiation_long_wave_*', 'radiation_short_wave_*'] },
  { topic: 'sunshine', pattern: /^sunshine_duration(?:_|$)/, shown: ['sunshine_duration_*'] },
  { topic: 'visibility', pattern: /^visibility(?:_|$)/, shown: ['visibility_*'] },
  { topic: 'evaporation', pattern: /^(?:evapo(?:ration|transpiration)|temperature_water_evaporation_pan)(?:_|$)/, shown: ['evaporation_amount_*', 'evapotranspiration_*', 'temperature_water_evaporation_pan_*'] },
  { topic: 'soil-moisture', pattern: /^soil_moisture(?:_|$)/, shown: ['soil_moisture_*'] },
  { topic: 'present-weather', pattern: /^(?:weather|soil_state_index)(?:_|$)/, shown: ['weather', 'weather_*', 'soil_state_index'] },
  { topic: 'clouds', pattern: /^cloud_(?:cover|height|type)(?:_|$)/, shown: ['cloud_cover_*', 'cloud_height_*', 'cloud_type_*'] },
  { topic: 'snow', pattern: /^(?:snow_(?:depth|cover)|water_equivalent_snow_depth)(?:_|$)/, shown: ['snow_depth_*', 'snow_cover', 'water_equivalent_snow_depth_*'] },
  // the names of exactly these three: the forecast's `road_surface_condition_forecast` and the grass probe's `temperature_surface_mean` are no road station
  { topic: 'road-stations', pattern: /^(?:road_surface_condition|water_film_thickness|temperature_surface)$/, shown: ['road_surface_condition', 'water_film_thickness', 'temperature_surface'] },
  // the level and the discharge of a gauge, and the level of the groundwater table: not the water temperature or the current
  { topic: 'water-level', pattern: /^(?:stage|discharge|groundwater_level)(?:_|$)/, shown: ['stage_*', 'discharge_*', 'groundwater_level'] },
]

/**
 * The tools of the app an entry points to, for a reader who wants to see what the entry describes: the page of the tool
 * and the key of the catalog (`i18n/locales`) of the words of the link.
 */
export const TOPIC_TOOLS: Partial<Record<TopicId, readonly { to: string, labelKey: string }[]>> = {
  radar: [{ to: '/radar', labelKey: 'measurement.toolRadar' }],
}

/**
 * The tools of the app an entry points to.
 *
 * @param topic The id of the entry
 * @returns The page and the label key of each tool, none for an entry that points to no tool
 */
export function topicTools(topic: TopicId): readonly { to: string, labelKey: string }[] {
  return TOPIC_TOOLS[topic] ?? []
}

/**
 * The entry that explains a parameter of the glossary.
 *
 * @param name The canonical name of the parameter (`wind_gust_max`)
 * @returns The id of the entry, or `undefined` for a parameter that has none
 */
export function topicOfParameter(name: string): TopicId | undefined {
  return TOPIC_RULES.find(rule => rule.pattern.test(name))?.topic
}

/**
 * The key of the catalog (`i18n/locales`) of an entry's short name, the one the glossary shows in the language of the
 * interface (`measurement.topics.observationForecastDerived`): the keys are camel case, the anchors are not.
 *
 * @param topic The id of the entry
 * @returns The key
 */
export function topicLabelKey(topic: TopicId): string {
  return `measurement.topics.${topic.replace(/-(\w)/g, (_, letter: string) => letter.toUpperCase())}`
}

/**
 * The words that stand for the parameters an entry explains.
 *
 * @param topic The id of the entry
 * @returns The patterns of its rules (`wind_gust_*`), none for an entry that explains no parameter
 */
export function parameterPatterns(topic: TopicId): string[] {
  return TOPIC_RULES.filter(rule => rule.topic === topic).flatMap(rule => [...rule.shown])
}
