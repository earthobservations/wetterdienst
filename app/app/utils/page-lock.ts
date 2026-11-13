import { isIOS } from '@vueuse/core'

// The page behind an open modal dialog, held for real on iOS (GH-3761). reka-ui holds the body with `overflow: hidden`,
// which iOS Safari does not honour for the root scroller while an input is focused and the keyboard is up: the whole
// document rubber-bands or scrolls under the finger, the dialog in it, and the pull-to-refresh arrow shows above it. So
// while a modal is open the body is taken out of the flow where it stands (`position: fixed` with the scroll offset as
// its `top`, which looks the same and leaves nothing to scroll), the root has no bounce and no pull-to-refresh
// (`overscroll-behavior: none`), and the offset is put back on close. The dialog is sized to the visual viewport (the
// part of the page that is on the screen, which the keyboard shrinks), so the browser has no reason to pan to the
// field: its size and position are written to `--app-vv-height` and `--app-vv-top` on `<html>` for as long as the lock
// holds, and `main.css` (`html[data-page-locked] .app-vv-dialog`) lays the dialog out by them.
//
// It composes with reka-ui's lock, which sets `overflow`, the paddings and `pointer-events` of the body and gives them
// back on its own: this one sets other properties (`position`, `top`, `left`, `right`, `width`, `overscroll-behavior`)
// and gives back what each had before it, so the two do not meet. Several modals (one opening while another closes)
// share one lock: it is taken at the first and let go of at the last, from the offset of the first.

/** What the lock reads and writes of the window: a test serves its own */
type PageWindow = Pick<Window, 'scrollX' | 'scrollY' | 'scrollTo' | 'visualViewport'>

/** The properties of the body that the lock writes */
const BODY_PROPERTIES = ['position', 'top', 'left', 'right', 'width', 'overscroll-behavior'] as const

let holders = 0
let release: (() => void) | undefined

function takeLock(doc: Document, win: PageWindow): () => void {
  const root = doc.documentElement
  const body = doc.body
  const x = win.scrollX
  const y = win.scrollY

  // what the body and the root had written themselves, to give back exactly that
  const before = BODY_PROPERTIES.map(name => [name, body.style.getPropertyValue(name), body.style.getPropertyPriority(name)] as const)
  const rootOverscroll = [root.style.getPropertyValue('overscroll-behavior'), root.style.getPropertyPriority('overscroll-behavior')] as const

  body.style.setProperty('position', 'fixed')
  body.style.setProperty('top', `${-y}px`)
  body.style.setProperty('left', '0')
  body.style.setProperty('right', '0')
  body.style.setProperty('width', '100%')
  body.style.setProperty('overscroll-behavior', 'none')
  root.style.setProperty('overscroll-behavior', 'none')
  root.setAttribute('data-page-locked', '')

  // the visual viewport: what is on the screen, which the keyboard makes smaller and the browser pans
  const viewport = win.visualViewport
  const size = () => {
    if (!viewport)
      return
    root.style.setProperty('--app-vv-height', `${viewport.height}px`)
    root.style.setProperty('--app-vv-top', `${viewport.offsetTop}px`)
  }
  size()
  viewport?.addEventListener('resize', size)
  viewport?.addEventListener('scroll', size)

  return () => {
    viewport?.removeEventListener('resize', size)
    viewport?.removeEventListener('scroll', size)
    root.style.removeProperty('--app-vv-height')
    root.style.removeProperty('--app-vv-top')
    root.removeAttribute('data-page-locked')
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
    // after the body is in the flow again, so that the offset is there to go to; at once, not smoothly
    win.scrollTo({ left: x, top: y, behavior: 'instant' })
  }
}

/**
 * Holds the page for a modal dialog that is open, and returns what lets go of it. The lock is taken at the first holder
 * and let go of at the last; a holder lets go once. Only on iOS (`ios`, which a test serves): the other browsers hold
 * the page with the `overflow: hidden` of reka-ui, and there the keyboard resizes the page and nothing pans.
 */
export function lockPage(doc: Document = document, win: PageWindow = window, ios: boolean = isIOS): () => void {
  if (!ios)
    return () => {}
  if (holders++ === 0)
    release = takeLock(doc, win)
  let held = true
  return () => {
    if (!held)
      return
    held = false
    if (--holders === 0) {
      release?.()
      release = undefined
    }
  }
}
