/**
 * What the backend answers for `GET /api/kostra` (`dwd/kostra`, GH-4072), written out for the tests' fixtures: the cell of DWD's 5 km
 * grid that holds the point, and the table of 22 durations by 9 return periods with a depth, an intensity and DWD's uncertainty.
 *
 * The depths follow a smooth rule of the shape of DWD's tables (the depth grows with the duration and with the return period), so that a
 * curve rises left to right and the nine do not cross; they are no real cell's. The intensity is the depth over the duration, as the
 * backend writes it (to a tenth).
 */

export const DURATIONS = [5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 360, 540, 720, 1080, 1440, 2880, 4320, 5760, 7200, 8640, 10080]
export const RETURN_PERIODS = [1, 2, 3, 5, 10, 20, 30, 50, 100]

export interface KostraValue {
  duration_minutes: number
  return_period_years: number
  depth_mm: number | null
  intensity_l_s_ha: number | null
  uncertainty_percent: number | null
}

/** The depth of a rain of `minutes` that returns every `years` years, in mm (one decimal) */
export function depthOf(minutes: number, years: number): number {
  return Math.round((4.5 * (minutes ** 0.42) * (1 + 0.32 * Math.log(years))) * 10) / 10
}

export interface KostraOptions {
  /** The cell: DWD's `INDEX_RC` and its centre */
  cell?: { index_rc: string, row: number, column: number, latitude: number, longitude: number }
  /** Values to take out (a duration and a return period DWD gives no value for) */
  missing?: Array<[number, number]>
}

export function kostraAnswer(options: KostraOptions = {}) {
  const values: KostraValue[] = []
  for (const minutes of DURATIONS) {
    for (const years of RETURN_PERIODS) {
      const missing = options.missing?.some(([d, y]) => d === minutes && y === years)
      const depth = depthOf(minutes, years)
      values.push({
        duration_minutes: minutes,
        return_period_years: years,
        depth_mm: missing ? null : depth,
        intensity_l_s_ha: missing ? null : Math.round(depth / minutes * 10000 / 60 * 10) / 10,
        uncertainty_percent: missing ? null : 10 + (years > 30 ? 2 : 0) + (minutes > 1440 ? 1 : 0),
      })
    }
  }
  return {
    metadata: {
      provider: {
        name_short: 'DWD',
        name_english: 'German Weather Service',
        country: 'Germany',
        copyright: '© Deutscher Wetterdienst (DWD)',
        attribution: 'Source: Deutscher Wetterdienst',
        license: { spdx_id: 'CC-BY-4.0', name: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
      },
      retrieved_at: '2026-11-27T10:00:00Z',
    },
    edition: 'KOSTRA-DWD-2020',
    cell: options.cell ?? { index_rc: '144197', row: 144, column: 197, latitude: 50.747211, longitude: 13.777738 },
    values,
  }
}

/** The 400 the backend answers for a point outside the grid (an RFC 9457 problem) */
export const OUTSIDE_PROBLEM = {
  type: 'urn:wetterdienst:problem:bad-request',
  title: 'Bad Request',
  status: 400,
  detail: 'The point 40.0, 3.0 is outside the area of KOSTRA-DWD-2020, which covers Germany and a border of about 10 km around it.',
}
