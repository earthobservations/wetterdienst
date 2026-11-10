/**
 * Whether the focus is on one of Reka's guards: the invisible stop at either end of an open menu
 * (`data-reka-focus-guard`), or a focus proxy at either end of the toast region (`ToastViewport`'s `FocusProxy`).
 * A guard hands the focus on at once, or the next Tab leaves it, and it is not content that could be covered
 * (Firefox's walk ended on a proxy, at -2,-2, as `focus-obscured`).
 *
 * It runs in the page (`page.evaluate`), so it reads `document` and nothing of this module. The proxy is matched by
 * where it is, not by an attribute: a `span` with `tabindex="0"`, a pixel clipped to nothing at the window's corner,
 * first or last child of the `role="region"` element that holds the list of the toasts (`ol[data-slot="viewport"]`).
 * Reka UI 2.11.0 no longer gives it `aria-hidden` (a focusable element is not hidden from assistive technology,
 * unovue/reka-ui#2980), so that is no part of the match.
 */
export function isFocusGuard(): boolean {
  const node = document.activeElement
  if (!node)
    return false
  if (node.hasAttribute('data-reka-focus-guard'))
    return true
  const region = node.parentElement
  return node.tagName === 'SPAN' && node.getAttribute('tabindex') === '0'
    && region?.getAttribute('role') === 'region' && region.querySelector(':scope > ol[data-slot="viewport"]') != null
    && (node === region.firstElementChild || node === region.lastElementChild)
}
