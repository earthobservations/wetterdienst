/**
 * What the backend answers for `GET /api/storm-cells` (`dwd/storm_cells`, GH-4202), written out for the tests' fixtures
 * (GH-4208): the `metadata` block with DWD's terms, the `reference_time` of the scan and one entry for each cell, in the
 * shape of `DwdStormCellsResult.to_dict()` asked without the forecast track (`track=false`). A scan with no cell is the
 * usual one: DWD writes one every 5 minutes and about 80 % of them are empty.
 */

export interface CellOptions {
  cell_id: string
  latitude: number
  longitude: number
  /** 0 weak to 3 extreme, null where DWD gave none */
  severity?: number | null
  speed?: number | null
  /** The calculated bearing the cell moves towards */
  direction?: number | null
  /** The half-width of the square outline in degrees of latitude (0.12 is about 13 km) */
  size?: number
  /** Another outline than the square: a GeoJSON geometry of the answer */
  geometry?: unknown
}

const LABELS = ['weak', 'moderate', 'severe', 'extreme']

/**
 * The reference time of a scan that came `minutesAgo` minutes before `now`, on the 5-minute grid DWD writes them on, as the
 * backend writes it. The default of a scan of these fixtures: the app takes a scan more than 20 minutes old for out of date
 * and draws none of its cells, so a fixture has to be of the time of the test (which a test with a fake clock reads through
 * `Date.now()` as well).
 */
export function recentReference(now: number = Date.now(), minutesAgo = 6): string {
  const grid = 5 * 60_000
  const at = Math.floor((now - minutesAgo * 60_000) / grid) * grid
  return `${new Date(at).toISOString().replace('Z', '')}000+00:00`
}

/** A closed ring of GeoJSON, `[longitude, latitude]`, round a centre: a square, the longitude's half-width as wide for the latitude's cosine */
export function ringAround(latitude: number, longitude: number, size: number): number[][] {
  const wide = size / Math.cos(latitude * Math.PI / 180)
  const corners = [[-wide, -size], [wide, -size], [wide, size], [-wide, size], [-wide, -size]]
  return corners.map(([dx, dy]) => [Number((longitude + dx!).toFixed(5)), Number((latitude + dy!).toFixed(5))])
}

/**
 * One cell of the answer. The backend's columns (`_SCHEMA` of `dwd/storm_cells/api.py`) are all nullable and the document
 * types a cell as an open object, so a fixture states what it writes: a test takes the outline and the centre away from a
 * cell (DWD gave it neither), which the nullable `geometry` and centroid say.
 */
export interface StormCellRow {
  reference_time: string
  cell_id: string
  code: string
  predecessor_code: string | null
  split_event: boolean
  merge_event: boolean
  first_detection: string
  number_detections: number
  severity: number | null
  severity_label: string | null
  severity_decimal: number | null
  hail_flag: number
  heavy_rain_flag: number
  gust_flag: number
  centroid_latitude: number | null
  centroid_longitude: number | null
  cell_speed_kmh: number | null
  direction_degrees: number | null
  covered_area_km2: number
  geometry: unknown
}

export function stormCell(options: CellOptions): StormCellRow {
  const { cell_id, latitude, longitude, size = 0.12 } = options
  const severity = options.severity === undefined ? 1 : options.severity
  return {
    reference_time: '2026-11-17T22:15:00.000000+00:00',
    cell_id,
    code: `20261117221500000000${cell_id.padStart(2, '0')}`,
    predecessor_code: null,
    split_event: false,
    merge_event: false,
    first_detection: '2026-11-17T22:05:00.000000+00:00',
    number_detections: 3,
    severity,
    severity_label: severity === null ? null : LABELS[severity]!,
    severity_decimal: severity,
    hail_flag: 0,
    heavy_rain_flag: 0,
    gust_flag: 0,
    centroid_latitude: latitude,
    centroid_longitude: longitude,
    cell_speed_kmh: options.speed === undefined ? 35 : options.speed,
    direction_degrees: options.direction === undefined ? 45 : options.direction,
    covered_area_km2: 120,
    geometry: options.geometry ?? { type: 'Polygon', coordinates: [ringAround(latitude, longitude, size)] },
  }
}

export interface ScanOptions {
  /** The reference time of the scan, UTC */
  referenceTime?: string
  /** The warnings of the answer's `metadata` block (`scan-stale`) */
  warnings?: Array<{ code: string, message: string }>
}

export function stormCellsAnswer(cells: StormCellRow[] = [], options: ScanOptions = {}) {
  return {
    metadata: {
      api_version: '1',
      schema_version: '1',
      retrieved_at: new Date().toISOString(),
      data_updated_at: '2026-11-17T22:19:44.000000+00:00',
      provider: {
        name_local: 'Deutscher Wetterdienst',
        name_english: 'German Weather Service',
        country: 'Germany',
        copyright: '© Deutscher Wetterdienst (DWD), KONRAD3D convective cells',
        url: 'https://opendata.dwd.de/weather/radar/konrad3d',
        license: { spdx_id: 'CC-BY-4.0', name: 'Creative Commons Attribution 4.0 International', url: 'https://creativecommons.org/licenses/by/4.0/' },
        attribution: 'Source: Deutscher Wetterdienst',
      },
      counts: { stations: 0, rows: cells.length },
      warnings: options.warnings ?? [],
    },
    reference_time: options.referenceTime ?? recentReference(),
    cells,
  }
}

/** A scan with the cells the screenshots and the e2e specs show: four of different severities, with their motion, over Germany */
export function exampleScan(referenceTime?: string) {
  return stormCellsAnswer([
    stormCell({ cell_id: '7', latitude: 50.1, longitude: 8.7, severity: 2, speed: 48, direction: 62, size: 0.16 }),
    stormCell({ cell_id: '12', latitude: 51.3, longitude: 12.4, severity: 3, speed: 31, direction: 95, size: 0.2 }),
    stormCell({ cell_id: '3', latitude: 48.6, longitude: 11.2, severity: 1, speed: 22, direction: 140, size: 0.12 }),
    stormCell({ cell_id: '21', latitude: 52.9, longitude: 9.1, severity: 0, speed: 15, direction: 250, size: 0.1 }),
  ], { referenceTime })
}

export function emptyScan(referenceTime: string = recentReference()) {
  return stormCellsAnswer([], { referenceTime })
}
