import { isIOS } from '@vueuse/core'

// The page behind an open modal dialog, held for real on iOS (GH-3761). reka-ui holds the body with `overflow: hidden`,
// which iOS Safari does not honour for the root scroller while an input is focused and the keyboard is up: the whole
// document rubber-bands or scrolls under the finger, the dialog in it, and the pull-to-refresh arrow shows above it. So
// while a modal is open the body is taken out of the flow where it stands (`position: fixed` with the scroll offset as
// its `top`, which looks the same and leaves nothing to scroll), the root is asked for no bounce and no pull-to-refresh
// (`overscroll-behavior: none`, which WebKit may not honour for the pull-to-refresh: WebKit bug 275947, so that part
// aims to and is to be checked on a device), and the offset is put back on close.
//
// Two holds, because they end at different times (`lockPage`, `holdViewportLayout`). The lock of the page ends when the
// dialog is closed. The layout by the visual viewport (the part of the page that is on the screen, which the keyboard
// shrinks) lasts until the dialog has left: reka-ui keeps the content mounted for the length of its closing animation,
// the keyboard is still up for part of that, and a dialog that snapped back to the whole window then would be partly
// under the keyboard and could make the browser scroll to reveal the field, undoing the offset that was just put back.
// The layout is written as `--app-vv-height` and `--app-vv-top` on `<html>` with `data-dialog-viewport`, and `main.css`
// (`html[data-dialog-viewport] .app-vv-dialog`) lays the dialog out by them, so the browser has no reason to pan to the
// field.
//
// The lock composes with reka-ui's, which sets `overflow`, the paddings and `pointer-events` of the body and gives them
// back on its own: this one sets other properties (`position`, `top`, `left`, `right`, `width`, `overscroll-behavior`)
// and gives back what each had before it, so the two do not meet. Several modals (one opening while another closes)
// share one lock: it is taken at the first and let go of at the last, from the offset of the first.
//
// A step of the history while the lock is on (the back swipe with the search open) is the reader's, not the dialog's.
// The router saves the position of the page that is left when it handles `popstate`, from `window.scrollX` and
// `scrollY`, which are 0 under a fixed body: so while the lock is on they answer the offset the page is at (it is the
// page's position, which the lock only holds still), and the page that is left is saved where it was. (A listener of
// the capture phase that let go of the lock first does not do it: on `window` the listeners run in the order they were
// added, and the router's is the older.) A release that finds the address changed (the dialog closing because the
// route did, and the router has the new page to put where it belongs) puts nothing back, so that it does not move the
// page that is arrived at.

/** What the lock reads and writes of the window: a test serves its own */
type PageWindow = Pick<Window, 'scrollX' | 'scrollY' | 'scrollTo' | 'visualViewport' | 'location'>

/** The properties of the body that the lock writes */
const BODY_PROPERTIES = ['position', 'top', 'left', 'right', 'width', 'overscroll-behavior'] as const

/** The lock that is on: how many modals hold it, and what lets go of it */
interface Lock {
  holders: number
  release: () => void
}

/** The properties of the window that answer the offset of the page */
const OFFSETS = ['scrollX', 'scrollY'] as const
let lock: Lock | undefined

function takeLock(doc: Document, win: PageWindow): Lock {
  const root = doc.documentElement
  const body = doc.body
  const x = win.scrollX
  const y = win.scrollY
  const href = win.location.href

  // what the body and the root had written themselves, to give back exactly that
  const before = BODY_PROPERTIES.map(name => [name, body.style.getPropertyValue(name), body.style.getPropertyPriority(name)] as const)
  const rootOverscroll = [root.style.getPropertyValue('overscroll-behavior'), root.style.getPropertyPriority('overscroll-behavior')] as const

  body.style.setProperty('position', 'fixed')
  body.style.setProperty('top', `${-y}px`)
  body.style.setProperty('left', `${-x}px`)
  body.style.setProperty('right', '0')
  body.style.setProperty('width', '100%')
  body.style.setProperty('overscroll-behavior', 'none')
  root.style.setProperty('overscroll-behavior', 'none')

  // the page is still at (x, y) as far as anything that asks is concerned, though the window has nothing to scroll
  const offsets = OFFSETS.map(name => [name, Object.getOwnPropertyDescriptor(win, name)] as const)
  Object.defineProperty(win, 'scrollX', { configurable: true, get: () => x })
  Object.defineProperty(win, 'scrollY', { configurable: true, get: () => y })

  const release = () => {
    for (const [name, value, priority] of before) {
      if (value)
        body.style.setProperty(name, value, priority)
      else
        body.style.removeProperty(name)
    }
    if (rootOverscroll[0])
      root.style.setProperty('overscroll-behavior', rootOverscroll[0], rootOverscroll[1])
    else
      root.style.removeProperty('overscroll-behavior')
    for (const [name, descriptor] of offsets) {
      if (descriptor)
        Object.defineProperty(win, name, descriptor)
      else
        delete (win as unknown as Record<string, unknown>)[name]
    }
    // after the body is in the flow again, so that the offset is there to go to; at once, not smoothly; and not onto
    // another page than the one it was taken from
    if (win.location.href === href)
      win.scrollTo({ left: x, top: y, behavior: 'instant' })
  }
  return { holders: 0, release }
}

/**
 * Holds the page for a modal dialog that is open, and returns what lets go of it. The lock is taken at the first holder
 * and let go of at the last; a holder lets go once. Only on iOS (`ios`, which a test serves): the other browsers hold
 * the page with the `overflow: hidden` of reka-ui, and there the keyboard resizes the page and nothing pans.
 */
export function lockPage(doc: Document = document, win: PageWindow = window, ios: boolean = isIOS): () => void {
  if (!ios)
    return () => {}
  const mine = lock ?? takeLock(doc, win)
  lock = mine
  mine.holders++
  let held = true
  return () => {
    if (!held)
      return
    held = false
    if (--mine.holders === 0) {
      lock = undefined
      mine.release()
    }
  }
}

// how many dialogs hold the layout, and what takes it down
let layoutHolders = 0
let releaseLayout: (() => void) | undefined

/**
 * Lays the dialogs that carry `app-vv-dialog` out by the visual viewport for as long as it is held, and returns what
 * lets go of it (at the last holder). Written to `--app-vv-height` and `--app-vv-top` on `<html>` on `resize` and
 * `scroll` of the visual viewport, with `data-dialog-viewport`. Only on iOS, as the lock.
 */
export function holdViewportLayout(doc: Document = document, win: PageWindow = window, ios: boolean = isIOS): () => void {
  if (!ios)
    return () => {}
  if (layoutHolders++ === 0) {
    const root = doc.documentElement
    const viewport = win.visualViewport
    const size = () => {
      if (!viewport)
        return
      root.style.setProperty('--app-vv-height', `${viewport.height}px`)
      root.style.setProperty('--app-vv-top', `${viewport.offsetTop}px`)
    }
    root.setAttribute('data-dialog-viewport', '')
    size()
    viewport?.addEventListener('resize', size)
    viewport?.addEventListener('scroll', size)
    releaseLayout = () => {
      viewport?.removeEventListener('resize', size)
      viewport?.removeEventListener('scroll', size)
      root.style.removeProperty('--app-vv-height')
      root.style.removeProperty('--app-vv-top')
      root.removeAttribute('data-dialog-viewport')
    }
  }
  let held = true
  return () => {
    if (!held)
      return
    held = false
    if (--layoutHolders === 0) {
      releaseLayout?.()
      releaseLayout = undefined
    }
  }
}
