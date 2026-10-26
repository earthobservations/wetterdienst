// The page's own answer to being framed by another site (GH-2607). Only `/widget` is meant to be: the server says
// so in the headers of `/widget` and `/widget/` as they were written (`server/utils/widgetFrame.ts`). Behind a proxy
// that rewrites the path before it forwards it (`/%77idget`, `//widget` and `/x/../widget` arrive as `/widget`),
// the server cannot tell, so the page does, where the location it was really loaded at is known: framed by another
// site, it draws nothing outside the widget and does not navigate away from it.

/**
 * Whether a route path is the widget's: `/widget` or `/widget/`, exactly. This is the server's predicate
 * (`server/utils/widgetFrame.ts`), not the router's, which also matches `/Widget` and `/WIDGET`.
 *
 * @param path The path of the route the page is at, as the router has it
 * @returns True for the widget
 */
export function isWidgetPath(path: string | undefined): boolean {
  return path === '/widget' || path === '/widget/'
}

/**
 * Whether this window sits in a frame of a page of another origin.
 *
 * A frame of the app's own origin is not one: the policy of every page but the widget lets no other origin frame
 * it, so a parent of the same origin is the app itself. Where the top window cannot be asked, it is another
 * origin's, and a window that cannot tell is taken to be framed.
 *
 * @param win The window of the page
 * @returns True if the top window is not this one and is not of this origin
 */
export function isFramedByAnotherOrigin(win: Pick<Window, 'self' | 'top'>): boolean {
  try {
    if (win.self === win.top)
      return false
    // reading the location of a window of another origin throws; the address is not used
    void win.top?.location.href
    return false
  }
  catch {
    return true
  }
}

/**
 * What a page that is framed by another origin may do at a path.
 *
 * @param framed Whether the window is framed by another origin (`isFramedByAnotherOrigin`)
 * @param path The path of the route the page is at
 * @returns `blank` where nothing of the app may be drawn: framed anywhere but the widget
 */
export function frameGuard(framed: boolean, path: string | undefined): { blank: boolean } {
  return { blank: framed && !isWidgetPath(path) }
}

/**
 * Whether a navigation may go ahead. Framed by another origin, a page stays on the widget: a navigation that does
 * not end there is stopped, the ones that load the page included (the page draws nothing at a path that is not the
 * widget's, whatever the router has resolved it to).
 *
 * @param framed Whether the window is framed by another origin
 * @param to The path the navigation ends at
 * @returns False for a navigation to stop
 */
export function allowsNavigation(framed: boolean, to: string | undefined): boolean {
  return !framed || isWidgetPath(to)
}

/**
 * Stops every navigation of `router` that leaves the widget, where the page is framed by another origin.
 *
 * @param router The router, or anything that takes a `beforeEach` guard
 * @param router.beforeEach Registers the guard
 * @param framed Whether the window is framed by another origin
 */
export function guardNavigation(router: { beforeEach: (guard: (to: { path: string }) => false | undefined) => unknown }, framed: boolean): void {
  if (!framed)
    return
  router.beforeEach(to => allowsNavigation(framed, to.path) ? undefined : false)
}
