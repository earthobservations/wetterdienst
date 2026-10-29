// Whether the command palette is open, shared by the search button of the header, the Ctrl+K / Cmd+K shortcut
// and the palette itself (GH-3518). The element that had the focus when it opened is kept, so that the focus goes
// back to it when the palette closes, whether the button opened it or the shortcut did.

let opener: HTMLElement | null = null

export function useCommandPalette() {
  const open = useState('command-palette-open', () => false)

  function show() {
    if (open.value)
      return
    const active = typeof document !== 'undefined' ? document.activeElement : null
    opener = active instanceof HTMLElement && active !== document.body ? active : null
    open.value = true
  }

  function hide() {
    open.value = false
  }

  /** The element to give the focus back to, once: a second close has nothing to return to */
  function takeOpener(): HTMLElement | null {
    const element = opener
    opener = null
    return element && element.isConnected ? element : null
  }

  return { open, show, hide, takeOpener }
}

/** Ctrl+K, and Cmd+K on a Mac: the shortcut that opens the palette (and closes it again) */
export function isPaletteShortcut(event: KeyboardEvent): boolean {
  return (event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === 'k'
}
