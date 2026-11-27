import { Info } from 'luxon'
import tzLookup from 'tz-lookup'

/**
 * The time zone of a position, which the dates of the forecast are read in (the chart's axis, the table's times, the day that is
 * Today): UTC where there is no position or the zone is one the browser does not know, since a zone it does not know would make
 * every date of the chart invalid.
 */
export function zoneOfPosition(latitude: number | null | undefined, longitude: number | null | undefined): string {
  if (latitude == null || longitude == null)
    return 'UTC'
  try {
    const zone = tzLookup(latitude, longitude)
    return Info.isValidIANAZone(zone) ? zone : 'UTC'
  }
  catch {
    return 'UTC'
  }
}
