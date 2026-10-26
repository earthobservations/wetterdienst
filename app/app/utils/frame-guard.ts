// The page's own answer to being framed by another site (GH-2607). Only `/widget` is meant to be: the server says
// so in the headers of `/widget` and `/widget/` as they were written (`server/utils/widgetFrame.ts`). Behind a proxy
// that rewrites the path before it forwards it (`/%77idget`, `//widget` and `/x/../widget` arrive as `/widget`),
// the server cannot tell, so the page does, where the location it was really loaded at is known: framed by another
// site, it draws nothing outside the widget. `app.vue` draws nothing, and `error.vue`, which replaces it for a 404 or
// a fatal error, does the same; both ask `useFrameBlank`.

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

/** How many frames up `isFramedByAnotherOrigin` looks before it gives up, as a page that deep is not one to trust */
const MAX_FRAME_DEPTH = 32

/**
 * Whether this window sits in a frame of a page of another origin, at any level.
 *
 * Each ancestor, from the parent up to the top window, is asked for its location, which only a window of this
 * origin answers: a frame of another origin anywhere between the top and this window is a frame of another origin,
 * also under a top window of the app's own origin. A frame of the app's own origin, all the way up, is not: the
 * policy of every page but the widget lets no other origin frame it, so those parents are the app itself. A window
 * that cannot tell, or is too deep to ask, is taken to be framed.
 *
 * @param win The window of the page
 * @returns True if some ancestor is not of this origin, or cannot be asked
 */
export function isFramedByAnotherOrigin(win: Pick<Window, 'parent'>): boolean {
  try {
    let current: Pick<Window, 'parent'> = win
    for (let depth = 0; depth < MAX_FRAME_DEPTH; depth++) {
      const parent = current.parent
      if (!parent || parent === current)
        return false
      // reading the location of a window of another origin throws; the address is not used
      void parent.location.href
      current = parent
    }
    return true
  }
  catch {
    return true
  }
}

/**
 * What a page that is framed by another origin may draw at a path.
 *
 * @param framed Whether the window is framed by another origin (`isFramedByAnotherOrigin`)
 * @param path The path of the route the page is at
 * @returns `blank` where nothing of the app may be drawn: framed anywhere but the widget
 */
export function frameGuard(framed: boolean, path: string | undefined): { blank: boolean } {
  return { blank: framed && !isWidgetPath(path) }
}
