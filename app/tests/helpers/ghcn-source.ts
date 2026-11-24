import type { APIRequestContext } from '@playwright/test'

// Which source the GHCN daily reader of the backend took a station's file from. NOAA's NCEI is read first; when it fails (a 503
// in an outage) the reader takes the AWS mirror, whose file may end months earlier, and tells it in the `source-fallback` warning
// of the answer (GH-4230). The app's `/_ghcn/annual` leaves the warning out of its answer (it carries the provider and the years
// only), so a test that must know asks the generic API for the station, which carries it in `metadata.warnings` (GH-4387).

/** The code of the warning the backend gives when a station's file came from the mirror */
export const SOURCE_FALLBACK = 'source-fallback'

/** Whether an answer of the generic API (`/api/values` with its metadata) says that a file was read from the mirror */
export function readFromMirror(answer: unknown): boolean {
  const warnings = (answer as { metadata?: { warnings?: unknown } } | null | undefined)?.metadata?.warnings
  return Array.isArray(warnings) && warnings.some(warning => (warning as { code?: unknown } | null)?.code === SOURCE_FALLBACK)
}

/**
 * Asks the generic API for one day of a station, to learn from the answer's warnings whether its file came from the mirror. The
 * file is read whole whatever the day, and the day is one both sources have.
 *
 * @throws {Error} The API did not answer with values: the question is not answered, and the test must not guess
 */
export async function stationWasReadFromMirror(request: APIRequestContext, station: string, timeout = 200_000): Promise<boolean> {
  const response = await request.get('/api/values', {
    params: {
      provider: 'noaa',
      network: 'ghcn',
      parameters: 'daily/data/temperature_air_max_2m',
      stations: station,
      timestamp: '2020-01-01',
      with_metadata: 'true',
    },
    timeout,
  })
  if (!response.ok())
    throw new Error(`The generic API answered ${response.status()} for a day of ${station}, so it is not known which source it was read from`)
  return readFromMirror(await response.json())
}

export interface RunningYearCheck {
  /** Whether the running year was checked: it cannot be where the file came from the mirror */
  checked: boolean
  /** What is wrong with the last year, null if nothing is */
  problem: string | null
}

/**
 * What holds of the last year of a station's annual values. Where NCEI answered, the last year is the running one and has no value
 * yet (a year is a value only when it is complete). Where the mirror answered its file may end in an earlier year, so the running
 * year is not asked for: only that the last year is not a year with a value, as the first is not either. NCEI answering without the
 * running year is a problem; the mirror's file ending in a year before it is not.
 *
 * @param values - The annual rows of the answer, in order
 * @param year - The year it is
 * @param mirror - Whether the file was read from the mirror
 */
export function checkRunningYear(values: ReadonlyArray<{ timestamp: string, value: number | null }>, year: number, mirror: boolean): RunningYearCheck {
  const last = values.at(-1)
  if (!last)
    return { checked: !mirror, problem: 'the answer has no years' }
  const lastYear = Number(last.timestamp.slice(0, 4))
  if (!mirror && lastYear !== year)
    return { checked: true, problem: `the last year is ${lastYear}, not the running ${year}, although NCEI answered` }
  if (last.value !== null)
    return { checked: !mirror, problem: `the last year ${lastYear} has the value ${last.value}, not null` }
  return { checked: !mirror, problem: null }
}
