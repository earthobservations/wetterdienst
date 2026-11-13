import { shouldCancelDialogTouch } from '~/utils/dialog-touch'

/**
 * Keeps a finger in an open dialog from moving the page behind it (GH-3761). The one place for the three dialogs (the
 * search, the place dialog of "Ask the weather", the menu sheet): any `role="dialog"` is covered, so a new one needs
 * nothing of its own. A one-finger move that no box between the finger and the dialog can follow (a list already at
 * its top or its end, a part that does not scroll) is cancelled, which neither `overflow: hidden` on the body nor
 * `overscroll-behavior` does for iOS Safari with the on-screen keyboard up (see `utils/dialog-touch.ts`). A pinch is
 * left alone (WCAG 1.4.4). Call it once, in the root component; it takes no part where touch events are not made.
 */
export function useDialogTouchGuard() {
  if (import.meta.server)
    return

  let lastX = 0
  let lastY = 0

  useEventListener(document, 'touchstart', (event: TouchEvent) => {
    const touch = event.touches[0]
    if (touch) {
      lastX = touch.clientX
      lastY = touch.clientY
    }
  }, { passive: true, capture: true })

  useEventListener(document, 'touchmove', (event: TouchEvent) => {
    const touch = event.touches[0]
    if (!touch || event.touches.length > 1)
      return
    const dx = touch.clientX - lastX
    const dy = touch.clientY - lastY
    lastX = touch.clientX
    lastY = touch.clientY
    if (event.cancelable && shouldCancelDialogTouch(event.target, dx, dy))
      event.preventDefault()
  }, { passive: false, capture: true })
}
