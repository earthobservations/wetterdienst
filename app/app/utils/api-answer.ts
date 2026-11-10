import { RETRY_TRANSIENT } from './fetch-retry'

/**
 * What the app takes for an answer of the REST API, and what it does not.
 *
 * `$fetch` hands back whatever it was answered with: a 200 page of HTML (a `NUXT_API_BASE` that points
 * at another site, a proxy's error page, the page a host serves for an address it does not know) is a
 * string, and `answer.stations ?? []` of a string is an empty list, which a page tells as "no
 * stations". An outage must not read as no data (the rule the backend keeps for its listings), so an
 * answer that is not the JSON the endpoint gives is a failure, told as any other in the page's error
 * card. {@link API_ANSWER} is that check as options for `$fetch` and `useFetch`; `fetch` of the app
 * calls {@link assertJsonAnswer} itself.
 */

/** The `type` of the problem for an answer that is not what the endpoint gives: the app's own and the proxy's, one kind */
export const UNEXPECTED_ANSWER_TYPE = 'urn:wetterdienst:problem:unexpected-answer'

export const HTML_TYPE = /^\s*(?:text\/html|application\/xhtml\+xml)\b/i

/**
 * What an endpoint's answer holds, where it is a fact the page relies on: a list under a key, or an
 * object. Only the endpoints whose answer a page reads as a list or an object are here, and only for
 * the JSON answer: another `format` (csv, geojson, ...) has another form.
 */
const LISTS: Record<string, string> = {
  '/api/stations': 'stations',
  '/api/stripes/stations': 'stations',
  '/api/values': 'values',
  '/api/stripes/values': 'values',
  '/api/interpolate': 'values',
  '/api/summarize': 'values',
  '/api/providers': 'providers',
  '/api/issues': 'issues',
  '/api/history': 'histories',
}
const ARRAYS = new Set(['/api/glossary'])
const OBJECTS = new Set(['/api/coverage'])

/** The failure of an answer that is not the data: a 502, with the problem the backend's own are written as */
export class UnexpectedAnswerError extends Error {
  statusCode = 502
  statusMessage = 'Bad Gateway'
  data: { type: string, title: string, status: number, detail: string }

  constructor(detail: string) {
    super(detail)
    this.name = 'UnexpectedAnswerError'
    this.data = { type: UNEXPECTED_ANSWER_TYPE, title: this.statusMessage, status: this.statusCode, detail }
  }
}

/** The sentence for an answer of the wrong kind, in the words of the REST API's own problems (English, not translated) */
export function describeWrongKind(contentType: string | null): string {
  const kind = contentType?.split(';')[0]?.trim()
  return HTML_TYPE.test(kind ?? '')
    ? 'The API answered with a web page, not data. The address of the API may be wrong, or a proxy in front of it answered with its own page.'
    : `The API answered with ${kind || 'an answer of no type'}, not JSON. The address of the API may be wrong, or a proxy in front of it answered instead of it.`
}

/** The sentence for a body that is no JSON, whatever its content type says it is */
function describeUnreadable(contentType: string | null): string {
  const kind = contentType?.split(';')[0]?.trim()
  return kind && /json/i.test(kind)
    ? `The API answered with ${kind}, but the body is not valid JSON. The address of the API may be wrong, or a proxy in front of it answered instead of it.`
    : describeWrongKind(contentType ?? 'text/plain')
}

/** The sentence for a success answer with no body, where the endpoint gives JSON */
const DESCRIBE_EMPTY = 'The API answered with no body, not data. The address of the API may be wrong, or a proxy in front of it answered instead of it.'

function describeWrongShape(what: string): string {
  return `The answer of the API does not have the form of this endpoint: ${what}. The address of the API may be wrong, or a proxy in front of it answered instead of it.`
}

function pathOf(request: unknown): { path: string, format: string | null } | null {
  try {
    const url = new URL(String(request), 'http://app.invalid')
    return { path: url.pathname.replace(/^\/api\/v1(?=\/)/, '/api'), format: url.searchParams.get('format') }
  }
  catch {
    return null
  }
}

/**
 * Why an answer is not what the endpoint gives, or null where it is (or where the app asked for something other
 * than its JSON: a text, a file).
 *
 * @param request - The address asked for
 * @param answer - What came back
 * @param answer.status - The HTTP status
 * @param answer.contentType - The `content-type` header
 * @param answer.data - The body, where it was read
 * @param asked - What the caller named
 * @param asked.responseType - The `responseType` of its request
 */
export function unexpectedAnswerReason(
  request: unknown,
  answer: { status: number, contentType: string | null, data?: unknown },
  asked: { responseType?: string } = {},
): string | null {
  // an error status is the failure of its own, which ofetch throws; no body is an answer of no data
  if (answer.status < 200 || answer.status >= 300 || answer.status === 204)
    return null
  const target = pathOf(request)
  // the format is the query's, which is part of the address by the time a hook sees it
  const format = String(target?.format ?? 'json').toLowerCase()
  const type = answer.contentType ?? ''
  // a page is never what the API gives, in a text as well; its own `format=html` is asked for by name
  if (HTML_TYPE.test(type))
    return format === 'html' ? null : describeWrongKind(type)
  if ((asked.responseType && asked.responseType !== 'json') || format !== 'json')
    return null
  if (!target || !(LISTS[target.path] || ARRAYS.has(target.path) || OBJECTS.has(target.path)))
    return null
  // no body, or a text where the endpoint's JSON was to be: the body was not parsed as JSON, which says what it is
  if (answer.data === undefined)
    return DESCRIBE_EMPTY
  if (typeof answer.data === 'string')
    return answer.data.trim() === '' ? DESCRIBE_EMPTY : describeUnreadable(type || 'text/plain')
  const key = LISTS[target.path]
  const data = answer.data as Record<string, unknown> | null
  if (key)
    return data && !Array.isArray(data) && typeof data === 'object' && Array.isArray(data[key]) ? null : describeWrongShape(`no list of \`${key}\``)
  if (ARRAYS.has(target.path))
    return Array.isArray(data) ? null : describeWrongShape('no list')
  if (OBJECTS.has(target.path))
    return data && !Array.isArray(data) && typeof data === 'object' ? null : describeWrongShape('no object')
  return null
}

/** The hook for `$fetch` and `useFetch` (`onResponse`): throws {@link UnexpectedAnswerError} for an answer that is not the endpoint's JSON, which is not asked again */
export function rejectUnexpectedAnswer(context: {
  request: unknown
  response?: { status: number, headers: Headers, _data?: unknown }
  options: { responseType?: string }
}): void {
  const { request, response, options } = context
  if (!response)
    return
  const reason = unexpectedAnswerReason(
    request,
    { status: response.status, contentType: response.headers.get('content-type'), data: response._data },
    { responseType: options.responseType },
  )
  if (reason)
    throw new UnexpectedAnswerError(reason)
}

/** The options that make a `$fetch` or `useFetch` of the REST API fail on an answer that is not its JSON */
export const API_ANSWER = { onResponse: rejectUnexpectedAnswer }

/** {@link API_ANSWER} and the one retry of {@link RETRY_TRANSIENT}: the options of a GET to the REST API */
export const API_FETCH = { ...RETRY_TRANSIENT, ...API_ANSWER }

/**
 * For a request made with `fetch`, which has no hook: the answer's body as JSON, or the failure where it is not the
 * endpoint's JSON. An error status is the caller's to tell, so it is not looked at here.
 *
 * @param request - The address asked for
 * @param response - What `fetch` answered
 * @returns The parsed body of an answer with a success status
 */
export async function readJsonAnswer<T>(request: string, response: Response): Promise<T> {
  const contentType = response.headers.get('content-type')
  // the type says it is not JSON before the body is read: a page is never parsed
  if (HTML_TYPE.test(contentType ?? '')) {
    const early = unexpectedAnswerReason(request, { status: response.status, contentType })
    if (early)
      throw new UnexpectedAnswerError(early)
  }
  const text = await response.text()
  // an answer with no body is no data, where `undefined` would be returned for the page to read as none
  if (!text.trim())
    throw new UnexpectedAnswerError(DESCRIBE_EMPTY)
  let data: unknown
  try {
    data = JSON.parse(text)
  }
  catch {
    throw new UnexpectedAnswerError(describeUnreadable(contentType))
  }
  const reason = unexpectedAnswerReason(request, { status: response.status, contentType, data })
  if (reason)
    throw new UnexpectedAnswerError(reason)
  return data as T
}
