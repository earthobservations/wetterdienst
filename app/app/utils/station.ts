/**
 * Label a station by its name, id and region, as the station picker and the map's markers show it.
 *
 * A network without regions, e.g. DWD MOSMIX, sends `region` as null for every station, so the
 * region is left out rather than labelled "null". A station without a name, e.g. a postcode of
 * dwd/derived climate_correction_factor, is labelled by its id.
 *
 * @param station - The station to label
 * @returns The label
 * @example
 * stationLabel({ name: 'JAN MAYEN', station_id: '01001', region: null }) // 'JAN MAYEN (ID: 01001)'
 * stationLabel({ name: null, station_id: '01067', region: null }) // 'ID: 01067'
 */
export function stationLabel(station: Pick<Station, 'name' | 'station_id' | 'region'>): string {
  const details = [`ID: ${station.station_id}`, station.region].filter(Boolean).join(', ')
  return station.name ? `${station.name} (${details})` : details
}

/**
 * Whether a station has a position: a postcode of dwd/derived climate_correction_factor has none,
 * so it has no place on the map and no point to offer an interpolation.
 *
 * @param station - The station to check
 * @returns Whether its latitude and longitude are both given
 */
export function hasPosition(station: Pick<Station, 'latitude' | 'longitude'>): boolean {
  return station.latitude != null && station.longitude != null
}

/**
 * Label a station by its name and id, as a chosen station's chip and the interpolation's station
 * picker show it; a station without a name, e.g. a postcode of dwd/derived
 * climate_correction_factor chosen in station mode, by its id alone.
 *
 * @param station - The station to label
 * @returns The label
 * @example
 * stationShortLabel({ name: 'JAN MAYEN', station_id: '01001' }) // 'JAN MAYEN (01001)'
 * stationShortLabel({ name: null, station_id: '01067' }) // '01067'
 */
export function stationShortLabel(station: Pick<Station, 'name' | 'station_id'>): string {
  return station.name ? `${station.name} (${station.station_id})` : station.station_id
}
