// Unit types and the units a reader would want to see values in. A curated subset of what the backend
// UnitConverter can convert to, in both dimensions and by a wide margin: 8 of its 19 convertible
// types have a row here, and the rows that do carry a subset of their units -- the length ones three
// or four of six. Adding a unit or a type is a product decision, not a gap to be closed by copying
// the backend, and one unit cannot be added at all: it refuses millimeter_per_second as a target,
// that being what BUFR publishes a rain rate in rather than a unit to read one in.
// Each `default` is the backend's own default target for that type (`UnitConverter.targets`), which
// the explorer names in its "Default (...)" choice and pins in every request.
export const UNIT_TARGET_TYPES = [
  { type: 'temperature', units: ['degree_celsius', 'degree_kelvin', 'degree_fahrenheit'], default: 'degree_celsius' },
  { type: 'speed', units: ['meter_per_second', 'kilometer_per_hour', 'knots', 'beaufort'], default: 'meter_per_second' },
  { type: 'pressure', units: ['pascal', 'hectopascal', 'kilopascal'], default: 'hectopascal' },
  { type: 'precipitation', units: ['millimeter', 'liter_per_square_meter'], default: 'millimeter' },
  {
    type: 'precipitation_intensity',
    units: ['millimeter_per_hour', 'liter_per_square_meter_per_hour'],
    default: 'millimeter_per_hour',
  },
  { type: 'length_short', units: ['millimeter', 'centimeter', 'meter'], default: 'centimeter' },
  { type: 'length_medium', units: ['millimeter', 'centimeter', 'meter', 'kilometer'], default: 'meter' },
  { type: 'length_long', units: ['meter', 'kilometer', 'mile', 'nautical_mile'], default: 'kilometer' },
]

/**
 * The `unit_targets` a request sends: the user's choice for each type, and the listed default for
 * every type in `UNIT_TARGET_TYPES` left at "Default". The server merges its `WD_TS_UNIT_TARGETS`
 * into a request's targets, so a type the request leaves out comes in the server's unit, not the
 * one the "Default (...)" choice names; naming every listed type keeps that label true.
 */
export function pinnedUnitTargets(chosen: Record<string, string>): Record<string, string> {
  const targets: Record<string, string> = Object.fromEntries(
    UNIT_TARGET_TYPES.map(unitType => [unitType.type, unitType.default]),
  )
  for (const [type, unit] of Object.entries(chosen)) {
    if (unit != null && String(unit).trim() !== '')
      targets[type] = unit
  }
  return targets
}
