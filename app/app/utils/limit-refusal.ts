/** The `type` of the problem the REST API refuses a request over one of its limits with (400). */
export const LIMIT_EXCEEDED_TYPE = 'urn:wetterdienst:problem:limit-exceeded'

/**
 * What a request was refused for: `rows` (an answer of more rows than the server sends as one body)
 * or `stations` (a request that reads more stations than one may). `stream_rows`, the limit of a
 * streamed answer, is read as well, but the app asks for none, so it has no state of its own.
 */
export interface LimitRefusal {
  limit: 'rows' | 'stations' | 'stream_rows'
  /** what the server allows */
  maximum: number
  /** what the request comes to, by the server's count */
  requested: number
}

const LIMITS: readonly string[] = ['rows', 'stations', 'stream_rows']

/**
 * The refusal a failed request carries, or null for any other failure. The problem's fields are read
 * rather than its text, which is English: `limit`, `maximum` and `requested` are numbers the page
 * words itself. ofetch's error holds the parsed body as `data`, a request asked for as text its
 * JSON as a string; one whose fields are missing or no numbers is no refusal the page can use.
 */
export function limitRefusal(error: unknown): LimitRefusal | null {
  let body = (error as { data?: unknown } | null | undefined)?.data
  if (typeof body === 'string') {
    try {
      body = JSON.parse(body)
    }
    catch {
      return null
    }
  }
  const problem = body as Record<string, unknown> | null | undefined
  if (!problem || typeof problem !== 'object' || problem.type !== LIMIT_EXCEEDED_TYPE)
    return null
  const { limit, maximum, requested } = problem
  if (typeof limit !== 'string' || !LIMITS.includes(limit))
    return null
  if (typeof maximum !== 'number' || typeof requested !== 'number' || !Number.isFinite(maximum) || !Number.isFinite(requested))
    return null
  return { limit: limit as LimitRefusal['limit'], maximum, requested }
}
