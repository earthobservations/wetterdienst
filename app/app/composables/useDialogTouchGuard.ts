import type { Ref } from 'vue'
import { onScopeDispose, watch } from 'vue'
import { holdDialogTouch } from '../utils/dialog-touch'

/**
 * Keeps a finger in an open modal dialog from moving the page behind it, on iOS (GH-3761; the reasons and what it
 * does not cover are in `utils/dialog-touch.ts`). Call it in the component of a `UModal` with that modal's `open`: the
 * guard is held for as long as it is open, and the touch listeners are on the document only while some modal is. A
 * popover is no modal and does not call it, so its `role="dialog"` is not the guard's. Nothing is done on the server.
 */
export function useDialogTouchGuard(open: Readonly<Ref<boolean>>) {
  if (import.meta.server)
    return

  let letGo: (() => void) | undefined
  const stop = watch(open, (isOpen) => {
    if (isOpen && !letGo) {
      letGo = holdDialogTouch()
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
