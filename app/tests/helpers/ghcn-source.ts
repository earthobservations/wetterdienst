// Which source the GHCN daily reader of the backend took a station's file from. NOAA's NCEI is read first; when it fails (a 503
// in an outage) the reader takes the AWS mirror, whose file may end months earlier, and tells it in the `source-fallback` warning
// of the answer (GH-4230). The app's `/_ghcn/annual` passes the warning on in its own answer's `metadata.warnings` (GH-4390), so a
// test that must know reads it there (GH-4387).

/** The code of the warning the backend gives when a station's file came from the mirror */
export const SOURCE_FALLBACK = 'source-fallback'

/** Whether an answer of the generic API (`/api/values` with its metadata), or the app's own `/_ghcn/annual`, says that a file was read from the mirror */
export function readFromMirror(answer: unknown): boolean {
  const warnings = (answer as { metadata?: { warnings?: unknown } } | null | undefined)?.metadata?.warnings
  return Array.isArray(warnings) && warnings.some(warning => (warning as { code?: unknown } | null)?.code === SOURCE_FALLBACK)
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
