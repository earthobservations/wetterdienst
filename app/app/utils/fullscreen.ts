// Full screen for one element of the page (GH-4227): the map's stage. Two ways, one state.
//
// Where the browser has the Fullscreen API on an element (desktop, Android, iPad) the element is asked to go full
// screen, which also takes the browser's own toolbars away. Where it has not (iPhone Safari offers it for a video only)
// or refuses (a frame without `allowfullscreen`, a request that is no user's gesture) the element covers the whole page
// instead, as a full-screen mode of the app (`position: fixed` over the app's bars, by the page's own rule), and
// everything else of the page is made `inert`, so that neither the keyboard nor a screen reader leaves it.
// This file is the parts of that which a test can serve a document for.

/** How the element is shown: not full screen, by the browser's own API, or by the app covering the page */
export type FullscreenMode = 'off' | 'native' | 'app'

/** The members of a document that the Fullscreen API has, standard and WebKit's prefixed ones */
export interface FullscreenDocument {
  fullscreenEnabled?: boolean
  webkitFullscreenEnabled?: boolean
  fullscreenElement?: Element | null
  webkitFullscreenElement?: Element | null
  exitFullscreen?: () => Promise<void>
  webkitExitFullscreen?: () => Promise<void> | void
}
/** The members of an element that ask for it */
export interface FullscreenElement {
  requestFullscreen?: (options?: FullscreenOptions) => Promise<void>
  webkitRequestFullscreen?: () => Promise<void> | void
}

/** The events that say the document went into or out of full screen (standard and WebKit's) */
export const FULLSCREEN_EVENTS = ['fullscreenchange', 'webkitfullscreenchange'] as const

/** Whether the document lets an element go full screen by the API: it has the call, and the page may use it */
export function supportsNativeFullscreen(doc: FullscreenDocument, element: FullscreenElement): boolean {
  const enabled = doc.fullscreenEnabled ?? doc.webkitFullscreenEnabled ?? false
  return enabled && typeof (element.requestFullscreen ?? element.webkitRequestFullscreen) === 'function'
}

/** The element that is full screen by the API, or null */
export function fullscreenElementOf(doc: FullscreenDocument): Element | null {
  return doc.fullscreenElement ?? doc.webkitFullscreenElement ?? null
}

/** Asks the element to go full screen; a prefixed call that returns nothing is a promise that has resolved */
export async function requestNativeFullscreen(element: FullscreenElement): Promise<void> {
  if (element.requestFullscreen) {
    await element.requestFullscreen({ navigationUI: 'hide' })
    return
  }
  await element.webkitRequestFullscreen?.()
}

/** Leaves the full screen of the API */
export async function exitNativeFullscreen(doc: FullscreenDocument): Promise<void> {
  if (doc.exitFullscreen) {
    await doc.exitFullscreen()
    return
  }
  await doc.webkitExitFullscreen?.()
}

/**
 * Makes everything of the page but the element and the elements it is in `inert` (a keyboard and a screen reader do not
 * reach it, a pointer does not hit it): the siblings of the element and of each of its ancestors, up to the body. Returns
 * what puts it back. An element that was inert before is left as it was, and is not made reachable again.
 */
export function inertOutside(element: HTMLElement): () => void {
  const made: Element[] = []
  let node: HTMLElement | null = element
  while (node?.parentElement) {
    const parent: HTMLElement = node.parentElement
    for (const sibling of Array.from(parent.children)) {
      if (sibling === node || sibling.hasAttribute('inert'))
        continue
      sibling.setAttribute('inert', '')
      made.push(sibling)
    }
    if (parent === element.ownerDocument.body)
      break
    node = parent
  }
  return () => {
    for (const sibling of made)
      sibling.removeAttribute('inert')
  }
}
