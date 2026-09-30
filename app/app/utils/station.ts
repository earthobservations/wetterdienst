/**
 * Label a station by its name, id and region, as the station picker and the map's markers show it.
 *
 * A network without regions, e.g. DWD MOSMIX, sends `region` as null for every station, so the
 * region is left out rather than labelled "null".
 *
 * @param station - The station to label
 * @returns The label
 * @example
 * stationLabel({ name: 'JAN MAYEN', station_id: '01001', region: null }) // 'JAN MAYEN (ID: 01001)'
 */
export function stationLabel(station: Pick<Station, 'name' | 'station_id' | 'region'>): string {
  return station.region
    ? `${station.name} (ID: ${station.station_id}, ${station.region})`
    : `${station.name} (ID: ${station.station_id})`
}
