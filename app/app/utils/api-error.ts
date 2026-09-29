/**
 * One entry of a FastAPI validation error (422): where the problem is, and what it is.
 * The backend's rules over several parameters report the same way, located at each
 * parameter involved, e.g. `{ loc: ['query', 'station'], msg: 'Cannot be combined with name' }`.
 */
interface ValidationErrorEntry {
  loc?: (string | number)[]
  msg?: string
}

/**
 * Describe an error response body of the REST API as one line of text.
 *
 * FastAPI answers with `{ detail }`: a string for the errors the endpoints raise themselves
 * (400, 404), a list of entries for a request that fails validation (422). Each entry is told
 * by the parameter it is located at; the `query` or `body` in front of it says only where the
 * parameter came from, and a rule about no parameter in particular is located at that alone.
 *
 * @param body - Parsed error response body, or anything else
 * @returns The description, or null when the body carries no `detail`
 * @example
 * describeApiError({ detail: [{ loc: ['query', 'station'], msg: 'Cannot be combined with name' }] })
 * // 'station: Cannot be combined with name'
 */
export function describeApiError(body: unknown): string | null {
  const detail = (body as { detail?: unknown } | null | undefined)?.detail
  if (typeof detail === 'string')
    return detail
  if (!Array.isArray(detail))
    return null
  const lines = (detail as ValidationErrorEntry[]).map((entry) => {
    const where = (entry.loc ?? []).slice(1).join('.')
    return where ? `${where}: ${entry.msg}` : String(entry.msg)
  })
  return lines.length ? lines.join('; ') : null
}

/**
 * Describe a failed request as one line of text: the REST API's `detail` when it answered, the
 * error's own message when it did not.
 *
 * A request asked for as text gets its error body as text as well, so a JSON body is read first.
 *
 * @param error - What the request threw, or the error useFetch holds
 * @returns The description
 */
export function describeFetchError(error: unknown): string {
  const failed = error as { data?: unknown, message?: string } | null | undefined
  let body = failed?.data
  if (typeof body === 'string') {
    try {
      body = JSON.parse(body)
    }
    catch {}
  }
  return describeApiError(body) ?? failed?.message ?? String(error)
}
