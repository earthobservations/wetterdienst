import type { MaybeRefOrGetter, Ref, WatchSource } from 'vue'

/**
 * Hands the focus on from a failure's notice, with its Retry, to what the Retry was for.
 *
 * A Retry that works takes the notice away, and the button with it: the focus the button held fell
 * to the page's body, sending a keyboard or screen reader user back to the top. Taken away while
 * the focus is in it, the notice moves the focus to `target` once the page has updated -- a target
 * that is no control of its own needs a `tabindex` of -1 to take it. Focus that had moved elsewhere
 * stays where it is. A Retry that fails too keeps the notice, and its button the focus.
 *
 * @param shown whether the notice is shown
 * @param notice the notice, holding its Retry
 * @param target what the Retry was for
 */
export function useFocusAfterRetry(
  shown: WatchSource<boolean>,
  notice: Readonly<Ref<HTMLElement | null>>,
  target: MaybeRefOrGetter<HTMLElement | null | undefined>,
) {
  watch(shown, async (isShown, wasShown) => {
    // read before the page updates, while the notice, and the focus in it, are still there
    if (isShown || !wasShown || !notice.value?.contains(document.activeElement))
      return
    await nextTick()
    toValue(target)?.focus()
  }, { flush: 'pre' })
}
