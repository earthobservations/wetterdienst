// The page's own answer to being framed by another site (GH-2607). Only `/widget` is meant to be: the server says
// so in the headers of `/widget` and `/widget/` as they were written (`server/utils/widgetFrame.ts`). Behind a proxy
// that rewrites the path before it forwards it (`/%77idget`, `//widget` and `/x/../widget` arrive as `/widget`),
// the server cannot tell, so the page does, where the location it was really loaded at is known: framed by another
// site, it draws nothing outside the widget and does not navigate away from it.

/** The name of the widget's route, which is `pages/widget.vue` */
export const WIDGET_ROUTE = 'widget'

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
 * What a page that is framed by another origin may do at a route.
 *
 * @param framed Whether the window is framed by another origin (`isFramedByAnotherOrigin`)
 * @param routeName The name of the route the page is at, if it resolved to one
 * @returns `blank` where nothing of the app may be drawn: framed anywhere but the widget
 */
export function frameGuard(framed: boolean, routeName: string | symbol | null | undefined): { blank: boolean } {
  return { blank: framed && routeName !== WIDGET_ROUTE }
}

/**
 * Whether a navigation may go ahead. Framed by another origin, a page stays on the widget: the first navigation,
 * the one that loads the page, is not stopped (the page draws nothing at a route that is not the widget), every
 * later one that does not end at the widget is.
 *
 * @param framed Whether the window is framed by another origin
 * @param to The name of the route the navigation ends at
 * @param initial Whether this is the navigation that loads the page
 * @returns False for a navigation to stop
 */
export function allowsNavigation(framed: boolean, to: string | symbol | null | undefined, initial: boolean): boolean {
  return !framed || initial || to === WIDGET_ROUTE
}
