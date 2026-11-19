import type { Ref } from 'vue'
import { onScopeDispose, watch } from 'vue'
import { holdDialogTouch } from '../utils/dialog-touch'
import { holdViewportLayout, lockPage } from '../utils/page-lock'

/**
 * Holds the page behind a modal dialog on iOS for as long as it is open (GH-3761): the page is fixed where it stands and
 * gets its scroll offset back on close (`utils/page-lock.ts`), and a finger in the dialog that no box can follow is not
 * let through to it (`utils/dialog-touch.ts`). Call it in the component of a `UModal` with that modal's `open`. The
 * lock and the listeners are taken at the first modal that opens and let go of when the last closes.
 *
 * A dialog with a field (`layout`, the default: the search and the place dialog, which carry `app-vv-dialog`) is also
 * laid out by the visual viewport, and that lasts until the dialog has left, not until it is closed: bind the returned
 * `afterLeave` to the `UModal`'s `@after:leave`. On close the field that has the focus is blurred before the page is
 * let go of, so that the keyboard starts to drop first and the browser has no field to scroll to when the offset is
 * put back. A popover is no modal and does not call it. Nothing is done on the server.
 */
export function useModalDialogHold(open: Readonly<Ref<boolean>>, options: { layout?: boolean } = {}) {
  const afterLeave = () => {}
  if (import.meta.server)
    return { afterLeave }

  const { layout = true } = options
  let held: { unlock: () => void, release: () => void } | undefined
  let letGoOfLayout: (() => void) | undefined

  const leave = () => {
    letGoOfLayout?.()
    letGoOfLayout = undefined
  }

  const stop = watch(open, (isOpen) => {
    if (isOpen) {
      if (!held) {
        // the lock first, so that the offset it reads is the page's before anything of the dialog is there
        held = { unlock: lockPage(), release: holdDialogTouch() }
      }
      if (layout && !letGoOfLayout)
        letGoOfLayout = holdViewportLayout()
    }
    else if (held) {
      // the keyboard drops first, then the page goes back to where it was
      const focused = document.activeElement
      if (focused instanceof HTMLElement && focused.closest('[role="dialog"]'))
        focused.blur()
      held.release()
      held.unlock()
      held = undefined
    }
  }, { immediate: true, flush: 'sync' })

  onScopeDispose(() => {
    stop()
    held?.release()
    held?.unlock()
    held = undefined
    leave()
  })

  return {
    // the dialog has left: unless it was opened again meanwhile, the layout by the visual viewport ends
    afterLeave: () => {
      if (!open.value)
        leave()
    },
  }
}
