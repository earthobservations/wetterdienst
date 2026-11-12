// The unit types a reader can choose a unit for, and the units offered for each: the one list that the settings
// page (`/settings`) offers rows from and the requests of the tools send their `unit_targets` from (GH-3878). A
// curated subset of what the backend UnitConverter can convert to: 18 of its 28 types have a row here, and the
// length ones carry all six of their units. Adding a unit or a type is a product decision, not a gap to be closed by
// copying the backend. Left out on purpose: mass_per_volume, degree_hour, volume and length_tiny are convertible
// types with no row, and precipitation_intensity leaves out millimeter_per_second, which the backend refuses as a
// target (it is what BUFR publishes a rain rate in, not a unit to read one in). concentration lists the two per-litre
// units and not the two per-cubic-metre spellings of them.
// Each `default` is the backend's own default target for that type (`UnitConverter.targets`): what a request
// that names no unit for the type gets, and what the settings start from. tests/unit/unit-targets.test.ts holds them to the
// settings' defaults, and, through tests/unit/unit-target-defaults.json, tests/model/test_app_unit_target_defaults.py
// to `UnitConverter.targets`.
const LENGTH = ['millimeter', 'centimeter', 'meter', 'kilometer', 'mile', 'nautical_mile']

export interface UnitTargetType {
  type: string
  /** The key of the type's name on the settings page */
  label: string
  units: readonly string[]
  default: string
  /** Which block of the settings page the type is in. */
  group: 'weather' | 'other'
}

export const UNIT_TARGET_TYPES: readonly UnitTargetType[] = [
  { type: 'temperature', label: 'settings.unitTemperature', units: ['degree_celsius', 'degree_kelvin', 'degree_fahrenheit'], default: 'degree_celsius', group: 'weather' },
  { type: 'precipitation', label: 'settings.unitPrecipitation', units: ['millimeter', 'liter_per_square_meter'], default: 'millimeter', group: 'weather' },
  {
    type: 'precipitation_intensity',
    label: 'settings.unitPrecipitationIntensity',
    units: ['millimeter_per_hour', 'liter_per_square_meter_per_hour'],
    default: 'millimeter_per_hour',
    group: 'weather',
  },
  { type: 'pressure', label: 'settings.unitPressure', units: ['pascal', 'hectopascal', 'kilopascal'], default: 'hectopascal', group: 'weather' },
  { type: 'speed', label: 'settings.unitSpeed', units: ['meter_per_second', 'kilometer_per_hour', 'knots', 'beaufort'], default: 'meter_per_second', group: 'weather' },
  { type: 'angle', label: 'settings.unitAngle', units: ['degree', 'radian', 'gradian'], default: 'degree', group: 'weather' },
  { type: 'fraction', label: 'settings.unitFraction', units: ['decimal', 'percent', 'one_eighth'], default: 'percent', group: 'weather' },
  { type: 'length_short', label: 'settings.unitLengthShort', units: LENGTH, default: 'centimeter', group: 'weather' },
  { type: 'length_medium', label: 'settings.unitLengthMedium', units: LENGTH, default: 'meter', group: 'weather' },
  { type: 'length_long', label: 'settings.unitLengthLong', units: LENGTH, default: 'kilometer', group: 'weather' },
  {
    type: 'energy_per_area',
    label: 'settings.unitEnergyPerArea',
    units: ['joule_per_square_centimeter', 'joule_per_square_meter', 'kilojoule_per_square_meter', 'megajoule_per_square_meter'],
    default: 'megajoule_per_square_meter',
    group: 'weather',
  },
  {
    type: 'power_per_area',
    label: 'settings.unitPowerPerArea',
    units: ['watt_per_square_centimeter', 'watt_per_square_meter', 'kilowatt_per_square_meter'],
    default: 'watt_per_square_meter',
    group: 'weather',
  },
  { type: 'time', label: 'settings.unitTime', units: ['second', 'minute', 'hour'], default: 'second', group: 'weather' },
  { type: 'duration', label: 'settings.unitDuration', units: ['second', 'minute', 'hour'], default: 'hour', group: 'weather' },
  {
    type: 'degree_day',
    label: 'settings.unitDegreeDay',
    units: ['degree_celsius_day', 'degree_kelvin_day', 'degree_fahrenheit_day'],
    default: 'degree_celsius_day',
    group: 'weather',
  },
  { type: 'concentration', label: 'settings.unitConcentration', units: ['milligram_per_liter', 'gram_per_liter'], default: 'milligram_per_liter', group: 'other' },
  {
    type: 'conductivity',
    label: 'settings.unitConductivity',
    units: ['microsiemens_per_centimeter', 'microsiemens_per_meter', 'siemens_per_centimeter', 'siemens_per_meter'],
    default: 'microsiemens_per_centimeter',
    group: 'other',
  },
  { type: 'volume_per_time', label: 'settings.unitVolumePerTime', units: ['liter_per_second', 'cubic_meter_per_second'], default: 'cubic_meter_per_second', group: 'other' },
]

/**
 * The `unit_targets` a request sends: the unit chosen for each type in `UNIT_TARGET_TYPES` (the app settings'
 * `units`), the listed default for a type with none or one that is not on its list. Every type is named, so that a
 * request asks for the same units on any server: the server merges its `WD_TS_UNIT_TARGETS` into the targets of a
 * request, and a type the request leaves out would come in the server's unit rather than the one shown on the
 * settings page.
 */
export function requestUnitTargets(chosen: Record<string, string | undefined>): Record<string, string> {
  return Object.fromEntries(UNIT_TARGET_TYPES.map(({ type, units, default: listed }) => {
    const unit = chosen[type]
    return [type, unit && units.includes(unit) ? unit : listed]
  }))
}

/** The unit type the numbers of each kind of climate stripes are of: the annual mean temperature, the annual precipitation sum */
const STRIPES_UNIT_TYPE = { temperature: 'temperature', precipitation: 'precipitation' } as const

/**
 * The `unit_targets` a request for the values of climate stripes sends (GH-3980): the unit the app settings choose for
 * the type of the kind, `degree_celsius` or `millimeter` where the settings name none that is listed. Only that type,
 * as the stripes read one parameter: another one would change nothing of the answer and only the address of the request.
 * The stripes' colours are relative, so the unit changes the numbers and not the stripes.
 */
export function stripesUnitTargets(kind: keyof typeof STRIPES_UNIT_TYPE, chosen: Record<string, string | undefined>): Record<string, string> {
  const type = STRIPES_UNIT_TYPE[kind]
  return { [type]: requestUnitTargets(chosen)[type]! }
}

const UNIT_SYMBOLS: Record<string, string> = {
  degree_celsius: '°C',
  degree_kelvin: 'K',
  degree_fahrenheit: '°F',
  millimeter: 'mm',
  liter_per_square_meter: 'l/m²',
}

/** The symbol a unit is written with next to a number (`degree_celsius` is `°C`), the unit's name with spaces for any other */
export function unitSymbol(unit: string): string {
  return UNIT_SYMBOLS[unit] ?? unit.replaceAll('_', ' ')
}
