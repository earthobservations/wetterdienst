/**
 * What the backend answers for `GET /api/radar/frames` (`dwd/radar`, GH-3788), written out for the tests' fixtures: the loop of the
 * analysis (a frame for every run, every 5 minutes), the 24 frames of the forecast of the newest run, the bounds of the images, the
 * legend of the seven classes and the `metadata` block with DWD's terms. The times are UTC with a `Z`, as the backend writes them.
 */

export const RADAR_CLASSES = [
  { lower: 0.1, upper: 0.5, color: '#c7e9b4', label: '0.1 to under 0.5 mm/h' },
  { lower: 0.5, upper: 1, color: '#7fcdbb', label: '0.5 to under 1 mm/h' },
  { lower: 1, upper: 2.5, color: '#41b6c4', label: '1 to under 2.5 mm/h' },
  { lower: 2.5, upper: 5, color: '#1d91c0', label: '2.5 to under 5 mm/h' },
  { lower: 5, upper: 10, color: '#225ea8', label: '5 to under 10 mm/h' },
  { lower: 10, upper: 25, color: '#253494', label: '10 to under 25 mm/h' },
  { lower: 25, upper: null, color: '#081d58', label: '25 mm/h and more' },
]

export const RADAR_BOUNDS = { west: 1.4633, south: 45.6823, east: 18.7316, north: 56.2194 }

const FIVE_MINUTES = 5 * 60_000

/** A time on the grid of DWD's runs, `minutesAgo` before `now`, as the backend writes it (UTC with a `Z`, no fraction) */
export function runTime(now: number = Date.now(), minutesAgo = 6): string {
  const at = Math.floor((now - minutesAgo * 60_000) / FIVE_MINUTES) * FIVE_MINUTES
  return `${new Date(at).toISOString().replace('.000Z', 'Z')}`
}

export interface RadarOptions {
  /** The newest run, UTC (default: 6 minutes before `now`, on the grid) */
  run?: string
  /** How many minutes of the analysis (default 120: 25 frames, the newest run included) */
  past?: number
  /** How many frames of the forecast (default 24: 5 to 120 minutes after the run) */
  forecast?: number
  /** The `metadata` warnings (`radar-stale`) */
  warnings?: Array<{ code: string, message: string }>
  now?: number
}

export function radarAnswer(options: RadarOptions = {}) {
  const run = options.run ?? runTime(options.now)
  const newest = Date.parse(run)
  const past = options.past ?? 120
  const frames: Array<{ time: string, run: string, lead_minutes: number, kind: 'observation' | 'forecast' }> = []
  for (let minutes = past; minutes >= 0; minutes -= 5) {
    const time = new Date(newest - minutes * 60_000).toISOString().replace('.000Z', 'Z')
    frames.push({ time, run: time, lead_minutes: 0, kind: 'observation' })
  }
  for (let lead = 5; lead <= 5 * (options.forecast ?? 24); lead += 5)
    frames.push({ time: new Date(newest + lead * 60_000).toISOString().replace('.000Z', 'Z'), run, lead_minutes: lead, kind: 'forecast' })
  return {
    metadata: {
      api_version: '1',
      schema_version: '1',
      retrieved_at: new Date(options.now ?? Date.now()).toISOString(),
      provider: {
        name_local: 'Deutscher Wetterdienst',
        name_english: 'German Weather Service',
        country: 'Germany',
        copyright: '© Deutscher Wetterdienst (DWD), radar products',
        url: 'https://opendata.dwd.de/weather/radar/',
        license: { spdx_id: 'CC-BY-4.0', name: 'Creative Commons Attribution 4.0 International', url: 'https://creativecommons.org/licenses/by/4.0/' },
        attribution: 'Source: Deutscher Wetterdienst',
      },
      warnings: options.warnings ?? [],
      processing_note: 'Processed by wetterdienst.',
    },
    product: { id: 'rv', name: 'RV composite', step_minutes: 5, unit: 'mm/h' },
    run,
    image: { crs: 'EPSG:3857', bounds: RADAR_BOUNDS, width: 1200, height: 1169, media_type: 'image/png' },
    legend: { unit: 'mm/h', transparent_below: 0.1, classes: RADAR_CLASSES },
    frames,
  }
}
