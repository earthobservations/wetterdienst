/**
 * Whether the command palette (components/SearchPalette.vue) is open, shared by what opens it: the search button of
 * the header, Ctrl+K / ⌘K anywhere, and the home page's place button, which opens it with a hint of what to type.
 */
export function usePalette() {
  const open = useState('palette-open', () => false)
  /** What the palette is opened for: everything, or a place for the home page's questions */
  const scope = useState<'all' | 'place'>('palette-scope', () => 'all')

  function openPalette(next: 'all' | 'place' = 'all') {
    scope.value = next
    open.value = true
  }

  return { open, scope, openPalette }
}
