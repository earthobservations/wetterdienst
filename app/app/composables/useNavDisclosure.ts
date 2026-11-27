import type { Ref } from 'vue'

/**
 * The behaviour of a disclosure of links in the header (GH-3518, GH-4500): the reference and the "More" menu of the tools that do not fit.
 * A disclosure of links, not an ARIA menu: Tab walks into the panel, the links are links, and Escape, a click elsewhere or the focus
 * leaving it close it (WAI-ARIA APG, "disclosure navigation"); a page change closes it too. `root` is the element that holds the
 * button and the panel, `trigger` the button.
 */
export function useNavDisclosure(root: Readonly<Ref<HTMLElement | null>>, trigger: Readonly<Ref<HTMLButtonElement | null>>) {
  const route = useRoute()
  const open = ref(false)
  const panelId = useId()

  watch(() => route.path, () => {
    open.value = false
  })
  onClickOutside(root, () => {
    open.value = false
  })

  // Escape is heard on the whole document while the panel is open: a click on its padding leaves the focus on the
  // body, where a listener of the panel itself would not hear it
  useEventListener(document, 'keydown', (event: KeyboardEvent) => {
    // not where the focus is in another layer (a dialog the search opened over the panel): its Escape is its own
    const active = document.activeElement
    const elsewhere = active && active !== document.body && !root.value?.contains(active)
    if (event.key === 'Escape' && open.value && !elsewhere) {
      open.value = false
      trigger.value?.focus()
    }
  })

  function onFocusout(event: FocusEvent) {
    // a focus that goes nowhere (`relatedTarget` null: a click on the panel's padding, a link a browser does not
    // focus on mousedown, the window losing focus) leaves it open: a click elsewhere is `onClickOutside`'s
    const next = event.relatedTarget as Node | null
    if (next && !root.value?.contains(next))
      open.value = false
  }

  return { open, panelId, onFocusout }
}
