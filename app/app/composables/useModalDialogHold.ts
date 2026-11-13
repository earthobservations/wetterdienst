import type { Ref } from 'vue'
import { onScopeDispose, watch } from 'vue'
import { holdDialogTouch } from '../utils/dialog-touch'
import { lockPage } from '../utils/page-lock'

/**
 * Holds the page behind a modal dialog on iOS for as long as it is open (GH-3761): the page is fixed where it stands,
 * with no bounce and no pull-to-refresh, and gets its scroll offset back on close (`utils/page-lock.ts`), and a
 * finger in the dialog that no box can follow is not let through to it (`utils/dialog-touch.ts`). Call it in the
 * component of a `UModal` with that modal's `open`. The listeners and the lock are taken at the first modal that opens
 * and let go of when the last closes. A popover is no modal and does not call it. Nothing is done on the server.
 */
export function useModalDialogHold(open: Readonly<Ref<boolean>>) {
  if (import.meta.server)
    return

  let letGo: (() => void) | undefined
  const stop = watch(open, (isOpen) => {
    if (isOpen && !letGo) {
      // the lock first, so that the offset it reads is the page's before anything of the dialog is there
      const unlock = lockPage()
      const release = holdDialogTouch()
      letGo = () => {
        release()
        unlock()
      }
    }
    else if (!isOpen && letGo) {
      letGo()
      letGo = undefined
    }
  }, { immediate: true, flush: 'sync' })

  onScopeDispose(() => {
    stop()
    letGo?.()
    letGo = undefined
  })
}
