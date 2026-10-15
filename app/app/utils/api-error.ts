/**
 * One entry of a validation error (422): where the problem is, and what it is.
 * The backend's rules over several parameters report the same way, located at each
 * parameter involved, e.g. `{ loc: ['query', 'station'], msg: 'Cannot be combined with name' }`.
 */
interface ValidationErrorEntry {
  loc?: (string | number)[]
  msg?: string
}

/** Tell each entry of a validation error by the parameter it is located at. */
function describeValidationErrors(entries: ValidationErrorEntry[]): string | null {
  const lines = entries.map((entry) => {
    const where = (entry.loc ?? []).slice(1).join('.')
    return where ? `${where}: ${entry.msg}` : String(entry.msg)
  })
  return lines.length ? lines.join('; ') : null
}

/**
 * Describe an error response body of the REST API as one line of text.
 *
 * The backend answers every error with an RFC 9457 problem (`application/problem+json`):
 * `{ type, title, status, detail }`, where `detail` is text, and for a request that fails validation
 * (422) also `errors`, a list of entries. Each entry is told by the parameter it is located at; the
 * `query` or `body` in front of it says only where the parameter came from, and a rule about no
 * parameter in particular is located at that alone. A backend from before the problem answered the
 * entries as `detail` itself, which is read as well.
 *
 * @param body - Parsed error response body, or anything else
 * @returns The description, or null when the body carries no `detail`
 * @example
 * describeApiError({ detail: 'station: Cannot be combined with name', errors: [{ loc: ['query', 'station'], msg: 'Cannot be combined with name' }] })
 * // 'station: Cannot be combined with name'
 */
export function describeApiError(body: unknown): string | null {
  const problem = body as { detail?: unknown, errors?: unknown } | null | undefined
  if (Array.isArray(problem?.errors)) {
    const described = describeValidationErrors(problem.errors as ValidationErrorEntry[])
    if (described)
      return described
  }
  const detail = problem?.detail
  if (typeof detail === 'string')
    return detail
  if (!Array.isArray(detail))
    return null
  return describeValidationErrors(detail as ValidationErrorEntry[])
}

/**
 * Describe a failed request as one line of text: the REST API's `detail` when it answered with one,
 * its status when it answered without, the error's own message when there was no answer at all.
 *
 * A request asked for as text gets its error body as text as well, so a JSON body is read first.
 * The status is told only where an answer came, which ofetch's error carries as its `response`, and
 * useFetch's wrapping of it as its `cause`'s: useFetch gives every failure a status of 500 unless an
 * answer said otherwise, one that never reached the backend included. An HTTP/2 answer has no
 * status text, and an empty one no body, so neither tells whether one came. ofetch begins its
 * message with the whole request, `[GET] "/api/...?...": `, which is left out.
 *
 * @param error - What the request threw, or the error useFetch holds
 * @returns The description
 */
export function describeFetchError(error: unknown): string {
  const failed = error as {
    data?: unknown
    message?: string
    statusCode?: number
    statusMessage?: string
    response?: unknown
    cause?: { response?: unknown }
  } | null | undefined
  let body = failed?.data
  if (typeof body === 'string') {
    try {
      body = JSON.parse(body)
    }
    catch {}
  }
  const detail = describeApiError(body)
  if (detail)
    return detail
  if (failed?.statusCode && (failed.response ?? failed.cause?.response))
    return [failed.statusCode, failed.statusMessage].filter(Boolean).join(' ')
  // an empty message, as h3 gives an error it made from nothing, falls through to the error itself
  // ofetch marks a request nothing answered `<no response>`, its own token, left out as well
  return failed?.message?.replace(/^\[\w+\] "[^"]*": (?:<no response> )?/, '') || String(error)
}
