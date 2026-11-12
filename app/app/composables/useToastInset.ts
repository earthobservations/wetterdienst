/** The class that marks the toast region (`UApp`'s `toaster.ui.viewport`), so that its size can be measured */
export const TOAST_VIEWPORT_CLASS = 'app-toast-viewport'

/** The custom property on `<html>` that holds the height the toasts cover at the bottom of the window */
export const TOAST_INSET_PROPERTY = '--app-toast-inset'

/**
 * Keeps what a toast covers clear of the focus (WCAG 2.4.11 Focus Not Obscured).
 *
 * The toasts stand at the bottom right of the window, over the footer, and a link of the footer that
 * the Tab key reached lay under one for as long as it was open (GH-3575). While a toast is shown, the
 * height it covers is written to `--app-toast-inset` on `<html>`, and `main.css` makes it room at the
 * foot of the page and a scroll padding, so that the browser scrolls a focused element above the
 * toasts. It is `0px` when there is none. Call it once, in the root component. The toasts are at the
 * bottom of the window: for toasts at the top the inset would have to be the top one.
 */
export function useToastInset() {
  if (import.meta.server)
    return

  const { toasts } = useToast()
  const root = document.documentElement
  let viewport: Element | null = null

  const apply = () => {
    const rect = viewport?.getBoundingClientRect()
    // a region with no toast in it is as high as nothing, wherever it stands
    const inset = rect && rect.height > 0 ? Math.max(0, Math.ceil(window.innerHeight - rect.top)) : 0
    root.style.setProperty(TOAST_INSET_PROPERTY, `${inset}px`)
  }
  const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(apply)

  const follow = () => {
    const current = document.querySelector(`.${TOAST_VIEWPORT_CLASS}`)
    if (current !== viewport) {
      if (viewport)
        observer?.unobserve(viewport)
      viewport = current
      if (viewport)
        observer?.observe(viewport)
    }
    apply()
  }

  // the region appears with the first toast and its height follows the toasts through the observer
  watch(() => toasts.value.length, follow, { flush: 'post' })
  useEventListener('resize', apply)
  onScopeDispose(() => {
    observer?.disconnect()
    root.style.removeProperty(TOAST_INSET_PROPERTY)
  })
}
