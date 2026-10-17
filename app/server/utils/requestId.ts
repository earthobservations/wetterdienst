// The id of a request, as the backend writes it in `X-Request-ID` and in the `request_id` of a problem
// (docs/usage/restapi.md, "Errors"): the client's own where it sends a plain one (letters, digits and
// `._~-`, up to 128 characters), else one made here.
const REQUEST_ID = /^[\w.~-]{1,128}$/

export function requestIdOf(sent: string | undefined): string {
  return sent && REQUEST_ID.test(sent) ? sent : globalThis.crypto.randomUUID().replaceAll('-', '')
}
