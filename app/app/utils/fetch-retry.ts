/**
 * The failures a GET to the REST API is asked for once more, as options for useFetch or $fetch.
 *
 * ofetch asks a failed GET once more by default, on a 408, 409, 425, 429, 500, 502, 503 or 504.
 * This is that list without the 500: the REST API answers a failure on its or the source's side
 * with a 500, where asking again doubles the work behind it and fails the same way. A 502 or 503,
 * as a proxy or the app's own server gives where the backend cannot be reached, a 504 from a proxy
 * and a 408, 409, 425 or 429 keep the one retry ofetch gives them, which recovers a failure that
 * passes.
 *
 * ofetch 1.5.1 counts a request no answer came to, one the browser's connection dropped, as a 500,
 * so it is not asked again either.
 */
export const RETRY_TRANSIENT = { retryStatusCodes: [408, 409, 425, 429, 502, 503, 504] }
