// The page "How weather is measured" (GH-3787): its entries, the anchor each one has, and which glossary parameters
// each one explains. The texts are in `i18n/measurement/` (a page of long text is not in the eleven catalogs of the
// interface, as the privacy policy is not); this file is what the page, the glossary and the explanations of
// "Ask the weather" (GH-3764) share, so that a link to an entry is built from one place.

/** The path of the page */
export const MEASUREMENT_PATH = '/measurement'

/** The entries, in the order of the page. The id is the anchor (`/measurement#wind`) and is never changed once released. */
export const TOPICS = [
  'temperature',
  'wind',
  'precipitation',
  'sunshine',
  'snow',
  'normals',
  'time',
  'observation-forecast-derived',
] as const

export type TopicId = (typeof TOPICS)[number]

/** The two sections of the page: the measurements (and the normals that sum them up), and how to read the data */
export const TOPIC_GROUPS: readonly { id: 'measured' | 'reading', topics: readonly TopicId[] }[] = [
  { id: 'measured', topics: ['temperature', 'wind', 'precipitation', 'sunshine', 'snow', 'normals'] },
  { id: 'reading', topics: ['time', 'observation-forecast-derived'] },
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
 * `tests/unit/measurement.test.ts` names it: the dew point, the wet-bulb and the water temperature are humidity and
 * hydrology, whose entries are not written yet; the form of precipitation and the soil moisture are not what the entries
 * of precipitation and temperature explain.
 *
 * A parameter whose name ends in `_normal` is a normal of the provider (`sunshine_duration_normal`), whatever it is a
 * normal of, so that rule comes first.
 */
export const TOPIC_RULES: readonly TopicRule[] = [
  { topic: 'normals', pattern: /_normal$/, shown: ['*_normal'] },
  { topic: 'temperature', pattern: /^temperature_(?:air|soil)(?:_|$)/, shown: ['temperature_air_*', 'temperature_soil_*'] },
  { topic: 'wind', pattern: /^wind_(?:speed|gust|direction|force)(?:_|$)/, shown: ['wind_speed_*', 'wind_gust_*', 'wind_direction_*', 'wind_force_*'] },
  { topic: 'precipitation', pattern: /^precipitation_(?:amount|intensity)(?:_|$)/, shown: ['precipitation_amount_*', 'precipitation_intensity_*'] },
  { topic: 'sunshine', pattern: /^sunshine_duration(?:_|$)/, shown: ['sunshine_duration_*'] },
  { topic: 'snow', pattern: /^(?:snow_(?:depth|cover)|water_equivalent_snow_depth)(?:_|$)/, shown: ['snow_depth_*', 'snow_cover', 'water_equivalent_snow_depth_*'] },
]

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
