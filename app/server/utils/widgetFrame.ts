// Who may frame the widget (GH-2607). `/widget` is the one page meant to sit in a frame of another site
// (`/widget?station=...`, docs/usage/app.md): it reads weather data and has no control that does more. Every other
// page keeps `frame-ancestors 'self'` and `X-Frame-Options: SAMEORIGIN`.
//
// It is not a route rule, because a rule is matched on the decoded path (`/%77idget` is `/widget` to it), while
// the app's router does not take that for the widget and renders a page that is not one. The request line is
// compared as the client wrote it instead, and only `/widget` and `/widget/` (with a query) are the widget.

/**
 * Whether a request line is the widget, as written: the path is exactly `/widget` or `/widget/`, nothing
 * decoded, nothing resolved, whatever the query is.
 *
 * @param rawUrl The request's path and query as they came in (`req.url`)
 * @returns True for the widget
 */
export function isWidgetRequest(rawUrl: string | undefined): boolean {
  const path = (rawUrl ?? '').split(/[?#]/, 1)[0]
  return path === '/widget' || path === '/widget/'
}

/**
 * The policy of a widget response, in which any origin may frame it.
 *
 * @param policy The `Content-Security-Policy` the response has, if any
 * @returns The policy with `frame-ancestors *` in the place of the app's own, or `undefined` where there is none
 */
export function widgetPolicy(policy: string | undefined): string | undefined {
  if (!policy)
    return undefined
  const directives = policy.split(';').map(part => part.trim()).filter(Boolean)
  return [...directives.filter(part => !/^frame-ancestors(?:\s|$)/i.test(part)), 'frame-ancestors *'].join('; ')
}
