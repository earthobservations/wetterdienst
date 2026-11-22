/**
 * Takes the reader to the element an address's anchor names (`/settings#settings-friendly-labels`) and puts the focus there, where
 * the element can have it, so that a keyboard and a screen reader continue where the page has taken the eyes and not at the
 * link or the search result that was used (WCAG 2.4.3). The router scrolls too, but not on a first load of the address (the
 * page is drawn after the browser looked for the anchor) and not to an element that is there only once data has come.
 *
 * @param hash The anchor with its `#`, as `route.hash` has it
 * @param fallback The id of another element where the one named is not on the page (a row of a list that is hidden)
 * @returns Whether an element was found
 */
export function revealAnchor(hash: string, fallback?: (id: string) => string | undefined): boolean {
  let id = hash.replace(/^#/, '')
  try {
    id = decodeURIComponent(id)
  }
  catch {
    return false
  }
  const other = id ? fallback?.(id) : undefined
  const target = (id ? document.getElementById(id) : null) ?? (other ? document.getElementById(other) : null)
  if (!target)
    return false
  target.scrollIntoView({ block: 'start' })
  if (target.matches('a[href], button, input, select, textarea, summary, [tabindex]'))
    target.focus({ preventScroll: true })
  return true
}

/**
 * The anchors of a page (GH-3790): with `auto` it reveals the element the address names when the page is shown and when the
 * anchor changes; without, it hands back the function for a page that knows when its anchor is there.
 */
export function useRevealHash(options: { auto?: boolean, fallback?: (id: string) => string | undefined } = {}) {
  const route = useRoute()
  const reveal = (hash: string) => revealAnchor(hash, options.fallback)
  if (options.auto) {
    onMounted(() => {
      if (route.hash)
        void nextTick(() => reveal(route.hash))
    })
    watch(() => route.hash, (hash) => {
      if (hash)
        void nextTick(() => reveal(hash))
    })
  }
  return reveal
}
